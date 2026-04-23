-- Migration 015: Task enhancements — more statuses, sub-tasks, comments
-- Safe to re-run: YES (idempotent)

-- ── 1. Extend status constraint ─────────────────────────────────
DO $$
BEGIN
  ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_status_check;
  ALTER TABLE tasks ADD CONSTRAINT tasks_status_check
    CHECK (status IN ('open', 'in_progress', 'done', 'blocked'));
EXCEPTION WHEN duplicate_object THEN
  NULL;
END $$;

-- ── 2. Sub-tasks (self-referential) ─────────────────────────────
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);

-- ── 3. Task comments ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_comments (
  id         BIGSERIAL PRIMARY KEY,
  task_id    BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  body       TEXT NOT NULL,
  author     TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id);

DO $$
BEGIN
  ALTER TABLE task_comments ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS "anon can read task_comments" ON task_comments;
  CREATE POLICY "anon can read task_comments" ON task_comments FOR SELECT USING (true);
  DROP POLICY IF EXISTS "anon can insert task_comments" ON task_comments;
  CREATE POLICY "anon can insert task_comments" ON task_comments FOR INSERT WITH CHECK (true);
  DROP POLICY IF EXISTS "anon can delete task_comments" ON task_comments;
  CREATE POLICY "anon can delete task_comments" ON task_comments FOR DELETE USING (true);
END $$;

-- ── 4. Update v_team_metrics: overdue = non-done past due date ──
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
  WHERE created_at BETWEEN week_start AND week_end AND changed_by IS NOT NULL
  GROUP BY changed_by
),
created AS (
  SELECT assigned_to AS member, COUNT(*) AS deals_created
  FROM leads, week_bounds
  WHERE created_at BETWEEN week_start AND week_end AND assigned_to IS NOT NULL
  GROUP BY assigned_to
),
task_stats AS (
  SELECT
    assigned_to AS member,
    COUNT(*) FILTER (WHERE status = 'done') AS tasks_done,
    COUNT(*) FILTER (WHERE status != 'done' AND parent_id IS NULL AND due_date < CURRENT_DATE) AS tasks_overdue
  FROM tasks WHERE assigned_to IS NOT NULL
  GROUP BY assigned_to
),
contact_stats AS (
  SELECT
    assigned_to AS member,
    ROUND(AVG(EXTRACT(EPOCH FROM (NOW() - COALESCE(last_activity_at, created_at))) / 86400)::numeric, 1) AS avg_days_no_contact
  FROM leads
  WHERE status NOT IN ('converted', 'lost') AND assigned_to IS NOT NULL
  GROUP BY assigned_to
)
SELECT
  tm.name AS member,
  COALESCE(c.deals_created, 0) AS deals_created,
  COALESCE(a.deals_advanced, 0) AS deals_advanced,
  COALESCE(t.tasks_done, 0) AS tasks_done,
  COALESCE(t.tasks_overdue, 0) AS tasks_overdue,
  COALESCE(cs.avg_days_no_contact, 0) AS avg_days_no_contact
FROM team_members tm
LEFT JOIN advances a ON a.member = tm.name
LEFT JOIN created c ON c.member = tm.name
LEFT JOIN task_stats t ON t.member = tm.name
LEFT JOIN contact_stats cs ON cs.member = tm.name;
