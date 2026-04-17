-- Migration 013: Questionnaire columns on leads table
-- Run in Supabase SQL Editor

ALTER TABLE leads ADD COLUMN IF NOT EXISTS business_type TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS business_type_other TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS service_interest JSONB DEFAULT '[]';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS current_marketing TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS budget_range TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS questionnaire_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS questionnaire_completed_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS questionnaire_step INTEGER DEFAULT 0;
