"""The vision loop: newest frame -> YOLO -> 3D localization -> NetworkTables + dashboard."""

from __future__ import annotations

import logging
import threading
import time

from aether_vision.config import ConfigStore
from aether_vision.detector import Detector
from aether_vision.localization import locate, point_cloud
from aether_vision.networktables import NetworkTables
from aether_vision.telemetry import Telemetry
from aether_vision.types import FrameSet, Latest, Result, Target

_log = logging.getLogger(__name__)


class PipelineThread:
    def __init__(
        self,
        store: ConfigStore,
        frames: Latest[FrameSet],
        results: Latest[tuple[FrameSet, Result]],
        telemetry: Telemetry,
        nt: NetworkTables | None,
    ) -> None:
        self._store = store
        self._frames = frames
        self._results = results
        self._telemetry = telemetry
        self._nt = nt
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(5.0)

    def _run(self) -> None:
        detector: Detector | None = None
        loaded: object = None
        seq = 0
        count, since = 0, time.monotonic()
        put = self._telemetry.put
        while not self._stop.is_set():
            new_seq, frames = self._frames.wait_newer(seq, 0.5)
            if frames is None or new_seq == seq:
                continue
            seq = new_seq
            config = self._store.current
            detector_config = config.detector
            model = (
                detector_config.model_path,
                detector_config.labels_path,
                detector_config.use_npu,
            )
            try:
                if model != loaded:
                    detector = None
                    put("pipeline/state", "loading model")
                    detector = Detector(config.detector)
                    loaded = model
                    put("pipeline/backend", detector.backend)
                assert detector is not None

                start = time.perf_counter()
                detections = detector.detect(frames.color, config.detector)
                detected = time.perf_counter()
                depth = frames.load_depth() if detections else None
                cloud = None
                if depth is not None:
                    cloud = point_cloud(depth, frames.depth_scale_m, frames.geometry)
                depth_done = time.perf_counter()
                targets = []
                for detection in detections:
                    found = (
                        None if cloud is None else locate(detection.box, cloud, config.camera_mount)
                    )
                    targets.append(Target(detection, *found) if found else Target(detection))
                localized = time.perf_counter()

                result = Result(frames.capture_time_s, tuple(targets))
                self._results.put((frames, result))
                if self._nt is not None:
                    self._nt.publish(result)
            except Exception as error:
                _log.exception("Pipeline failed")
                put("pipeline/state", f"error: {error}")
                self._stop.wait(1.0)  # don't spin on a persistent error (e.g. missing model)
                continue

            put("pipeline/state", "running")
            put("pipeline/targets", len(targets))
            put("pipeline/detect_ms", round((detected - start) * 1000, 1))
            put("pipeline/depth_ms", round((depth_done - detected) * 1000, 1))
            put("pipeline/localize_ms", round((localized - depth_done) * 1000, 1))
            put("pipeline/latency_ms", round(result.latency_ms, 1))
            count += 1
            if count == 10:
                now = time.monotonic()
                put("pipeline/fps", round(count / (now - since), 1))
                count, since = 0, now
