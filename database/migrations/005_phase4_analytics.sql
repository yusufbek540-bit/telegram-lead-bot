-- ============================================================
-- Phase 4 — Analytics & Reporting Migration
-- Safe to re-run (all statements are idempotent)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- Add robust multi-touch attribution mechanisms avoiding hard substitutions
ALTER TABLE leads ADD COLUMN IF NOT EXISTS original_source TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS touchpoints JSONB DEFAULT '[]'::JSONB;

-- In case existing records lack an original_source, safely retro-map their static current source parameters
UPDATE leads SET original_source = source WHERE original_source IS NULL;
