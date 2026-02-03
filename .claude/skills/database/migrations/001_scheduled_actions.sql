-- Migration: 001_scheduled_actions
-- Description: Create scheduled_actions table for storing follow-up actions
-- Created: 2026-01-19
--
-- This migration creates the scheduled_actions table used by the Telegram agent
-- to persist scheduled follow-up messages and other delayed actions.
--
-- Usage: psql $DATABASE_URL -f migrations/001_scheduled_actions.sql

-- =============================================================================
-- SCHEDULED_ACTIONS TABLE
-- =============================================================================
-- Stores all scheduled actions (follow-ups, reminders) for the Telegram agent.
-- Actions persist across daemon restarts and are recovered on startup.

CREATE TABLE IF NOT EXISTS scheduled_actions (
    -- Primary key: UUID auto-generated for each action
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Prospect identification (telegram_id as string)
    prospect_id VARCHAR(255) NOT NULL,

    -- Type of action: 'follow_up', 'reminder', 'pre_meeting', etc.
    action_type VARCHAR(50) NOT NULL,

    -- When this action should be executed (stored in UTC)
    scheduled_for TIMESTAMPTZ NOT NULL,

    -- Current status of the action
    -- 'pending'   - waiting to be executed
    -- 'executed'  - successfully completed
    -- 'cancelled' - cancelled before execution
    status VARCHAR(20) DEFAULT 'pending',

    -- Flexible JSON payload for action-specific data
    -- Example for follow_up:
    -- {
    --   "message_template": "Hi! Just following up...",
    --   "reason": "client requested callback in 2 hours",
    --   "conversation_context": {...}
    -- }
    payload JSONB DEFAULT '{}',

    -- Audit timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Execution tracking
    executed_at TIMESTAMPTZ,

    -- Cancellation tracking
    cancelled_at TIMESTAMPTZ,
    cancel_reason VARCHAR(255)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for fast lookup by prospect_id
-- Used when: cancelling all pending actions for a prospect, fetching prospect history
CREATE INDEX IF NOT EXISTS idx_scheduled_actions_prospect
    ON scheduled_actions(prospect_id);

-- Partial index for efficient pending job scheduling
-- Only indexes pending actions, optimized for scheduler queries
-- Used when: finding next job to execute, recovering pending jobs on startup
CREATE INDEX IF NOT EXISTS idx_scheduled_actions_pending
    ON scheduled_actions(scheduled_for)
    WHERE status = 'pending';

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE scheduled_actions IS 'Stores scheduled follow-up actions for the Telegram sales agent';
COMMENT ON COLUMN scheduled_actions.id IS 'Unique identifier for the scheduled action (UUID)';
COMMENT ON COLUMN scheduled_actions.prospect_id IS 'Telegram ID of the prospect (stored as varchar for flexibility)';
COMMENT ON COLUMN scheduled_actions.action_type IS 'Type of action: follow_up, reminder, pre_meeting, etc.';
COMMENT ON COLUMN scheduled_actions.scheduled_for IS 'UTC timestamp when action should be executed';
COMMENT ON COLUMN scheduled_actions.status IS 'Action status: pending, executed, or cancelled';
COMMENT ON COLUMN scheduled_actions.payload IS 'JSON payload with action-specific data (message template, context, etc.)';
COMMENT ON COLUMN scheduled_actions.created_at IS 'When the action was created';
COMMENT ON COLUMN scheduled_actions.updated_at IS 'When the action was last modified';
COMMENT ON COLUMN scheduled_actions.executed_at IS 'When the action was executed (NULL if not yet executed)';
COMMENT ON COLUMN scheduled_actions.cancelled_at IS 'When the action was cancelled (NULL if not cancelled)';
COMMENT ON COLUMN scheduled_actions.cancel_reason IS 'Reason for cancellation: client_responded, human_active, manual, etc.';
