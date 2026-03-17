# Hailo-10H VLM Add-ons for Home Assistant

> A community blueprint for integrating the **Hailo-10H AI accelerator** with
> Home Assistant. Includes a ready-to-use VLM (Vision Language Model) chat
> add-on and detailed instructions for HA configuration, automations, and
> Lovelace dashboards.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-aarch64-green.svg)
![HA](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5.svg)

---

## Table of Contents

1. [What's Included](#whats-included)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [VLM Model Setup](#vlm-model-setup)
5. [Add-on Configuration](#add-on-configuration)
6. [Lovelace Dashboard Card](#lovelace-dashboard-card)
7. [Automation Examples](#automation-examples)
8. [REST Sensors & Commands](#rest-sensors--commands)
9. [Building Your Own Hailo Add-on](#building-your-own-hailo-add-on)
10. [Architecture Overview](#architecture-overview)
11. [Troubleshooting](#troubleshooting)
12. [Contributing](#contributing)

---

## What's Included

| Add-on | Description |
|--------|-------------|
| **[Hailo-10H VLM Chat](hailo_vlm/)** | Capture camera images and ask an AI about them via a web UI embedded in HA |

The VLM Chat add-on demonstrates the full pipeline:
camera → frame capture → VLM inference on Hailo-10H → natural-language answer.

It is designed as a starting point — fork it, extend it, or use the patterns
below to create your own Hailo-powered automations.

---

## Prerequisites

### Hardware

- **Raspberry Pi 5** (4 GB or 8 GB RAM)
- **Hailo-10H AI HAT+** (M.2 module on AI HAT+)
- **USB camera** (any UVC-compatible webcam)

### Software

- **Home Assistant OS** built with the `hailo10h-pci` driver and
  `hailo10h-firmware` packages. Use the fork at:
  <https://github.com/mikehailodev/operating-system> (branch
  `feature/hailort-package`)
- **HailoRT 5.2.0** — the pre-built `.deb` and Python `.whl` are bundled in
  the add-on (no compilation needed)
- A **VLM HEF model** file for Hailo-10H (see [VLM Model Setup](#vlm-model-setup))

### Verify Hardware on the Host

After flashing the HAOS image, SSH into the host and confirm:

```bash
# Kernel module loaded
lsmod | grep hailo
# Expected: hailo1x_pci  ...

# Device node present
ls /dev/hailo*
# Expected: /dev/hailo0  /dev/hailo_control

# PCI device detected
lspci -nn | grep 1e60
# Expected: ...1e60:45c4...
```

---

## Installation

### 1. Add the Repository to Home Assistant

1. Open Home Assistant → **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu (top right) → **Repositories**
3. Paste the repository URL:
   ```
   https://github.com/mikehailodev/hailo-vlm-addon
   ```
4. Click **Add** → **Close**

### 2. Install the Add-on

1. The **Hailo-10H VLM Chat** add-on should now appear in the store
2. Click it → **Install**
3. Wait for the Docker image to build (first install takes a few minutes
   to install the bundled HailoRT packages)

### 3. Configure & Start

1. Go to the add-on's **Configuration** tab
2. Adjust options (camera device, model parameters)
3. Click **Start**
4. Switch to the **Log** tab to verify startup:
   ```
   ✓ Hailo device found at /dev/hailo0
   ✓ Camera found at /dev/video0
   Server starting on 0.0.0.0:8099
   ```
5. Click **Open Web UI** (or find "Hailo VLM" in the sidebar)

---

## VLM Model Setup

The add-on needs a compiled Hailo HEF model file for VLM inference.

### Download

Visit the [Hailo Model Zoo / Developer Zone](https://hailo.ai/developer-zone/)
and download a Hailo-10H VLM HEF, for example:

- **Qwen2-VL-2B-Instruct** (recommended — small, fast, good quality)

### Place the Model

Copy the `.hef` file to the Home Assistant **media** or **share** directory.
The add-on auto-discovers any `.hef` file with "vlm" or "qwen" in its name.

Using the Samba or SSH add-ons:

```bash
# Via SSH add-on
scp Qwen2-VL-2B-Instruct.hef root@homeassistant.local:/media/
```

Or use the **File Editor** / **Samba** add-on to copy it into `/media/`.

---

## Add-on Configuration

Edit in **Settings → Add-ons → Hailo-10H VLM Chat → Configuration**:

```yaml
camera_device: "/dev/video0"    # USB camera device path
max_tokens: 200                  # Maximum tokens in VLM response
temperature: 0.1                 # Sampling temperature (lower = more focused)
default_prompt: "Describe the image"
system_prompt: "You are a helpful assistant that analyzes images and answers questions about them."
```

| Option | Type | Range | Description |
|--------|------|-------|-------------|
| `camera_device` | string | — | Path to the V4L2 camera device |
| `max_tokens` | int | 50–1000 | Cap on generated tokens per response |
| `temperature` | float | 0.0–2.0 | Sampling randomness (0 = greedy) |
| `default_prompt` | string | — | Used when the prompt field is empty |
| `system_prompt` | string | — | System instruction for the VLM |

---

## Lovelace Dashboard Card

### Basic Ingress Panel Card

The simplest approach — embed the add-on's web UI directly into a dashboard:

```yaml
type: iframe
url: /api/hassio_ingress/<YOUR_ADDON_TOKEN>/
aspect_ratio: "4:3"
title: Hailo VLM Chat
```

> **Tip:** Find `<YOUR_ADDON_TOKEN>` in the add-on's **Info** tab under
> "Open Web UI" link, or in `.storage/ingress` on the HA host.

### MJPEG Camera Card + VLM Button Card

For a split layout — camera stream on one card, VLM interaction on another:

```yaml
type: vertical-stack
cards:
  # Live camera stream via the add-on MJPEG endpoint
  - type: picture-glance
    title: Hailo-10H Camera
    camera_image: camera.hailo_vlm_camera  # see REST camera below
    entities: []

  # Quick-action button to trigger VLM analysis
  - type: button
    name: "Analyze Scene"
    icon: mdi:eye
    tap_action:
      action: call-service
      service: rest_command.hailo_vlm_capture_and_ask
      data:
        prompt: "What is happening in this scene?"
    hold_action:
      action: navigate
      navigation_path: /api/hassio_ingress/<YOUR_ADDON_TOKEN>/
```

### Custom Dashboard Page (Horizontal Layout)

```yaml
views:
  - title: AI Vision
    icon: mdi:eye
    panel: true
    cards:
      - type: horizontal-stack
        cards:
          - type: iframe
            url: /api/hassio_ingress/<YOUR_ADDON_TOKEN>/
            aspect_ratio: "16:9"
```

---

## REST Sensors & Commands

The add-on exposes a REST API on its ingress URL. You can create HA sensors
and commands that interact with it.

### `configuration.yaml` — REST Command

```yaml
rest_command:
  # Capture a frame from the VLM add-on camera
  hailo_vlm_capture:
    url: "http://a0d7b954-hailo-vlm:8099/api/capture"
    method: POST
    content_type: "application/json"

  # Ask the VLM about the captured frame
  hailo_vlm_ask:
    url: "http://a0d7b954-hailo-vlm:8099/api/ask"
    method: POST
    content_type: "application/json"
    payload: '{"prompt": "{{ prompt }}"}'

  # Resume live video
  hailo_vlm_resume:
    url: "http://a0d7b954-hailo-vlm:8099/api/resume"
    method: POST

  # Capture + Ask in one sequence
  hailo_vlm_capture_and_ask:
    url: "http://a0d7b954-hailo-vlm:8099/api/capture"
    method: POST
    content_type: "application/json"
```

> **Note:** Replace `a0d7b954-hailo-vlm` with your add-on's actual hostname.
> You can find it in the add-on logs or by inspecting the Docker network.
> The slug-based hostname format is: `<8-char-hash>-<slug_with_underscores_as_hyphens>`.

### `configuration.yaml` — REST Sensor (VLM Status)

```yaml
sensor:
  - platform: rest
    name: "Hailo VLM Status"
    resource: "http://a0d7b954-hailo-vlm:8099/api/status"
    value_template: >
      {% if value_json.hailo_device and value_json.camera_ok %}
        ready
      {% elif value_json.camera_ok %}
        no_hailo
      {% elif value_json.hailo_device %}
        no_camera
      {% else %}
        offline
      {% endif %}
    json_attributes:
      - hailo_available
      - hailo_device
      - camera_ok
      - camera_device
    scan_interval: 30
```

### MJPEG Camera Entity

Add the add-on's MJPEG stream as a camera entity:

```yaml
camera:
  - platform: mjpeg
    name: "Hailo VLM Camera"
    mjpeg_url: "http://a0d7b954-hailo-vlm:8099/video_feed"
    still_image_url: "http://a0d7b954-hailo-vlm:8099/video_feed"
```

---

## Automation Examples

### 1. Periodic Scene Description (Every 5 Minutes)

Capture an image and log what the VLM sees on a schedule:

```yaml
automation:
  - alias: "Hailo VLM — Periodic Scene Check"
    description: "Every 5 minutes, capture and describe the camera scene"
    trigger:
      - platform: time_pattern
        minutes: "/5"
    condition:
      - condition: state
        entity_id: sensor.hailo_vlm_status
        state: "ready"
    action:
      - service: rest_command.hailo_vlm_capture
      - delay: "00:00:02"
      - service: rest_command.hailo_vlm_ask
        data:
          prompt: "Briefly describe what you see in this image."
      - delay: "00:00:30"
      - service: rest_command.hailo_vlm_resume
```

### 2. Doorbell Ring — Describe Who's at the Door

When a doorbell sensor triggers, ask the VLM to describe the visitor:

```yaml
automation:
  - alias: "Hailo VLM — Doorbell Visitor Check"
    trigger:
      - platform: state
        entity_id: binary_sensor.doorbell
        to: "on"
    action:
      - service: rest_command.hailo_vlm_capture
      - delay: "00:00:02"
      - service: rest_command.hailo_vlm_ask
        data:
          prompt: "Describe the person at the door. What are they wearing? Are they carrying anything?"
      - service: notify.mobile_app_phone
        data:
          title: "Someone at the door"
          message: "VLM analysis in progress — check the Hailo VLM panel."
      - delay: "00:00:30"
      - service: rest_command.hailo_vlm_resume
```

### 3. Motion-Triggered Object Identification

When a motion sensor fires, ask the VLM what caused it:

```yaml
automation:
  - alias: "Hailo VLM — Motion Analysis"
    trigger:
      - platform: state
        entity_id: binary_sensor.backyard_motion
        to: "on"
    condition:
      - condition: state
        entity_id: sensor.hailo_vlm_status
        state: "ready"
    action:
      - service: rest_command.hailo_vlm_capture
      - delay: "00:00:01"
      - service: rest_command.hailo_vlm_ask
        data:
          prompt: "Motion was detected. What is moving in this image? Is it a person, animal, vehicle, or something else?"
      - delay: "00:00:30"
      - service: rest_command.hailo_vlm_resume
```

### 4. Daily Summary via Persistent Notification

```yaml
automation:
  - alias: "Hailo VLM — Daily Overview"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: rest_command.hailo_vlm_capture
      - delay: "00:00:02"
      - service: rest_command.hailo_vlm_ask
        data:
          prompt: "Give a brief morning summary of what you see. Mention weather conditions, any people, vehicles, or notable objects."
      - delay: "00:00:30"
      - service: persistent_notification.create
        data:
          title: "Morning Camera Summary"
          message: "VLM analysis complete — check the Hailo VLM panel for details."
      - service: rest_command.hailo_vlm_resume
```

---

## Building Your Own Hailo Add-on

This repository serves as a **template** for the community. Here's how to
build your own Hailo-10H powered add-on:

### Addon Structure

```
your-addon/
├── config.yaml          # HA add-on manifest
├── build.yaml           # Custom base image (Debian, for glibc)
├── Dockerfile           # Build HailoRT + your app
├── DOCS.md              # User documentation
├── README.md            # Short description
├── translations/
│   └── en.yaml          # Configuration labels
└── rootfs/
    └── opt/your_app/
        ├── run.sh       # Entrypoint (reads /data/options.json)
        ├── app.py       # Your Python application
        └── ...
```

### Key Patterns

**1. Access the Hailo device:** In `config.yaml`, set `full_access: true` so
the container can see `/dev/hailo0`. Also set `video: true` for camera access.

**2. Install HailoRT in Dockerfile:** Use `build.yaml` to override the base
image to Debian (Alpine doesn't work with HailoRT). Install from pre-built
packages (`.deb` + `.whl`) — download them from the
[Hailo Developer Zone](https://hailo.ai/developer-zone/):

```dockerfile
# Place .deb and .whl in a packages/ directory next to the Dockerfile
COPY packages/ /tmp/packages/
RUN apt-get update \
    && dpkg -i /tmp/packages/h10-hailort_5.2.0_arm64.deb \
    || (apt-get install -f -y && dpkg -i /tmp/packages/h10-hailort_5.2.0_arm64.deb) \
    && ldconfig && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages --no-cache-dir \
    /tmp/packages/hailort-5.2.0-cp311-cp311-linux_aarch64.whl \
    && rm -rf /tmp/packages
```

**3. Read options:** Use `jq` in your `run.sh` to parse `/data/options.json`:

```bash
VALUE=$(jq -r '.my_option // "default"' /data/options.json)
export VALUE
exec python3 /opt/your_app/main.py
```

**4. Ingress integration:** Set `ingress: true` and `ingress_port: <port>` in
`config.yaml`. In your web app, handle the `X-Ingress-Path` header (HA
rewrites URLs through the ingress proxy).

**5. Use hailo_platform:** In Python:

```python
from hailo_platform import VDevice
from hailo_platform.genai import VLM

params = VDevice.create_params()
vdevice = VDevice(params)
vlm = VLM(vdevice, "/path/to/model.hef")
```

### What Else Can You Build?

- **Object detection** — Run a YOLO HEF model for real-time detection
- **Person re-identification** — Track people across multiple cameras
- **License plate recognition** — Read plates from driveway cameras
- **Pet detection** — Alert when your pet is doing something naughty
- **Package delivery** — Detect packages left at the door
- **Safety monitoring** — Detect falls, smoke, or unusual activity

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   Home Assistant OS                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ HAOS Kernel (hailo1x_pci driver + hailo10h firmware)│  │
│  └──────────────────┬──────────────────────────────────┘  │
│                     │ /dev/hailo0                          │
│  ┌──────────────────┴──────────────────────────────────┐  │
│  │  Docker Container: hailo_vlm                         │  │
│  │  ┌───────────────┐  ┌────────────────┐              │  │
│  │  │  Flask Server  │  │  VLM Backend   │              │  │
│  │  │  (port 8099)   │──│  (hailo_platform│              │  │
│  │  │                │  │   + genai.VLM) │              │  │
│  │  │  MJPEG stream  │  │                │              │  │
│  │  │  REST API      │  │  Multiprocess  │              │  │
│  │  │  Web UI        │  │  Worker        │              │  │
│  │  └───────┬────────┘  └───────┬────────┘              │  │
│  │          │ /dev/video0       │ /dev/hailo0            │  │
│  └──────────┴───────────────────┴───────────────────────┘  │
│                     │                                      │
│  ┌──────────────────┴──────────────────────────────────┐  │
│  │   HA Ingress Proxy (/api/hassio_ingress/<token>/)   │  │
│  │          ↕ Lovelace cards / Automations              │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| Add-on fails to start | Check Logs tab | Ensure HAOS has `hailo10h-pci` driver |
| "No Hailo device" warning | `ls /dev/hailo*` on host | Reboot, check PCIe connection |
| "No camera" warning | `ls /dev/video*` on host | Plug in USB camera, set `video: true` |
| VLM gives demo responses | Check for `.hef` file in `/media` | Download and place VLM HEF model |
| Slow inference | Normal for first prompt | Subsequent prompts are faster; try lower `max_tokens` |
| Build fails | Check Logs tab for details | Ensure base image is Debian (not Alpine); verify `.deb`/`.whl` are in `packages/` |
| Blank video in Lovelace | Ingress token wrong | Re-check the iframe URL / addon hostname |

### Useful Host Commands

```bash
# Check Hailo driver
ha host exec -- lsmod | grep hailo

# Check camera
ha host exec -- ls -la /dev/video*

# Check add-on container
ha addons info hailo_vlm

# View add-on logs
ha addons logs hailo_vlm
```

---

## Contributing

This is a community project. Contributions welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Ideas for Contribution

- Additional VLM model support (Llama-Vision, etc.)
- Object detection add-on using YOLO HEF models
- Better Lovelace custom card component
- Streaming token-by-token VLM responses (SSE)
- Multi-camera support
- Integration with HA conversation agent

---

## License

MIT — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Hailo](https://hailo.ai/) — Hailo-10H AI accelerator & HailoRT SDK
- [Home Assistant](https://www.home-assistant.io/) — The open smart home platform
- [Home Assistant OS](https://github.com/home-assistant/operating-system) — Linux distribution for HA
