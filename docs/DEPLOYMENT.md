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
(`camera_mount`), and model, then click **Save**.

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

Then click **Restart** on the dashboard (or
`sudo systemctl restart aether-vision`). A restart reloads all code.
`config/config.json` is kept.

## Qualcomm QCS6490

The QCS6490 has a Hexagon NPU that runs quantized models much faster than the
CPU. Aether Vision uses it through LiteRT (TensorFlow Lite) with Qualcomm's QNN
delegate.

1. **Install Aether Vision** with `scripts/install.sh`. The installer detects a
   QCS6490 (or QCM6490) from the device tree and then also:
   - adds Qualcomm's package repository (on a RUBIK Pi 3 the Thundercomm PPA
     that `rubikpi-script/install_ppa_pkgs.sh` uses, elsewhere
     `ppa:ubuntu-qcom-iot/qcom-ppa`) and installs the AI packages
     (`libqnn-dev`, `qnn-tools`, `tensorflow-lite-qcom-apps`, …), which provide
     `libQnnTFLiteDelegate.so`;
   - installs `ai-edge-litert==1.3.0`, the LiteRT release the delegate is
     validated with (`uv sync --extra qcs6490` for a manual install).

   Pass `--qcs6490` if detection misses your board, or `--no-qcs6490` to skip
   all of this. The demo apps, desktop and GTK packages from Qualcomm's guide
   are not needed and are not installed.
2. **Get a quantized TFLite model.** The NPU only runs uint8/int8 models;
   layers it can't run fall back to the CPU. Either export one with Ultralytics:
   ```bash
   yolo export model=your_model.pt format=tflite int8=True imgsz=640
   ```
   or download a pre-quantized `w8a8` model from Qualcomm AI Hub (separate
   `boxes`, `scores` and `classes` outputs; the detector reads both formats).
   Copy it into `models/`.
3. **Point the detector at it**: set `detector.model_path` (and `labels_path`,
   one class name per line) on the dashboard. `detector.use_npu` is on by default.
4. **Check** the `pipeline/backend` telemetry value on the dashboard. It should
   read `npu`, and `pipeline/detect_ms` should be around 10 ms for a 640x640 model.

If the delegate fails to load, the detector logs a warning and runs on the CPU
(`pipeline/backend` reads `cpu`).

## Troubleshooting

| Symptom | What to check |
|---|---|
| Camera state shows `error: ...` | `rs-enumerate-devices` (librealsense tools) or `lsusb` shows the camera; udev rules installed (`ls /etc/udev/rules.d/99-realsense*`); use a USB 3 port and cable; another program may be using the camera |
| Pipeline `error: ...` about the model | `detector.model_path` is relative to the install folder |
| NetworkTables shows `waiting` | Check `team` / `server_address` and that the robot is reachable (`ping 10.TE.AM.2`) |
| Positions are NaN | Not enough valid depth in the box: the object is too close (< ~0.2 m), too far (> 8 m), or reflective/transparent |
| Positions are offset or rotated | Re-measure `camera_mount`; `pitch_deg` is positive when tilted **down** |
| Dashboard page is a 404 | The frontend isn't built: re-run `scripts/install.sh` (it installs Node.js if needed) |
| Installer can't reach the internet | It needs github.com, nodejs.org, pypi.org and your distro's package mirror. Behind a proxy, set `HTTPS_PROXY` |
| `aether-vision: command not found` / `uv: command not found` | Open a new shell so `~/.local/bin` is on `PATH`, or use `.venv/bin/aether-vision` |
| Low FPS | Check `pipeline/detect_ms` and `pipeline/localize_ms` telemetry; make sure `pipeline/backend` is `npu` |
