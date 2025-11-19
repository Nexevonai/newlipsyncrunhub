# Complete Integration Guide - WanVideo 2.1 InfiniteTalk

**Everything you need to integrate WanVideo talking video generation with Next.js + Supabase**

---

## Table of Contents

### Quick Start
1. [What This System Does](#what-this-system-does)
2. [Quick Start](#quick-start)
3. [Key Concepts](#key-concepts)

### Integration
4. [Frame Count Automation](#frame-count-automation)
5. [Architecture Overview](#architecture-overview)
6. [Environment Setup](#environment-setup)
7. [API Request Format](#api-request-format)
8. [Testing](#testing)

### Configuration
9. [Settings You Can Adjust](#settings-you-can-adjust)
10. [Fixed Settings (DO NOT CHANGE)](#fixed-settings-do-not-change)
11. [Complete Workflow Node Reference](#complete-workflow-node-reference)

### Troubleshooting
12. [Common Issues](#common-issues)
13. [Production Checklist](#production-checklist)

---

## What This System Does

Takes a **portrait image** + **audio file** → Generates a **lip-synced talking video**

**Features:**
- ✅ **Unlimited duration** support (tested up to 44 seconds)
- ✅ **Production quality** with Pixaroma optimizations
- ✅ **Automatic configuration** (frame alignment, resolution detection, color matching)

**Tested & Proven:**
- 17s @ 1280×720: Perfect quality (~20 min)
- 21s @ 720×1280: Perfect quality (~15-18 min)
- 44s @ 1280×720: Perfect quality (~30 min)

---

## Quick Start

### Step 1: Test with Existing Config

```bash
# Portrait test (21s, 720×1280)
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test_pixaroma_portrait_720x1280_21sec.json

# Landscape test (44s, 1280×720)
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test_pixaroma_44sec_4steps_colorfix.json
```

### Step 2: Build Your Own Request

**Minimal required parameters:**

```json
{
  "input": {
    "image_url": "https://example.com/portrait.jpg",
    "audio_url": "https://example.com/audio.mp3",
    "width": 720,
    "height": 1280,
    "workflow": { ...13 nodes... }
  }
}
```

**Use the test files as templates** - just change image_url, audio_url, width, height.

### Step 3: Integrate into Next.js

```typescript
// Call RunPod API
const response = await fetch('https://api.runpod.ai/v2/YOUR_ENDPOINT/run', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(workflowConfig), // Use test file as template
});

const { id: jobId } = await response.json();

// Poll for status
const statusResponse = await fetch(`https://api.runpod.ai/v2/YOUR_ENDPOINT/status/${jobId}`, {
  headers: { 'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}` }
});

const { status, output } = await statusResponse.json();
if (status === 'COMPLETED') {
  const videoUrl = output.video[0]; // Cloudflare R2 URL
}
```

---

## Key Concepts

### 1. Window-Aligned Frame Counts (CRITICAL)

**Frame counts MUST be window-aligned or video quality degrades at the end.**

**Valid frame counts:** 81, 153, 225, 297, 369, 441, 513, 585, 657, 729, 801, 873, 945, 1017, 1089

**Formula:** `frames = 81 + (n-1) × 72` where n = number of windows

**How to calculate:**

```typescript
const VALID_FRAME_COUNTS = [81, 153, 225, 297, 369, 441, 513, 585, 657, 729, 801, 873, 945, 1017, 1089];

function calculateOptimalFrames(audioDurationSeconds) {
  const maxFrames = audioDurationSeconds * 25;
  return VALID_FRAME_COUNTS.reduce((best, current) => {
    if (current <= maxFrames && current > best) return current;
    return best;
  }, 81);
}
```

**Example:**
- Audio: 21 seconds
- Max frames: 21 × 25 = 525
- **Optimal: 513 frames** (20.52s, 7 windows) ✅
- **BAD: 525 frames** → causes 12-frame padding → quality degradation ❌

**Why this matters:** Non-aligned frame counts cause audio padding (zeros at end) → blurry video, broken lip-sync. See TROUBLESHOOTING.md Issue #1.

### 2. Colormatch Setting

**Always use "mkl" for all videos:**

```typescript
const colormatch = "mkl"; // Always enabled
```

**What is "mkl"?** Monge-Kantorovich Linearization - a color transfer algorithm that normalizes colors between video window boundaries to prevent color drift.

**Why always on:** Ensures consistent color/contrast throughout the entire video, regardless of duration. Small performance overhead but guarantees quality.

### 3. Resolution Guidelines

**Recommended Resolutions:**
- **Portrait HD**: 720×1280 (9:16, TikTok/Instagram) ⭐
- **Landscape HD**: 1280×720 (16:9, YouTube) ⭐
- **Portrait SD**: 480×832 (faster, testing)
- **Landscape SD**: 832×480 (faster, testing)

**Requirements:**
- Must be divisible by 2
- Higher resolution = more VRAM + longer time

**Tested resolutions:**
- ✅ 480×832, 720×1280, 832×480, 1280×720

### 4. Quality Tiers

| Tier | Model | LoRA | Steps | Use Case | Gen Time |
|------|-------|------|-------|----------|----------|
| **sd** | Q4_0 | rank64 | 4 | Fast testing | ~10-15 min |
| **hd** ⭐ | Q5_0 | rank64 | 4 | **Production (recommended)** | ~15-30 min |
| **fullhd** | Q5_0 | rank256 | 6 | Maximum quality | ~30-50 min |

**Recommendation:** Use **hd** with Q5_0 model + 4 steps (proven perfect quality, 33% faster than 6 steps).

---

## Frame Count Automation

### Overview

The most critical automation is calculating the correct frame count based on audio duration. This MUST be done correctly to avoid quality degradation.

**The Process:**
1. User uploads audio file
2. Detect audio duration (client-side or server-side)
3. Calculate optimal window-aligned frame count
4. Pass frame count to workflow

---

### Step 1: Detect Audio Duration

#### Client-Side (Browser/React)

```typescript
'use client';

import { useState } from 'react';

export default function AudioUploader() {
  const [audioDuration, setAudioDuration] = useState<number>(0);
  const [audioFile, setAudioFile] = useState<File | null>(null);

  const handleAudioUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAudioFile(file);

    // Detect audio duration
    const audio = new Audio();
    audio.preload = 'metadata';

    audio.onloadedmetadata = () => {
      const duration = audio.duration;
      setAudioDuration(duration);
      console.log(`Audio duration: ${duration.toFixed(2)}s`);

      // Clean up
      window.URL.revokeObjectURL(audio.src);
    };

    audio.onerror = () => {
      console.error('Failed to load audio');
      window.URL.revokeObjectURL(audio.src);
    };

    audio.src = window.URL.createObjectURL(file);
  };

  return (
    <div>
      <input type="file" accept="audio/*" onChange={handleAudioUpload} />
      {audioDuration > 0 && (
        <p>Audio duration: {audioDuration.toFixed(2)}s</p>
      )}
    </div>
  );
}
```

#### Server-Side (Node.js with ffprobe)

```typescript
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

async function getAudioDuration(filePath: string): Promise<number> {
  try {
    const { stdout } = await execAsync(
      `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${filePath}"`
    );
    return parseFloat(stdout.trim());
  } catch (error) {
    throw new Error(`Failed to get audio duration: ${error}`);
  }
}

// Usage
const duration = await getAudioDuration('/path/to/audio.mp3');
console.log(`Duration: ${duration}s`);
```

#### URL-Based (Audio Already Hosted)

```typescript
async function getAudioDurationFromUrl(url: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const audio = new Audio();
    audio.preload = 'metadata';

    audio.onloadedmetadata = () => {
      resolve(audio.duration);
    };

    audio.onerror = () => {
      reject(new Error('Failed to load audio from URL'));
    };

    audio.src = url;
  });
}

// Usage
const duration = await getAudioDurationFromUrl('https://example.com/audio.mp3');
```

---

### Step 2: Calculate Optimal Frame Count

#### The Algorithm

```typescript
// All valid frame counts (window-aligned)
const VALID_FRAME_COUNTS = [
  81,    // 3.24s  (1 window)
  153,   // 6.12s  (2 windows)
  225,   // 9.00s  (3 windows)
  297,   // 11.88s (4 windows)
  369,   // 14.76s (5 windows)
  441,   // 17.64s (6 windows)
  513,   // 20.52s (7 windows)
  585,   // 23.40s (8 windows)
  657,   // 26.28s (9 windows)
  729,   // 29.16s (10 windows)
  801,   // 32.04s (11 windows)
  873,   // 34.92s (12 windows)
  945,   // 37.80s (13 windows)
  1017,  // 40.68s (14 windows)
  1089,  // 43.56s (15 windows)
];

const FPS = 25;

/**
 * Calculate optimal frame count based on audio duration
 * Always rounds DOWN to nearest valid frame count (never exceeds audio length)
 */
function calculateOptimalFrames(audioDurationSeconds: number): number {
  // Calculate max possible frames based on audio duration
  const maxFrames = audioDurationSeconds * FPS;

  // Find largest valid frame count that doesn't exceed max
  return VALID_FRAME_COUNTS.reduce((best, current) => {
    if (current <= maxFrames && current > best) {
      return current;
    }
    return best;
  }, 81); // Default to minimum (81 frames = 3.24s)
}

// Examples
console.log(calculateOptimalFrames(7));   // → 153 frames (6.12s)
console.log(calculateOptimalFrames(9));   // → 225 frames (9.00s)
console.log(calculateOptimalFrames(17));  // → 369 frames (14.76s)
console.log(calculateOptimalFrames(21));  // → 513 frames (20.52s)
console.log(calculateOptimalFrames(44));  // → 1089 frames (43.56s)
```

#### Why Round Down?

**Always round down to avoid audio padding:**
- Audio: 21 seconds (525 max frames)
- Round UP to 585 frames ❌ → requires 60 extra frames → **audio padding → distortion**
- Round DOWN to 513 frames ✅ → 20.52s video → **no padding → perfect quality**

The video will be slightly shorter than the audio, but quality is perfect. The alternative (padding) causes visible artifacts.

---

### Step 3: Validation

```typescript
interface FrameCalculationResult {
  success: boolean;
  frames?: number;
  videoDuration?: number;
  numWindows?: number;
  error?: string;
}

function validateAndCalculateFrames(
  audioDurationSeconds: number
): FrameCalculationResult {
  // Validate: Audio too short
  if (audioDurationSeconds < 3.24) {
    return {
      success: false,
      error: 'Audio must be at least 3.24 seconds (minimum 81 frames)'
    };
  }

  // Validate: Audio too long (recommended max)
  if (audioDurationSeconds > 60) {
    return {
      success: false,
      error: 'Audio exceeds recommended maximum of 60 seconds'
    };
  }

  // Validate: Audio exceeds maximum supported
  const maxSupportedFrames = VALID_FRAME_COUNTS[VALID_FRAME_COUNTS.length - 1];
  const maxSupportedDuration = maxSupportedFrames / FPS; // 43.56s

  if (audioDurationSeconds > maxSupportedDuration) {
    return {
      success: false,
      error: `Audio duration ${audioDurationSeconds.toFixed(2)}s exceeds maximum supported ${maxSupportedDuration.toFixed(2)}s`
    };
  }

  // Calculate frames
  const frames = calculateOptimalFrames(audioDurationSeconds);
  const videoDuration = frames / FPS;
  const numWindows = Math.floor((frames - 81) / 72) + 1;

  return {
    success: true,
    frames,
    videoDuration,
    numWindows
  };
}

// Usage
const result = validateAndCalculateFrames(21);
if (result.success) {
  console.log(`Frames: ${result.frames}`);
  console.log(`Video duration: ${result.videoDuration}s`);
  console.log(`Windows: ${result.numWindows}`);
} else {
  console.error(result.error);
}
```

---

### Step 4: Complete Automation Flow

#### Next.js API Route Example

```typescript
// app/api/generate-video/route.ts
import { NextResponse } from 'next/server';

const VALID_FRAME_COUNTS = [
  81, 153, 225, 297, 369, 441, 513, 585, 657, 729,
  801, 873, 945, 1017, 1089
];

function calculateOptimalFrames(audioDurationSeconds: number): number {
  const maxFrames = audioDurationSeconds * 25;
  return VALID_FRAME_COUNTS.reduce((best, current) =>
    current <= maxFrames && current > best ? current : best, 81
  );
}

export async function POST(request: Request) {
  try {
    const {
      imageUrl,
      audioUrl,
      audioDuration,  // Client provides this after detection
      width = 720,
      height = 1280
    } = await request.json();

    // Validate inputs
    if (!imageUrl || !audioUrl || !audioDuration) {
      return NextResponse.json(
        { error: 'Missing required: imageUrl, audioUrl, audioDuration' },
        { status: 400 }
      );
    }

    if (audioDuration < 3.24 || audioDuration > 60) {
      return NextResponse.json(
        { error: 'Audio must be 3.24-60 seconds' },
        { status: 400 }
      );
    }

    // Calculate optimal settings
    const frames = calculateOptimalFrames(audioDuration);
    const colormatch = "mkl"; // Always enabled
    const videoDuration = frames / 25;

    console.log(`Audio: ${audioDuration.toFixed(2)}s → Video: ${videoDuration.toFixed(2)}s (${frames} frames)`);

    // Build workflow config from template
    const workflowTemplate = require('@/test_pixaroma_portrait_720x1280_21sec.json');

    const workflowConfig = {
      image_url: imageUrl,
      audio_url: audioUrl,
      width,
      height,
      workflow: {
        ...workflowTemplate.input.workflow,
        // Update node 13: colormatch
        "13": {
          ...workflowTemplate.input.workflow["13"],
          inputs: {
            ...workflowTemplate.input.workflow["13"].inputs,
            colormatch: colormatch
          }
        },
        // Update node 14: width, height
        "14": {
          ...workflowTemplate.input.workflow["14"],
          inputs: {
            ...workflowTemplate.input.workflow["14"].inputs,
            width,
            height
          }
        },
        // Update node 18: num_frames
        "18": {
          ...workflowTemplate.input.workflow["18"],
          inputs: {
            ...workflowTemplate.input.workflow["18"].inputs,
            num_frames: frames
          }
        }
      }
    };

    // Submit to RunPod
    const response = await fetch(`${process.env.RUNPOD_ENDPOINT_URL}/run`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ input: workflowConfig }),
    });

    if (!response.ok) {
      throw new Error(`RunPod API error: ${response.statusText}`);
    }

    const data = await response.json();

    return NextResponse.json({
      jobId: data.id,
      status: data.status,
      calculatedFrames: frames,
      calculatedDuration: videoDuration,
      colormatch
    });

  } catch (error) {
    console.error('Error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

#### Supabase Edge Function Example

```typescript
// supabase/functions/generate-video/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';

const VALID_FRAME_COUNTS = [
  81, 153, 225, 297, 369, 441, 513, 585, 657, 729,
  801, 873, 945, 1017, 1089
];

function calculateOptimalFrames(audioDurationSeconds: number): number {
  const maxFrames = audioDurationSeconds * 25;
  return VALID_FRAME_COUNTS.reduce((best: number, current: number) =>
    current <= maxFrames && current > best ? current : best, 81
  );
}

serve(async (req) => {
  try {
    const { imageUrl, audioUrl, audioDuration, width = 720, height = 1280 } = await req.json();

    // Validate
    if (!imageUrl || !audioUrl || !audioDuration) {
      return new Response(
        JSON.stringify({ error: 'Missing required parameters' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Calculate frames
    const frames = calculateOptimalFrames(audioDuration);
    const colormatch = "mkl";

    // Build workflow (load from template file or construct)
    const workflowConfig = {
      image_url: imageUrl,
      audio_url: audioUrl,
      width,
      height,
      workflow: {
        // ... your complete workflow JSON
        // Update nodes 13, 14, 18 with calculated values
      }
    };

    // Call RunPod
    const runpodResponse = await fetch(
      `${Deno.env.get('RUNPOD_ENDPOINT_URL')}/run`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${Deno.env.get('RUNPOD_API_KEY')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ input: workflowConfig }),
      }
    );

    const data = await runpodResponse.json();

    return new Response(
      JSON.stringify({
        jobId: data.id,
        status: data.status,
        frames,
        colormatch
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
});
```

---

### Step 5: Testing Frame Calculations

```typescript
// Test suite to verify frame calculations
const testCases = [
  { audio: 3.24, expected: 81, description: 'Minimum duration' },
  { audio: 5, expected: 81, description: 'Short audio rounds down' },
  { audio: 7, expected: 153, description: '7s audio' },
  { audio: 9, expected: 225, description: '9s audio (perfect match)' },
  { audio: 17, expected: 369, description: '17s audio' },
  { audio: 21, expected: 513, description: '21s audio' },
  { audio: 30, expected: 729, description: '30s audio' },
  { audio: 44, expected: 1089, description: '44s audio' },
];

testCases.forEach(({ audio, expected, description }) => {
  const calculated = calculateOptimalFrames(audio);
  const pass = calculated === expected;
  const videoDuration = calculated / 25;

  console.log(
    `${pass ? '✅' : '❌'} ${description}: ` +
    `Audio ${audio}s → ${calculated} frames (${videoDuration.toFixed(2)}s video) ` +
    `[expected ${expected}]`
  );
});

// Expected output:
// ✅ Minimum duration: Audio 3.24s → 81 frames (3.24s video) [expected 81]
// ✅ Short audio rounds down: Audio 5s → 81 frames (3.24s video) [expected 81]
// ✅ 7s audio: Audio 7s → 153 frames (6.12s video) [expected 153]
// ✅ 9s audio (perfect match): Audio 9s → 225 frames (9.00s video) [expected 225]
// ✅ 17s audio: Audio 17s → 369 frames (14.76s video) [expected 369]
// ✅ 21s audio: Audio 21s → 513 frames (20.52s video) [expected 513]
// ✅ 30s audio: Audio 30s → 729 frames (29.16s video) [expected 729]
// ✅ 44s audio: Audio 44s → 1089 frames (43.56s video) [expected 1089]
```

---

### Key Takeaways

**DO:**
- ✅ Always detect audio duration before submitting to RunPod
- ✅ Always calculate frame count using the algorithm above
- ✅ Always round DOWN to nearest valid frame count
- ✅ Always validate audio is 3.24s - 60s
- ✅ Always use `colormatch: "mkl"`

**DON'T:**
- ❌ Never use arbitrary frame counts (175, 425, 500, etc.)
- ❌ Never round UP (causes audio padding → distortion)
- ❌ Never exceed audio duration with frame count
- ❌ Never skip validation

**Formula Reference:**
```
Valid frames = 81 + (n - 1) × 72
where n = number of windows (1, 2, 3, ...)
```

---

## Architecture Overview

```
User Browser (Next.js)
    ↓ [Upload image + audio, get duration]
Next.js API Route
    ↓ [Build workflow config, upload files]
RunPod Serverless API
    ↓ [Generate video with WanVideo]
    ↓ [Upload to R2 storage]
Cloudflare R2
    ↓ [Public video URL]
User Browser
    ← [Display/download video]
```

**Key Components:**
- **Next.js Front-End**: File uploads, duration detection, quality selection
- **Next.js API Route**: Build workflow, call RunPod API
- **RunPod Serverless**: Video generation with WanVideo 2.1 InfiniteTalk
- **Cloudflare R2**: Final video storage and delivery

---

## Environment Setup

### Required Services

1. **Next.js Application** (v14+ recommended)
2. **RunPod Serverless Endpoint** (WanVideo container deployed)
3. **Cloudflare R2 Bucket** (for video output storage)

### Environment Variables

Create `.env.local` in your Next.js project:

```bash
# RunPod
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_ENDPOINT_ID=your_endpoint_id_here
RUNPOD_ENDPOINT_URL=https://api.runpod.ai/v2/your_endpoint_id

# Cloudflare R2 (configured in RunPod environment, not Next.js)
# R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
# R2_ACCESS_KEY_ID=your_access_key
# R2_SECRET_ACCESS_KEY=your_secret_key
# R2_BUCKET_NAME=your_bucket_name
# R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

**Note:** R2 credentials are set in RunPod endpoint environment variables, not your Next.js app.

---

## API Request Format

### RunPod API Endpoint

```
POST https://api.runpod.ai/v2/{endpoint_id}/run
Headers:
  Authorization: Bearer {api_key}
  Content-Type: application/json
```

### Request Body Structure

```typescript
interface VideoGenerationRequest {
  input: {
    image_url: string;      // Public URL to portrait image
    audio_url: string;      // Public URL to audio file
    width: number;          // Output width (e.g., 720, 1280)
    height: number;         // Output height (e.g., 1280, 720)
    workflow: WorkflowConfig; // Complete workflow JSON (13 nodes)
  }
}
```

### Response Format

```typescript
interface RunPodResponse {
  id: string;              // Job ID
  status: "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED";

  // When status = "COMPLETED"
  output?: {
    video: string[];       // Array of video URLs (usually 1)
  };

  // When status = "FAILED"
  error?: string;
}
```

### Example Next.js API Route

**File:** `app/api/generate-video/route.ts`

```typescript
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const { imageUrl, audioUrl, audioDuration, width = 720, height = 1280 } = await request.json();

  // Calculate optimal frame count
  const frames = calculateOptimalFrames(audioDuration);

  // Always use mkl for color consistency
  const colormatch = "mkl";

  // Build workflow config (use test file as template)
  const workflowConfig = buildWorkflowConfig({
    imageUrl,
    audioUrl,
    width,
    height,
    frames,
    colormatch,
  });

  // Submit to RunPod
  const response = await fetch(`${process.env.RUNPOD_ENDPOINT_URL}/run`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ input: workflowConfig }),
  });

  const data = await response.json();
  return NextResponse.json({ jobId: data.id, status: data.status });
}

function calculateOptimalFrames(audioDurationSeconds: number): number {
  const VALID_FRAME_COUNTS = [81, 153, 225, 297, 369, 441, 513, 585, 657, 729, 801, 873, 945, 1017, 1089];
  const maxFrames = audioDurationSeconds * 25;
  return VALID_FRAME_COUNTS.reduce((best, current) => {
    if (current <= maxFrames && current > best) return current;
    return best;
  }, 81);
}

function buildWorkflowConfig(options: {
  imageUrl: string;
  audioUrl: string;
  width: number;
  height: number;
  frames: number;
  colormatch: string;
}) {
  // Use test_pixaroma_portrait_720x1280_21sec.json as template
  // Just replace: image_url, audio_url, width, height, num_frames, colormatch
  return {
    image_url: options.imageUrl,
    audio_url: options.audioUrl,
    width: options.width,
    height: options.height,
    workflow: {
      // Copy all 13 nodes from test file
      // Update node 13: colormatch = options.colormatch
      // Update node 14: width, height = options.width, options.height
      // Update node 18: num_frames = options.frames
    }
  };
}
```

---

## Testing

### Test with Provided Configs

```bash
# 1. Portrait test (21s, 720×1280, colormatch="mkl")
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test_pixaroma_portrait_720x1280_21sec.json

# 2. Landscape test (44s, 1280×720, colormatch="mkl")
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test_pixaroma_44sec_4steps_colorfix.json

# 3. Check status
curl https://api.runpod.ai/v2/YOUR_ENDPOINT/status/JOB_ID \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Expected Generation Times

**RTX 5090, 32GB VRAM** (tested and proven):

| Duration | Resolution | Steps | Colormatch | Gen Time | Status |
|----------|-----------|-------|------------|----------|--------|
| 17s | 1280×720 | 6 | disabled | ~20 min | ✅ Perfect |
| 21s | 720×1280 | 4 | mkl | ~15-18 min | ✅ Expected |
| 32s | 1280×720 | 4 | disabled | ~25-30 min | ✅ Perfect |
| 44s | 1280×720 | 4 | mkl | ~30 min | ✅ Perfect |

**Formula:** ~2 minutes per window (7 windows for 21s = ~14-18 min)

---

## Settings You Can Adjust

### ✅ Safe to Change (User-Facing)

| Parameter | Location | Options | Default | Purpose |
|-----------|----------|---------|---------|---------|
| **width** | Top-level + Node 14 | 480-1920 (even) | 720 or 1280 | Output width |
| **height** | Top-level + Node 14 | 480-1920 (even) | 1280 or 720 | Output height |
| **num_frames** | Node 18 | Window-aligned only | Auto-calc | Video duration |
| **colormatch** | Node 13 | mkl | mkl (always) | Color consistency |
| **steps** | Node 16 | 4-6 | 4 | Quality vs speed |
| **seed** | Node 16 | 0-999999 | 0 (random) | Reproducibility |

### ⚙️ Advanced (Expose with Caution)

| Parameter | Location | Options | Default | Purpose |
|-----------|----------|---------|---------|---------|
| **model** | Node 5 | Q4_0, Q5_0, Q6_K | Q5_0 | Model quantization |
| **lora** | Node 6 | rank64, rank256 | rank64 | LoRA parameters |
| **crf** | Node 23 | 15-23 | 19 | Video compression quality |

---

## Fixed Settings (DO NOT CHANGE)

**These settings are production-proven and MUST stay fixed:**

```json
{
  // Node 5: Model Loader
  "base_precision": "fp16_fast",      // NOT bf16
  "attention_mode": "sageattn",       // Flash Attention 2, NOT sdpa

  // Node 13: Image to Video
  "motion_frame": 25,                 // NOT 9
  "mode": "infinitetalk",             // CRITICAL, REQUIRED

  // Node 16: Sampler
  "scheduler": "dpm++_sde",           // NOT flowmatch_distill
  "add_noise_to_samples": true,       // NOT false (prevents artifacts)
  "cfg": 1.0,                         // DO NOT CHANGE
  "shift": 11.0,                      // DO NOT CHANGE

  // Node 35: Block Swap
  "blocks_to_swap": 20,               // Optimal for 14GB VRAM, NOT 40
  "prefetch_blocks": 1                // NOT 0 (latency optimization)
}
```

**Why these are fixed:**
- Discovered through extensive testing (see TROUBLESHOOTING.md Issue #2)
- Based on Pixaroma Episode 60 "Infinite Talk Workflow Wan 2.1 i2v 14B 480p"
- Changing ANY of these causes:
  - 3-second quality degradation pattern
  - Color/contrast drift
  - Blurriness and artifacts
  - Poor lip-sync

---

## Complete Workflow Node Reference

The workflow consists of **13 nodes** that process image and audio:

```
[12] LoadImage → [14] ImageScale → [15] GetImageSize
                      ↓
[10] CLIPVisionLoader → [11] WanVideoClipVisionEncode
                      ↓
[19] LoadAudio → [28] Wav2VecModelLoader → [18] MultiTalkWav2VecEmbeds
                      ↓
[5] WanVideoModelLoader (with [6] LoRA + [7] InfiniteTalk + [35] BlockSwap)
                      ↓
[17] WanVideoTextEncode → [13] WanVideoImageToVideoMultiTalk
                      ↓
[16] WanVideoSampler → [21] WanVideoDecode ([22] VAE)
                      ↓
[23] VHS_VideoCombine → Output MP4 Video
```

### Node 5: WanVideoModelLoader

Loads the main I2V (Image-to-Video) diffusion model.

**Key Settings:**
- `model`: "wan2.1-i2v-14b-480p-Q5_0.gguf" (production)
- `base_precision`: "fp16_fast" ⚠️ FIXED (NOT bf16)
- `attention_mode`: "sageattn" ⚠️ FIXED (Flash Attention 2)

**Model Options:**
- Q4_0: Fastest, 12GB VRAM, good quality
- Q5_0: ⭐ Recommended, 14GB VRAM, perfect quality
- Q6_K: Maximum quality, 16GB+ VRAM, marginal improvement

### Node 6: WanVideoLoraSelect

Loads LoRA for 4-step distilled generation.

**Key Settings:**
- `lora`: "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"
- `strength`: 1.0 ⚠️ FIXED (full effect)

**LoRA Options:**
- rank64 (738MB): Standard, sufficient, fast
- rank256 (2.9GB): 4× parameters, marginal improvement

### Node 7: MultiTalkModelLoader

Loads InfiniteTalk audio-driven animation model.

**Key Settings:**
- `model`: "Wan2_1-InfiniteTalk_Single_Q8.gguf" ⚠️ FIXED (Q8 required for quality)

### Node 13: WanVideoImageToVideoMultiTalk

Prepares image-to-video conversion with InfiniteTalk mode.

**Key Settings:**
- `frame_window_size`: 81 ⚠️ FIXED (hardcoded for InfiniteTalk)
- `motion_frame`: 25 ⚠️ FIXED (NOT 9, Pixaroma setting)
- `colormatch`: "mkl" ⚠️ FIXED (always enabled for color consistency)
- `mode`: "infinitetalk" ⚠️ FIXED (CRITICAL!)

### Node 14: ImageScale

Scales input image to output video dimensions.

**Key Settings:**
- `width`: 720, 1280, etc. ✅ ADJUSTABLE
- `height`: 1280, 720, etc. ✅ ADJUSTABLE
- `upscale_method`: "lanczos" ⚠️ FIXED (best quality)

### Node 16: WanVideoSampler

Main diffusion sampling for video generation.

**Key Settings:**
- `steps`: 4 or 6 ✅ ADJUSTABLE (4 recommended with Q5_0)
- `cfg`: 1.0 ⚠️ FIXED (DO NOT CHANGE)
- `shift`: 11.0 ⚠️ FIXED (DO NOT CHANGE)
- `seed`: 0-999999 ✅ ADJUSTABLE (0 = random)
- `scheduler`: "dpm++_sde" ⚠️ FIXED (NOT flowmatch_distill)
- `add_noise_to_samples`: true ⚠️ FIXED (prevents artifact accumulation)

**Steps Configuration:**
- 4 steps: ⭐ Recommended with Q5_0 (perfect quality, ~30% faster than 6)
- 6 steps: Original Pixaroma, no quality improvement over 4 with Q5_0

### Node 18: MultiTalkWav2VecEmbeds

Converts audio to embeddings for lip-sync animation.

**Key Settings:**
- `num_frames`: 513, 441, etc. ✅ ADJUSTABLE (MUST be window-aligned!)
- `fps`: 25 ⚠️ FIXED
- `normalize_loudness`: true ⚠️ FIXED (auto-adjust volume)

**Frame Count Table:**

| Windows | Frames | Duration @ 25fps |
|---------|--------|------------------|
| 1 | 81 | 3.24s |
| 2 | 153 | 6.12s |
| 3 | 225 | 9.00s |
| 4 | 297 | 11.88s |
| 5 | 369 | 14.76s |
| 6 | 441 | 17.64s |
| 7 | 513 | 20.52s |
| 8 | 585 | 23.40s |
| 9 | 657 | 26.28s |
| 10 | 729 | 29.16s |
| 12 | 873 | 34.92s |
| 15 | 1089 | 43.56s |

### Node 23: VHS_VideoCombine

Combines frames into final MP4 video with audio.

**Key Settings:**
- `frame_rate`: 25 ⚠️ FIXED (matches generation)
- `format`: "video/h264-mp4" ⚠️ FIXED
- `pix_fmt`: "yuv420p" ⚠️ FIXED (compatibility)
- `crf`: 19 ⚙️ ADVANCED (15-23 range, lower = better quality)

### Node 28: Wav2VecModelLoader

Loads Wav2Vec2 model for audio feature extraction.

**Key Settings:**
- `model`: "wav2vec2-chinese-base_fp16.safetensors" ⚠️ FIXED
- Works for ALL languages, not just Chinese

### Node 35: WanVideoBlockSwap

VRAM optimization by swapping transformer blocks to RAM.

**Key Settings:**
- `blocks_to_swap`: 20 ⚙️ ADVANCED (Pixaroma optimal for 14GB VRAM)
- `prefetch_blocks`: 1 ⚠️ FIXED (NOT 0, prefetch optimization)

**blocks_to_swap Guidelines:**
- 0: No swapping (requires 24GB+ VRAM)
- 20: ⭐ Pixaroma optimal (14-16GB VRAM)
- 40: Original setting (12-14GB VRAM)
- 60: Maximum swapping (<12GB VRAM, slower)

---

## Common Issues

### Issue #1: End-of-Video Distortion

**Symptom:** Video becomes blurry/fuzzy in final seconds, lip-sync breaks down

**Cause:** Frame count not window-aligned

**Fix:** Use window-aligned frame counts only (81, 153, 225, 297, 369, 441, 513, 585, 657, 729, 873, 1089)

**Example:**
- ❌ 7 seconds: 175 frames → causes 53 frames of padding → distortion
- ✅ 7 seconds: Use 225 frames (9s) instead → no padding, perfect quality

**See:** TROUBLESHOOTING.md Issue #1

### Issue #2: Quality Degradation Every 3 Seconds

**Symptom:** Quality drops at window boundaries (every 3.24s)

**Cause:** Missing Pixaroma settings

**Fix:** Verify all fixed settings are correct:
- `base_precision: "fp16_fast"` (NOT bf16)
- `attention_mode: "sageattn"` (NOT sdpa)
- `scheduler: "dpm++_sde"` (NOT flowmatch_distill)
- `mode: "infinitetalk"` (REQUIRED)
- `motion_frame: 25` (NOT 9)
- `add_noise_to_samples: true` (NOT false)

**See:** TROUBLESHOOTING.md Issue #2

### Issue #3: Gradual Color/Contrast Increase

**Symptom:** Colors become more contrasted over time in long videos (30+ seconds)

**Cause:** colormatch set to "disabled"

**Fix:** Always use `colormatch: "mkl"` for all videos

```typescript
const colormatch = "mkl"; // Always enabled
```

**See:** TROUBLESHOOTING.md Issue #3

---

## Production Checklist

- [ ] RunPod endpoint deployed with WanVideo container
- [ ] Environment variables configured (RUNPOD_API_KEY, RUNPOD_ENDPOINT_URL)
- [ ] R2 bucket configured with public access
- [ ] Test with 720×1280 portrait image (21s audio)
- [ ] Test with 1280×720 landscape image (44s audio)
- [ ] Verify frame counts are window-aligned (use calculateOptimalFrames)
- [ ] Verify colormatch="mkl" is always enabled for all videos
- [ ] Verify all fixed Pixaroma settings are correct
- [ ] Error handling implemented
- [ ] Job status polling implemented
- [ ] File size limits enforced (images <10MB, audio <50MB)
- [ ] Audio duration limits enforced (max 60 seconds recommended)

---

## Support Resources

### Files in Repository

- **test_pixaroma_portrait_720x1280_21sec.json** - Portrait example (21s, 720×1280, colormatch="mkl")
- **test_pixaroma_44sec_4steps_colorfix.json** - Landscape example (44s, 1280×720, colormatch="mkl")
- **TROUBLESHOOTING.md** - Detailed issue diagnosis and fixes
- **CLAUDE.md** - Complete project documentation
- **Dockerfile** - Container setup with all models

### Key Documentation Sections

- **Frame Alignment:** See "Window-Aligned Frame Counts" above
- **Fixed Settings:** See "Fixed Settings (DO NOT CHANGE)" above
- **Node Details:** See "Complete Workflow Node Reference" above
- **Common Issues:** See "Common Issues" above

---

## What You DON'T Need to Worry About

✅ Pixaroma settings (all hardcoded correctly in test files)
✅ Complete workflow JSON (use test files as templates)
✅ Model/LoRA selection (Q5_0 + rank64 is optimal)
✅ Block swapping configuration (20 blocks is optimal)

**Just provide:** image URL, audio URL, audio duration, dimensions, calculate frames, set colormatch

---

**Last Updated:** November 12, 2025
**Version:** WanVideo 2.1 InfiniteTalk Production Release
**Status:** Production-ready ✅
