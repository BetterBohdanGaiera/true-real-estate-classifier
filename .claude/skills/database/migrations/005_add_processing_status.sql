-- Migration: 005_add_processing_status
-- Description: Add processing status support for polling daemon
-- Created: 2026-01-28
--
-- This migration adds support for the 'processing' status to prevent
-- duplicate execution when using database polling with row-level locking.
-- The started_processing_at timestamp enables detection of stale/stuck
-- actions that need recovery after daemon crashes or timeouts.
--
-- Usage: psql $DATABASE_URL -f migrations/005_add_processing_status.sql

-- =============================================================================
-- ADD PROCESSING TIMESTAMP COLUMN
-- =============================================================================
-- Tracks when an action transitioned to 'processing' status.
-- Used for timeout detection: if an action has been processing longer than
-- the configured timeout (e.g., 5 minutes), it can be recovered and retried.

ALTER TABLE scheduled_actions
ADD COLUMN IF NOT EXISTS started_processing_at TIMESTAMPTZ;

-- =============================================================================
-- POLLING PERFORMANCE INDEX
-- =============================================================================
-- Optimized partial index for the polling daemon's main query pattern.
-- Indexes both 'pending' and 'processing' actions ordered by scheduled_for,
-- enabling efficient:
--   1. Fetching due pending actions for execution
--   2. Finding stale processing actions for recovery
--
-- This supplements (not replaces) the existing idx_scheduled_actions_pending
-- index which remains for backward compatibility.

CREATE INDEX IF NOT EXISTS idx_scheduled_actions_polling
ON scheduled_actions (scheduled_for, status)
WHERE status IN ('pending', 'processing');

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN scheduled_actions.started_processing_at IS 'UTC timestamp when action entered processing status (for timeout/recovery detection)';
