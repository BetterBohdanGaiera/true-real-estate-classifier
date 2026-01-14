#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-genai", "python-dotenv"]
# ///
"""
Gemini Video Analysis with File State Wait

Handles the file upload state issue by polling until file is ACTIVE.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


def get_api_key() -> str:
    """Load and return GEMINI_API_KEY from environment."""
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in environment")
        sys.exit(1)
    return api_key


def wait_for_file_active(client: genai.Client, file_name: str, max_wait: int = 600) -> bool:
    """Wait for file to become ACTIVE state."""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            file_info = client.files.get(name=file_name)
            state = file_info.state.name if hasattr(file_info.state, 'name') else str(file_info.state)
            print(f"File state: {state}")
            if state == "ACTIVE":
                return True
            elif state == "FAILED":
                print("ERROR: File processing failed")
                return False
        except Exception as e:
            print(f"Error checking file state: {e}")
        time.sleep(10)
    print("ERROR: Timeout waiting for file to become ACTIVE")
    return False


def analyze_video(video_path: str, prompt: str, output_path: str):
    """Analyze video with Gemini, waiting for file to be ready."""
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    video_file = Path(video_path)
    if not video_file.exists():
        print(f"ERROR: Video file not found: {video_path}")
        sys.exit(1)

    print(f"Uploading video: {video_file.name}")
    uploaded_file = client.files.upload(file=str(video_file))
    print(f"Uploaded file: {uploaded_file.name}")

    print("Waiting for file to become ACTIVE...")
    if not wait_for_file_active(client, uploaded_file.name):
        sys.exit(1)

    print("Generating analysis...")
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[uploaded_file, prompt]
        )

        analysis_text = response.text

        # Save to output file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(analysis_text, encoding='utf-8')
        print(f"Analysis saved to: {output_path}")

    except Exception as e:
        print(f"ERROR during analysis: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Analyze video with Gemini")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--prompt", required=True, help="Analysis prompt")
    parser.add_argument("--output", required=True, help="Output file path")

    args = parser.parse_args()
    analyze_video(args.video, args.prompt, args.output)


if __name__ == "__main__":
    main()
