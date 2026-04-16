# Telegram Lead Capture Bot + TWA

A complete lead capture system for marketing agencies. Includes a Telegram bot with AI assistant (Claude), bilingual support (Uzbek/Russian), inline menus, and a Telegram Web App (TWA) mini-site. Leads are automatically captured into a Supabase CRM.

## Architecture

```
Meta Ad → t.me/botname?start=campaign_id
                  │
                  ▼
         ┌─── Telegram Bot ───┐
         │  • Welcome + Menu  │
         │  • AI Assistant    │──→ Claude API
         │  • Contact Capture │
         │  • Admin Commands  │
         └────────┬───────────┘
                  │
                  ▼
            ┌─ Supabase ─┐        ┌──── TWA ────┐
            │  leads      │        │  Services   │
            │  convos     │◄───────│  Projects   │
            │  events     │        │  FAQ        │
            └─────────────┘        │  Contact    │
                                   └─────────────┘
```

## Quick Start

### 1. Create Telegram Bot
1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`, choose a name and username
3. Copy the **bot token**

### 2. Get API Keys
- **Claude API**: [console.anthropic.com](https://console.anthropic.com) → Create key → Add $5 credit
- **Supabase**: [supabase.com](https://supabase.com) → New Project → Copy URL + anon key

### 3. Set Up Database
1. Go to Supabase → SQL Editor
2. Paste the contents of `database/schema.sql`
3. Click **Run**

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values:
# BOT_TOKEN, CLAUDE_API_KEY, SUPABASE_URL, SUPABASE_KEY, ADMIN_IDS
```

### 5. Run the Bot

**Option A: Python directly**
```bash
pip install -r requirements.txt
python -m bot.main
```

**Option B: Docker**
```bash
docker-compose up -d
```

### 6. Deploy TWA
1. Push the `twa/` folder to a GitHub repo
2. Connect to [Vercel](https://vercel.com) or [Netlify](https://netlify.com) (free)
3. Get the HTTPS URL (e.g., `https://your-twa.vercel.app`)
4. Update `TWA_URL` in your `.env`
5. Set TWA in BotFather: `/setmenubutton` → paste your URL

### 7. Set Up Meta Ads
Use these deep links as ad destinations:
```
Campaign 1: https://t.me/yourbotname?start=meta_general
Campaign 2: https://t.me/yourbotname?start=meta_services
Campaign 3: https://t.me/yourbotname?start=meta_retarget
```

## Customization

### Replace Placeholder Content
Search for `[PRICE]`, `[X]`, and bracket placeholders `[...]` across these files:

| File | What to replace |
|------|----------------|
| `bot/texts.py` | Bot menu text (services, projects, FAQ, about) |
| `bot/prompts/system_prompt.txt` | AI assistant knowledge base |
| `twa/index.html` | TWA website content, stats, projects |
| `.env` | Agency name, admin IDs |

### Add Your Branding
- **TWA**: Edit colors in `:root` CSS variables in `twa/index.html`
- **Bot**: Update emoji and text formatting in `bot/texts.py`
- **Logo**: Add to TWA hero section

## Admin Commands

| Command | Description |
|---------|-------------|
| `/leads` | View last 15 leads |
| `/lead <id>` | Detailed lead profile + chat history |
| `/stats` | Lead analytics (by source, status) |
| `/export` | Download all leads as CSV |

## Project Structure

```
telegram-lead-bot/
├── bot/
│   ├── main.py                 # Bot entry point
│   ├── config.py               # Environment config
│   ├── texts.py                # Bilingual text (UZ/RU)
│   ├── handlers/
│   │   ├── start.py            # /start + deep link capture
│   │   ├── menu.py             # Button callbacks
│   │   ├── contact.py          # Phone capture
│   │   ├── ai_chat.py          # AI responses
│   │   ├── admin.py            # Admin commands
│   │   └── twa.py              # TWA data handler
│   ├── keyboards/
│   │   └── main_menu.py        # All keyboard layouts
│   ├── services/
│   │   ├── ai_service.py       # Claude API
│   │   └── db_service.py       # Supabase CRUD
│   └── prompts/
│       └── system_prompt.txt   # AI system prompt
├── twa/
│   └── index.html              # TWA single-page app
├── database/
│   └── schema.sql              # Supabase tables
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Lead Flow

```
Tap 1: Lead clicks Meta ad       → Opens Telegram
Tap 2: Bot auto-welcomes         → Lead captured (name, ID, source)
        Lead taps buttons / chats → AI answers, events tracked
Tap 3: Shares phone (1-tap)      → Full contact in CRM
        Team gets notified        → Follow up
```

## Cost

| Item | Monthly Cost |
|------|-------------|
| Telegram Bot API | Free |
| Bot hosting (Railway) | $5–10 |
| TWA hosting (Vercel) | Free |
| Database (Supabase) | Free |
| Claude API | $10–50 |
| **Total** | **$15–60** |
