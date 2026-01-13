#!/usr/bin/env python3
"""
Simple Telegram authentication script.
Run in terminal: uv run python auth.py
"""
import asyncio
import json
from pathlib import Path
from telethon import TelegramClient

CONFIG_DIR = Path.home() / '.telegram_dl'
CONFIG_FILE = CONFIG_DIR / 'config.json'
SESSION_FILE = CONFIG_DIR / 'user.session'

async def main():
    # Load config
    with open(CONFIG_FILE) as f:
        config = json.load(f)

    print("Connecting to Telegram...")
    client = TelegramClient(str(SESSION_FILE), config['api_id'], config['api_hash'])

    # This will prompt for phone and code
    await client.start()

    me = await client.get_me()
    print(f"\n✓ Authenticated as: {me.first_name} (@{me.username})")
    print(f"  ID: {me.id}")

    await client.disconnect()
    print(f"\n✓ Session saved to: {SESSION_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
