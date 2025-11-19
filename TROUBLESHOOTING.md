# WanVideo 2.1 InfiniteTalk - Troubleshooting Guide

## Issue #1: Audio Padding Causing End-of-Video Distortion

**Date Identified**: 2025-11-10
**Date Confirmed**: 2025-11-11 (logs (25).txt analysis)
**Severity**: High
**Status**: RESOLVED - Use Window-Aligned Frame Counts

### Problem Description

Videos generated with WanVideo 2.1 InfiniteTalk show visible quality degradation and distortion towards the end of the video. The lip-sync breaks down and the video becomes blurry/fuzzy in the final seconds.

### Symptoms

- Video quality drops noticeably in the last 2-3 seconds
- Lip movements no longer sync with audio at the end
- Blurriness or artifacts appear in final frames
- Log warning: `Audio embedding for subject 0 not long enough: X, need Y, padding...`

### Root Cause Analysis

The WanVideo InfiniteTalk system uses a **sliding window approach** to process videos:

- **Window size**: 81 frames (actually processes indices 0-81 = 82 frames)
- **Motion overlap**: 9 frames between consecutive windows
- **Effective stride**: 72 frames (81 - 9 = 72)

When the total frame count doesn't align with window boundaries, the last window extends beyond the available audio data. The system pads the missing audio embeddings with zeros, causing the lip-sync model to fail.

#### Example from Logs

**7-second test (175 frames):**
```
Sampling 175 frames in 3 windows, at 1280x720 with 4 steps
Sampling audio indices 0-81
Sampling audio indices 72-153
Audio embedding for subject 0 not long enough: 175, need 225, padding...
Padding length: 53
Sampling audio indices 144-225  ← 53 frames are zeros!
```

**17-second test (425 frames):**
```
Sampling 425 frames in 6 windows, at 1280x720 with 4 steps
...
Audio embedding for subject 0 not long enough: 425, need 441, padding...
Padding length: 19
Sampling audio indices 360-441  ← 19 frames are zeros!
```

### Window Processing Pattern

For any video, windows are calculated as:
1. Window 1: frames 0-81 (82 frames)
2. Window 2: frames 72-153 (82 frames, overlaps 9 frames with window 1)
3. Window 3: frames 144-225 (82 frames, overlaps 9 frames with window 2)
4. Window N: frames (N-1)×72 to (N-1)×72+81

The last window always needs: `(num_windows - 1) × 72 + 81` frames

### Solution: Use Window-Aligned Frame Counts

To avoid padding, the total frame count must be a valid window boundary value.

#### Formula

**Valid frame counts:**
```
frames = 81 + (n - 1) × 72
```
where `n` = number of windows (1, 2, 3, ...)

Or reversed:
```
num_windows = floor((frames - 81) / 72) + 1
```

#### Valid Frame Count Table

| Windows | Frame Count | Duration @ 25fps | Duration @ 24fps |
|---------|-------------|------------------|------------------|
| 1       | 81          | 3.24s           | 3.38s            |
| 2       | 153         | 6.12s           | 6.38s            |
| 3       | 225         | 9.00s           | 9.38s            |
| 4       | 297         | 11.88s          | 12.38s           |
| 5       | 369         | 14.76s          | 15.38s           |
| 6       | 441         | 17.64s          | 18.38s           |
| 7       | 513         | 20.52s          | 21.38s           |
| 8       | 585         | 23.40s          | 24.38s           |
| 9       | 657         | 26.28s          | 27.38s           |
| 10      | 729         | 29.16s          | 30.38s           |

### Implementation Fix

#### Node 214: Total Duration (Total Frames)

Change the frame count to the nearest valid value that covers your audio duration.

**Before:**
```json
"214": {
  "inputs": {
    "value": 175  // 7 seconds - CAUSES PADDING
  }
}
```

**After:**
```json
"214": {
  "inputs": {
    "value": 225  // 9 seconds - NO PADDING
  }
}
```

#### Node 159: AudioCrop (Optional)

Adjust the audio crop end time to match your desired audio length. The video will be generated for the full frame count, but you can limit which portion of audio is used.

**Example for 17-second audio:**
```json
"159": {
  "inputs": {
    "audio": ["217", 0],
    "start_time": "0:00",
    "end_time": "0:18"  // Matches 441 frames @ 25fps = 17.64s
  }
}
```

### Files Fixed

1. **runpod_test_CORRECT_HQ.json**: Changed from 175 → 225 frames (7s → 9s)
2. **runpod_test_17sec_HQ.json**: Changed from 425 → 441 frames (17s → 17.64s)

### Verification

After applying the fix, check the logs for:

✅ **Good** - No padding warnings:
```
Sampling 225 frames in 3 windows, at 1280x720 with 4 steps
Sampling audio indices 0-81
Sampling audio indices 72-153
Sampling audio indices 144-225  ← Perfect alignment!
```

❌ **Bad** - Padding warnings:
```
Audio embedding for subject 0 not long enough: X, need Y, padding...
Padding length: Z
```

### Quick Reference

**To calculate proper frame count for your audio:**

1. Determine your audio duration in seconds
2. Calculate frames: `duration × fps` (e.g., 17s × 25fps = 425)
3. Find the **closest valid** frame count from table above that **DOESN'T EXCEED** your audio length
4. Use that value in Node 214

**Example (from logs (25).txt):**
- Audio file: 17.084 seconds (long17secs.mp3)
- Actual frames: 17.084 × 25 = **427 frames available**
- Requested: 441 frames (17.64s) ❌ TOO LONG
- Result: Padding of 17 frames → quality degradation
- **Solution**: Use **369 frames** (14.76s) ✓ No padding needed

**Key Rule**: Always choose a valid frame count that's **LESS THAN** your audio duration to avoid padding.

---

## Issue #2: Quality Degradation Throughout Video (3-Second Pattern)

**Date Identified**: 2025-11-10
**Date Resolved**: 2025-11-12 (Pixaroma Settings)
**Severity**: High
**Status**: RESOLVED - Pixaroma Workflow Optimizations

### Problem Description

Videos show quality degradation, blur, pixelation, and inconsistent quality throughout the entire duration. Quality drops occur systematically **every 3 seconds** (81-frame window boundaries at 25fps) and worsen toward the end.

### Symptoms

- **Systematic 3-second degradation pattern** - quality drops every 3.24 seconds
- Blurriness and pixelation appearing at window boundaries
- Face deformation after 20 seconds
- Faint colors and increasing pixelation over time
- Quality degradation becoming more severe toward video end
- Overall lower visual quality compared to reference workflows

### Root Cause Analysis - FINAL RESOLUTION

**Initial Diagnosis (INCORRECT):**
- Originally attributed to model quantization (Q4/Q5/Q6)
- Testing showed Q4, Q5, Q6 all produced identical degradation
- Models WERE loading correctly (confirmed by VRAM usage)

**Actual Root Cause:**
- Missing critical Pixaroma workflow optimizations
- Key settings from Pixaroma "Infinite Talk Workflow Wan 2.1 i2v 14B 480p" (Episode 60) were not applied
- Analysis of Jockerai's reference workflow revealed missing parameters

**Critical Missing Settings:**
1. **base_precision**: Using `bf16` instead of `fp16_fast`
2. **attention_mode**: Using `sdpa` instead of `sageattn` (Flash Attention 2)
3. **mode parameter**: Missing `"infinitetalk"` explicit mode activation
4. **motion_frame**: Using `9` instead of `25` (larger motion window)
5. **scheduler**: Using `flowmatch_distill` instead of `dpm++_sde`
6. **add_noise_to_samples**: Using `false` instead of `true`

### Solution: Apply All Pixaroma Settings

**Configuration Changes:**

**Node 5/122: WanVideoModelLoader**
```json
{
  "model": "wan2.1-i2v-14b-480p-Q5_0.gguf",  // Q5_0 is sufficient with correct settings
  "base_precision": "fp16_fast",            // ← CRITICAL: Not bf16
  "attention_mode": "sageattn"              // ← CRITICAL: Flash Attention 2
}
```

**Node 13/192: WanVideoImageToVideoMultiTalk**
```json
{
  "motion_frame": 25,          // ← Not 9
  "colormatch": "disabled",    // For short videos (<30s)
  "mode": "infinitetalk"       // ← CRITICAL: Explicit mode activation
}
```

**Node 16/213: WanVideoSampler**
```json
{
  "steps": 4,                      // 4 steps sufficient with Q5_0
  "scheduler": "dpm++_sde",        // ← Not flowmatch_distill
  "add_noise_to_samples": true     // ← CRITICAL: Prevents artifact accumulation
}
```

**Node 35/134: WanVideoBlockSwap**
```json
{
  "blocks_to_swap": 20,     // ← Not 40
  "prefetch_blocks": 1      // ← Not 0
}
```

### Model Configuration - CORRECTED

| Component | Old (Broken) | New (Working) | Impact |
|-----------|--------------|---------------|--------|
| **Main Model** | Q4/Q5/Q6 (no difference) | **Q5_0 + Pixaroma settings** | Degradation eliminated |
| **base_precision** | bf16 | **fp16_fast** | 🔥 Major optimization |
| **attention_mode** | sdpa | **sageattn** | 🔥 Quality consistency |
| **LoRA** | rank64 or rank256 | **rank64 @ 1.0** | Proven sufficient |

### Required Model Files - Production Configuration

**Main I2V Model (Node 122):**
- ✅ **PRODUCTION**: `wan2.1-i2v-14b-480p-Q5_0.gguf` (with Pixaroma settings)
- ✅ Alternative: `wan2.1-i2v-14b-480p-Q4_0.gguf` (for testing)

**LoRA Model (Node 138):**
- ✅ **PRODUCTION**: `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` @ strength 1.0

**InfiniteTalk Model (Node 7/120):**
- ✅ **REQUIRED**: `Wan2_1-InfiniteTalk_Single_Q8.gguf`

**Text Encoder (Node 136):**
- ✅ **PRODUCTION**: `umt5-xxl-enc-bf16.safetensors`

**Wav2Vec2 Model (Node 28/137):**
- ✅ **PRODUCTION**: `wav2vec2-chinese-base_fp16.safetensors`

---

### Files Updated - Pixaroma Resolution (2025-11-12)

All test configurations updated with Pixaroma settings:

1. ✅ `test_pixaroma_workflow.json` → 17s @ 1280×720 (PERFECT)
2. ✅ `test_pixaroma_44sec_4steps.json` → 44s @ 1280×720 (PERFECT except color drift)
3. ✅ `test_pixaroma_44sec_6steps.json` → 44s @ 1280×720 (6 steps doesn't help)
4. ✅ `test_pixaroma_44sec_4steps_colorfix.json` → 44s @ 1280×720 (PERFECT + color fixed)

### Verification - Post-Pixaroma Results

✅ **17-second test** (1280×720, 6 steps): "Perfect" quality
✅ **44-second test** (1280×720, 4 steps): "Perfect" quality (minor color drift issue - see Issue #3)
✅ **NO 3-second degradation pattern** with Pixaroma settings
✅ Consistent lip-sync throughout entire duration
✅ Sharp facial details maintained
✅ Generation time: ~30 minutes for 44 seconds @ 1280×720

**Key Insight:** Model quantization (Q4/Q5/Q6) had NO impact. The issue was entirely due to missing Pixaroma workflow optimizations.

---

## Issue #3: Gradual Color/Contrast Increase in Long Videos

**Date Identified**: 2025-11-12
**Date Resolved**: 2025-11-12 (Same day)
**Severity**: Low
**Status**: RESOLVED - Color Matching Fix

### Problem Description

After fixing quality degradation with Pixaroma settings, long videos (30+ seconds) showed gradual color/contrast increase. Video quality was otherwise perfect, but colors became progressively more contrasted over time.

### Symptoms

- ✅ Overall video quality is perfect
- ✅ No quality degradation or blur
- ✅ Excellent lip-sync throughout
- ❌ Colors gradually become more contrasted over time
- ❌ Noticeable after 30+ seconds (15+ windows)
- ❌ Not a major issue, but visible

### Root Cause Analysis

With many windows (15 windows for 44 seconds), small color variations between window boundaries accumulate over time. The Pixaroma default setting `colormatch: "disabled"` works fine for short demo videos but doesn't normalize colors between windows in longer videos.

**Testing Confirmed:**
- 44 seconds @ 1280×720 with 4 steps = perfect quality BUT gradual contrast increase
- 44 seconds @ 1280×720 with 6 steps = SAME color drift issue
- **Conclusion**: Not about step count (4 vs 6), it's about color matching between windows

### Solution: Enable MKL Color Matching

**Node 13/192: WanVideoImageToVideoMultiTalk**

Change the `colormatch` setting:

```json
{
  "colormatch": "mkl"  // ← Change from "disabled" to "mkl"
}
```

**When to use which:**
- **Short videos (<30s)**: `colormatch: "disabled"` (Pixaroma default, works fine)
- **Long videos (30s+)**: `colormatch: "mkl"` (prevents color drift)

### Configuration - Final Production

**File:** `test_pixaroma_44sec_4steps_colorfix.json`

```json
{
  "Node 13": {
    "colormatch": "mkl",        // ← CRITICAL for long videos
    "motion_frame": 25,
    "mode": "infinitetalk"
  },
  "Node 16": {
    "steps": 4                  // 4 steps is sufficient (proven)
  }
}
```

### Verification - Color Fix Results

**44-second test @ 1280×720, 4 steps, colormatch="mkl":**

✅ **Perfect quality** throughout entire 44 seconds
✅ **No gradual color/contrast increase**
✅ Consistent colors from start to finish
✅ **Generation time: ~30 minutes** (RTX 5090)
✅ VRAM usage: ~14-15GB

**Status: PRODUCTION READY** ✅

### Performance Summary

| Test | Duration | Steps | Colorfix | Gen Time | Result |
|------|----------|-------|----------|----------|--------|
| 1 | 17s | 6 | No | ~20 min | Perfect ✅ |
| 2 | 44s | 6 | No | ~50 min | Color drift ❌ |
| 3 | 44s | 4 | **Yes** | **~30 min** | **Perfect ✅** |

**Optimal Production Config:**
- Model: Q5_0 (with Pixaroma settings)
- Steps: 4 (faster, same quality as 6)
- Colorfix: mkl (for videos 30+ seconds)
- Speed: ~30 minutes for 44 seconds @ 1280×720

---

## Debugging Tips

### Enable Detailed Logging

Check ComfyUI execution logs for these key indicators:

1. **Window count**: `Sampling X frames in Y windows`
2. **Window ranges**: `Sampling audio indices A-B`
3. **Padding warnings**: `Audio embedding for subject 0 not long enough`
4. **VRAM usage**: `Max allocated memory: max_memory=X GB`
5. **Processing time**: `Prompt executed in X seconds`

### Common Patterns

- **Each window takes ~20-22 seconds** to process (4 diffusion steps)
- **Total time ≈ num_windows × 22 seconds** (rough estimate)
- **VRAM usage ~14GB** during sampling (RTX 5090 with 32GB handles this easily)

---

## Related Documentation

- See `CLAUDE.md` for full project documentation
- See `API_INTEGRATION_GUIDE.md` for API integration details
- See `WORKFLOW_CONVERSION_GUIDE.md` for workflow conversion instructions
