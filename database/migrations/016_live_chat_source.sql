-- 016: add source column to conversations to distinguish AI chat from live chat
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'ai_chat';
UPDATE conversations SET source = 'ai_chat' WHERE source IS NULL;
