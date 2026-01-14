# ElevenLabs Speech-to-Text Skill

Audio and video transcription using ElevenLabs Scribe API.

## Setup

Add to `.env`:
```
ELEVENLABS_API_KEY=your_api_key_here
```

## Quick Reference

```bash
# Basic transcription
uv run .claude/skills/eleven-labs/scripts/transcribe.py audio.mp3

# With speakers (meeting/interview)
uv run .claude/skills/eleven-labs/scripts/transcribe.py meeting.mp4 --diarize --format markdown

# From URL
uv run .claude/skills/eleven-labs/scripts/transcribe.py --url "https://s3.example.com/audio.mp3"

# Full options
uv run .claude/skills/eleven-labs/scripts/transcribe.py audio.mp3 \
    --diarize \
    --num-speakers 3 \
    --entities pii \
    --format json \
    --output transcript.json
```

## Options

| Flag | Description |
|------|-------------|
| `--format` | `text` (default), `json`, `markdown` |
| `--diarize` | Identify speakers |
| `--num-speakers N` | Expected speaker count |
| `--timestamps` | `none`, `word`, `character` |
| `--entities` | `all`, `pii`, `phi`, `pci` |
| `--language CODE` | ISO language (auto-detect default) |
| `--output FILE` | Save to file |

## Supported Formats

Audio: MP3, WAV, M4A, FLAC, OGG, AAC
Video: MP4, MOV, AVI, MKV, WebM

Max size: 3GB (local) / 2GB (URL)
