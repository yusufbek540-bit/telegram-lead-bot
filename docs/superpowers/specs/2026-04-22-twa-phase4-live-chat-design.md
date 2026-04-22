# TWA Phase 4: Manager Live-Chat Bridge — Design

## Goal

Let a client in the TWA send a message to a real manager via a "Chat with manager" button. The manager receives the message in Telegram with a Reply button. The reply is routed back to the client as a Telegram DM. All messages are logged to the shared `conversations` table and shown in the CRM with a `👤 Live` badge.

## Architecture

The TWA gains a "Chat with manager" panel on the Contact tab. On submit, `tg.sendData({ action: 'live_chat_request', message })` fires (closes the TWA — intentional). The bot receives the action, sets `live_chat = True` on the lead, saves the message to `conversations` with `source = 'live_chat'`, notifies the assigned manager (or all admins) with an inline Reply button. Admin taps Reply → ForceReply prompt → admin types response → bot DMs the client and logs the reply. The CRM conversation view shows a `👤 Live` badge on messages with `source = 'live_chat'`.

## Tech Stack

Vanilla HTML/CSS/JS (TWA), aiogram 3.x, Supabase, Python, React (CRM)

---

## Components

### 1. TWA — Contact tab additions (`twa/index.html`)

**New UI elements:**
- A `<button class="cta-btn" id="chatManagerBtn" data-t="chat_btn">` below the contact form
- A slide-up panel `<div id="chatPanel">` containing:
  - `<textarea id="chatInput" data-t="chat_placeholder" placeholder="...">` 
  - `<button onclick="sendLiveChat()" data-t="chat_send">`
  - A note: `<p data-t="chat_note">` ("We'll reply in Telegram shortly" / "Ответим в Telegram")

**JS function `sendLiveChat()`:**
```javascript
function sendLiveChat() {
    const msg = document.getElementById('chatInput').value.trim();
    if (!msg) return;
    tg.sendData(JSON.stringify({ action: 'live_chat_request', message: msg }));
}
```

**New translation keys (uz / ru):**

| Key | uz | ru |
|-----|----|----|
| `chat_btn` | `💬 Menejer bilan gaplashing` | `💬 Написать менеджеру` |
| `chat_placeholder` | `Xabaringizni yozing...` | `Напишите ваш вопрос...` |
| `chat_send` | `Yuborish` | `Отправить` |
| `chat_note` | `Tez orada Telegram orqali javob beramiz` | `Ответим в Telegram в ближайшее время` |

---

### 2. Database migration (`database/migrations/016_live_chat_source.sql`)

```sql
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'ai_chat';
UPDATE conversations SET source = 'ai_chat' WHERE source IS NULL;
```

---

### 3. Bot — `db_service.py` (`save_message`)

Add optional `source` parameter (default `'ai_chat'`):

```python
async def save_message(self, telegram_id: int, role: str, message: str,
                       is_sent: bool = True, source: str = 'ai_chat'):
    is_read = False if role == "user" else True
    self.client.table("conversations").insert({
        "telegram_id": telegram_id,
        "role": role,
        "message": message,
        "is_sent": is_sent,
        "is_read": is_read,
        "source": source,
    }).execute()
    ...
```

All existing callers pass no `source` so they default to `'ai_chat'` — no other changes needed.

---

### 4. Bot — `twa.py` (new action branch)

New branch in `handle_web_app_data`:

```python
elif action == "live_chat_request":
    msg_text = data.get("message", "").strip()
    if not msg_text:
        return

    # Activate live chat session
    await db.update_lead(user.id, live_chat=True)
    await db.track_event(user.id, "live_chat_requested", {"source": "twa"})

    # Save client message
    await db.save_message(user.id, "user", msg_text, source="live_chat")

    # Notify manager / admins (with Reply button — see live_chat.py)
    from bot.handlers.live_chat import _notify_managers
    lead = await db.get_lead(user.id)
    await _notify_managers(message.bot, lead, message_text=msg_text)

    # Confirm to client
    confirm = "✅ Xabaringiz yuborildi! Tez orada Telegram orqali javob beramiz." if lang != "ru" \
        else "✅ Сообщение отправлено! Мы ответим в Telegram в ближайшее время."
    await message.answer(confirm)
```

---

### 5. Bot — `live_chat.py` (admin reply mechanism)

**In-memory reply routing dict** (module level):
```python
# Maps admin telegram_id → client telegram_id while a reply is pending
active_replies: dict[int, int] = {}
```

**Modify `_notify_managers`** — add `reply_markup` with inline Reply button:
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

kb = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="💬 Reply", callback_data=f"lr:{lead['telegram_id']}")
]])

for tid in target_ids:
    try:
        await bot.send_message(tid, text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
```

**New `cb_live_reply` callback handler:**
```python
@router.callback_query(F.data.startswith("lr:"))
async def cb_live_reply(callback: CallbackQuery):
    client_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id

    # Get client name for context
    lead = await db.get_lead(client_id)
    name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "User"

    active_replies[admin_id] = client_id

    from aiogram.types import ForceReply
    await callback.message.answer(
        f"↩️ Replying to <b>{escape(name)}</b>. Type your message:",
        parse_mode="HTML",
        reply_markup=ForceReply(selective=True),
    )
    await callback.answer()
```

**New `handle_admin_reply` message handler** (catches admin messages while reply is pending — uses a plain `F.text` filter with an early-return guard since aiogram 3.x doesn't support dynamic sets in `.in_()`):
```python
@router.message(F.text)
async def handle_admin_reply(message: Message):
    admin_id = message.from_user.id
    client_id = active_replies.pop(admin_id, None)
    if not client_id:
        return

    # Send reply to client
    await message.bot.send_message(client_id, message.text)

    # Save to conversations
    await db.save_message(client_id, "assistant", message.text, source="live_chat")

    # Confirm to admin
    lead = await db.get_lead(client_id)
    name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "User"
    await message.answer(f"✅ Sent to {escape(name)}")
```

**Handler registration order in `live_chat.py`:** `handle_admin_reply` must be registered before `ai_chat` to avoid the admin's reply being processed as an AI chat message. Since `live_chat` router is already registered before `ai_chat` in `main.py` (line 51-52), this is satisfied automatically.

---

### 6. CRM — conversation bubble badge (`crm/index.html`)

At line 2813, the bubble render currently:
```jsx
<div key={m.id} className={`chat-bubble ${m.role === 'user' ? 'chat-user' : 'chat-assistant'} ...`}>
```

Change to:
```jsx
<div key={m.id} className={`chat-bubble ${m.role === 'user' ? 'chat-user' : 'chat-assistant'} ...`}>
  {m.source === 'live_chat' && (
    <span style={{ fontSize: 10, opacity: 0.7, marginBottom: 2, display: 'block' }}>👤 Live</span>
  )}
  {m.message}
</div>
```

Also update the Supabase `select` at line 2152 to include the `source` column:
```javascript
supabase.from('conversations').select('*, source').eq('telegram_id', lead.telegram_id)...
```
(Currently `select('*')` — `*` already includes `source` once the column exists, so no change needed.)

---

## Data Flow

```
Client taps "Chat with manager" in TWA
  → types message → tg.sendData(live_chat_request) → TWA closes
  → bot receives web_app_data
  → lead.live_chat = True
  → conversations.insert(role=user, source=live_chat)
  → admin notified with Reply button
  → client gets "Message sent" confirmation

Admin taps Reply button
  → active_replies[admin_id] = client_id
  → ForceReply prompt sent to admin

Admin types reply
  → handle_admin_reply fires
  → bot.send_message(client_id, reply)
  → conversations.insert(role=assistant, source=live_chat)
  → admin gets "✅ Sent to [Name]"

CRM view
  → conversations fetched with source column
  → live_chat messages show 👤 Live badge
```

## Edge Cases

- **Empty message**: `sendLiveChat()` returns early if input is blank; bot handler also returns if `msg_text` is empty.
- **Admin sends message without tapping Reply**: `handle_admin_reply` only fires when `admin_id in active_replies` — no accidental routing.
- **Multiple admins notified**: Each gets their own Reply button. First one to reply wins; `active_replies` is per-admin so they don't interfere.
- **Client sends follow-up messages in Telegram**: `ai_chat.py` already detects `lead.live_chat == True` and forwards to managers — existing behavior, no changes needed.
