# Video Frames - AI Agent Skill

[![Skills](https://img.shields.io/badge/skills.sh-video--frames-blue)](https://skills.sh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Extract frames from video files using ffmpeg, optimized for AI/LLM vision analysis. This skill enables AI agents to analyze video content by converting videos into JPEG frames that can be attached to prompts.

## Features

- **Multiple extraction modes**: Fixed FPS, scene-change detection, or target frame count
- **Quality presets**: `efficient`, `balanced`, `detailed`, and `ocr` for different use cases
- **Model-aware optimization**: Resize frames for Claude, OpenAI, Gemini, or universal compatibility
- **OCR enhancements**: Grayscale, high-contrast, and sharpening for text extraction
- **Token estimation**: Get accurate token counts for each model before attaching frames
- **Timestamp overlays**: Add timestamps to frames for temporal reference

## Installation

```bash
npx skills add <your-username>/video-frames-skill
```

## Prerequisites

ffmpeg and ffprobe must be installed and on PATH:

```bash
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Ubuntu/Debian
```

## Quick Start

```bash
# Extract ~30 frames (auto-calculates FPS)
python3 scripts/extract_frames.py video.mp4 --max-frames 30

# Scene detection for presentations/tutorials
python3 scripts/extract_frames.py presentation.mp4 --scene-threshold 0.3

# OCR mode for screencasts
python3 scripts/extract_frames.py screencast.mp4 --preset ocr --max-frames 40
```

## Presets

| Preset      | Max dim | Quality | Best for                   |
| ----------- | ------- | ------- | -------------------------- |
| `efficient` | 768px   | 5       | Bulk frames, long videos   |
| `balanced`  | 1024px  | 3       | General analysis (default) |
| `detailed`  | 1568px  | 2       | Fine detail, small objects |
| `ocr`       | 1568px  | 1       | Text/document extraction   |

## Model Optimization

Use `--target-model` to optimize frame dimensions for specific LLMs:

| Model       | Max dim | Rationale                                |
| ----------- | ------- | ---------------------------------------- |
| `claude`    | 1568px  | Max native resolution before auto-resize |
| `openai`    | 768px   | Aligned to 512px tile grid               |
| `gemini`    | 768px   | Aligned to 768px tile boundaries         |
| `universal` | 768px   | Sweet spot across all models (default)   |

## Output

The script outputs JSON with:
- List of extracted frame paths
- Resolution information
- Token estimates for Claude, OpenAI, and Gemini
- Extraction summary

## Supported Agents

This skill works with all major AI coding agents:
- Claude Code
- Cursor
- Windsurf
- Codex
- GitHub Copilot
- Cline
- And [40+ more](https://skills.sh)

## License

MIT
