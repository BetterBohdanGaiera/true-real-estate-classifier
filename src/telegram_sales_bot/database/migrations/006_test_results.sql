-- Migration: 006_test_results
-- Description: Create tables for storing automated stress test results and assessments
-- Created: 2026-01-29
--
-- This migration creates tables for persisting conversation test results from
-- the automated stress testing system. Enables tracking test scores over time,
-- analyzing trends, and validating conversation quality.
--
-- Usage: psql $DATABASE_URL -f migrations/006_test_results.sql

-- =============================================================================
-- TEST_RESULTS TABLE
-- =============================================================================
-- Stores complete results from each automated conversation test.
-- Links to test_assessments for detailed quality scoring.

CREATE TABLE IF NOT EXISTS test_results (
    -- Primary key: UUID auto-generated for each test result
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scenario identification
    scenario_name VARCHAR(255) NOT NULL,  -- e.g., "Rapid Fire Burst", "Skeptical Investor"

    -- Persona that was simulated
    persona_id VARCHAR(255) NOT NULL,  -- Persona name from scenario definition

    -- Conversation outcome from ConversationOutcome enum
    -- Values: 'zoom_scheduled', 'follow_up_proposed', 'client_refused', 'escalated', 'inconclusive'
    outcome VARCHAR(50) NOT NULL,

    -- Overall assessment score (0-100) from ConversationAssessment
    overall_score INTEGER NOT NULL,

    -- Conversation statistics
    total_turns INTEGER NOT NULL,  -- Number of conversation turns (agent + persona)
    duration_seconds FLOAT NOT NULL,  -- How long the test took to complete

    -- Success metrics
    email_collected BOOLEAN DEFAULT FALSE,  -- Whether prospect provided email
    call_scheduled BOOLEAN DEFAULT FALSE,  -- Whether Zoom meeting was scheduled (key success metric)

    -- Actions used by agent during conversation
    -- Example: {"respond": 5, "schedule": 1, "check_availability": 1}
    agent_actions_used JSONB DEFAULT '{}',

    -- When the test was executed (stored in UTC)
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Audit timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TEST_ASSESSMENTS TABLE
-- =============================================================================
-- Stores detailed quality assessments for each test result.
-- Contains all fields from ConversationAssessment model.
-- One-to-one relationship with test_results.

CREATE TABLE IF NOT EXISTS test_assessments (
    -- Primary key: UUID auto-generated for each assessment
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to test_results
    -- CASCADE delete: removing test result removes its assessment
    test_result_id UUID NOT NULL REFERENCES test_results(id) ON DELETE CASCADE,

    -- Overall assessment score (0-100)
    overall_score INTEGER NOT NULL,

    -- Qualitative feedback arrays
    what_went_well TEXT[],  -- 3-5 specific positives
    areas_for_improvement TEXT[],  -- 3-5 specific suggestions
    critical_issues TEXT[],  -- Empty if none, contains error messages on failure

    -- Detailed scores (0-10 each)
    personalization_score INTEGER NOT NULL,  -- Used client name, personalized responses
    questions_score INTEGER NOT NULL,  -- Ended messages with open questions
    value_first_score INTEGER NOT NULL,  -- Explained value before asking for info

    -- BANT methodology coverage
    -- {"budget": bool, "authority": bool, "need": bool, "timeline": bool}
    bant_coverage JSONB NOT NULL,

    -- Methodology adherence scores (0-10)
    zmeyka_adherence INTEGER NOT NULL,  -- Followed Zmeyka methodology pattern
    objection_handling INTEGER NOT NULL,  -- Addressed objections professionally

    -- Binary quality checks
    zoom_close_attempt BOOLEAN NOT NULL,  -- Attempted to schedule Zoom meeting
    message_length_appropriate BOOLEAN NOT NULL,  -- Messages were 2-5 sentences
    formal_language BOOLEAN NOT NULL,  -- Used formal "Vy" in Russian
    no_forbidden_topics BOOLEAN NOT NULL,  -- Did not mention freehold for foreigners

    -- Recommended next steps for improvement
    recommended_actions TEXT[],

    -- Audit timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for filtering test results by scenario name
-- Used when: analyzing performance across different scenarios
CREATE INDEX IF NOT EXISTS idx_test_results_scenario
    ON test_results(scenario_name);

-- Index for time-based queries (descending for most recent first)
-- Used when: fetching recent tests, analyzing trends over time
CREATE INDEX IF NOT EXISTS idx_test_results_timestamp
    ON test_results(timestamp DESC);

-- Index for filtering by overall score
-- Used when: finding low/high performing tests, score distribution analysis
CREATE INDEX IF NOT EXISTS idx_test_results_score
    ON test_results(overall_score);

-- Index for efficient joins from assessments to results
-- Used when: fetching assessment details for a test result
CREATE INDEX IF NOT EXISTS idx_test_assessments_result
    ON test_assessments(test_result_id);

-- =============================================================================
-- COMMENTS
-- =============================================================================

-- Table comments
COMMENT ON TABLE test_results IS 'Stores automated stress test results for conversation quality tracking';
COMMENT ON TABLE test_assessments IS 'Stores detailed quality assessments linked to test results';

-- test_results column comments
COMMENT ON COLUMN test_results.id IS 'Unique identifier for the test result (UUID)';
COMMENT ON COLUMN test_results.scenario_name IS 'Name of the test scenario that was executed';
COMMENT ON COLUMN test_results.persona_id IS 'Name/identifier of the simulated persona';
COMMENT ON COLUMN test_results.outcome IS 'Final conversation outcome: zoom_scheduled, follow_up_proposed, client_refused, escalated, inconclusive';
COMMENT ON COLUMN test_results.overall_score IS 'Overall quality score from assessment (0-100)';
COMMENT ON COLUMN test_results.total_turns IS 'Total number of conversation turns (both agent and persona)';
COMMENT ON COLUMN test_results.duration_seconds IS 'Time taken to complete the test in seconds';
COMMENT ON COLUMN test_results.email_collected IS 'Whether the agent successfully collected prospect email';
COMMENT ON COLUMN test_results.call_scheduled IS 'Whether a Zoom meeting was successfully scheduled (key success metric)';
COMMENT ON COLUMN test_results.agent_actions_used IS 'JSON object tracking count of each action type used by agent';
COMMENT ON COLUMN test_results.timestamp IS 'UTC timestamp when the test was executed';
COMMENT ON COLUMN test_results.created_at IS 'UTC timestamp when the record was created';

-- test_assessments column comments
COMMENT ON COLUMN test_assessments.id IS 'Unique identifier for the assessment (UUID)';
COMMENT ON COLUMN test_assessments.test_result_id IS 'Foreign key to the associated test result';
COMMENT ON COLUMN test_assessments.overall_score IS 'Overall quality score (0-100)';
COMMENT ON COLUMN test_assessments.what_went_well IS 'Array of 3-5 specific positive observations';
COMMENT ON COLUMN test_assessments.areas_for_improvement IS 'Array of 3-5 specific improvement suggestions';
COMMENT ON COLUMN test_assessments.critical_issues IS 'Array of critical issues found (empty if none)';
COMMENT ON COLUMN test_assessments.personalization_score IS 'Score for personalization (0-10): using client name, tailoring responses';
COMMENT ON COLUMN test_assessments.questions_score IS 'Score for question quality (0-10): ending with open questions';
COMMENT ON COLUMN test_assessments.value_first_score IS 'Score for value-first approach (0-10): explaining value before asking';
COMMENT ON COLUMN test_assessments.bant_coverage IS 'JSON object tracking BANT discovery: {budget, authority, need, timeline}';
COMMENT ON COLUMN test_assessments.zmeyka_adherence IS 'Score for Zmeyka methodology adherence (0-10)';
COMMENT ON COLUMN test_assessments.objection_handling IS 'Score for objection handling quality (0-10)';
COMMENT ON COLUMN test_assessments.zoom_close_attempt IS 'Whether agent attempted to schedule a Zoom meeting';
COMMENT ON COLUMN test_assessments.message_length_appropriate IS 'Whether messages were appropriate length (2-5 sentences)';
COMMENT ON COLUMN test_assessments.formal_language IS 'Whether formal language (Vy) was used in Russian';
COMMENT ON COLUMN test_assessments.no_forbidden_topics IS 'Whether agent avoided forbidden topics (freehold for foreigners)';
COMMENT ON COLUMN test_assessments.recommended_actions IS 'Array of concrete next steps for improvement';
COMMENT ON COLUMN test_assessments.created_at IS 'UTC timestamp when the record was created';
