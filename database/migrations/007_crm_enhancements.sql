-- ============================================================
-- CRM Enhancements — Media Campaigns & Live Chat
-- ============================================================

-- 1. Campaign media support
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS media_url TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS media_type TEXT CHECK (media_type IN ('photo', 'video'));

-- 2. Live Chat tracking
ALTER TABLE leads ADD COLUMN IF NOT EXISTS live_chat BOOLEAN DEFAULT FALSE; -- TRUE while user has an active live chat session
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_sent BOOLEAN DEFAULT TRUE; -- True for user/bot messages, False for CRM messages pending delivery
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT TRUE; 

-- Update is_sent to TRUE for existing messages
UPDATE conversations SET is_sent = TRUE WHERE is_sent IS NULL;
ALTER TABLE conversations ALTER COLUMN is_sent SET NOT NULL;
ALTER TABLE conversations ALTER COLUMN is_sent SET DEFAULT TRUE;

-- Update is_read logic: 
-- Non-user messages are read by default.
-- When a user sends a message, it should be is_read=FALSE.
ALTER TABLE conversations ALTER COLUMN is_read SET DEFAULT TRUE;

-- 3. Notify CRM of new messages (Supabase Realtime)
-- Add conversations to realtime publication only if not already a member
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'conversations'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE conversations;
  END IF;
END $$;
