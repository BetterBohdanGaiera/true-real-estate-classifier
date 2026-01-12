#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
#     "anthropic",
# ]
# ///

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def get_tts_script_path():
    """
    Determine which TTS script to use based on available API keys.
    Priority order: ElevenLabs > OpenAI > pyttsx3
    """
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    pyttsx3_script = tts_dir / "pyttsx3_tts.py"
    if pyttsx3_script.exists():
        return str(pyttsx3_script)

    return None


def summarize_session_with_haiku(transcript_path: str) -> str:
    """
    Read session transcript and generate a spoken summary using Claude Haiku.

    Args:
        transcript_path: Path to the .jsonl transcript file

    Returns:
        str: A brief, speakable summary of what was accomplished
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return "Session complete."

    # Read transcript
    transcript_content = []
    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        # Extract relevant content from transcript
                        if entry.get('type') == 'user':
                            transcript_content.append(f"User: {entry.get('message', {}).get('content', '')[:500]}")
                        elif entry.get('type') == 'assistant':
                            msg = entry.get('message', {})
                            if isinstance(msg, dict):
                                content = msg.get('content', [])
                                if isinstance(content, list):
                                    for block in content[:3]:  # Limit blocks
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            transcript_content.append(f"Assistant: {block.get('text', '')[:300]}")
                    except json.JSONDecodeError:
                        pass
    except Exception:
        return "Session complete."

    if not transcript_content:
        return "Session complete."

    # Limit transcript to last ~2000 chars for Haiku
    transcript_text = "\n".join(transcript_content[-20:])[-2000:]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""Based on this session transcript, generate a brief 1-2 sentence spoken summary of what was accomplished.
Speak directly as if announcing completion to the user. Be concise and natural.
Examples: "I've updated the TTS configuration to use ElevenLabs with the Bella voice." or "Fixed the authentication bug and added tests."

Transcript:
{transcript_text}

Summary (1-2 sentences, spoken naturally):"""
            }]
        )

        return response.content[0].text.strip()
    except Exception:
        return "Session complete."


def announce_completion(transcript_path: str = None):
    """Announce completion using TTS with session-specific summary."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return

        # Generate session-specific summary using Haiku
        if transcript_path and os.path.exists(transcript_path):
            completion_message = summarize_session_with_haiku(transcript_path)
        else:
            completion_message = "Session complete."

        subprocess.run(
            ["uv", "run", tts_script, completion_message],
            capture_output=True,
            timeout=15
        )

    except Exception:
        pass


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--notify', action='store_true', help='Enable TTS completion announcement')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract required fields
        session_id = input_data.get("session_id", "")
        stop_hook_active = input_data.get("stop_hook_active", False)

        # Ensure log directory exists
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "stop.json")

        # Read existing log data or initialize empty list
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []
        
        # Append new data
        log_data.append(input_data)
        
        # Write back to file with formatting
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        # Handle --chat switch
        if args.chat and 'transcript_path' in input_data:
            transcript_path = input_data['transcript_path']
            if os.path.exists(transcript_path):
                # Read .jsonl file and convert to JSON array
                chat_data = []
                try:
                    with open(transcript_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Skip invalid lines
                    
                    # Write to logs/chat.json
                    chat_file = os.path.join(log_dir, 'chat.json')
                    with open(chat_file, 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        # Announce completion via TTS (only if --notify flag is set)
        if args.notify:
            transcript_path = input_data.get('transcript_path')
            announce_completion(transcript_path)

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
