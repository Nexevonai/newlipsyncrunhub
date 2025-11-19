# WanVideo 2.1 InfiniteTalk - RunPod Serverless Project Status

**Last Updated**: 2025-11-09
**Current Status**: Container build in progress (fixes applied, awaiting build completion)

---

## Project Overview

### What We're Building
A **RunPod serverless endpoint** that generates talking head videos with lip-sync using WanVideo 2.1 InfiniteTalk.

**Input**: Image URL + Audio URL
**Output**: MP4 video with synchronized lip movements uploaded to Cloudflare R2

### Conversion History
- **Original Project**: Vibe Voice TTS (audio voice cloning)
- **Converted To**: WanVideo 2.1 InfiniteTalk (talking video generation)
- **Conversion Date**: 2025-11-08
- **Base Project**: upscale2flare (image upscaling workflow)

---

## Current Configuration

### Docker Environment
```dockerfile
Base Image: runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04
Python: 3.11 (in venv)
PyTorch: 2.8.0
CUDA Runtime: 12.8.1
ComfyUI CUDA: 12.9 (binaries compatible with 12.8.1 runtime)
```

### System Dependencies
- build-essential (C/C++ compilers for SageAttention)
- ninja-build (fast build system for compilation)
- ffmpeg (video processing)
- curl, git, wget, unzip (standard utilities)

### GPU Compatibility
- **Primary Target**: RTX 5090 (sm_120 - Blackwell architecture)
- **Also Supports**: RTX 3090, 4090, A100, etc. (sm_80, sm_86, sm_90)
- **Note**: RTX 5090 performance optimal with driver 572+, US-CA-2 region recommended

---

## Models Configuration

### All 7 Models Required

| Model | Size | Path | Purpose |
|-------|------|------|---------|
| Main I2V | 10.2GB | `unet/wan2.1-i2v-14b-480p-Q4_0.gguf` | Image-to-video generation |
| InfiniteTalk | 2.04GB | `unet/InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q6_K.gguf` | Lip-sync model |
| Text Encoder | 6.74GB | `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` | Prompt encoding |
| VAE | 254MB | `vae/wan_2.1_vae.safetensors` | Video decoder |
| CLIP Vision | 1.26GB | `clip_vision/clip_vision_h.safetensors` | Image encoding |
| Distill LoRA | 738MB | `loras/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | 4-step fast generation |
| Wav2Vec2 | 1.5GB | Auto-download on first use | Audio embeddings |

**CRITICAL**: Model paths must include subdirectories (e.g., `InfiniteTalk/...`, `Lightx2v/...`)

---

## Issues Encountered & Fixes Applied

### Issue 1: Model Path Validation Errors ✅ FIXED
**Error**: `Value not in list: model: 'Wan2_1-InfiniteTalk_Single_Q6_K.gguf'`

**Root Cause**: Workflow referenced models without subdirectory paths

**Fix**: Updated both `test_request.json` and `workflow_api_wanvideo.json`:
- Node 120: `Wan2_1-InfiniteTalk_Single_Q6_K.gguf` → `InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q6_K.gguf`
- Node 138: `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` → `Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`

### Issue 2: SageAttention Installation Failure ✅ FIXED
**Error**: `exit code: 1` during `pip install sageattention`

**Root Cause**: Missing compilation dependencies

**Fix**:
1. Added `build-essential` and `ninja-build` to system packages
2. Changed installation to: `pip install sageattention --no-build-isolation`

### Issue 3: Docker Base Image Not Found ✅ FIXED
**Error**: `runpod/pytorch:2.7.0-py3.11-cuda12.8.0-devel-ubuntu22.04: not found`

**Root Cause**: Wrong tag format (RunPod uses `-cudnn-devel` not `-devel`)

**Fix**: Changed to existing image:
```dockerfile
FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04
```

### Issue 4: ComfyUI CUDA Version Mismatch ✅ FIXED
**Error**: `Invalid value for '--cuda-version': '12.8' is not one of '12.9', '12.6', '12.4', '12.1', '11.8'`

**Root Cause**: comfy-cli doesn't support CUDA 12.8

**Fix**: Changed to supported version:
```dockerfile
RUN comfy --skip-prompt install --nvidia --cuda-version 12.9
```

### Issue 5: Original Model Filenames Wrong ✅ FIXED (Earlier)
**Error**: Build failing during model downloads

**Root Cause**: Incorrect filenames with `_2` suffixes that don't exist on HuggingFace

**Fixes Applied**:
- Main I2V: `Q4_0_2.gguf` → `Q4_0.gguf`
- InfiniteTalk: `Q6_K_2.gguf` → `Q6_K.gguf`
- Text Encoder: Wrong repo → Correct repo and filename
- Distill LoRA: `Wan2.1-lightx2v...` → `lightx2v...`

---

## Current Test Status

### Completed
✅ Container build configuration updated
✅ Model paths corrected
✅ SageAttention installation fixed
✅ Docker base image verified
✅ ComfyUI CUDA compatibility resolved

### Pending
⏳ Container build completion
⏳ First test execution with test_request.json
⏳ R2 environment variables configuration
⏳ Video output validation

### Test Files Ready
- `test_request.json` - Complete workflow with test URLs
  - Image: `https://raw.githubusercontent.com/Nexevonai/infittalktest/main/50women.png`
  - Audio: `https://raw.githubusercontent.com/Nexevonai/infittalktest/main/sendemail.mp3`

---

## File Reference

### Core Files
| File | Purpose | Status |
|------|---------|--------|
| `Dockerfile` | Container build config | ✅ Updated |
| `src/rp_handler.py` | RunPod serverless handler | ✅ Ready |
| `src/ComfyUI_API_Wrapper.py` | ComfyUI API client | ✅ Ready |
| `src/start.sh` | Container startup script | ✅ Ready |

### Workflow Files
| File | Purpose | Status |
|------|---------|--------|
| `workflow_api_wanvideo.json` | API format workflow (32 nodes) | ✅ Fixed |
| `test_request.json` | Test API request | ✅ Fixed |
| `input.json` | Example input format | ⚠️ Needs update |
| `response.json` | Example output format | ⚠️ Needs update |

### Documentation
| File | Purpose | Status |
|------|---------|--------|
| `CLAUDE.md` | Project instructions | ✅ Updated |
| `PROJECT_STATUS.md` | This file | ✅ Current |
| `API_INTEGRATION_GUIDE.md` | API usage guide | ℹ️ Exists |
| `WORKFLOW_CONVERSION_GUIDE.md` | Conversion notes | ℹ️ Exists |

---

## API Request Format

### Input Schema
```json
{
  "input": {
    "image_url": "https://example.com/image.jpg",
    "audio_url": "https://example.com/audio.mp3",
    "width": 639,        // OPTIONAL - override default
    "height": 640,       // OPTIONAL - override default
    "workflow": { ... }  // Complete workflow JSON
  }
}
```

### Output Schema
```json
{
  "video": [
    "https://pub-xxx.r2.dev/uuid_video.mp4"
  ]
}
```

---

## Environment Variables Required

```bash
# Cloudflare R2 Configuration
R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

**Status**: ⚠️ Need to be configured in RunPod endpoint settings

---

## Custom Nodes Installed

1. **ComfyUI-WanVideoWrapper** - Main WanVideo integration
2. **audio-separation-nodes-comfyui** - Demucs vocal extraction
3. **ComfyUI-VideoHelperSuite** - VHS_VideoCombine for MP4 output
4. **ComfyUI-KJNodes** - Image resize utilities

---

## Workflow Parameters

### Default Settings
- **Resolution**: 639×640 (configurable via API)
- **Frame Rate**: 25 fps
- **Total Frames**: 175 (~7 seconds)
- **Generation Steps**: 4 (with LoRA distillation)
- **Audio Processing**: Vocal separation enabled
- **Attention Mode**: SageAttention (sageattn)

### Node Configuration Highlights
- **Node 122** (Main Model): sageattn, offload_device, bf16
- **Node 134** (Block Swap): 40 blocks swapped to RAM
- **Node 138** (LoRA): Strength 0.8 for 4-step generation
- **Node 213** (Sampler): flowmatch_distill scheduler

---

## Known Issues & Workarounds

### SageAttention Warning (RESOLVED)
- **Issue**: "No module named 'sageattention'" warning
- **Status**: ✅ Fixed with build-essential, ninja-build, and --no-build-isolation
- **Impact**: None once build completes

### RTX 5090 Performance (ONGOING)
- **Issue**: Some RunPod regions have driver 570.x (suboptimal for RTX 5090)
- **Workaround**: Deploy to US-CA-2 region for driver 572+
- **Impact**: 2x performance difference possible

### First Run Auto-Downloads (EXPECTED)
- **Models**: Wav2Vec2 (~1.5GB) and Demucs (~500MB) download on first execution
- **Workaround**: First request will take longer (~2-5 minutes extra)
- **Impact**: One-time delay, subsequent requests normal speed

---

## Next Steps

### Immediate (In Progress)
1. ⏳ Complete container build
2. ⏳ Verify SageAttention loads successfully
3. ⏳ Configure R2 environment variables in RunPod

### Testing Phase
1. ⏳ Run first test with test_request.json
2. ⏳ Verify video output quality
3. ⏳ Monitor VRAM usage on RTX 5090
4. ⏳ Measure generation time (target: ~30-60 seconds for 7 second video)

### Optimization (Future)
1. ⬜ Test different resolutions (1080p, 720p)
2. ⬜ Benchmark different LoRA strengths
3. ⬜ Test longer duration videos (15-30 seconds)
4. ⬜ Optimize audio processing pipeline

---

## Technical Notes

### VRAM Usage Estimate
- **Minimum**: 12GB (with block swapping)
- **Recommended**: 24GB (RTX 5090, RTX 4090)
- **Optimal**: 32GB (for smoother generation)

### Generation Speed Estimate
- **4 steps with LoRA**: ~30-60 seconds for 7-second video
- **Variable factors**: Resolution, frame count, VRAM, driver version

### Architecture Support
- **sm_120**: RTX 5090 (Blackwell)
- **sm_90**: H100, RTX 6000 Ada
- **sm_86**: RTX 3090, A6000
- **sm_80**: A100

---

## Command Reference

### Build Container
```bash
# RunPod handles this automatically via Dockerfile
# Manual build (local testing):
docker build -t vibevoice-runpod .
```

### Test Locally (if needed)
```bash
docker run --gpus all -p 8188:8188 vibevoice-runpod
```

### View Logs
```bash
# Via RunPod dashboard > Logs tab
# Or download logs from worker interface
```

---

## Troubleshooting Guide

### Build Fails at Model Download
- **Check**: HuggingFace connectivity
- **Fix**: Verify model filenames match repository exactly

### Container Starts but Handler Fails
- **Check**: R2 environment variables set correctly
- **Fix**: Verify R2_ENDPOINT_URL, credentials, and bucket name

### Workflow Validation Errors
- **Check**: Model paths include subdirectories
- **Fix**: Ensure paths match: `InfiniteTalk/...`, `Lightx2v/...`

### Out of Memory Errors
- **Check**: GPU has sufficient VRAM (12GB minimum)
- **Fix**: Increase block_swap (line 71 in workflow), or use lower resolution

### Slow Performance on RTX 5090
- **Check**: Driver version (`nvidia-smi`)
- **Fix**: Request pod in US-CA-2 region with driver 572+

---

## Version History

### v1.1 (Current) - 2025-11-09
- ✅ Fixed Docker base image tag
- ✅ Fixed ComfyUI CUDA version compatibility
- ✅ Added SageAttention with proper compilation flags
- ✅ Updated model paths with subdirectories
- ⏳ Build in progress

### v1.0 - 2025-11-08
- ✅ Initial conversion from Vibe Voice to WanVideo
- ✅ Created workflow_api_wanvideo.json
- ✅ Updated Dockerfile with WanVideo models
- ✅ Modified rp_handler.py for video output
- ⚠️ Had model path validation errors

---

## Contact & Resources

### Official Documentation
- [WanVideo GitHub](https://github.com/kijai/ComfyUI-WanVideoWrapper)
- [RunPod Docs](https://docs.runpod.io/)
- [Cloudflare R2 Docs](https://developers.cloudflare.com/r2/)

### Model Sources
- [Main I2V Model](https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf)
- [InfiniteTalk Model](https://huggingface.co/Kijai/WanVideo_comfy_GGUF)
- [Text Encoder & Other Models](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged)

---

**End of Status Document**
*This document should be updated as the project progresses*
