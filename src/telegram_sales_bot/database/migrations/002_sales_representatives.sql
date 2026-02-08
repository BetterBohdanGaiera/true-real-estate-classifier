-- Migration: 002_sales_representatives
-- Description: Create sales_representatives table for managing sales team members
-- Created: 2026-01-21
--
-- This migration creates the sales_representatives table used by the Registry Bot
-- to manage sales team registration and track their status.
--
-- Usage: psql $DATABASE_URL -f migrations/002_sales_representatives.sql

-- =============================================================================
-- SALES_REPRESENTATIVES TABLE
-- =============================================================================
-- Stores all registered sales representatives with their profile and status.

CREATE TABLE IF NOT EXISTS sales_representatives (
    -- Primary key: UUID auto-generated for each rep
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Telegram identification
    telegram_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(255),

    -- Profile information
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,

    -- Status tracking
    -- 'pending'   - registered, awaiting approval (not used in auto-approve mode)
    -- 'active'    - approved and active
    -- 'suspended' - temporarily disabled
    -- 'removed'   - permanently removed
    status VARCHAR(50) DEFAULT 'active',

    -- Google Calendar integration
    calendar_account_name VARCHAR(255),

    -- Admin privileges
    is_admin BOOLEAN DEFAULT FALSE,

    -- Timestamps
    registered_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES sales_representatives(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for fast lookup by telegram_id
-- Used when: checking if user is registered, getting rep by telegram ID
CREATE INDEX IF NOT EXISTS idx_sales_reps_telegram_id
    ON sales_representatives(telegram_id);

-- Index for filtering by status
-- Used when: listing active reps, assigning prospects
CREATE INDEX IF NOT EXISTS idx_sales_reps_status
    ON sales_representatives(status);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE sales_representatives IS 'Stores registered sales representatives for the Registry Bot';
COMMENT ON COLUMN sales_representatives.id IS 'Unique identifier for the sales rep (UUID)';
COMMENT ON COLUMN sales_representatives.telegram_id IS 'Telegram user ID for the sales rep';
COMMENT ON COLUMN sales_representatives.telegram_username IS 'Telegram @username (without @)';
COMMENT ON COLUMN sales_representatives.name IS 'Full name of the sales rep';
COMMENT ON COLUMN sales_representatives.email IS 'Corporate email address';
COMMENT ON COLUMN sales_representatives.status IS 'Current status: pending, active, suspended, removed';
COMMENT ON COLUMN sales_representatives.calendar_account_name IS 'Google Calendar account for meeting scheduling';
COMMENT ON COLUMN sales_representatives.is_admin IS 'Whether this rep has admin privileges';
COMMENT ON COLUMN sales_representatives.registered_at IS 'When the rep completed registration';
COMMENT ON COLUMN sales_representatives.approved_at IS 'When the rep was approved (auto-approved in current mode)';
COMMENT ON COLUMN sales_representatives.approved_by IS 'UUID of admin who approved (NULL if auto-approved)';
