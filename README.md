# Video Frames — AI Agent Skill

[![skills.sh](https://img.shields.io/badge/skills.sh-video--frames-blue)](https://skills.sh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Requires ffmpeg](https://img.shields.io/badge/requires-ffmpeg-orange)](https://ffmpeg.org)

> Extract frames from video files using ffmpeg, optimized for LLM vision analysis. Supports scene detection, model-aware resizing, quality presets, OCR mode, and automatic token estimation.

## Features

- **Automatic FPS calculation** — specify a target frame count with `--max-frames` and let the script figure out the right extraction rate
- **Scene-change detection** — extract one frame per visual scene transition instead of fixed intervals
- **Model-aware optimization** — resize frames to align with Claude, OpenAI, or Gemini tile boundaries to minimize wasted tokens
- **Quality presets** — four presets (`efficient`, `balanced`, `detailed`, `ocr`) for different use cases
- **OCR mode** — grayscale + high contrast + sharpening pipeline for extracting text from screencasts and presentations
- **Timestamp overlay** — burn source filename and `hh:mm:ss` timestamp into each frame for temporal reference
- **Token estimation** — JSON output includes per-model token estimates so you can verify frames fit within context limits
- **Zero dependencies** — pure Python 3 + ffmpeg, no pip packages required

## Installation

### Via skills.sh (recommended)

```bash
npx skills add mugnimaestra/video-frames-skill
```

### Manual installation

Clone the repository into your agent's skills directory:

```bash
git clone https://github.com/mugnimaestra/video-frames-skill.git ~/.agents/skills/video-frames
```

### Prerequisites

ffmpeg and ffprobe must be installed and on PATH:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (scoop)
scoop install ffmpeg
```

## Quick Start

Extract ~30 frames from a video (auto-calculates FPS):

```bash
python3 scripts/extract_frames.py video.mp4 --max-frames 30
```

Extract with scene-change detection (one frame per scene):

```bash
python3 scripts/extract_frames.py presentation.mp4 --scene-threshold 0.3
```

Extract frames optimized for Claude at maximum detail:

```bash
python3 scripts/extract_frames.py video.mp4 --max-frames 30 --target-model claude --preset detailed
```

Read text from a screencast using the OCR pipeline:

```bash
python3 scripts/extract_frames.py screencast.mp4 --max-frames 40 --preset ocr
```

## Presets

Four quality presets control resolution, JPEG compression, and image processing:

| Preset | Max Dimension | JPEG Quality | Extras | Best For |
|---|---|---|---|---|
| `efficient` | 768px | 5 | — | Bulk frames, long videos |
| `balanced` | 1024px | 3 | — | General analysis (default) |
| `detailed` | 1568px | 2 | — | Fine detail, small objects |
| `ocr` | 1568px | 1 (best) | Grayscale + high contrast + sharpen | Text/document extraction |

Quality and max dimension can be overridden independently:

```bash
python3 scripts/extract_frames.py video.mp4 --preset balanced --quality 1 --max-dimension 1568
```

## Usage Guide

### Frame Selection Modes

**`--max-frames N` (recommended)** — Specify the target number of frames. The script auto-calculates the optimal FPS based on video duration, clamped to 0.05–30.0 FPS. This is the preferred approach because it adapts to any video length.

```bash
python3 scripts/extract_frames.py video.mp4 --max-frames 30
```

**`--fps N`** — Extract at a fixed rate. Use when you need precise control over sampling intervals.

```bash
python3 scripts/extract_frames.py video.mp4 --fps 0.5  # 1 frame every 2 seconds
```

| Video Length | Recommended FPS | Rationale |
|---|---|---|
| < 30s | 2–5 | Short clip, capture detail |
| 30s – 5min | 1 | Good coverage vs. frame count |
| 5min – 30min | 0.5 | Avoid excessive frames |
| > 30min | 0.1–0.2 | Sample key moments only |

**`--scene-threshold`** — Detect visual scene changes instead of extracting at fixed intervals. Ideal for presentations, edited footage, and tutorials.

```bash
# Standard sensitivity
python3 scripts/extract_frames.py video.mp4 --scene-threshold 0.3

# Less sensitive, minimum 2s between frames
python3 scripts/extract_frames.py action.mp4 --scene-threshold 0.5 --min-scene-interval 2.0
```

> **Note:** `--fps` and `--scene-threshold` are mutually exclusive. `--max-frames` only works with FPS mode.

### Model Optimization

Use `--target-model` to resize frames to align with a model's native tile/patch boundaries:

| Model | Max Dimension | Rationale |
|---|---|---|
| `claude` | 1568px | Max native resolution before auto-resize |
| `openai` | 768px | Aligned to 512px tile grid (shortest side 768) |
| `gemini` | 768px | Aligned to 768px tile boundaries |
| `universal` | 768px | Sweet spot across all models (default) |

```bash
python3 scripts/extract_frames.py video.mp4 --max-frames 30 --target-model claude
```

`--target-model` sets the max dimension unless `--max-dimension` is explicitly provided (CLI override takes priority).

### OCR Mode

For videos containing text — screencasts, presentations, terminal recordings:

```bash
# Full OCR pipeline via preset
python3 scripts/extract_frames.py screencast.mp4 --preset ocr --max-frames 40

# Manual OCR flags (can combine with any preset)
python3 scripts/extract_frames.py video.mp4 --grayscale --high-contrast
```

- `--grayscale` — converts frames to grayscale, reducing file size ~60% with no OCR accuracy loss
- `--high-contrast` — applies `contrast=1.3, brightness=0.05` to improve text/background separation
- The `ocr` preset enables both flags **plus** unsharp-mask sharpening at 1568px, quality 1

### Timestamp Overlay

Burn the source filename and `hh:mm:ss` timestamp into each frame (white text on semi-transparent black box, bottom-right corner):

```bash
python3 scripts/extract_frames.py video.mp4 --timestamps --max-frames 30
```

Use when the user needs to reference specific moments in the video.

## CLI Reference

| Option | Type | Default | Description |
|---|---|---|---|
| `video_path` | positional | *(required)* | Path to the video file |
| `--fps` | float | `1.0` | Frames per second to extract (mutually exclusive with `--scene-threshold`) |
| `--scene-threshold` | float | — | Scene-change detection sensitivity, 0.0–1.0 (mutually exclusive with `--fps`) |
| `--min-scene-interval` | float | `1.0` | Minimum seconds between scene-change frames |
| `--max-frames` | int | — | Target frame count; auto-calculates FPS (FPS mode only) |
| `--preset` | choice | `balanced` | Quality preset: `efficient` / `balanced` / `detailed` / `ocr` |
| `--max-dimension` | int | — | Override max pixel dimension (longest edge) |
| `--quality` | int | — | JPEG quality 1–31 (1 = best, 31 = worst) |
| `--target-model` | choice | — | Optimize for: `claude` / `openai` / `gemini` / `universal` |
| `--grayscale` | flag | off | Convert frames to grayscale |
| `--high-contrast` | flag | off | Boost contrast for text readability |
| `--timestamps` | flag | off | Overlay filename + timestamp on frames |
| `--output-dir` | string | temp dir | Output directory for extracted frames |

## Output Format

The script prints JSON to stdout:

```json
{
  "output_dir": "/tmp/video_frames_abc123/",
  "frames": [
    "/tmp/video_frames_abc123/frame_00001.jpg",
    "/tmp/video_frames_abc123/frame_00002.jpg"
  ],
  "preset": "balanced",
  "resolution": { "width": 1024, "height": 576 },
  "token_estimate": {
    "frame_count": 30,
    "per_frame": {
      "claude": 787,
      "openai_high": 765,
      "openai_low": 85,
      "gemini": 258
    },
    "total": {
      "claude": 23610,
      "openai_high": 22950,
      "openai_low": 2550,
      "gemini": 7740
    }
  },
  "summary": {
    "video_duration_seconds": 120.5,
    "extraction_method": "max_frames",
    "scene_changes_detected": null,
    "frames_extracted": 30,
    "estimated_total_tokens": {
      "claude": 23610,
      "openai_high": 22950,
      "openai_low": 2550,
      "gemini": 7740
    }
  }
}
```

| Field | Description |
|---|---|
| `output_dir` | Directory containing the extracted JPEG frames |
| `frames` | Ordered list of frame file paths |
| `preset` | Quality preset that was applied |
| `resolution` | Output frame dimensions (after resizing) |
| `token_estimate.per_frame` | Per-frame token cost for each model |
| `token_estimate.total` | Total token cost across all frames |
| `summary.extraction_method` | How frames were selected: `fps`, `max_frames`, or `scene_detection` |

On error, JSON with an `"error"` key is printed to stderr and the script exits with code 1.

## Token Estimation

Token costs are calculated per-model using their native image processing formulas:

- **Claude**: `ceil(width × height / 750)` tokens per frame
- **OpenAI (legacy tile-based)**: Images are tiled into 512×512 blocks → `tiles × 170 + 85` tokens per frame. Low-detail mode is a flat 85 tokens.
- **OpenAI (newer patch-based)**: Models like GPT-5.4-mini use 32×32 pixel patches with model-specific multipliers. See [OpenAI vision docs](https://platform.openai.com/docs/guides/vision) for latest rates.
- **Gemini**: Images are tiled into 768×768 blocks → `tiles × 258` tokens per frame (minimum 258)

### Cross-Model Sweet Spots

> OpenAI estimates below are for legacy tile-based models (GPT-4o/4.1).

| Preset | Max Dim | Claude | OpenAI (high) | Gemini | Best For |
|---|---|---|---|---|---|
| `efficient` | 768px | ~443–786 | 255–765 | 258 | Bulk frames, long videos |
| `balanced` | 1024px | ~787–1,400 | 765 | 258–516 | General analysis |
| `detailed` | 1568px | ~1,590–1,843 | 765–1,445 | 516–1,032 | Fine detail needed |
| `ocr` | 1568px | ~1,590–1,843 | 765–1,445 | 516–1,032 | Text extraction |

**Key insight:** 768px is the universal sweet spot — efficient tile packing on OpenAI (4 tiles = 765 tokens), minimum useful detail on Gemini (1 tile = 258 tokens), and well under Claude's auto-resize threshold (~786 tokens).

Keep total frame count under ~50 for optimal LLM context usage.

## Supported Agents

This skill works with any AI coding agent that supports the [skills.sh](https://skills.sh) format:

- **Claude Code** (Anthropic)
- **Cursor**
- **Windsurf**
- **Cline / Roo Code**
- **Amp**
- **OpenCode**

## Project Structure

```
video-frames-skill/
├── SKILL.md                          # Agent-facing skill instructions
├── README.md                         # This file
├── scripts/
│   └── extract_frames.py             # Main extraction script (Python 3 + ffmpeg)
└── references/
    └── llm-image-specs.md            # Detailed token formulas per model
```

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes and test with various video formats
4. Submit a pull request

**Report issues:** [github.com/mugnimaestra/video-frames-skill/issues](https://github.com/mugnimaestra/video-frames-skill/issues)

## License

MIT
