"""Auto-annotate captured images, review the labels, and pack a dataset for training.

    uv run --group training training/annotate.py label      # YOLO-World boxes for new images
    uv run training/annotate.py review                      # label editor at :5805
    uv run training/annotate.py pack                        # -> training/dataset.zip

Classes come from ``training/classes.json``: class name -> text prompts. The order of the
names is the class id order. Several prompts may map to one class; describe what the
camera sees ("yellow foam ball", not "game piece").

``label`` uses YOLO-World, an open-vocabulary detector, by default. Once you have a model
trained on your classes it is usually a better annotator for new sessions:
``label --model best.pt``. Its boxes are a starting point, not ground truth: review them.

``review`` is a label editor in the browser. It shows the least confident auto-labels
first, then images nobody has labeled, so it also works for labeling by hand without
``label``. Draw boxes by dragging, click a box to select it, drag to move, drag its corners
to resize; 1-9 pick the class, Delete removes the selected box, ctrl+z undoes. → / k keep
(marks the image reviewed; an image kept without boxes is a negative), ← back, x reject
(moves the image to data/rejected), c clears all boxes. Edits are saved immediately.

``pack`` splits train/val by chunks of consecutive frames (neighbouring frames are
near-identical, so a per-frame split leaks training images into validation) and writes a
zip to upload as a Kaggle dataset for ``training/train.ipynb``.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
IMAGES, LABELS, REJECTED = DATA / "images", DATA / "labels", DATA / "rejected"
META = DATA / "annotations.json"  # per image: box confidences, reviewed flag
SUFFIXES = {".jpg", ".jpeg", ".png"}


# --- shared ----------------------------------------------------------------------------------


def load_classes(path: Path) -> dict[str, list[str]]:
    classes: dict[str, list[str]] = json.loads(path.read_text())
    if not classes:
        raise SystemExit(f"{path} has no classes")
    return classes


def all_images() -> list[Path]:
    return sorted(p for p in IMAGES.rglob("*") if p.suffix.lower() in SUFFIXES)


def key(image: Path) -> str:
    return image.relative_to(IMAGES).as_posix()


def label_path(image: Path) -> Path:
    return LABELS / image.relative_to(IMAGES).with_suffix(".txt")


def read_label_rows(path: Path) -> list[list[float]]:
    if not path.exists():
        return []
    return [
        [float(v) for v in line.split()] for line in path.read_text().splitlines() if line.strip()
    ]


def write_label_rows(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{int(r[0])} {r[1]:.6f} {r[2]:.6f} {r[3]:.6f} {r[4]:.6f}" for r in rows]
    path.write_text("".join(line + "\n" for line in lines))


def load_meta() -> dict[str, dict[str, object]]:
    return json.loads(META.read_text()) if META.exists() else {}


def save_meta(meta: dict[str, dict[str, object]]) -> None:
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=1, sort_keys=True))


# --- label -----------------------------------------------------------------------------------


def label(args: argparse.Namespace) -> None:
    from ultralytics import YOLO, YOLOWorld

    classes = load_classes(args.classes)
    names = list(classes)
    if "world" in Path(args.model).name.lower():
        model = YOLOWorld(args.model)
        prompts = [(prompt, c) for c, name in enumerate(names) for prompt in classes[name]]
        model.set_classes([p for p, _ in prompts])
        to_class = [c for _, c in prompts]
    else:  # a model trained on our classes, in the same order
        model = YOLO(args.model)
        to_class = list(range(len(names)))

    images = all_images()
    if args.sessions:
        images = [p for p in images if p.parent.name in args.sessions]
    todo = [p for p in images if args.overwrite or not label_path(p).exists()]
    print(f"labeling {len(todo)} of {len(images)} images with {args.model}")
    meta = load_meta()
    boxes_total = empty = 0
    for start in range(0, len(todo), args.batch):
        chunk = todo[start : start + args.batch]
        results = model.predict(
            [str(p) for p in chunk],
            conf=args.conf,
            iou=0.5,
            agnostic_nms=True,  # several prompts of one class find the same object
            imgsz=args.imgsz,
            device=args.device,
            verbose=False,
        )
        for image, result in zip(chunk, results, strict=True):
            rows, confs = [], []
            for (cx, cy, w, h), c, s in zip(
                result.boxes.xywhn.tolist(),
                result.boxes.cls.int().tolist(),
                result.boxes.conf.tolist(),
                strict=True,
            ):
                if w * h > args.max_area:  # open-vocabulary models sometimes box the whole frame
                    continue
                rows.append([to_class[c], cx, cy, w, h])
                confs.append(round(s, 3))
            write_label_rows(label_path(image), rows)
            meta[key(image)] = {"conf": confs, "reviewed": False}
            boxes_total += len(rows)
            empty += not rows
        save_meta(meta)
        print(f"\r{min(start + args.batch, len(todo))}/{len(todo)}", end="", flush=True)
    print(f"\n{boxes_total} boxes, {empty} images without boxes (kept as negatives)")


# --- review ----------------------------------------------------------------------------------

PAGE = """<!doctype html>
<title>Review labels</title>
<style>
  body { font-family: system-ui, sans-serif; background: #111; color: #eee; margin: 16px; }
  canvas { border: 1px solid #333; cursor: crosshair; display: block; }
  button { font-size: 15px; padding: 6px 14px; margin: 0 6px 6px 0; }
  #caption { font-family: monospace; margin: 8px 0; }
  #classes span { display: inline-block; padding: 3px 10px; margin: 0 6px 6px 0;
                  border: 2px solid transparent; border-radius: 4px; cursor: pointer; }
  #classes span.on { border-color: #fff; }
  .warn { color: #fb0; } .help { color: #888; font-size: 14px; }
</style>
<div id="caption"></div>
<div id="classes"></div>
<canvas id="canvas"></canvas>
<p>
  <button onclick="go(-1)">← Back</button>
  <button onclick="keep()">Keep → (k)</button>
  <button onclick="undo()">Undo (ctrl+z)</button>
  <button onclick="clearBoxes()">Clear boxes (c)</button>
  <button onclick="reject()" style="background:#a33;color:#fff">Reject image (x)</button>
  <label><input type="checkbox" id="unreviewed" checked onchange="load()"> unreviewed only</label>
</p>
<p class="help">
  Drag on the image to draw a box of the selected class. Click a box to select it, drag it to
  move, drag its corners to resize. 1-9 pick the class (and change the selected box's class),
  Delete removes the selected box, Esc deselects. Edits save immediately; Keep also marks the
  image reviewed.
</p>
<script>
const COLORS = ['#ffc800', '#0078ff', '#50dc50', '#dc50dc', '#ff5050', '#50dcdc', '#ff9a3c'];
const HANDLE = 8;  // px around a corner that grabs it
const canvas = document.getElementById('canvas'), ctx = canvas.getContext('2d');
let names = [], items = [], i = 0, rows = [], sel = -1, cls = 0, undoStack = [], drag = null;
const img = new Image();
img.onload = () => { fit(); paint(); };

async function api(url, options) { return (await fetch(url, options)).json(); }
const q = () => 'path=' + encodeURIComponent(items[i].path);

async function load() {
  names = await api('/api/classes');
  const only = document.getElementById('unreviewed').checked;
  items = await api('/api/items?unreviewed=' + only);
  i = 0; pickClass(0); open();
}
async function open() {
  const cap = document.getElementById('caption');
  if (!items.length) { cap.textContent = 'Nothing to review.'; canvas.width = 0; return; }
  i = Math.max(0, Math.min(i, items.length - 1));
  const data = await api('/api/labels?' + q());
  rows = data.rows; sel = -1; undoStack = [];
  img.src = '/api/raw?' + q();
  caption();
}
function caption() {
  const it = items[i];
  const warn = it.uncertain ? ' <span class="warn">⚠ uncertain</span>' : '';
  const state = it.reviewed ? '  ✓ reviewed' : it.labeled ? '' : '  (no labels yet)';
  document.getElementById('caption').innerHTML =
    `${i + 1}/${items.length}  ${it.path}  boxes: ${rows.length}${state}${warn}`;
}
function pickClass(c) {
  if (c >= names.length) return;
  cls = c;
  document.getElementById('classes').innerHTML = names.map((n, k) =>
    `<span class="${k === cls ? 'on' : ''}" style="background:${COLORS[k % COLORS.length]}33"
       onclick="setClass(${k})">${k + 1} ${n}</span>`).join('');
}
function setClass(c) {
  pickClass(c);
  if (sel >= 0 && rows[sel].c !== c) { snapshot(); rows[sel].c = c; rows[sel].conf = 1; save(); }
  paint();
}

function fit() {
  const s = Math.min((innerWidth - 40) / img.width, (innerHeight * 0.72) / img.height, 2);
  canvas.width = Math.round(img.width * s); canvas.height = Math.round(img.height * s);
}
function paint() {
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const W = canvas.width, H = canvas.height;
  rows.forEach((r, k) => {
    const color = COLORS[r.c % COLORS.length];
    ctx.lineWidth = k === sel ? 3 : 2; ctx.strokeStyle = color;
    ctx.strokeRect(r.x1 * W, r.y1 * H, (r.x2 - r.x1) * W, (r.y2 - r.y1) * H);
    const text = (names[r.c] ?? r.c) + (r.conf < 1 ? ' ' + r.conf.toFixed(2) : '');
    ctx.font = '13px sans-serif'; ctx.fillStyle = color;
    ctx.fillText(text, r.x1 * W + 2, Math.max(12, r.y1 * H - 4));
    if (k === sel) for (const [x, y] of corners(r)) ctx.fillRect(x * W - 4, y * H - 4, 8, 8);
  });
  if (drag && drag.mode === 'draw') {
    ctx.setLineDash([5, 4]); ctx.strokeStyle = COLORS[cls % COLORS.length]; ctx.lineWidth = 2;
    ctx.strokeRect(drag.x0 * W, drag.y0 * H, (drag.x - drag.x0) * W, (drag.y - drag.y0) * H);
    ctx.setLineDash([]);
  }
}
const corners = (r) => [[r.x1, r.y1], [r.x2, r.y1], [r.x1, r.y2], [r.x2, r.y2]];
function point(e) {
  const b = canvas.getBoundingClientRect();
  const clamp = (v) => Math.max(0, Math.min(1, v));
  return [clamp((e.clientX - b.left) / b.width), clamp((e.clientY - b.top) / b.height)];
}
function snapshot() {
  undoStack.push(JSON.stringify(rows));
  if (undoStack.length > 100) undoStack.shift();
}
function undo() {
  if (!undoStack.length) return;
  rows = JSON.parse(undoStack.pop()); sel = -1; save(); paint();
}

canvas.onmousedown = (e) => {
  if (!items.length) return;
  const [x, y] = point(e), W = canvas.width, H = canvas.height;
  if (sel >= 0) {  // a corner of the selected box: resize, anchored at the opposite corner
    const r = rows[sel];
    const k = corners(r).findIndex(([cx, cy]) =>
      Math.abs(cx - x) * W <= HANDLE && Math.abs(cy - y) * H <= HANDLE);
    if (k >= 0) {
      snapshot();
      drag = { mode: 'resize', ax: k % 2 ? r.x1 : r.x2, ay: k < 2 ? r.y2 : r.y1 };
      return;
    }
  }
  const hits = rows.map((r, k) => [(r.x2 - r.x1) * (r.y2 - r.y1), k])
    .filter(([, k]) => x >= rows[k].x1 && x <= rows[k].x2 && y >= rows[k].y1 && y <= rows[k].y2)
    .sort((a, b) => a[0] - b[0]);
  if (hits.length) {  // the smallest box under the cursor: select and move
    sel = hits[0][1]; pickClass(rows[sel].c); snapshot();
    drag = { mode: 'move', x, y, moved: false };
  } else {
    sel = -1; drag = { mode: 'draw', x0: x, y0: y, x, y };
  }
  paint();
};
window.onmousemove = (e) => {
  if (!drag) return;
  const [x, y] = point(e);
  if (drag.mode === 'draw') { drag.x = x; drag.y = y; }
  else if (drag.mode === 'resize') {
    Object.assign(rows[sel], { x1: Math.min(x, drag.ax), x2: Math.max(x, drag.ax),
                               y1: Math.min(y, drag.ay), y2: Math.max(y, drag.ay), conf: 1 });
  } else {
    const r = rows[sel];
    const dx = Math.max(-r.x1, Math.min(1 - r.x2, x - drag.x));
    const dy = Math.max(-r.y1, Math.min(1 - r.y2, y - drag.y));
    if (dx || dy) { r.x1 += dx; r.x2 += dx; r.y1 += dy; r.y2 += dy; r.conf = 1; drag.moved = true; }
    drag.x = x; drag.y = y;
  }
  paint();
};
window.onmouseup = () => {
  if (!drag) return;
  const d = drag; drag = null;
  if (d.mode === 'draw') {
    const r = { c: cls, x1: Math.min(d.x0, d.x), x2: Math.max(d.x0, d.x),
                y1: Math.min(d.y0, d.y), y2: Math.max(d.y0, d.y), conf: 1 };
    if ((r.x2 - r.x1) * canvas.width >= 4 && (r.y2 - r.y1) * canvas.height >= 4) {
      snapshot(); rows.push(r); sel = rows.length - 1; save();
    }
  } else if (d.mode === 'resize' || d.moved) {
    save();
  } else {
    undoStack.pop();  // a plain click: nothing changed
  }
  paint();
};

async function save() {
  const r = await api('/api/labels?' + q(), {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(rows) });
  Object.assign(items[i], r); caption();
}
function go(d) { i += d; open(); }
async function keep() {
  if (!items.length) return;
  Object.assign(items[i], await api('/api/keep?' + q(), { method: 'POST' }));
  i += 1; open();
}
function clearBoxes() { if (rows.length) { snapshot(); rows = []; sel = -1; save(); paint(); } }
async function reject() {
  if (!items.length) return;
  await api('/api/reject?' + q(), { method: 'POST' });
  items.splice(i, 1); open();
}
document.onkeydown = (e) => {
  if (e.target.tagName === 'INPUT') return;
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
  else if (e.key >= '1' && e.key <= '9') setClass(Number(e.key) - 1);
  else if ((e.key === 'Delete' || e.key === 'Backspace') && sel >= 0) {
    e.preventDefault(); snapshot(); rows.splice(sel, 1); sel = -1; save(); paint();
  }
  else if (e.key === 'Escape') { sel = -1; paint(); }
  else if (e.key === 'ArrowRight' || e.key === 'k') keep();
  else if (e.key === 'ArrowLeft') go(-1);
  else if (e.key === 'x') reject();
  else if (e.key === 'c') clearBoxes();
};
window.onresize = () => { if (img.width) { fit(); paint(); } };
load();
</script>
"""


def review(args: argparse.Namespace) -> None:
    import uvicorn
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.responses import FileResponse, HTMLResponse

    names = list(load_classes(args.classes))
    meta = load_meta()

    def resolve(path: str) -> Path:
        image = (IMAGES / path).resolve()
        if not image.is_relative_to(IMAGES.resolve()) or not image.is_file():
            raise HTTPException(404, "no such image")
        return image

    def confidences(path: str, n: int) -> list[float]:
        confs = list(meta.get(path, {}).get("conf", []))  # type: ignore[call-overload]
        return confs if len(confs) == n else [1.0] * n

    def entry(image: Path) -> dict[str, object]:
        path = key(image)
        labeled = label_path(image).exists()
        n = len(read_label_rows(label_path(image)))
        confs = confidences(path, n)
        return {
            "path": path,
            "labeled": labeled,
            "boxes": n,
            "reviewed": bool(meta.get(path, {}).get("reviewed")),
            "uncertain": bool(confs) and min(confs) < args.review_conf,
            "min_conf": min(confs) if confs else 1.0,
        }

    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/classes")
    def classes() -> list[str]:
        return names

    @app.get("/api/items")
    def items(unreviewed: bool = True) -> list[dict[str, object]]:
        entries = [entry(p) for p in all_images()]
        if unreviewed:
            entries = [e for e in entries if not e["reviewed"]]
        # Uncertain auto-labels first, then the rest, then images nobody labeled yet.
        return sorted(
            entries, key=lambda e: (e["reviewed"], not e["labeled"], e["min_conf"], e["path"])
        )

    @app.get("/api/raw")
    def raw(path: str) -> FileResponse:
        return FileResponse(resolve(path))

    @app.get("/api/labels")
    def get_labels(path: str) -> dict[str, list[dict[str, float]]]:
        rows = read_label_rows(label_path(resolve(path)))
        boxes = [
            {
                "c": int(c),
                "x1": cx - w / 2,
                "y1": cy - h / 2,
                "x2": cx + w / 2,
                "y2": cy + h / 2,
                "conf": conf,
            }
            for (c, cx, cy, w, h), conf in zip(rows, confidences(path, len(rows)), strict=True)
        ]
        return {"rows": boxes}

    @app.put("/api/labels")
    def put_labels(path: str, boxes: list[dict[str, float]] = Body(...)) -> dict[str, object]:  # noqa: B008
        image = resolve(path)
        rows, confs = [], []
        for b in boxes:
            c = int(b["c"])
            if not 0 <= c < len(names):
                raise HTTPException(422, f"class {c} out of range")
            x1, x2 = sorted(min(max(float(b[k]), 0.0), 1.0) for k in ("x1", "x2"))
            y1, y2 = sorted(min(max(float(b[k]), 0.0), 1.0) for k in ("y1", "y2"))
            if x2 - x1 <= 0 or y2 - y1 <= 0:
                continue
            rows.append([c, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1])
            confs.append(round(float(b.get("conf", 1.0)), 3))
        write_label_rows(label_path(image), rows)
        meta.setdefault(path, {})["conf"] = confs
        save_meta(meta)
        return entry(image)

    @app.post("/api/keep")
    def keep(path: str) -> dict[str, object]:
        image = resolve(path)
        if not label_path(image).exists():  # kept without boxes: a negative example
            write_label_rows(label_path(image), [])
        meta.setdefault(path, {})["reviewed"] = True
        save_meta(meta)
        return entry(image)

    @app.post("/api/reject")
    def reject(path: str) -> dict[str, bool]:
        image = resolve(path)
        for src, base in ((image, IMAGES), (label_path(image), LABELS)):
            if src.exists():
                dst = REJECTED / base.name / src.relative_to(base)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(src, dst)
        meta.pop(path, None)
        save_meta(meta)
        return {"rejected": True}

    print(f"review: http://localhost:{args.port}  (Ctrl+C to stop)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


# --- pack ------------------------------------------------------------------------------------


def pack(args: argparse.Namespace) -> None:
    names = list(load_classes(args.classes))
    meta = load_meta()
    labeled = [p for p in all_images() if label_path(p).exists()]
    if args.reviewed_only:
        labeled = [p for p in labeled if meta.get(key(p), {}).get("reviewed")]
    if not labeled:
        raise SystemExit("no labeled images; run `label` first")

    chunks: list[list[Path]] = []
    for session in sorted({p.parent for p in labeled}):
        frames = [p for p in labeled if p.parent == session]
        chunks += [frames[i : i + args.chunk] for i in range(0, len(frames), args.chunk)]
    if len(chunks) < 2:
        raise SystemExit("not enough images for a validation split; capture more")
    random.Random(args.seed).shuffle(chunks)
    n_val = max(1, round(len(chunks) * args.val_fraction))
    splits = {"val": chunks[:n_val], "train": chunks[n_val:]}

    counts = {s: np.zeros(len(names), np.int64) for s in splits}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w") as archive:
        for split, split_chunks in splits.items():
            for image in (p for chunk in split_chunks for p in chunk):
                name = f"{image.parent.name}__{image.name}"  # unique across sessions
                archive.write(image, f"dataset/images/{split}/{name}", zipfile.ZIP_STORED)
                rows = read_label_rows(label_path(image))
                archive.writestr(
                    f"dataset/labels/{split}/{Path(name).with_suffix('.txt')}",
                    "".join(f"{int(r[0])} {r[1]} {r[2]} {r[3]} {r[4]}\n" for r in rows),
                    zipfile.ZIP_DEFLATED,
                )
                for r in rows:
                    counts[split][int(r[0])] += 1
        archive.writestr(
            "dataset/data.yaml",
            "path: .\ntrain: images/train\nval: images/val\nnames:\n"
            + "".join(f"  {i}: {name}\n" for i, name in enumerate(names)),
        )
    for split, split_chunks in splits.items():
        n = sum(len(c) for c in split_chunks)
        per_class = ", ".join(f"{name} {counts[split][i]}" for i, name in enumerate(names))
        print(f"{split:5s} {n:5d} images  boxes: {per_class}")
    size = args.out.stat().st_size / 1e6
    print(f"wrote {args.out} ({size:.0f} MB); upload it as a Kaggle dataset for train.ipynb")


# --- main ------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--classes", type=Path, default=ROOT / "classes.json")
    parser.add_argument("--data", type=Path, default=DATA, help="data root (default: %(default)s)")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("label", help="auto-annotate images that have no labels yet")
    p.add_argument("--model", default="yolov8x-worldv2.pt", help="YOLO-World or a trained .pt")
    p.add_argument("--conf", type=float, default=0.25, help="drop boxes below this confidence")
    p.add_argument("--max-area", type=float, default=0.6, help="drop boxes larger than this")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default=None, help="e.g. 0 or cpu; default: auto")
    p.add_argument("--sessions", nargs="*", help="only these session folders")
    p.add_argument("--overwrite", action="store_true", help="relabel images that have labels")
    p.set_defaults(run=label)

    p = commands.add_parser("review", help="review labels in the browser")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5805)
    p.add_argument("--review-conf", type=float, default=0.45, help="flag boxes below this")
    p.set_defaults(run=review)

    p = commands.add_parser("pack", help="split train/val and write the dataset zip")
    p.add_argument("--out", type=Path, default=ROOT / "dataset.zip")
    p.add_argument("--val-fraction", type=float, default=0.15)
    p.add_argument("--chunk", type=int, default=40, help="consecutive frames kept together")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--reviewed-only", action="store_true", help="skip images not yet reviewed")
    p.set_defaults(run=pack)

    args = parser.parse_args()
    global IMAGES, LABELS, REJECTED, META
    IMAGES, LABELS, REJECTED = args.data / "images", args.data / "labels", args.data / "rejected"
    META = args.data / "annotations.json"
    args.run(args)


if __name__ == "__main__":
    main()
