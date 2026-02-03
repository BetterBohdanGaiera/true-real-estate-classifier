-- Migration: 003_test_prospects
-- Description: Create test_prospects table for managing test leads
-- Created: 2026-01-21
--
-- This migration creates the test_prospects table used for assigning
-- test leads to sales representatives for practice and validation.
--
-- Usage: psql $DATABASE_URL -f migrations/003_test_prospects.sql

-- =============================================================================
-- TEST_PROSPECTS TABLE
-- =============================================================================
-- Stores test prospects that can be assigned to sales reps for practice.

CREATE TABLE IF NOT EXISTS test_prospects (
    -- Primary key: String ID for easy reference
    id VARCHAR(255) PRIMARY KEY,

    -- Telegram identification (username with @)
    telegram_id VARCHAR(255) NOT NULL,

    -- Profile information
    name VARCHAR(255) NOT NULL,
    context TEXT,
    email VARCHAR(255),
    notes TEXT,

    -- Status tracking
    -- 'unreached'       - not yet contacted
    -- 'contacted'       - initial contact made
    -- 'in_conversation' - actively chatting
    -- 'converted'       - became a client
    -- 'archived'        - no longer active
    status VARCHAR(50) DEFAULT 'unreached',

    -- Assignment tracking
    assigned_rep_id UUID REFERENCES sales_representatives(id),
    last_contact_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for filtering by status
-- Used when: finding unreached prospects, listing by status
CREATE INDEX IF NOT EXISTS idx_test_prospects_status
    ON test_prospects(status);

-- Index for filtering by assigned rep
-- Used when: getting prospects for a specific rep
CREATE INDEX IF NOT EXISTS idx_test_prospects_assigned_rep
    ON test_prospects(assigned_rep_id);

-- =============================================================================
-- SEED TEST DATA
-- =============================================================================
-- Insert test prospects for sales rep training and system validation

INSERT INTO test_prospects (id, telegram_id, name, context, status, email, notes)
VALUES
    ('test_001', '@test_buyer_alex', 'Алексей Петров',
     'Интересуется виллой в Чангу, бюджет $300-500k',
     'unreached', 'alex.petrov@gmail.com',
     'Видел рекламу в Instagram'),

    ('test_002', '@test_investor_maria', 'Мария Козлова',
     'Инвестор, рассматривает апартаменты для сдачи',
     'unreached', 'm.kozlova@yandex.ru',
     'Рекомендация от клиента'),

    ('test_003', '@test_family_dmitry', 'Дмитрий Новиков',
     'Семья с детьми, ищут дом для переезда',
     'unreached', 'd.novikov@mail.ru',
     'Планирует переезд через 6 месяцев')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE test_prospects IS 'Stores test prospects for sales rep training and validation';
COMMENT ON COLUMN test_prospects.id IS 'Unique identifier for the prospect (string format: test_XXX)';
COMMENT ON COLUMN test_prospects.telegram_id IS 'Telegram @username of the prospect';
COMMENT ON COLUMN test_prospects.name IS 'Full name of the prospect';
COMMENT ON COLUMN test_prospects.context IS 'Background context about the prospect interest';
COMMENT ON COLUMN test_prospects.status IS 'Current status: unreached, contacted, in_conversation, converted, archived';
COMMENT ON COLUMN test_prospects.assigned_rep_id IS 'UUID of the sales rep assigned to this prospect';
COMMENT ON COLUMN test_prospects.email IS 'Email address for meeting invitations';
COMMENT ON COLUMN test_prospects.notes IS 'Additional notes about the prospect';
COMMENT ON COLUMN test_prospects.last_contact_at IS 'When the prospect was last contacted';
