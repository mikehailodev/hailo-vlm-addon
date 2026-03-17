# Home Assistant Add-on: Hailo-10H VLM Chat

## How to use

### Prerequisites

1. **Hardware**: Raspberry Pi 5 with Hailo-10H AI HAT+ connected
2. **HAOS**: Home Assistant OS built with `hailo10h-pci` and `hailo10h-firmware`
   packages (see the operating-system fork)
3. **Camera**: USB camera connected to the Pi 5
4. **VLM Model**: A Hailo VLM HEF model file (e.g. Qwen2-VL-2B-Instruct)

### Quick Start

1. Install this add-on from the repository
2. Configure the camera device path (default: `/dev/video0`)
3. Place your VLM `.hef` model file in the HA `/media` or `/share` directory
4. Start the add-on
5. Open the Web UI from the sidebar

### Using the VLM Chat

1. **Live Video** — The camera feed streams in real time
2. **Capture** — Click the Capture button (or press `Enter`) to freeze the frame
3. **Ask** — Type a question and click Ask (or press `Enter`)
4. **View Response** — The VLM analyzes the image and returns its answer
5. **Resume** — Click Resume Video (or press `Enter`) to return to live

### Keyboard Shortcuts

- `Enter` to cycle: Capture → Ask → Resume → Capture → ...
- All interactions happen through the single video window

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `camera_device` | `/dev/video0` | Video device path |
| `max_tokens` | `200` | Max tokens per VLM response |
| `temperature` | `0.1` | Sampling temperature (0.0 = deterministic) |
| `default_prompt` | `Describe the image` | Prompt used when field is empty |
| `system_prompt` | *(helpful assistant)* | System prompt guiding VLM behavior |

## VLM Model

The add-on searches for `.hef` files containing "vlm" or "qwen" in the name
under `/media` and `/share`. Download a compatible model from the
[Hailo Model Zoo](https://hailo.ai/developer-zone/) and place it there.

**Recommended model:** `Qwen2-VL-2B-Instruct` (Hailo-10H optimized)

## Demo Mode

If no Hailo device is detected (or `hailo_platform` is not installed), the
add-on runs in **demo mode** with simulated responses. This lets you test the
UI and integration without hardware.

## Troubleshooting

- **No camera**: Check that `video: true` is set and the correct device path
  is configured. Run `ls /dev/video*` on the host.
- **No Hailo device**: Verify `lsmod | grep hailo` shows `hailo1x_pci` on the host.
- **Slow responses**: VLM inference on Hailo-10H typically takes 5-30 seconds
  depending on the model and prompt complexity.
