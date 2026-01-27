-- Migration: 004_sales_rep_sessions
-- Description: Add per-rep Telegram session and calendar tracking columns
-- Created: 2026-01-27
--
-- Adds columns to sales_representatives for multi-account support:
-- - telegram_phone: phone used for Telethon auth
-- - telegram_session_name: session file name (maps to ~/.telegram_dl/sessions/{name}.session)
-- - telegram_session_ready: whether auth succeeded
-- - agent_name: display name used in agent messages (overrides global AgentConfig.agent_name)
-- - calendar_connected: whether Google Calendar OAuth is complete

ALTER TABLE sales_representatives
  ADD COLUMN IF NOT EXISTS telegram_phone VARCHAR(20),
  ADD COLUMN IF NOT EXISTS telegram_session_name VARCHAR(255),
  ADD COLUMN IF NOT EXISTS telegram_session_ready BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS agent_name VARCHAR(100),
  ADD COLUMN IF NOT EXISTS calendar_connected BOOLEAN DEFAULT FALSE;
