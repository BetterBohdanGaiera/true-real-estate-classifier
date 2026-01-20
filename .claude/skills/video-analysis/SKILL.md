---
name: video-analysis
description: Analyzes video files and YouTube URLs using Google Gemini 3 Pro. Use when the user wants to analyze, summarize, transcribe, or extract information from videos. Trigger phrases include "analyze this video", "what's in this video", "summarize the video", "transcribe video", or any video understanding request.
---

# Video Analysis Skill

Analyze videos using Google Gemini 3 Pro's multimodal capabilities. Supports local video files and YouTube URLs.

## Prerequisites

Requires `GEMINI_API_KEY` in `.env` file. Run setup command to verify:

```bash
uv run scripts/analyze_video.py setup
```

Get your API key from: https://aistudio.google.com/apikey

## Quick Start

```bash
# Analyze a local video
uv run scripts/analyze_video.py analyze /path/to/video.mp4 "Summarize this video"

# Analyze a YouTube video
uv run scripts/analyze_video.py analyze "https://www.youtube.com/watch?v=VIDEO_ID" "What are the main topics?"

# Default prompt (summarize)
uv run scripts/analyze_video.py analyze video.mp4
```

## Commands

### Setup Check

Verify API key is configured:

```bash
uv run scripts/analyze_video.py setup
```

### Analyze Video

Analyze a video with a custom prompt:

```bash
# Local file
uv run scripts/analyze_video.py analyze video.mp4 "Describe what happens in detail"

# YouTube URL
uv run scripts/analyze_video.py analyze "https://youtu.be/xxx" "List the key points"

# With JSON output
uv run scripts/analyze_video.py analyze video.mp4 "Summarize" --json

# Specify model
uv run scripts/analyze_video.py analyze video.mp4 "Analyze" --model gemini-2.5-pro

# Video clipping (analyze specific portion)
uv run scripts/analyze_video.py analyze video.mp4 "What happens?" --start 60 --end 180

# Custom frame rate
uv run scripts/analyze_video.py analyze video.mp4 "Describe" --fps 5
```

## Options

| Option | Description |
|--------|-------------|
| `--json` | Output response as JSON |
| `--model <id>` | Model to use (default: gemini-3-pro-preview) |
| `--fps <int>` | Frame rate sampling (default: 1) |
| `--start <sec>` | Start offset in seconds |
| `--end <sec>` | End offset in seconds |

## Supported Inputs

**Local Files:**
- `.mp4`, `.webm`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.3gp`
- Maximum 2GB via File API

**YouTube URLs:**
- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`
- Up to 8 hours per day (free tier)

## Example User Requests

When user asks:

- "Analyze this video for me" -> `analyze <path> "Describe the video content"`
- "What's happening in this video?" -> `analyze <path> "What is happening in this video?"`
- "Summarize the presentation" -> `analyze <path> "Summarize the key points"`
- "Extract timestamps of important events" -> `analyze <path> "List key events with timestamps"`
- "Transcribe this video" -> `analyze <path> "Transcribe all spoken content"`
- "What's this YouTube tutorial about?" -> `analyze <url> "What topics are covered?"`
- "Analyze the first 5 minutes" -> `analyze <path> --start 0 --end 300 "Analyze"`

## Output

Returns the analysis result as plain text or JSON (with `--json` flag).

JSON format:
```json
{
  "success": true,
  "model": "gemini-3-pro-preview",
  "input": "video.mp4",
  "prompt": "Summarize this video",
  "analysis": "The video shows..."
}
```
