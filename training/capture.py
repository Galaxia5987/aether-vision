"""Record training images from the RealSense, with a live preview in the browser.

    uv run --extra realsense training/capture.py --session lab_day1
    uv run training/capture.py --session test --mock          # no camera

Open http://<host>:5804 for the preview and the Record / Pause button. Ctrl+C stops.
It runs headless, so it also works over SSH on the robot's coprocessor.

A frame is saved at most every ``--every`` seconds, and only if it is sharp (variance of
the Laplacian >= ``--min-sharpness``) and differs from the last saved frame (mean
absolute difference of an 80x60 gray thumbnail >= ``--min-change``).

Use the exposure the robot uses (``--exposure-us``): a model trained on auto-exposed
frames can struggle with a short fixed exposure. Move the camera and the objects:
distances, angles, lighting, partly hidden objects, motion blur. Also record frames
with no object in them (field, bumpers, people); they teach the model what to ignore.
One session per place / lighting / day keeps the train/val split honest.
"""

from __future__ import annotations

import argparse
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from aether_vision.camera import Mock, RealSense, Source
from aether_vision.config import CameraConfig

DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "images"

PAGE = """<!doctype html>
<title>Capture</title>
<style>
  body { font-family: system-ui, sans-serif; background: #111; color: #eee; margin: 16px; }
  img { max-width: 100%; border: 1px solid #333; }
  button { font-size: 18px; padding: 8px 20px; margin-right: 12px; }
  #status { font-family: monospace; font-size: 16px; }
</style>
<p><button id="toggle" onclick="fetch('/toggle', {method: 'POST'})">…</button>
<span id="status"></span></p>
<img src="/stream">
<script>
  async function poll() {
    try {
      const s = await (await fetch('/status')).json();
      document.getElementById('toggle').textContent = s.recording ? 'Pause' : 'Record';
      document.getElementById('status').textContent =
        `${s.session}  ${s.recording ? '● REC' : 'paused'}  saved ${s.saved}  ` +
        `sharpness ${s.sharpness.toFixed(0)}  change ${s.change.toFixed(1)}  ${s.reason}`;
    } catch (e) {}
  }
  setInterval(poll, 300); poll();
</script>
"""


class Recorder:
    def __init__(self, source: Source, args: argparse.Namespace) -> None:
        self._source = source
        self._args = args
        self.out = Path(args.out) / args.session
        self.out.mkdir(parents=True, exist_ok=True)
        self._index = len(list(self.out.glob("*.jpg")))
        self.recording = not args.paused
        self.saved = 0
        self.sharpness = 0.0
        self.change = 0.0
        self.reason = ""
        self.done = threading.Event()
        self._preview: bytes = b""
        self._preview_id = 0
        self._new_preview = threading.Condition()

    def run(self, stop: threading.Event) -> None:
        last_thumb: np.ndarray | None = None
        next_save = 0.0
        frames = 0
        try:
            while not stop.is_set():
                color = self._source.read().color
                frames += 1
                now = time.monotonic()
                gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
                self.sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                thumb = cv2.resize(gray, (80, 60), interpolation=cv2.INTER_AREA).astype(np.float32)
                self.change = (
                    float("inf") if last_thumb is None else float(np.abs(thumb - last_thumb).mean())
                )
                if self.sharpness < self._args.min_sharpness:
                    self.reason = "blurry"
                elif self.change < self._args.min_change:
                    self.reason = "no change"
                else:
                    self.reason = ""
                if self.recording and not self.reason and now >= next_save:
                    name = self.out / f"{self._args.session}_{self._index:05d}.jpg"
                    cv2.imwrite(str(name), color, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    self._index += 1
                    self.saved += 1
                    last_thumb, next_save = thumb, now + self._args.every
                    self.reason = "saved"
                    if self._args.max_images and self.saved >= self._args.max_images:
                        print(f"\nreached --max-images {self._args.max_images}")
                        break
                if frames % 3 == 0:
                    self._publish(color)
                print(
                    f"\rsaved {self.saved:5d}  sharpness {self.sharpness:6.0f}  "
                    f"change {min(self.change, 999):5.1f}  {self.reason:10s}",
                    end="",
                    flush=True,
                )
        finally:
            self.done.set()

    def _publish(self, color: np.ndarray) -> None:
        small = cv2.resize(color, (color.shape[1] // 2, color.shape[0] // 2))
        if self.recording:
            cv2.circle(small, (16, 16), 8, (0, 0, 255), -1)
        jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
        with self._new_preview:
            self._preview, self._preview_id = jpeg, self._preview_id + 1
            self._new_preview.notify_all()

    def stream(self) -> Iterator[bytes]:
        seen = -1
        while not self.done.is_set():
            with self._new_preview:
                if self._preview_id == seen:
                    self._new_preview.wait(timeout=1.0)
                if self._preview_id == seen:
                    continue
                jpeg, seen = self._preview, self._preview_id
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"


def make_app(recorder: Recorder) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/stream")
    def stream() -> StreamingResponse:
        return StreamingResponse(
            recorder.stream(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    @app.get("/status")
    def status() -> dict[str, object]:
        return {
            "session": recorder.out.name,
            "recording": recorder.recording,
            "saved": recorder.saved,
            "sharpness": recorder.sharpness,
            "change": min(recorder.change, 999.0),
            "reason": recorder.reason,
        }

    @app.post("/toggle")
    def toggle() -> dict[str, bool]:
        recorder.recording = not recorder.recording
        return {"recording": recorder.recording}

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--session", default=time.strftime("s%Y%m%d_%H%M%S"))
    parser.add_argument(
        "--out", default=str(DEFAULT_OUT), help="images root (default: %(default)s)"
    )
    parser.add_argument("--every", type=float, default=0.4, help="min seconds between saves")
    parser.add_argument("--min-sharpness", type=float, default=60.0)
    parser.add_argument("--min-change", type=float, default=6.0)
    parser.add_argument(
        "--max-images", type=int, default=0, help="stop after this many; 0 = no limit"
    )
    parser.add_argument("--paused", action="store_true", help="start paused; press Record")
    camera = parser.add_argument_group("camera")
    camera.add_argument("--mock", action="store_true", help="simulated camera, for testing")
    camera.add_argument("--serial", default="")
    camera.add_argument("--width", type=int, default=640)
    camera.add_argument("--height", type=int, default=480)
    camera.add_argument("--fps", type=int, default=30)
    camera.add_argument("--exposure-us", type=float, default=None, help="default: auto exposure")
    web = parser.add_argument_group("preview")
    web.add_argument("--host", default="0.0.0.0")
    web.add_argument("--port", type=int, default=5804)
    web.add_argument("--no-preview", action="store_true", help="no web server; console only")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CameraConfig(
        kind="mock" if args.mock else "realsense",
        serial=args.serial,
        width=args.width,
        height=args.height,
        fps=args.fps,
        exposure_us=args.exposure_us,
    )
    source: Source = Mock(config) if args.mock else RealSense(config)
    recorder = Recorder(source, args)
    stop = threading.Event()
    print(f"saving to {recorder.out}")
    try:
        if args.no_preview:
            recorder.run(stop)
            return
        server = uvicorn.Server(
            uvicorn.Config(
                make_app(recorder),
                host=args.host,
                port=args.port,
                log_level="warning",
                timeout_graceful_shutdown=1,
            )
        )

        def record() -> None:
            recorder.run(stop)
            server.should_exit = True

        thread = threading.Thread(target=record, name="capture", daemon=True)
        thread.start()
        print(f"preview: http://localhost:{args.port}  (Ctrl+C to stop)")
        server.run()
        stop.set()
        thread.join(5.0)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        source.close()
        print(f"\nsaved {recorder.saved} images to {recorder.out}")


if __name__ == "__main__":
    main()
