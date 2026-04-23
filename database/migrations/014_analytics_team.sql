-- Migration 014: Analytics views + Tasks table
-- Run in Supabase SQL Editor
-- Requires: crm_extension.sql (defines status_history) to have been run first
-- Safe to re-run: YES (idempotent)

-- ── 1. TASKS TABLE ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
  id          BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT REFERENCES leads(telegram_id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  description TEXT,
  assigned_to TEXT,
  due_date    DATE,
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
  created_by  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);

DO $$
BEGIN
  ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

  DROP POLICY IF EXISTS "anon can read tasks"   ON tasks;
  CREATE POLICY "anon can read tasks"   ON tasks FOR SELECT USING (true);

  DROP POLICY IF EXISTS "anon can insert tasks" ON tasks;
  CREATE POLICY "anon can insert tasks" ON tasks FOR INSERT WITH CHECK (true);

  DROP POLICY IF EXISTS "anon can update tasks" ON tasks;
  CREATE POLICY "anon can update tasks" ON tasks FOR UPDATE USING (true);

  DROP POLICY IF EXISTS "anon can delete tasks" ON tasks;
  CREATE POLICY "anon can delete tasks" ON tasks FOR DELETE USING (true);
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tasks_updated_at'
  ) THEN
    CREATE TRIGGER tasks_updated_at
      BEFORE UPDATE ON tasks
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;

-- ── 2. v_deal_cycle VIEW ────────────────────────────────────────
-- Avg days from lead creation to first conversion, grouped by month
CREATE OR REPLACE VIEW v_deal_cycle AS
SELECT
  TO_CHAR(DATE_TRUNC('month', l.created_at AT TIME ZONE 'Asia/Tashkent'), 'YYYY-MM') AS month,
  ROUND(AVG(
    EXTRACT(EPOCH FROM (sh.created_at - l.created_at)) / 86400
  )::numeric, 1) AS avg_days,
  COUNT(*) AS deal_count
FROM leads l
JOIN LATERAL (
  SELECT created_at
  FROM status_history
  WHERE telegram_id = l.telegram_id
    AND new_status = 'converted'
  ORDER BY created_at ASC
  LIMIT 1
) sh ON true
GROUP BY 1
ORDER BY 1 DESC;

-- ── 3. v_repeat_clients VIEW ────────────────────────────────────
CREATE OR REPLACE VIEW v_repeat_clients AS
SELECT
  (SELECT COUNT(*) FROM (
    SELECT telegram_id FROM revenue_events
    GROUP BY telegram_id HAVING COUNT(*) >= 2
  ) x) AS repurchase_count,
  (SELECT COUNT(*) FROM (
    SELECT telegram_id FROM status_history
    WHERE new_status = 'converted'
    GROUP BY telegram_id HAVING COUNT(*) >= 2
  ) x) AS reengaged_count,
  (SELECT COUNT(*) FROM leads WHERE status = 'converted') AS total_converted;

-- ── 4. v_team_metrics VIEW ─────────────────────────────────────
CREATE OR REPLACE VIEW v_team_metrics AS
WITH week_bounds AS (
  SELECT
    (DATE_TRUNC('week', NOW() AT TIME ZONE 'Asia/Tashkent')
      AT TIME ZONE 'Asia/Tashkent')::timestamptz AS week_start,
    ((DATE_TRUNC('week', NOW() AT TIME ZONE 'Asia/Tashkent')
      + INTERVAL '6 days 23:59:59')
      AT TIME ZONE 'Asia/Tashkent')::timestamptz AS week_end
),
advances AS (
  SELECT changed_by AS member, COUNT(*) AS deals_advanced
  FROM status_history, week_bounds
  WHERE created_at BETWEEN week_start AND week_end
    AND changed_by IS NOT NULL
  GROUP BY changed_by
),
created AS (
  SELECT assigned_to AS member, COUNT(*) AS deals_created
  FROM leads, week_bounds
  WHERE created_at BETWEEN week_start AND week_end
    AND assigned_to IS NOT NULL
  GROUP BY assigned_to
),
task_stats AS (
  SELECT
    assigned_to AS member,
    COUNT(*) FILTER (WHERE status = 'done')                              AS tasks_done,
    COUNT(*) FILTER (WHERE status = 'open' AND due_date < CURRENT_DATE) AS tasks_overdue
  FROM tasks
  WHERE assigned_to IS NOT NULL
  GROUP BY assigned_to
),
contact_stats AS (
  SELECT
    assigned_to AS member,
    ROUND(AVG(
      EXTRACT(EPOCH FROM (NOW() - COALESCE(last_activity_at, created_at))) / 86400
    )::numeric, 1) AS avg_days_no_contact
  FROM leads
  WHERE status NOT IN ('converted', 'lost')
    AND assigned_to IS NOT NULL
  GROUP BY assigned_to
)
SELECT
  tm.name                              AS member,
  COALESCE(c.deals_created, 0)        AS deals_created,
  COALESCE(a.deals_advanced, 0)       AS deals_advanced,
  COALESCE(t.tasks_done, 0)           AS tasks_done,
  COALESCE(t.tasks_overdue, 0)        AS tasks_overdue,
  COALESCE(cs.avg_days_no_contact, 0) AS avg_days_no_contact
FROM team_members tm
LEFT JOIN advances    a  ON a.member  = tm.name
LEFT JOIN created     c  ON c.member  = tm.name
LEFT JOIN task_stats  t  ON t.member  = tm.name
LEFT JOIN contact_stats cs ON cs.member = tm.name;
