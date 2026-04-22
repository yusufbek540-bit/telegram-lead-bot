# TWA Phase 4: Manager Live-Chat Bridge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let clients tap "Chat with manager" in the TWA, type a message, and send it via `tg.sendData` — the bot notifies the assigned manager with a Reply button; the manager replies in Telegram; the reply is sent to the client as a DM and logged with a `👤 Live` badge in the CRM.

**Architecture:** Phase 1+2 TWA changes were lost locally (commits only lived in a deleted worktree) so Task 1 restores them first. A new `source` column on `conversations` distinguishes live-chat from AI-chat messages. A module-level `active_replies` dict in `live_chat.py` routes admin replies to the correct client. All changes are in the current working directory — no worktrees.

**Tech Stack:** Vanilla HTML/CSS/JS (TWA), aiogram 3.x, Supabase, Python, React (CRM), Vercel static hosting

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `twa/index.html` | Modify | Restore Phase 1+2, add chat button + panel + JS + translations |
| `database/migrations/016_live_chat_source.sql` | Create | Add `source` column to `conversations` table |
| `bot/services/db_service.py` | Modify | Add `source` param to `save_message` |
| `bot/handlers/live_chat.py` | Modify | Add Reply button, `active_replies` dict, `cb_live_reply`, `handle_admin_reply` |
| `bot/handlers/twa.py` | Modify | Add `live_chat_request` action branch |
| `crm/index.html` | Modify | Show `👤 Live` badge on messages with `source === 'live_chat'` |

---

## Task 1: Restore Phase 1 TWA — Onboarding Questionnaire

**Context:** The deployed Vercel TWA has Phase 1 (onboarding questionnaire). Locally, `twa/index.html` is at the pre-Phase-1 state (1202 lines, no onboarding). If Phase 4 is deployed without restoring Phase 1 first, the live site will lose the questionnaire.

**Files:**
- Modify: `twa/index.html`

- [ ] **Step 1: Follow Phase 1 plan with current-directory paths**

Open `docs/superpowers/plans/2026-04-18-twa-centric-phase1-onboarding.md` and execute all tasks from it, with this path substitution:

**Replace ALL occurrences of:**
```
.worktrees/twa-centric-phase1/
```
**With:**
```
(current directory — no prefix needed)
```

So `twa/index.html` stays `twa/index.html`. `bot/handlers/twa.py` stays `bot/handlers/twa.py`.

Execute every task in the Phase 1 plan (Tasks 1–8) against the current directory files.

- [ ] **Step 2: Verify file grew to ~2200+ lines**

```bash
wc -l twa/index.html
```

Expected: 2100–2300 lines (Phase 1 adds the onboarding questionnaire div + ~1000 lines of CSS/JS).

- [ ] **Step 3: Verify Python compiles**

```bash
python3 -c "from bot.handlers.twa import router; from bot.handlers.menu import router; from bot.handlers.start import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit TWA and bot changes**

```bash
git add twa/index.html bot/handlers/twa.py bot/handlers/menu.py bot/handlers/start.py
git commit -m "feat: restore Phase 1 TWA onboarding questionnaire (was lost with worktree)"
```

---

## Task 2: Restore Phase 2 TWA — Services & Portfolio

**Context:** Phase 2 fixed two critical `tg.sendData()` bugs (closing app on nav + service tap), added service CTA buttons, and project filter chips. Also lost with the worktree.

**Files:**
- Modify: `twa/index.html`

- [ ] **Step 1: Follow Phase 2 plan with current-directory paths**

Open `docs/superpowers/plans/2026-04-22-twa-centric-phase2-services-portfolio.md` and execute Tasks 1–7 (skip Task 8 — deploy happens at the end of the current plan).

Same path substitution as Task 1 above: remove `.worktrees/twa-centric-phase1/` prefix from all paths.

- [ ] **Step 2: Verify no `action: 'section_viewed'` remains**

```bash
grep -n "section_viewed" twa/index.html
```

Expected: no output (the sendData tracking block was removed).

- [ ] **Step 3: Verify trackService function is fixed**

```bash
grep -A 4 "function trackService" twa/index.html
```

Expected output contains `select.value = service` — not `sendData`.

- [ ] **Step 4: Commit**

```bash
git add twa/index.html bot/handlers/twa.py
git commit -m "feat: restore Phase 2 TWA — sendData fixes, service CTAs, project filter chips"
```

---

## Task 3: DB migration — add source column to conversations

**Files:**
- Create: `database/migrations/016_live_chat_source.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- 016: add source column to conversations to distinguish AI chat from live chat
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'ai_chat';
UPDATE conversations SET source = 'ai_chat' WHERE source IS NULL;
```

Save this as `database/migrations/016_live_chat_source.sql`.

- [ ] **Step 2: Run migration in Supabase**

Open the Supabase SQL Editor for this project and run the SQL above.

Verify by running:
```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'conversations' AND column_name = 'source';
```

Expected: one row with `column_name = source`, `data_type = text`, `column_default = 'ai_chat'`.

- [ ] **Step 3: Commit**

```bash
git add database/migrations/016_live_chat_source.sql
git commit -m "feat(db): add source column to conversations for live-chat badge"
```

---

## Task 4: Add source param to db_service.py save_message

**Files:**
- Modify: `bot/services/db_service.py:220`

The current signature is `save_message(self, telegram_id, role, message, is_sent=True)`. It needs an optional `source` param that defaults to `'ai_chat'` so all existing callers work unchanged.

- [ ] **Step 1: Find the current save_message method**

Open `bot/services/db_service.py`. Find line 220:

```python
    async def save_message(self, telegram_id: int, role: str, message: str, is_sent: bool = True):
        """Save a conversation message and update lead's last_activity_at."""
        # Unread logic: if user sends message, mark as unread (is_read=False)
        is_read = False if role == "user" else True
        
        self.client.table("conversations").insert(
            {
                "telegram_id": telegram_id,
                "role": role,
                "message": message,
                "is_sent": is_sent,
                "is_read": is_read,
            }
        ).execute()
```

- [ ] **Step 2: Replace with the updated version**

```python
    async def save_message(self, telegram_id: int, role: str, message: str,
                           is_sent: bool = True, source: str = "ai_chat"):
        """Save a conversation message and update lead's last_activity_at."""
        # Unread logic: if user sends message, mark as unread (is_read=False)
        is_read = False if role == "user" else True

        self.client.table("conversations").insert(
            {
                "telegram_id": telegram_id,
                "role": role,
                "message": message,
                "is_sent": is_sent,
                "is_read": is_read,
                "source": source,
            }
        ).execute()
```

- [ ] **Step 3: Verify module compiles**

```bash
python3 -c "from bot.services.db_service import db; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add bot/services/db_service.py
git commit -m "feat(db): add source param to save_message for live-chat tracking"
```

---

## Task 5: Admin reply mechanism in live_chat.py

**Files:**
- Modify: `bot/handlers/live_chat.py`

Three additions: (1) module-level `active_replies` dict, (2) Reply button on admin notifications, (3) `cb_live_reply` callback, (4) `handle_admin_reply` message handler.

- [ ] **Step 1: Add imports and active_replies dict**

Open `bot/handlers/live_chat.py`. The current imports at the top are:
```python
from __future__ import annotations
"""
Live chat handler — ...
"""
from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import main_menu_keyboard, back_to_menu_keyboard
```

Replace with:
```python
from __future__ import annotations
"""
Live chat handler — lets users request a real manager and enables
two-way forwarding while the session is active.
"""
from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, ForceReply,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import main_menu_keyboard, back_to_menu_keyboard

# Maps admin telegram_id → client telegram_id while a reply is in flight.
# Single-instance bot only — in-memory is sufficient.
active_replies: dict[int, int] = {}
```

- [ ] **Step 2: Modify _notify_managers to include Reply button**

Find the `_notify_managers` helper (~line 60). The current loop:

```python
    for tid in target_ids:
        try:
            await bot.send_message(tid, text, parse_mode="HTML")
        except Exception:
            pass
```

Replace with:

```python
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💬 Reply",
            callback_data=f"lr:{lead['telegram_id']}",
        )
    ]])

    for tid in target_ids:
        try:
            await bot.send_message(tid, text, parse_mode="HTML", reply_markup=reply_kb)
        except Exception:
            pass
```

- [ ] **Step 3: Add cb_live_reply callback handler**

After the `cb_live_chat_request` handler (~line 36), add:

```python
@router.callback_query(F.data.startswith("lr:"))
async def cb_live_reply(callback: CallbackQuery):
    """Admin taps Reply button on a live-chat notification."""
    client_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id

    lead = await db.get_lead(client_id)
    name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "User"

    active_replies[admin_id] = client_id

    await callback.message.answer(
        f"↩️ Replying to <b>{escape(name)}</b>. Type your message:",
        parse_mode="HTML",
        reply_markup=ForceReply(selective=True),
    )
    await callback.answer()
```

- [ ] **Step 4: Add handle_admin_reply message handler**

After `cb_live_reply`, add:

```python
@router.message(F.text)
async def handle_admin_reply(message: Message):
    """Catch admin text messages when a reply is pending and route to client."""
    admin_id = message.from_user.id
    client_id = active_replies.pop(admin_id, None)
    if not client_id:
        return  # Not in reply mode — let ai_chat handle it

    # Send reply to client
    await message.bot.send_message(client_id, message.text)

    # Save to shared conversations (source=live_chat so CRM shows badge)
    await db.save_message(client_id, "assistant", message.text, source="live_chat")

    # Confirm to admin
    lead = await db.get_lead(client_id)
    name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "User"
    await message.answer(f"✅ Sent to <b>{escape(name)}</b>", parse_mode="HTML")
```

- [ ] **Step 5: Verify module compiles**

```bash
python3 -c "from bot.handlers.live_chat import router, active_replies; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add bot/handlers/live_chat.py
git commit -m "feat(bot): add admin Reply button and reply routing for live chat"
```

---

## Task 6: Add live_chat_request action to twa.py

**Files:**
- Modify: `bot/handlers/twa.py`

Add a new branch after the existing `elif action == "service_clicked":` block.

- [ ] **Step 1: Find the end of handle_web_app_data**

Open `bot/handlers/twa.py`. Find the last `elif` branch at the bottom of `handle_web_app_data`:

```python
    elif action == "service_clicked":
        await db.track_event(
            user.id, "twa_service_click", {"service": data.get("service", "")}
        )
```

- [ ] **Step 2: Add the new branch after it**

```python
    elif action == "live_chat_request":
        msg_text = data.get("message", "").strip()
        if not msg_text:
            return

        # Activate live chat session so follow-up Telegram messages are forwarded
        await db.update_lead(user.id, live_chat=True)
        await db.track_event(user.id, "live_chat_requested", {"source": "twa"})

        # Save client's opening message
        await db.save_message(user.id, "user", msg_text, source="live_chat")

        # Notify assigned manager / admins (with Reply button)
        from bot.handlers.live_chat import _notify_managers
        fresh_lead = await db.get_lead(user.id)
        await _notify_managers(message.bot, fresh_lead, message_text=msg_text)

        # Confirm to client
        if lang == "ru":
            confirm = "✅ Сообщение отправлено! Мы ответим в Telegram в ближайшее время."
        else:
            confirm = "✅ Xabaringiz yuborildi! Tez orada Telegram orqali javob beramiz."
        await message.answer(confirm)
```

- [ ] **Step 3: Verify module compiles**

```bash
python3 -c "from bot.handlers.twa import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/twa.py
git commit -m "feat(bot): handle live_chat_request action from TWA"
```

---

## Task 7: Add "Chat with manager" button and panel to TWA

**Files:**
- Modify: `twa/index.html`

Three changes: (1) CSS for the panel, (2) HTML button in `#about` + slide-up panel, (3) JS functions + new translation keys.

- [ ] **Step 1: Add CSS for the chat panel**

Find the closing `</style>` tag. Insert immediately before it:

```css
        /* ── LIVE CHAT PANEL ───────────────────────────── */
        #chatPanel {
            display: none;
            position: fixed;
            bottom: 0; left: 0; right: 0;
            background: var(--surface, #fff);
            border-top: 1px solid var(--border);
            border-radius: 16px 16px 0 0;
            padding: 20px 16px 32px;
            z-index: 1000;
            box-shadow: 0 -4px 24px rgba(0,0,0,0.12);
        }

        #chatPanel.open { display: block; }

        .chat-panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }

        .chat-panel-title {
            font-weight: 600;
            font-size: 15px;
        }

        .chat-panel-close {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: var(--text-secondary);
            line-height: 1;
        }

        #chatInput {
            width: 100%;
            box-sizing: border-box;
            padding: 10px 12px;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm, 8px);
            font-size: 14px;
            font-family: inherit;
            resize: none;
            min-height: 80px;
        }

        .chat-panel-note {
            font-size: 11px;
            color: var(--text-secondary);
            margin: 6px 0 12px;
        }
```

- [ ] **Step 2: Add "Chat with manager" button in the about section**

Find the contacts card closing tag in `#about`:

```html
    </div>
</div>
```

The contacts card ends with the closing `</div>` of `class="contacts"` then the card's `</div>`. Insert the chat button immediately after the last `</div>` inside `#about`, before `</div>` that closes the section itself:

```html
    <div class="about-card" style="margin-top:16px;">
        <button class="cta-btn" id="chatManagerBtn" onclick="openChatPanel()" data-t="chat_btn">
            💬 Menejer bilan gaplashing
        </button>
    </div>
```

- [ ] **Step 3: Add the slide-up panel HTML**

Find the `<!-- ── BOTTOM CTA ─────────────────────────────────── -->` comment just before `</body>`. Insert the panel immediately before that comment:

```html
<!-- ── LIVE CHAT PANEL ──────────────────────────── -->
<div id="chatPanel">
    <div class="chat-panel-header">
        <span class="chat-panel-title" data-t="chat_title">Menejerga xabar</span>
        <button class="chat-panel-close" onclick="closeChatPanel()">✕</button>
    </div>
    <textarea id="chatInput" rows="3" data-t-placeholder="chat_placeholder"></textarea>
    <p class="chat-panel-note" data-t="chat_note">Tez orada Telegram orqali javob beramiz</p>
    <button class="cta-btn" onclick="sendLiveChat()" style="width:100%;" data-t="chat_send">Yuborish</button>
</div>
```

- [ ] **Step 4: Add JS functions**

Find `// Init` near the end of the `<script>` block (just before `setLang(lang)`). Insert immediately before it:

```javascript
    // ── LIVE CHAT PANEL ──────────────────────────────
    function openChatPanel() {
        document.getElementById('chatPanel').classList.add('open');
    }

    function closeChatPanel() {
        document.getElementById('chatPanel').classList.remove('open');
        document.getElementById('chatInput').value = '';
    }

    function sendLiveChat() {
        const msg = document.getElementById('chatInput').value.trim();
        if (!msg) return;
        if (tg) {
            tg.sendData(JSON.stringify({ action: 'live_chat_request', message: msg }));
        }
    }
```

- [ ] **Step 5: Support data-t-placeholder in setLang**

Find `setLang` function — the part that handles `[data-t]` elements:

```javascript
        document.querySelectorAll('[data-t]').forEach(el => {
            const k = el.dataset.t;
            if (t[k] !== undefined) el.textContent = t[k];
        });
```

Add this block immediately after it:

```javascript
        document.querySelectorAll('[data-t-placeholder]').forEach(el => {
            const k = el.dataset.tPlaceholder;
            if (t[k] !== undefined) el.placeholder = t[k];
        });
```

- [ ] **Step 6: Add translation keys**

Find the end of the `uz` translations block — the last key before the closing `},`:

```javascript
            cta:"Boshlash — botda suhbat",
        },
```

Replace with:

```javascript
            cta:"Boshlash — botda suhbat",
            chat_btn:"💬 Menejer bilan gaplashing",
            chat_title:"Menejerga xabar",
            chat_placeholder:"Xabaringizni yozing...",
            chat_send:"Yuborish",
            chat_note:"Tez orada Telegram orqali javob beramiz",
        },
```

Find the end of the `ru` translations block:

```javascript
            cta:"Начать разговор в боте",
        }
```

Replace with:

```javascript
            cta:"Начать разговор в боте",
            chat_btn:"💬 Написать менеджеру",
            chat_title:"Сообщение менеджеру",
            chat_placeholder:"Напишите ваш вопрос...",
            chat_send:"Отправить",
            chat_note:"Ответим в Telegram в ближайшее время",
        }
```

- [ ] **Step 7: Verify in browser**

Open `twa/index.html` in a browser. Switch to "Haqimizda" / "О нас" tab. A "💬 Menejer bilan gaplashing" button should appear at the bottom of the section. Tapping it opens the slide-up panel. Typing a message and tapping "Yuborish" does nothing visually (since `tg` is null outside Telegram — that's expected). Switch language to RU and verify button + panel translate.

- [ ] **Step 8: Commit TWA changes**

```bash
cd twa
git add index.html
git commit -m "feat(twa): add Chat with manager button and slide-up panel"
cd ..
git add twa
git commit -m "chore: update twa submodule pointer — phase4 live chat panel"
```

---

## Task 8: CRM — show 👤 Live badge on live-chat messages

**Files:**
- Modify: `crm/index.html:2813`

- [ ] **Step 1: Find the chat bubble render**

Open `crm/index.html`. Find line 2813:

```jsx
                  <div key={m.id} className={`chat-bubble ${m.role === 'user' ? 'chat-user' : 'chat-assistant'} ${!m.is_sent ? 'pending' : ''}`} title={m.role === 'assistant' && !m.is_sent ? 'Pending delivery...' : ''}>
                    {m.message}
                    {m.role === 'assistant' && !m.is_sent && <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 4 }}>⏳</span>}
                  </div>
```

- [ ] **Step 2: Add the live badge**

Replace with:

```jsx
                  <div key={m.id} className={`chat-bubble ${m.role === 'user' ? 'chat-user' : 'chat-assistant'} ${!m.is_sent ? 'pending' : ''}`} title={m.role === 'assistant' && !m.is_sent ? 'Pending delivery...' : ''}>
                    {m.source === 'live_chat' && (
                      <span style={{ fontSize: 10, opacity: 0.65, display: 'block', marginBottom: 2 }}>👤 Live</span>
                    )}
                    {m.message}
                    {m.role === 'assistant' && !m.is_sent && <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 4 }}>⏳</span>}
                  </div>
```

- [ ] **Step 3: Verify the CRM still loads**

Open `crm/index.html` in a browser (or `https://crm-mqsd.vercel.app`). Open a lead's conversation panel. No JS errors in DevTools. Existing messages display normally. (The `👤 Live` badge only appears once you have a message with `source = 'live_chat'` in the DB.)

- [ ] **Step 4: Commit**

```bash
git add crm/index.html
git commit -m "feat(crm): show 👤 Live badge on live-chat conversation messages"
```

---

## Task 9: Deploy TWA + CRM + restart bot

**Files:**
- `twa/` (Vercel project `twa`, org `yusufs-projects-dc1d63ce`, live at `https://twa-jet.vercel.app`)
- `crm/` (Vercel project `crm-mqsd`, live at `https://crm-mqsd.vercel.app`)

- [ ] **Step 1: Deploy TWA**

```bash
cd twa
npx vercel --prod --yes
cd ..
```

Expected: last line `Production: https://twa-jet.vercel.app [Xs]`

- [ ] **Step 2: Deploy CRM**

```bash
cd crm
npx vercel --prod --yes
cd ..
```

Expected: last line `Production: https://crm-mqsd.vercel.app [Xs]`

- [ ] **Step 3: Restart bot**

```bash
pkill -f "bot.main"; python3 -m bot.main
```

Wait 3 seconds and confirm polling started (no import errors in output).

- [ ] **Step 4: End-to-end test checklist**

Open your Telegram bot → tap TWA → navigate to "Haqimizda" / "О нас" tab:

- [ ] "💬 Menejer bilan gaplashing" button visible
- [ ] Tapping it opens slide-up panel
- [ ] Typing a message and tapping "Yuborish" sends data and closes TWA
- [ ] Bot sends confirmation message in Telegram: "✅ Xabaringiz yuborildi!"
- [ ] Admin receives notification with `💬 Reply` inline button
- [ ] Admin taps Reply → ForceReply prompt appears: "↩️ Replying to [Name]. Type your message:"
- [ ] Admin types response → client receives it as DM
- [ ] Admin sees "✅ Sent to [Name]" confirmation
- [ ] Open CRM → find the lead → conversation panel shows messages with `👤 Live` badge
