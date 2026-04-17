-- Migration 011: Add lost_notes column to leads table
-- Run in Supabase SQL Editor

ALTER TABLE leads ADD COLUMN IF NOT EXISTS lost_notes TEXT;
