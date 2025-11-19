#!/usr/bin/env bash
set -e

# Use libtcmalloc for better memory management (from original script)
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

echo "worker-comfyui: Starting ComfyUI in the background..."
# Start ComfyUI server in the background, using args from original script
/venv/bin/python /root/comfy/ComfyUI/main.py --disable-auto-launch --listen 0.0.0.0 --port 8188 &

# --- CRITICAL FIX: Wait for ComfyUI to be ready ---
echo "Waiting for ComfyUI to be ready..."
while ! curl --silent --fail --head http://127.0.0.1:8188/history > /dev/null; do
    echo -n "."
    sleep 1
done
echo "ComfyUI is ready and listening."
# --- End of fix ---

echo "worker-comfyui: Starting RunPod Handler now that ComfyUI is ready."
# Start the RunPod handler only after ComfyUI is confirmed to be ready
/venv/bin/python -u /root/rp_handler.py
