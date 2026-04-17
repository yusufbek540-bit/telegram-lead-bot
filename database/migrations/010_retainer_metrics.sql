-- Migration 010: Retainer, Project, and Revenue Metrics
-- Creates tables for storing client data and tracking revenue events 
-- Supports retainer, project-based, and one-time clients using USD as default

DO $$
BEGIN
    -- Only run if table doesn't already exist to keep it idempotent
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'clients') THEN

        CREATE TABLE clients (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
            client_type TEXT NOT NULL DEFAULT 'retainer' CHECK (client_type IN ('retainer', 'project', 'one-time')),
            
            -- Retainer specific fields
            retainer_amount NUMERIC DEFAULT 0,
            retainer_start_date DATE,
            retainer_end_date DATE,
            retainer_status TEXT CHECK (retainer_status IN ('active', 'paused', 'cancelled') OR retainer_status IS NULL),
            last_renewal_date DATE,
            
            -- General client info
            currency TEXT NOT NULL DEFAULT 'USD',
            services JSONB DEFAULT '[]',
            churn_reason TEXT,
            
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_clients_telegram UNIQUE (telegram_id)
        );

        CREATE INDEX idx_clients_type ON clients(client_type);
        CREATE INDEX idx_clients_status ON clients(retainer_status);

    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'revenue_events') THEN

        CREATE TABLE revenue_events (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
            event_date DATE NOT NULL,
            event_month TEXT NOT NULL, -- e.g. '2026-04'
            amount NUMERIC NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            event_type TEXT NOT NULL CHECK (event_type IN ('payment', 'upgrade', 'downgrade', 'cancellation', 'new_retainer', 'project_milestone', 'one_time_fee')),
            services JSONB DEFAULT '[]',
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX idx_revenue_events_date ON revenue_events(event_date);
        CREATE INDEX idx_revenue_events_month ON revenue_events(event_month);
        CREATE INDEX idx_revenue_events_type ON revenue_events(event_type);
        
    END IF;
END $$;

-- Drop views if they exist so we can recreate them easily (idempotent)
DROP VIEW IF EXISTS v_mrr_summary CASCADE;
DROP VIEW IF EXISTS v_monthly_revenue_summary CASCADE;

-- ==========================================
-- VIEW 1: MRR & ARPC Summary 
-- ==========================================
CREATE OR REPLACE VIEW v_mrr_summary AS
SELECT 
    currency,
    SUM(retainer_amount) as total_mrr,
    COUNT(*) as active_clients,
    CASE 
        WHEN COUNT(*) > 0 THEN ROUND((SUM(retainer_amount) / COUNT(*))::numeric, 2)
        ELSE 0 
    END as arpc
FROM clients
WHERE client_type = 'retainer' AND retainer_status = 'active'
GROUP BY currency;

-- ==========================================
-- VIEW 2: Monthly Revenue Events Aggregation
-- ==========================================
CREATE OR REPLACE VIEW v_monthly_revenue_summary AS
SELECT 
    event_month,
    currency,
    -- Basic collection
    SUM(CASE WHEN event_type IN ('payment', 'new_retainer', 'project_milestone', 'one_time_fee') THEN amount ELSE 0 END) as collected_revenue,
    -- NRR / Expansion Math
    SUM(CASE WHEN event_type = 'upgrade' THEN amount ELSE 0 END) as expansion_revenue,
    SUM(CASE WHEN event_type = 'downgrade' THEN amount ELSE 0 END) as contraction_revenue,
    SUM(CASE WHEN event_type = 'cancellation' THEN amount ELSE 0 END) as churned_mrr
FROM revenue_events
GROUP BY event_month, currency
ORDER BY event_month DESC;

-- Enable RLS for clients and revenue_events so CRM can access from frontend
DO $$
BEGIN
    -- Clients RLS
    ALTER TABLE IF EXISTS clients ENABLE ROW LEVEL SECURITY;
    
    DROP POLICY IF EXISTS "anon can read clients" ON clients;
    CREATE POLICY "anon can read clients" ON clients FOR SELECT USING (true);
    
    DROP POLICY IF EXISTS "anon can insert clients" ON clients;
    CREATE POLICY "anon can insert clients" ON clients FOR INSERT WITH CHECK (true);
    
    DROP POLICY IF EXISTS "anon can update clients" ON clients;
    CREATE POLICY "anon can update clients" ON clients FOR UPDATE USING (true);
    
    DROP POLICY IF EXISTS "anon can delete clients" ON clients;
    CREATE POLICY "anon can delete clients" ON clients FOR DELETE USING (true);

    -- Revenue Events RLS
    ALTER TABLE IF EXISTS revenue_events ENABLE ROW LEVEL SECURITY;
    
    DROP POLICY IF EXISTS "anon can read revenue_events" ON revenue_events;
    CREATE POLICY "anon can read revenue_events" ON revenue_events FOR SELECT USING (true);
    
    DROP POLICY IF EXISTS "anon can insert revenue_events" ON revenue_events;
    CREATE POLICY "anon can insert revenue_events" ON revenue_events FOR INSERT WITH CHECK (true);
    
    DROP POLICY IF EXISTS "anon can update revenue_events" ON revenue_events;
    CREATE POLICY "anon can update revenue_events" ON revenue_events FOR UPDATE USING (true);
    
    DROP POLICY IF EXISTS "anon can delete revenue_events" ON revenue_events;
    CREATE POLICY "anon can delete revenue_events" ON revenue_events FOR DELETE USING (true);
END $$;
