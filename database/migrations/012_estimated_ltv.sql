-- Migration 012: Add estimated_ltv column to clients table
-- Run in Supabase SQL Editor

ALTER TABLE clients ADD COLUMN IF NOT EXISTS estimated_ltv NUMERIC(12, 2);
