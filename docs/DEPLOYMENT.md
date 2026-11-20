# Deployment

## Coprocessor setup

On the coprocessor (Ubuntu 22.04+ on x86-64 or ARM64):

```bash
git clone https://github.com/Galaxia5987/aether-vision.git
cd aether-vision
scripts/install.sh --service
```

The installer sets up everything the machine is missing (see the
[README](../README.md#install)), including Intel's udev rules so the camera
works without root. Unplug and replug the camera afterwards.

`--service` installs a systemd service that starts on boot, runs as your user,
and restarts if it ever exits.

Then open `http://<coprocessor>:5803`. Set your team number, camera mounting
(`localization.extrinsics`), and model, then click **Save**.

### Network

- Give the coprocessor a static IP on the robot network, e.g. `10.TE.AM.11`.
- The dashboard uses port **5803**. FRC allows ports 5800–5810 for team use.
- With `network_tables.team` set, the robot is found automatically. Set
  `network_tables.server_address` to connect to a specific address (e.g. a
  simulator on your laptop).

### Managing the service

```bash
systemctl status aether-vision          # is it running?
journalctl -u aether-vision -f          # live logs
sudo systemctl restart aether-vision    # restart
sudo systemctl disable --now aether-vision                     # stop and disable
sudo rm /etc/systemd/system/aether-vision.service && sudo systemctl daemon-reload   # remove
```

Logs are also written to `logs/aether-vision.log` and shown on the dashboard.

## Updating

```bash
cd aether-vision
git pull
scripts/install.sh            # add the same options you installed with
```

Then click **Restart process** on the dashboard (or
`sudo systemctl restart aether-vision`). A process restart reloads all code.
`config/config.json` is kept.

## Qualcomm QCS6490

The QCS6490 has a Hexagon NPU that runs quantized models much faster than the
CPU. Aether Vision uses it through LiteRT (TensorFlow Lite) with Qualcomm's QNN
delegate.

1. **Install the Qualcomm runtime.** `libQnnTFLiteDelegate.so` and the QNN HTP
   libraries come with the Qualcomm AI Engine Direct SDK (QAIRT) or the
   Qualcomm Linux image. Note where the delegate library is.
2. **Install Aether Vision** with `scripts/install.sh`. LiteRT is included by
   default, and on ARM64 the installer reports whether it found the QNN delegate.
3. **Export a quantized TFLite model**, e.g. with Ultralytics:
   ```bash
   yolo export model=your_model.pt format=tflite int8=True imgsz=640
   ```
   or compile one with Qualcomm AI Hub. Copy it into `models/`.
4. **Configure the detector** (see `examples/config.qcs6490.json`):
   ```json
   "detector": {
     "model_path": "models/your_model_int8.tflite",
     "backend": {
       "kind": "litert",
       "delegate": "qnn",
       "qnn_backend": "htp",
       "delegate_path": "/path/to/libQnnTFLiteDelegate.so"
     }
   }
   ```
   If the libraries are on the system library path, `delegate_path` can stay
   at its default. You may also need `LD_LIBRARY_PATH` / `ADSP_LIBRARY_PATH`
   set as described in Qualcomm's SDK documentation. For the service, add
   `Environment=` lines to `/etc/systemd/system/aether-vision.service`.
5. **Check** the `pipeline/object_detection/stages/detect/backend` telemetry
   value on the dashboard. It should read `litert[qnn:htp]`, and
   `stages/detect/latency_ms` should drop well below the CPU number.

If the delegate fails to load, the pipeline shows an error and retries every
few seconds. Fix the path and click **Save** or **Restart pipeline**.

**Alternative:** an ONNX Runtime build with the QNN execution provider. Set
`backend.providers` to `["QNNExecutionProvider", "CPUExecutionProvider"]`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Camera state stays `reconnecting` | `rs-enumerate-devices` (librealsense tools) or `lsusb` shows the camera; udev rules installed (`ls /etc/udev/rules.d/99-realsense*`); use a USB 3 port and cable |
| `No RealSense device connected` while plugged in | Replug after installing udev rules; another program may be using the camera |
| Pipeline `error: missing streams: depth` | The camera has no depth (USB/mock without depth); use `passthrough` or enable depth |
| Pipeline `build failed: Model file not found` | `detector.model_path` is relative to the install folder |
| NetworkTables shows `waiting` | Check `team` / `server_address` and that the robot is reachable (`ping 10.TE.AM.2`) |
| Positions are NaN | Not enough valid depth in the box: the object is too close (< ~0.2 m), too far, or reflective/transparent. Try lowering `clustering.min_points` or enabling `filters.hole_filling` |
| Positions are offset or rotated | Re-measure `localization.extrinsics`; `pitch_deg` is positive when tilted **down** |
| Dashboard says "Frontend not built" | Re-run `scripts/install.sh` (it installs Node.js if needed); it was installed with `--no-frontend` or the build failed |
| Installer can't reach the internet | It needs github.com, nodejs.org, pypi.org and your distro's package mirror. Behind a proxy, set `HTTPS_PROXY` |
| `aether-vision: command not found` / `uv: command not found` | Open a new shell so `~/.local/bin` is on `PATH`, or use `.venv/bin/aether-vision` |
| Low FPS | Check `stages/*/latency_ms` telemetry; use the NPU, a smaller model, `max_points`, or a larger `sample_stride` |
