---
name: transcribing-audio
description: Transcribes audio and video files to text using ElevenLabs Speech-to-Text API. Use when user asks to transcribe audio, convert speech to text, get transcripts, or needs audio transcription with speaker identification.
---

# ElevenLabs Speech-to-Text Skill

Transcribe audio and video files using the ElevenLabs Scribe API with support for speaker diarization, timestamps, and entity detection.

## Prerequisites

1. Get an API key from [ElevenLabs](https://elevenlabs.io/)
2. Add to `.env` file:
   ```
   ELEVENLABS_API_KEY=your_api_key_here
   ```

## Quick Start

```bash
# Basic transcription
uv run .claude/skills/eleven-labs/scripts/transcribe.py audio.mp3

# With speaker diarization
uv run .claude/skills/eleven-labs/scripts/transcribe.py audio.mp3 --diarize

# Markdown output with timestamps
uv run .claude/skills/eleven-labs/scripts/transcribe.py audio.mp3 --diarize --format markdown

# From URL (S3, GCS, R2, CDN)
uv run .claude/skills/eleven-labs/scripts/transcribe.py --url "https://storage.example.com/audio.mp3"
```

## Commands

### Basic Transcription

```bash
# Transcribe a local file
uv run .claude/skills/eleven-labs/scripts/transcribe.py FILE_PATH

# Transcribe from URL
uv run .claude/skills/eleven-labs/scripts/transcribe.py --url URL
```

### Options

| Option | Description |
|--------|-------------|
| `--format` | Output format: `text`, `json`, `markdown` (default: text) |
| `--diarize` | Enable speaker identification |
| `--num-speakers N` | Hint for expected speaker count (max 32) |
| `--timestamps` | Granularity: `none`, `word`, `character` (default: word) |
| `--entities` | Detect entities: `all`, `pii`, `phi`, `pci` |
| `--language` | ISO language code (auto-detected if omitted) |
| `--model` | Model: `scribe_v2` (default), `scribe_v1`, `scribe_v1_experimental` |
| `--no-audio-events` | Disable audio event tagging |
| `--output FILE` | Save output to file |

### Full Examples

```bash
# Meeting transcription with speakers
uv run .claude/skills/eleven-labs/scripts/transcribe.py meeting.mp4 \
    --diarize \
    --num-speakers 4 \
    --format markdown \
    --output meeting_transcript.md

# Interview with entity detection
uv run .claude/skills/eleven-labs/scripts/transcribe.py interview.mp3 \
    --diarize \
    --entities pii \
    --format json

# Podcast with character-level timestamps
uv run .claude/skills/eleven-labs/scripts/transcribe.py podcast.mp3 \
    --timestamps character \
    --format json

# Specific language
uv run .claude/skills/eleven-labs/scripts/transcribe.py audio.mp3 --language es
```

## Output Formats

### Text (default)

Plain transcription text:
```
Hello, this is a test transcription. Thank you for listening.
```

### Markdown

Formatted with timestamps and speakers:
```markdown
# Transcription

**Language:** English (eng)
**Duration:** 00:01:23

## Transcript

[00:00:00] **Speaker 1:** Hello, this is a test transcription.
[00:00:03] **Speaker 2:** Thank you for listening.

## Entities Detected

- **PII** (00:00:15): john.doe@email.com
```

### JSON

Full API response with word-level details:
```json
{
  "language_code": "eng",
  "language_probability": 0.98,
  "text": "Hello, this is a test transcription.",
  "words": [
    {
      "text": "Hello",
      "start": 0.0,
      "end": 0.5,
      "speaker_id": "speaker_1"
    }
  ],
  "entities": []
}
```

## Features

### Speaker Diarization

Identifies up to 32 different speakers in the audio:
```bash
uv run .claude/skills/eleven-labs/scripts/transcribe.py meeting.mp3 --diarize --num-speakers 3
```

### Entity Detection

Detects sensitive information:
- `pii` - Personal Identifiable Information (names, emails, phones)
- `phi` - Protected Health Information (medical conditions)
- `pci` - Payment Card Information (credit card numbers)
- `all` - All categories

```bash
uv run .claude/skills/eleven-labs/scripts/transcribe.py call.mp3 --entities all
```

### Audio Event Tagging

Tags non-speech sounds like laughter, applause, music:
```
[laughter] That was really funny [applause]
```

Disable with `--no-audio-events`.

## Supported Formats

All major audio and video formats:
- Audio: MP3, WAV, M4A, FLAC, OGG, AAC
- Video: MP4, MOV, AVI, MKV, WebM

Maximum file size: 3GB (local) or 2GB (URL)

## Example User Requests

| User says | Command |
|-----------|---------|
| "Transcribe this audio file" | `transcribe.py file.mp3` |
| "Get a transcript with speakers" | `transcribe.py file.mp3 --diarize --format markdown` |
| "Transcribe the meeting recording" | `transcribe.py meeting.mp4 --diarize` |
| "Convert this voice note to text" | `transcribe.py voice.m4a` |
| "Transcribe and detect PII" | `transcribe.py call.mp3 --entities pii` |

## Error Handling

| Error | Solution |
|-------|----------|
| "API key not found" | Add `ELEVENLABS_API_KEY` to `.env` |
| "File too large" | File exceeds 3GB limit |
| "Unsupported format" | Convert to MP3/WAV first |
| "Rate limit exceeded" | Wait and retry |

## API Reference

- [ElevenLabs Speech-to-Text](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
- [Scribe Documentation](https://elevenlabs.io/docs/overview/capabilities/speech-to-text)
