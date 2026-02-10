#!/usr/bin/env python3
"""
Re-authenticate the test_prospect Telethon session.
Run this script directly in terminal (not via Claude):
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/auth_test_prospect.py
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
    session_path = str(CONFIG_DIR / 'test_prospect')

    print(f"Session path: {session_path}.session")
    print("This will prompt for the @buddah_lucid phone number and verification code.\n")

    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    me = await client.get_me()
    print(f'\nAuthenticated as: {me.first_name} (@{me.username}) [ID: {me.id}]')
    await client.disconnect()
    print("Session saved. You can now run the E2E test.")


if __name__ == "__main__":
    asyncio.run(auth())
