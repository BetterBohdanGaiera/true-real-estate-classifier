#!/usr/bin/env python3
"""
Authenticate the buddah_lucid Telethon session.
Run this interactively in terminal:
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/auth_buddah_lucid.py
"""
import asyncio
import sys
sys.path.insert(0, '.claude/skills/telegram/scripts')

from dotenv import load_dotenv
load_dotenv()

from telegram_fetch import load_config, CONFIG_DIR
from telethon import TelegramClient


async def auth():
    config = load_config()
    api_id = config.get('api_id')
    api_hash = config.get('api_hash')
    session_path = str(CONFIG_DIR / 'buddah_lucid')

    print(f"Session path: {session_path}.session")
    print("Enter the phone number for @buddah_lucid when prompted.\n")

    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    me = await client.get_me()
    print(f'\nAuthenticated as: {me.first_name} (@{me.username}) [ID: {me.id}]')
    await client.disconnect()
    print("Session saved at ~/.telegram_dl/buddah_lucid.session")
    print("You can now run the E2E test.")


if __name__ == "__main__":
    asyncio.run(auth())
