#!/usr/bin/env python3
"""
Extract frames from a video file using ffmpeg with AI-friendly optimization.

Usage:
    python extract_frames.py <video_path> [options]

Frame Selection (mutually exclusive):
    --fps N                 Frames per second to extract (float, default: 1.0)
    --scene-threshold T     Extract on scene changes; T in 0.0-1.0 (lower=more
                            sensitive, default when flag used: 0.3)
    --min-scene-interval N  Min seconds between scene-change frames (default: 1.0)
    --max-frames N          Auto-calculate FPS to produce ~N frames (overrides --fps)

Image Quality:
    --preset PRESET         efficient | balanced | detailed | ocr (default: balanced)
    --max-dimension N       Override preset's max pixel dimension for longest edge
    --quality N             Override JPEG quality (1=best, 31=worst)

Model Optimization:
    --target-model MODEL    claude | openai | gemini | universal (default: universal)
                            Overrides max dimension to align with model tile boundaries.

OCR Enhancements:
    --grayscale             Convert frames to grayscale (smaller files, better OCR)
    --high-contrast         Boost contrast for text readability

Overlay:
    --timestamps            Overlay filename and timestamp on each frame

Output:
    --output-dir DIR        Directory to save frames (default: temp dir)

Output JSON includes frame list, resolution, token estimates, and extraction summary.

Requirements:
    ffmpeg and ffprobe on PATH (brew install ffmpeg)
"""

import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Preset configurations
# ---------------------------------------------------------------------------
PRESETS = {
    "efficient": {"max_dim": 768, "quality": 5, "sharpen": False},
    "balanced": {"max_dim": 1024, "quality": 3, "sharpen": False},
    "detailed": {"max_dim": 1568, "quality": 2, "sharpen": False},
    "ocr": {
        "max_dim": 1568,
        "quality": 1,
        "sharpen": True,
        "grayscale": True,
        "high_contrast": True,
    },
}

# Target-model dimension overrides (align to tile boundaries)
MODEL_DIMENSIONS = {
    "claude": 1568,    # max native resolution before auto-resize
    "openai": 768,     # shortest side 768, aligned to 512 tiles
    "gemini": 768,     # aligned to 768 tile boundaries
    "universal": 768,  # sweet spot for all models
}

# ---------------------------------------------------------------------------
# Helpers: video metadata via ffprobe
# ---------------------------------------------------------------------------

def get_video_duration(video_path):
    """Return video duration in seconds (float) using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError(f"Invalid video duration: {duration}")
    return duration


def get_frame_dimensions(frame_path):
    """Return (width, height) of a JPEG frame using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        frame_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    parts = result.stdout.strip().split("x")
    return int(parts[0]), int(parts[1])


# ---------------------------------------------------------------------------
# Token estimation functions (unchanged)
# ---------------------------------------------------------------------------

def estimate_claude_tokens(w, h):
    """Claude: (w * h) / 750 tokens per image."""
    return int(math.ceil((w * h) / 750))


def estimate_openai_high_tokens(w, h):
    """GPT-4o high detail: scale short side to 768, count 512x512 tiles, 170/tile + 85 base."""
    short_side = min(w, h)
    long_side = max(w, h)
    if short_side > 768:
        scale = 768 / short_side
        short_side = 768
        long_side = int(long_side * scale)
    tiles_x = math.ceil(long_side / 512)
    tiles_y = math.ceil(short_side / 512)
    return tiles_x * tiles_y * 170 + 85


def estimate_openai_low_tokens(_w, _h):
    """GPT-4o low detail: flat 85 tokens per image."""
    return 85


def estimate_gemini_tokens(w, h):
    """Gemini: if either dim > 384 -> ceil(w/768)*ceil(h/768)*258, else 258."""
    if w > 384 or h > 384:
        return math.ceil(w / 768) * math.ceil(h / 768) * 258
    return 258


# ---------------------------------------------------------------------------
# Scene-change detection helper
# ---------------------------------------------------------------------------

def detect_scene_timestamps(video_path, threshold=0.3, min_interval=1.0):
    """Run ffmpeg scene-detection pass and return list of timestamps (seconds).

    Uses showinfo to capture pts_time for each selected frame, then filters
    by *min_interval* to avoid burst detections.
    """
    select_expr = f"select='gt(scene\\,{threshold})',showinfo"
    cmd = [
        "ffmpeg", "-v", "info",
        "-i", video_path,
        "-vf", select_expr,
        "-vsync", "vfn",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # showinfo lines look like: ... pts_time:1.234 ...
    pts_pattern = re.compile(r"pts_time:\s*([\d.]+)")
    raw_times = sorted(float(m.group(1)) for m in pts_pattern.finditer(result.stderr))

    # Enforce minimum interval between detections
    if not raw_times:
        return raw_times
    filtered = [raw_times[0]]
    for t in raw_times[1:]:
        if t - filtered[-1] >= min_interval:
            filtered.append(t)
    return filtered


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def extract_frames(
    video_path,
    fps=1.0,
    timestamps=False,
    output_dir=None,
    preset="balanced",
    max_dimension=None,
    max_frames=None,
    quality_override=None,
    scene_threshold=None,
    min_scene_interval=1.0,
    target_model=None,
    grayscale=False,
    high_contrast=False,
):
    """Extract frames from a video with AI-friendly optimization.

    Returns a dict with output_dir, frames list, preset, resolution, token
    estimates, and an extraction summary.
    """
    # --- Validate inputs ---
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise EnvironmentError(f"{tool} not found on PATH. Install it: brew install ffmpeg")

    # --- Resolve preset config ---
    preset_config = PRESETS[preset]
    max_dim = max_dimension if max_dimension is not None else preset_config["max_dim"]
    jpeg_quality = quality_override if quality_override is not None else preset_config["quality"]
    sharpen = preset_config["sharpen"]
    if preset_config.get("grayscale"):
        grayscale = True
    if preset_config.get("high_contrast"):
        high_contrast = True

    # --- Target-model dimension override (lowest priority < preset < CLI) ---
    if target_model and max_dimension is None:
        max_dim = MODEL_DIMENSIONS[target_model]

    # --- Get video duration (needed for several paths) ---
    duration = get_video_duration(video_path)

    # --- Determine extraction method ---
    extraction_method = "fps"
    scene_changes_detected = None

    if scene_threshold is not None:
        extraction_method = "scene_detection"
    elif max_frames is not None:
        extraction_method = "max_frames"
        fps = max(0.05, min(30.0, max_frames / duration))

    # --- Prepare output directory ---
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="video_frames_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    # --- Build common video-filter chain (everything except frame selection) ---
    def _build_processing_filters():
        parts = []
        # Scale (down only, preserve aspect ratio)
        parts.append(
            f"scale=w='min({max_dim},iw)':h='min({max_dim},ih)'"
            f":force_original_aspect_ratio=decrease"
        )
        # Grayscale
        if grayscale:
            parts.append("format=gray")
        # High contrast
        if high_contrast:
            parts.append("eq=contrast=1.3:brightness=0.05")
        # Sharpen (OCR)
        if sharpen:
            parts.append("unsharp=5:5:0.7:5:5:0.0")
        # Timestamp overlay
        if timestamps:
            base_name = os.path.basename(video_path)
            timestamp_expr = r"%{pts\:hms}"
            text = f"{base_name} {timestamp_expr}"
            parts.append(
                "drawtext=fontcolor=white"
                ":fontsize='min(24, h/20)'"
                ":box=1:boxcolor=black@0.5"
                f":text='{text}':x=w-tw-10:y=h-th-10"
            )
        return parts

    pattern = os.path.join(output_dir, "frame_%05d.jpg")

    # --- Execute extraction ---
    if extraction_method == "scene_detection":
        # Two-pass: detect timestamps, then extract specific frames
        assert scene_threshold is not None
        scene_times = detect_scene_timestamps(
            video_path, threshold=scene_threshold, min_interval=min_scene_interval,
        )
        scene_changes_detected = len(scene_times)

        if scene_times:
            processing = _build_processing_filters()
            for idx, t in enumerate(scene_times, start=1):
                out_path = os.path.join(output_dir, f"frame_{idx:05d}.jpg")
                vf = ",".join(processing) if processing else None
                cmd = [
                    "ffmpeg", "-v", "error",
                    "-ss", str(t),
                    "-i", video_path,
                    "-frames:v", "1",
                ]
                if vf:
                    cmd += ["-vf", vf]
                cmd += ["-q:v", str(jpeg_quality), out_path]
                subprocess.run(cmd, check=True)
    else:
        # Standard FPS-based extraction (covers both "fps" and "max_frames")
        vf_parts = [f"fps={fps}"] + _build_processing_filters()
        vf = ",".join(vf_parts)
        cmd = [
            "ffmpeg", "-v", "error",
            "-i", video_path,
            "-vf", vf,
            "-q:v", str(jpeg_quality),
            pattern,
        ]
        subprocess.run(cmd, check=True)

    # --- Collect frames ---
    frames = sorted(glob.glob(os.path.join(output_dir, "frame_*.jpg")))
    frame_count = len(frames)

    # --- Empty result shortcut ---
    _zero_tokens = {"claude": 0, "openai_high": 0, "openai_low": 0, "gemini": 0}
    if frame_count == 0:
        return {
            "output_dir": output_dir,
            "frames": [],
            "preset": preset,
            "resolution": {"width": 0, "height": 0},
            "token_estimate": {
                "frame_count": 0,
                "per_frame": _zero_tokens,
                "total": _zero_tokens,
            },
            "summary": {
                "video_duration_seconds": round(duration, 2),
                "extraction_method": extraction_method,
                "scene_changes_detected": scene_changes_detected,
                "frames_extracted": 0,
                "estimated_total_tokens": _zero_tokens,
            },
        }

    # --- Get actual output dimensions ---
    width, height = get_frame_dimensions(frames[0])

    # --- Compute token estimates ---
    pf_claude = estimate_claude_tokens(width, height)
    pf_openai_high = estimate_openai_high_tokens(width, height)
    pf_openai_low = estimate_openai_low_tokens(width, height)
    pf_gemini = estimate_gemini_tokens(width, height)

    per_frame = {
        "claude": pf_claude,
        "openai_high": pf_openai_high,
        "openai_low": pf_openai_low,
        "gemini": pf_gemini,
    }
    total = {k: v * frame_count for k, v in per_frame.items()}

    return {
        "output_dir": output_dir,
        "frames": frames,
        "preset": preset,
        "resolution": {"width": width, "height": height},
        "token_estimate": {
            "frame_count": frame_count,
            "per_frame": per_frame,
            "total": total,
        },
        "summary": {
            "video_duration_seconds": round(duration, 2),
            "extraction_method": extraction_method,
            "scene_changes_detected": scene_changes_detected,
            "frames_extracted": frame_count,
            "estimated_total_tokens": total,
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract frames from a video using ffmpeg with AI-friendly optimization",
    )
    parser.add_argument("video_path", help="Path to the video file")

    # --- Frame selection (mutually exclusive: fps vs scene-threshold) ---
    rate_group = parser.add_mutually_exclusive_group()
    rate_group.add_argument(
        "--fps", type=float, default=1.0,
        help="Frames per second to extract (default: 1.0)",
    )
    rate_group.add_argument(
        "--scene-threshold", type=float, metavar="T",
        help="Scene-change sensitivity 0.0-1.0 (lower=more sensitive, default: 0.3)",
    )

    parser.add_argument(
        "--min-scene-interval", type=float, default=1.0, metavar="N",
        help="Min seconds between scene-change frames (default: 1.0)",
    )
    parser.add_argument(
        "--max-frames", type=int,
        help="Auto-calculate FPS to produce ~N frames (overrides --fps)",
    )

    # --- Image quality ---
    parser.add_argument(
        "--preset", choices=list(PRESETS.keys()), default="balanced",
        help="Quality preset (default: balanced)",
    )
    parser.add_argument(
        "--max-dimension", type=int,
        help="Override preset's max pixel dimension for the longest edge",
    )
    parser.add_argument(
        "--quality", type=int, choices=range(1, 32), metavar="1-31",
        help="Override JPEG quality (1=best, 31=worst)",
    )

    # --- Model optimization ---
    parser.add_argument(
        "--target-model",
        choices=list(MODEL_DIMENSIONS.keys()),
        help="Optimize dimensions for a target model (default: universal)",
    )

    # --- OCR enhancements ---
    parser.add_argument(
        "--grayscale", action="store_true",
        help="Convert frames to grayscale (better for OCR, smaller files)",
    )
    parser.add_argument(
        "--high-contrast", action="store_true",
        help="Boost contrast for text readability",
    )

    # --- Overlay & output ---
    parser.add_argument(
        "--timestamps", action="store_true",
        help="Overlay filename and timestamp on frames",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save frames (default: temp dir)",
    )

    args = parser.parse_args()

    try:
        result = extract_frames(
            video_path=args.video_path,
            fps=args.fps,
            timestamps=args.timestamps,
            output_dir=args.output_dir,
            preset=args.preset,
            max_dimension=args.max_dimension,
            max_frames=args.max_frames,
            quality_override=args.quality,
            scene_threshold=args.scene_threshold,
            min_scene_interval=args.min_scene_interval,
            target_model=args.target_model,
            grayscale=args.grayscale,
            high_contrast=args.high_contrast,
        )
        print(json.dumps(result, indent=2))
    except (FileNotFoundError, EnvironmentError, subprocess.CalledProcessError, ValueError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
