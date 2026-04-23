-- Add business_name column to leads
ALTER TABLE leads ADD COLUMN IF NOT EXISTS business_name TEXT;
