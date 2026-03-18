#!/bin/bash
set -e

CONFIG_PATH=/data/options.json

# Read options
CAMERA_DEVICE=$(jq -r '.camera_device // "/dev/video0"' "$CONFIG_PATH")
MAX_TOKENS=$(jq -r '.max_tokens // 200' "$CONFIG_PATH")
TEMPERATURE=$(jq -r '.temperature // 0.1' "$CONFIG_PATH")
DEFAULT_PROMPT=$(jq -r '.default_prompt // "Describe the image"' "$CONFIG_PATH")
SYSTEM_PROMPT=$(jq -r '.system_prompt // "You are a helpful assistant that analyzes images and answers questions about them."' "$CONFIG_PATH")

export CAMERA_DEVICE MAX_TOKENS TEMPERATURE DEFAULT_PROMPT SYSTEM_PROMPT

echo "=========================================="
echo " Hailo-10H VLM Chat Add-on"
echo "=========================================="
echo "Camera device: ${CAMERA_DEVICE}"
echo "Max tokens:    ${MAX_TOKENS}"
echo "Temperature:   ${TEMPERATURE}"
echo "=========================================="

# --- Diagnostics ---
echo ""
echo "--- Container diagnostics ---"
echo "Running as: $(id)"
echo "Capabilities:"
cat /proc/self/status | grep -i cap || echo "  (could not read capabilities)"
echo ""
echo "Device nodes:"
ls -la /dev/hailo* 2>/dev/null || echo "  No /dev/hailo* devices found"
ls -la /dev/video* 2>/dev/null || echo "  No /dev/video* devices found"
echo ""

# Check for Hailo device
if [ -e /dev/hailo0 ]; then
    echo "✓ Hailo device found at /dev/hailo0"
    # Test open() access (Hailo driver uses ioctl, not read, so dd won't work)
    if python3 -c "open('/dev/hailo0','rb').close()" 2>/dev/null; then
        echo "✓ Hailo device is accessible"
    else
        echo "✗ Hailo device exists but CANNOT be opened (EPERM)"
        echo "  Disable Protection Mode in the add-on Info tab and restart"
    fi
else
    echo "⚠ WARNING: No Hailo device found at /dev/hailo0"
    echo "  The add-on will start in demo mode without AI inference."
fi

# Check for camera
if [ -e "${CAMERA_DEVICE}" ]; then
    echo "✓ Camera found at ${CAMERA_DEVICE}"
else
    echo "⚠ WARNING: No camera found at ${CAMERA_DEVICE}"
    echo "  Video streaming will show a placeholder."
fi

echo ""
echo "Starting web server on port 8099..."
exec python3 /opt/hailo_vlm/server.py
