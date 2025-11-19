# ComfyUI Workflow Conversion Guide

Step-by-step guide showing how we converted the image upscaling workflow to Vibe Voice TTS. Use this as a template for converting to any other ComfyUI workflow.

---

## Table of Contents
1. [Overview](#overview)
2. [Step 1: Analyze the Current Setup](#step-1-analyze-the-current-setup)
3. [Step 2: Choose Your New Workflow](#step-2-choose-your-new-workflow)
4. [Step 3: Identify Required Models](#step-3-identify-required-models)
5. [Step 4: Update the Dockerfile](#step-4-update-the-dockerfile)
6. [Step 5: Convert Workflow to API Format](#step-5-convert-workflow-to-api-format)
7. [Step 6: Update the Handler](#step-6-update-the-handler)
8. [Step 7: Update Example Files](#step-7-update-example-files)
9. [Step 8: Test and Debug](#step-8-test-and-debug)
10. [Common Patterns](#common-patterns)

---

## Overview

### What We Converted

**FROM**: Image Upscaling Workflow
- Input: Images
- Process: 4x upscaling with AI enhancement
- Output: Upscaled images
- Models: SD1.5 checkpoint, LoRAs, ControlNet, Upscale models (~15GB)

**TO**: Vibe Voice TTS Workflow
- Input: Audio sample + Text
- Process: Voice cloning and speech generation
- Output: MP3 audio files
- Models: VibeVoice-Large, Qwen tokenizer (~20GB)

### Key Files Modified

| File | Purpose | Changes Required |
|------|---------|------------------|
| `Dockerfile` | Model downloads, dependencies | Always |
| `workflow_api.json` | Workflow definition | Always |
| `rp_handler.py` | Input/output handling | Sometimes |
| `ComfyUI_API_Wrapper.py` | ComfyUI API client | Sometimes |
| `input.json` | Example request | Always |
| `response.json` | Example response | Always |

---

## Step 1: Analyze the Current Setup

### 1.1 Document Current Workflow

Open `workflow_api.json` and identify:

```bash
# Count nodes
cat workflow_api.json | jq 'keys | length'

# List node types
cat workflow_api.json | jq 'to_entries[] | {id: .key, type: .value.class_type}'
```

**Original Workflow Nodes:**
- LoadImage (input)
- CheckpointLoaderSimple
- LoraLoader (x2)
- ControlNetLoader
- UpscaleModelLoader
- Various processing nodes
- SaveImage (output)

### 1.2 Document Current Models

Check `Dockerfile` for model downloads:

```dockerfile
# Lines 44-49 in original
RUN wget -O $COMFYUI_PATH/models/checkpoints/epicrealism_naturalSinRC1VAE.safetensors ...
RUN wget -O $COMFYUI_PATH/models/loras/more_details.safetensors ...
RUN wget -O $COMFYUI_PATH/models/controlnet/control_v11f1e_sd15_tile.pth ...
RUN wget -O $COMFYUI_PATH/models/upscale_models/4x_NMKD-Siax_200k.pth ...
```

**Models to remove**: ~15GB total

### 1.3 Document Handler Behavior

Check `rp_handler.py`:

```python
# Input type (line 39)
if 'image_url' in job_input:
    # Downloads and injects into LoadImage node

# Output type (line 64-68)
if node_data.get("class_type") == "SaveImage":
    # Retrieves and uploads images
```

**Input**: Images
**Output**: Images
**Content-Type**: image/png

---

## Step 2: Choose Your New Workflow

### 2.1 Design in ComfyUI (Recommended)

1. **Install ComfyUI locally**:
```bash
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
python main.py
```

2. **Install required custom nodes**:
   - Use ComfyUI Manager
   - Or manually git clone into `custom_nodes/`

3. **Build your workflow visually**

4. **Export as "Save (API Format)"** from menu

### 2.2 Use Existing Workflow

For our case, we found:
- **Source**: `Vibe Voice Workflow - Jockerai (1).json` (UI format)
- **Repository**: https://github.com/Enemyx-net/VibeVoice-ComfyUI
- **Format**: Needed conversion to API format

---

## Step 3: Identify Required Models

### 3.1 Find GitHub Repository

1. Search for the custom node:
   - Google: "ComfyUI [workflow name]"
   - GitHub search
   - ComfyUI Manager list

2. For Vibe Voice:
   - **Repo**: https://github.com/Enemyx-net/VibeVoice-ComfyUI
   - **Stars**: Check if actively maintained
   - **Issues**: Look for installation problems

### 3.2 Read Installation Instructions

From the README:

```markdown
## Installation
1. Clone repo to custom_nodes/
2. Download models:
   - VibeVoice-Large (18.7GB) from aoi-ot/VibeVoice-Large
   - Tokenizer from Qwen/Qwen2.5-1.5B
```

### 3.3 Document Model Requirements

Create a checklist:

| Model | Size | Source | Required | Path |
|-------|------|--------|----------|------|
| VibeVoice-Large | 18.7GB | HuggingFace: aoi-ot/VibeVoice-Large | Yes | models/vibevoice/VibeVoice-Large |
| Qwen Tokenizer | ~1GB | HuggingFace: Qwen/Qwen2.5-1.5B | Yes | models/vibevoice/tokenizer |

### 3.4 Check Python Dependencies

Look for `requirements.txt` or README:

```txt
diffusers
accelerate
transformers>=4.51.3
sentencepiece
soundfile
```

---

## Step 4: Update the Dockerfile

### 4.1 Remove Old Models

**Before:**
```dockerfile
# --- 5. 创建所有模型目录 ---
RUN mkdir -p \
    $COMFYUI_PATH/models/checkpoints \
    $COMFYUI_PATH/models/loras \
    $COMFYUI_PATH/models/controlnet \
    $COMFYUI_PATH/models/upscale_models

# --- 6. 下载所有模型文件 ---
RUN wget -O $COMFYUI_PATH/models/checkpoints/epicrealism_naturalSinRC1VAE.safetensors ...
RUN wget -O $COMFYUI_PATH/models/loras/more_details.safetensors ...
RUN wget -O $COMFYUI_PATH/models/controlnet/control_v11f1e_sd15_tile.pth ...
RUN wget -O $COMFYUI_PATH/models/upscale_models/4x_NMKD-Siax_200k.pth ...

# --- 7. 安装所有自定义节点 ---
RUN git clone https://github.com/Extraltodeus/ComfyUI-AutomaticCFG.git ...
RUN git clone https://github.com/pamparamm/sd-perturbed-attention.git ...
```

### 4.2 Add New Models

**After:**
```dockerfile
# --- 5. 创建 VibeVoice 模型目录 ---
RUN mkdir -p \
    $COMFYUI_PATH/models/vibevoice/tokenizer \
    $COMFYUI_PATH/models/vibevoice/VibeVoice-Large

# --- 6. 下载 VibeVoice 模型文件 ---
RUN /venv/bin/huggingface-cli download aoi-ot/VibeVoice-Large \
    --local-dir $COMFYUI_PATH/models/vibevoice/VibeVoice-Large \
    --local-dir-use-symlinks False

RUN /venv/bin/huggingface-cli download Qwen/Qwen2.5-1.5B \
    tokenizer_config.json vocab.json merges.txt tokenizer.json \
    --local-dir $COMFYUI_PATH/models/vibevoice/tokenizer \
    --local-dir-use-symlinks False

# --- 7. 安装 VibeVoice 自定义节点 ---
RUN git clone https://github.com/Enemyx-net/VibeVoice-ComfyUI.git \
    $COMFYUI_PATH/custom_nodes/VibeVoice-ComfyUI

# --- 8. 安装 VibeVoice Python 依赖 ---
RUN /venv/bin/python -m pip install \
    diffusers \
    accelerate \
    transformers>=4.51.3 \
    sentencepiece \
    soundfile
```

### 4.3 Add huggingface-hub Dependency

```dockerfile
# In the handler dependencies section (around line 28)
RUN /venv/bin/python -m pip install \
    opencv-python \
    imageio-ffmpeg \
    runpod \
    requests \
    websocket-client \
    boto3 \
    huggingface-hub  # ADD THIS
```

### 4.4 Important Notes

**Directory Structure:**
- ComfyUI looks for models in specific paths
- Check the custom node's code for expected paths
- For VibeVoice: `models/vibevoice/[model-name]/`

**Download Methods:**
- `wget`: For direct file URLs
- `huggingface-cli download`: For HuggingFace repos (recommended)
- `git lfs`: For large files in git repos

**Troubleshooting:**
- Use `--local-dir-use-symlinks False` to avoid symlink issues
- Specify exact files if downloading specific tokenizer files

---

## Step 5: Convert Workflow to API Format

### 5.1 Understanding Format Differences

**UI Format** (what ComfyUI saves by default):
```json
{
  "nodes": [
    {
      "id": 2,
      "type": "LoadAudio",
      "pos": [157, -1081],
      "size": [274, 136],
      "widgets_values": ["audio_file.mp3", null, null]
    }
  ],
  "links": [[8, 2, 0, 7, 0, "AUDIO"]]
}
```

**API Format** (what the handler needs):
```json
{
  "2": {
    "inputs": {
      "audio": "audio_file.mp3"
    },
    "class_type": "LoadAudio",
    "_meta": {
      "title": "LoadAudio"
    }
  }
}
```

### 5.2 Conversion Methods

#### Method A: Export from ComfyUI (Best)

1. Open workflow in ComfyUI
2. Ensure all custom nodes are installed
3. Menu → **"Save (API Format)"**
4. This gives clean, correct API format

#### Method B: Manual Conversion

If custom nodes aren't installed locally, convert manually:

**Step 1**: Identify nodes
```python
# From UI format
nodes = ui_json["nodes"]
for node in nodes:
    node_id = str(node["id"])
    node_type = node["type"]
    widgets = node.get("widgets_values", [])
```

**Step 2**: Map widgets to inputs

Check the node's code to see parameter names:
```python
# Example: VibeVoiceMultipleSpeakersNode
# widgets_values = [text, model, language, precision, ...]
# becomes:
"inputs": {
    "text": widgets[0],
    "model": widgets[1],
    "language": widgets[2],
    ...
}
```

**Step 3**: Create API structure
```python
api_workflow = {}
for node in nodes:
    api_workflow[str(node["id"])] = {
        "inputs": map_widgets_to_inputs(node),
        "class_type": node["type"],
        "_meta": {"title": node.get("title", node["type"])}
    }
```

### 5.3 Handle Missing Parameters

**Problem**: UI export may miss required parameters

**Example**: Our initial export was missing:
```python
# Missing from UI export:
- free_memory_after_generate
- quantize_llm
- use_sampling
- cfg_scale
- attention_type
- model (was model_name)
- diffusion_steps
- seed
```

**Solution**: Check worker logs

When testing, ComfyUI will tell you:
```
Failed to validate prompt for output 11:
* VibeVoiceMultipleSpeakersNode 7:
  - Required input is missing: seed
  - Required input is missing: diffusion_steps
  ...
```

Add these to your workflow JSON!

### 5.4 Find Default Values

**Where to look:**
1. **Node definition file** (`nodes/your_node.py`):
```python
@classmethod
def INPUT_TYPES(cls):
    return {
        "required": {
            "text": ("STRING", {"multiline": True}),
            "model": (["VibeVoice-Large"], {"default": "VibeVoice-Large"}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 999999}),
            ...
        }
    }
```

2. **UI workflow file** (widgets_values array)

3. **README examples**

---

## Step 6: Update the Handler

### 6.1 Determine What Needs Changing

Ask yourself:
- **Input type different?** (image → audio, text → image, etc.)
- **Output type different?** (SaveImage → SaveAudioMP3, etc.)
- **Content-Type different?** (image/png → audio/mpeg, etc.)

### 6.2 Update Input Handling

**If input type changed:**

Original (images):
```python
def download_image(url, save_path):
    # Downloads image

if 'image_url' in job_input:
    image_filename = f"input_{uuid.uuid4()}.png"
    # ...
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "LoadImage":
            workflow[node_id]["inputs"]["image"] = image_filename
```

Updated (audio):
```python
def download_audio(url, save_path):
    # Downloads audio

if 'audio_url' in job_input:
    audio_filename = f"input_{uuid.uuid4()}.mp3"
    # ...
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "LoadAudio":
            workflow[node_id]["inputs"]["audio"] = audio_filename
```

**Pattern:**
1. Rename function: `download_X()`
2. Change input parameter name: `X_url`
3. Change file extension: `.png` → `.mp3`
4. Change node search: `LoadImage` → `LoadAudio`
5. Change input field: `"image"` → `"audio"`

### 6.3 Update Output Detection

**If output node different:**

Original:
```python
output_node_id = None
for node_id, node_data in workflow.items():
    if node_data.get("class_type") == "SaveImage":
        output_node_id = node_id
        break
```

Updated:
```python
output_node_id = None
for node_id, node_data in workflow.items():
    if node_data.get("class_type") == "SaveAudioMP3":
        output_node_id = node_id
        break
```

### 6.4 Update Content Type

**If output format different:**

Original:
```python
s3_client.put_object(
    Bucket=bucket_name,
    Key=unique_filename,
    Body=image_bytes,
    ContentType='image/png'  # ← CHANGE THIS
)
```

Updated:
```python
s3_client.put_object(
    Bucket=bucket_name,
    Key=unique_filename,
    Body=audio_bytes,
    ContentType='audio/mpeg'  # ← NEW VALUE
)
```

### 6.5 Update Return Format

Original:
```python
return {"images": image_urls}
```

Updated:
```python
return {"audio": audio_urls}
```

### 6.6 Update API Wrapper (if needed)

**Problem**: `SaveAudioMP3` returns data under `'audio'` key, not `'images'`

**Solution**: Make wrapper flexible

Original (`ComfyUI_API_Wrapper.py` line 34):
```python
return history[prompt_id]['outputs'].get(output_node_id, {}).get('images', [])
```

Updated:
```python
outputs = history[prompt_id]['outputs'].get(output_node_id, {})
# Try both 'images' (for SaveImage) and 'audio' (for SaveAudioMP3)
return outputs.get('images', outputs.get('audio', []))
```

This makes it work for BOTH image and audio workflows!

---

## Step 7: Update Example Files

### 7.1 Update input.json

```json
{
  "input": {
    "audio_url": "https://raw.githubusercontent.com/user/repo/main/sample.mp3",
    "workflow": {
      // Your complete API format workflow here
    }
  }
}
```

### 7.2 Update response.json

```json
{
  "delayTime": 120,
  "executionTime": 45000,
  "id": "uuid-here",
  "output": {
    "audio": [
      "https://pub-xxx.r2.dev/uuid_filename.mp3"
    ]
  },
  "status": "COMPLETED",
  "workerId": "worker-id"
}
```

### 7.3 Update claude.md Documentation

Document:
- New workflow purpose
- New models used
- New input/output formats
- New parameters
- Storage requirements

---

## Step 8: Test and Debug

### 8.1 Build Locally First (if possible)

```bash
docker build -t my-workflow-test .
```

Watch for:
- Model download errors
- Missing dependencies
- Custom node installation failures

### 8.2 Deploy to RunPod

1. Push to GitHub
2. Create/update RunPod endpoint
3. Point to your repo
4. Set environment variables
5. Set container disk size appropriately
6. Trigger build

### 8.3 Check Build Logs

Go to **Builds** tab, look for:

✅ **Success indicators:**
```
Successfully installed diffusers-0.X.X
Cloning into 'VibeVoice-ComfyUI'...
[VibeVoice] Found 1 VibeVoice model(s) available
```

❌ **Error indicators:**
```
ERROR: Could not find a version that satisfies...
fatal: destination path exists...
ModuleNotFoundError: No module named 'diffusers'
```

### 8.4 Test with Simple Request

Use RunPod's **Requests** tab to test

**First test**: Use minimal text
```json
{
  "input": {
    "audio_url": "https://...",
    "workflow": {...}
  }
}
```

### 8.5 Debug Common Issues

#### Issue: "Required input is missing: X"

**Cause**: Workflow JSON missing parameters

**Solution**: Check worker logs, add missing parameters

#### Issue: "执行超时或工作流未生成任何音频输出"

**Cause**:
- Output node detection failed
- API wrapper not finding output
- Wrong output key

**Solution**: Check logs for actual execution

#### Issue: "ModuleNotFoundError"

**Cause**: Missing Python dependencies

**Solution**: Add to Dockerfile pip install

#### Issue: Model not found

**Cause**:
- Model download failed
- Wrong directory path
- Insufficient disk space

**Solution**:
- Check build logs
- Verify HuggingFace URLs
- Increase container disk size

---

## Common Patterns

### Pattern 1: Text-to-Image

**Changes needed:**
- Input: Text only (no file download)
- Output: SaveImage
- Handler: Minimal changes

**Dockerfile:**
```dockerfile
# Download SD checkpoint
RUN wget -O $COMFYUI_PATH/models/checkpoints/...

# Install custom samplers (if needed)
RUN git clone https://github.com/.../ComfyUI-CustomNodes
```

**Handler:**
```python
# No file download needed
# Just pass workflow with text in prompt node
```

### Pattern 2: Image-to-Image

**Changes needed:**
- Input: image_url (keep existing)
- Output: SaveImage (keep existing)
- Handler: Minimal/none

**Dockerfile:**
- Update models only
- Change custom nodes

**Handler:**
- Usually no changes needed!

### Pattern 3: Audio-to-Audio

**Changes needed:**
- Input: audio_url
- Output: SaveAudio node
- Handler: Update input/output handling

**Example**: Voice conversion, music generation

### Pattern 4: Multi-Input Workflows

**Example**: Image + Text → Image

**Handler changes:**
```python
if 'image_url' in job_input:
    # Download and inject image

if 'mask_url' in job_input:
    # Download and inject mask

# Text parameters directly in workflow JSON
```

### Pattern 5: Multi-Output Workflows

**Example**: Generate image + mask

**Handler changes:**
```python
# Find all SaveImage nodes
save_image_nodes = []
for node_id, node_data in workflow.items():
    if node_data.get("class_type") == "SaveImage":
        save_image_nodes.append(node_id)

# Collect outputs from all
all_images = []
for node_id in save_image_nodes:
    outputs = history[prompt_id]['outputs'].get(node_id, {}).get('images', [])
    all_images.extend(outputs)
```

---

## Workflow-Specific Tips

### For Stable Diffusion Workflows

**Common models needed:**
- Checkpoint (safetensors)
- VAE (optional)
- LoRAs (optional)
- ControlNet (optional)
- Embeddings (optional)

**Model paths:**
```
models/checkpoints/
models/vae/
models/loras/
models/controlnet/
models/embeddings/
```

### For Upscaling Workflows

**Common models:**
- Upscale model (ESRGAN, RealESRGAN, etc.)
- Optional: refinement checkpoint

**Watch out for:**
- Memory usage (large images)
- Processing time (increases with resolution)

### For Audio Workflows

**Common formats:**
- Input: MP3, WAV, FLAC
- Output: MP3 (configurable bitrate)

**Watch out for:**
- Audio file size limits
- Sample rate compatibility
- Mono vs stereo

### For Video Workflows

**Special considerations:**
- MUCH longer processing times
- Large file sizes
- May need different storage (not R2 for large files)
- Consider frame-by-frame processing

---

## Checklist Template

Use this for any workflow conversion:

### Pre-Conversion
- [ ] Tested workflow locally in ComfyUI
- [ ] Exported as API format
- [ ] Identified all required models
- [ ] Identified all custom nodes
- [ ] Identified Python dependencies
- [ ] Documented input/output types

### Dockerfile Updates
- [ ] Removed old models
- [ ] Removed old custom nodes
- [ ] Created new model directories
- [ ] Added model downloads
- [ ] Added custom node installations
- [ ] Added Python dependencies
- [ ] Added huggingface-hub (if using HF models)

### Handler Updates
- [ ] Updated input download function
- [ ] Updated input parameter name
- [ ] Updated input node detection
- [ ] Updated output node detection
- [ ] Updated Content-Type
- [ ] Updated return format
- [ ] Updated API wrapper (if needed)

### Documentation Updates
- [ ] Created/updated API workflow JSON
- [ ] Updated input.json example
- [ ] Updated response.json example
- [ ] Updated claude.md with new info
- [ ] Documented all parameters

### Testing
- [ ] Built Docker image
- [ ] Checked build logs
- [ ] Deployed to RunPod
- [ ] Tested with sample request
- [ ] Verified output format
- [ ] Tested error handling

---

## Quick Reference

### File Purposes

| File | When to Modify |
|------|----------------|
| `Dockerfile` | Always (models, dependencies) |
| `workflow_api.json` | Always (new workflow) |
| `rp_handler.py` | If input/output type changes |
| `ComfyUI_API_Wrapper.py` | If output key changes |
| `input.json` | Always (example) |
| `response.json` | Always (example) |
| `claude.md` | Always (documentation) |

### Common Node Types

| Purpose | Node Class Type | Output Key |
|---------|----------------|------------|
| Load Image | LoadImage | N/A |
| Load Audio | LoadAudio | N/A |
| Load Video | LoadVideo | N/A |
| Save Image | SaveImage | 'images' |
| Save Audio MP3 | SaveAudioMP3 | 'audio' |
| Save Video | SaveVideo | 'videos' |
| Text Encode | CLIPTextEncode | N/A |

### Docker Commands

```bash
# Build
docker build -t my-workflow .

# Run locally
docker run -it --gpus all -p 8188:8188 my-workflow

# Check size
docker images | grep my-workflow

# Clean up
docker system prune -a
```

### Git Commands

```bash
# Commit changes
git add .
git commit -m "Convert to [workflow name]"
git push

# Create branch for testing
git checkout -b test-new-workflow
```

---

## Troubleshooting Decision Tree

```
Workflow not working?
│
├─ Build failed?
│  ├─ Model download error → Check URLs, disk space
│  ├─ Git clone error → Check repo exists, credentials
│  └─ Pip install error → Check dependency names, versions
│
├─ Request validation failed?
│  ├─ Missing parameters → Check worker logs, add to workflow
│  ├─ Wrong node type → Check class_type spelling
│  └─ Invalid values → Check parameter ranges
│
├─ Execution completed but no output?
│  ├─ Check API wrapper output key
│  ├─ Check handler output node detection
│  └─ Check actual ComfyUI execution logs
│
└─ Execution failed mid-process?
   ├─ Model not found → Check paths, build logs
   ├─ Out of memory → Reduce batch size, model size
   └─ Node error → Check custom node compatibility
```

---

## Summary

Converting workflows requires:

1. **Understanding**: Know what changes (input, output, models)
2. **Research**: Read repos, READMEs, code
3. **Systematic approach**: Follow checklist
4. **Testing**: Build, deploy, test, iterate
5. **Documentation**: Update all docs and examples

**Key insight**: Most conversions follow the same pattern - just swap models, nodes, and adjust input/output handling!

---

**Good luck with your workflow conversions!** 🚀

Remember: Test locally first, read the logs, and ask for help in the ComfyUI/custom node repos if stuck.
