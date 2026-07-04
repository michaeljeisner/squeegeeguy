# Squeegee Guy Lead-Gen + Appointment Setting

This system finds new customers, emails them, answers their replies, and **books
jobs onto your calendar — automatically**. You wake up to appointments that are
already set.

What it does, all day, every day:

1. **7:00 AM — daily pipeline.** Searches Google for Tucson businesses
   (restaurants, dental offices, dealerships, hotels…), finds their email
   addresses, has AI score each one, writes a personalized cold email for every
   good prospect, and sends them (with polite follow-ups a few days later if
   nobody answers).
2. **Every 15 minutes — the booking agent.** Checks the inbox. When a prospect
   replies, AI answers *as you*: it answers questions, offers real open time
   slots from your calendar, and when they pick one it **books the appointment**,
   emails them a confirmation with a calendar invite (.ics), and emails you the
   same invite so it lands on your calendar.
3. **Website leads too.** The new website's quote form feeds the same system —
   form submitters get an instant reply that already offers open time slots.
4. **Daily digest.** Every morning you get one email: jobs booked in the last
   24 hours (on top), upcoming appointments, who was contacted, top prospects,
   and any errors.

Anything sensitive — pricing negotiation, complaints, big complex jobs — is
**escalated to you** instead of auto-answered. Anyone who says "stop" is
suppressed forever, automatically.

---

## Before You Start: What You Need

| What | Cost | Why |
|---|---|---|
| Google Workspace email (`@gosqueegeeguy.com`) | ~$6/mo | Sends outreach and receives replies |
| Google Places API key | Free (up to ~5,000 searches/month) | Finds businesses in Tucson |
| Anthropic API key | ~$5–15/mo | AI that scores leads, writes emails, and books appointments |

> **Important:** Do NOT use a personal Gmail for cold outreach. Use an address
> on your own sending domain (like `chip@gosqueegeeguy.com`) so email lands in
> inboxes and your main domain's reputation stays clean.

---

## One-Time Setup

### Step 1 — Install uv

Open Terminal (`Cmd + Space`, type "Terminal", Enter) and paste:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Close and reopen Terminal, then check: `uv --version`

### Step 2 — Download this project

```
git clone https://github.com/michaeljeisner/squeegeeguy.git
cd squeegeeguy
uv sync
```

### Step 3 — Get your API keys

**Google Places API key:**
1. https://console.cloud.google.com → new project "SqueegeeGuy"
2. APIs & Services → Enable **Places API (New)**
3. Credentials → Create Credentials → API Key (looks like `AIzaSy...`)

**Anthropic API key:**
1. https://console.anthropic.com → API Keys → Create Key (`sk-ant-...`)
2. Add $10 in credits under Billing

**Google Workspace App Password** (for sending email):
1. Log into your `@gosqueegeeguy.com` account at https://myaccount.google.com
2. Security → turn ON 2-Step Verification
3. Security → App Passwords → create one for "Mail" → copy the 16-char password

### Step 4 — Create your secrets file

```
cp .env.example .env
open -e .env
```

Fill in every blank line — API keys, the app password, and your business
details (`OWNER_NAME`, `BUSINESS_PHONE`, `BUSINESS_ADDRESS`).

> **BUSINESS_ADDRESS is legally required** on every cold email (CAN-SPAM Act).
> A P.O. box or UPS Store address is fine.

**Never share `.env` or commit it to GitHub — it contains your passwords.**

### Step 5 — Set your working hours

Open `config.py` and check the `AvailabilityConfig` section. This is the
calendar the booking agent offers to prospects:

```python
workdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5)  # Mon–Sat (Sunday off)
day_start_hour: int = 8      # earliest appointment
day_end_hour: int = 17       # latest end time
slot_minutes: int = 120      # length of a job block
min_notice_hours: int = 18   # never book sooner than this
```

### Step 6 — Dry run (nothing is sent)

```
uv run python run.py --dry-run
```

Check the drafted emails look right. Also sanity-check your open slots:

```
uv run python appointments.py
```

### Step 7 — Test SMTP, then go live

```
uv run python send.py        # sends one test email to OWNER_EMAIL
bash setup.sh                # installs both scheduled jobs
```

`setup.sh` installs two background jobs that run while your Mac is on:
- **7:00 AM daily** — the full lead-gen pipeline
- **Every 15 minutes** — the reply/booking agent

---

## Daily Usage

Honestly? Read the morning digest, show up to the jobs, and reply to the
escalation emails. That's it.

### The morning digest

Subject: `SqueegeeGuy Daily Digest — 2026-07-15`. Jobs booked in the last 24
hours are at the top, then upcoming appointments, then pipeline stats.

### When someone replies to an outreach email

- **Interested / has questions:** The AI answers within 15 minutes, offering
  open time slots from your calendar. Back-and-forth continues automatically.
- **They pick a time:** Appointment is booked. They get a confirmation with a
  calendar invite; you get an alert email **plus the same .ics invite** — open
  it to add the job to your calendar.
- **Pricing haggling, complaints, complex jobs:** Escalated to you. Reply from
  your own inbox; the AI stops touching that thread (it caps itself at 4
  auto-replies per lead anyway).
- **"Not interested" / "Stop":** Suppressed automatically, follow-ups
  cancelled. They will never be contacted again.

### Website quote form

The new site is in `site/index.html`. Its form POSTs to the inbound receiver:

```
uv run python inbound.py     # listens on port 8765
```

To use it in production, host `site/index.html` anywhere (Cloudflare Pages,
Netlify, your current host) and point `QUOTE_ENDPOINT` at a public URL for the
inbound server (Cloudflare Tunnel or Tailscale Funnel work well on a Mac). If
the endpoint is ever unreachable, the form falls back to opening a pre-filled
email to you — no lead is lost.

### Checking the database

Download [DB Browser for SQLite](https://sqlitebrowser.org) (free) and open
`squeegeeguy.db`:
- `leads` — every prospect and their status
- `outreach` — every email drafted/sent
- `conversations` — full reply threads
- `appointments` — every booked job

---

## Adjusting How It Behaves

All settings are in `config.py`:

**Minimum score to email (default 60):** `min_fit_score: int = 60`

**Daily send limits (warmup — don't rush this):**
```python
warmup_schedule = {1: 5, 2: 10, 3: 20, 4: 30, 5: 50}   # week: emails/day
```

**Business categories to target:** edit the `categories` tuple.

**Follow-up timing:** `followup_delays_days = (3, 7)` — days after the initial
email. Follow-ups are cancelled instantly if the prospect replies.

---

## Manually Blocking Someone

```
uv run python -c "import db; db.add_suppression('someone@example.com', 'manual')"
```

## Stopping and Starting

```
# Pause everything
launchctl unload ~/Library/LaunchAgents/com.squeegeeguy.leadgen.plist
launchctl unload ~/Library/LaunchAgents/com.squeegeeguy.replies.plist

# Resume
launchctl load ~/Library/LaunchAgents/com.squeegeeguy.leadgen.plist
launchctl load ~/Library/LaunchAgents/com.squeegeeguy.replies.plist

# Run right now
uv run python run.py          # full pipeline
uv run python checkin.py      # just check replies / book appointments

# Logs
tail -f /tmp/com.squeegeeguy.leadgen.log /tmp/com.squeegeeguy.replies.log
cat /tmp/com.squeegeeguy.leadgen.err /tmp/com.squeegeeguy.replies.err
```

## Tests

```
uv run python test_core.py
```

Covers follow-up due dates, reply-cancels-followups, suppression, slot
generation, double-booking prevention, working-hours validation, and .ics
generation. Runs against a temp database — never touches your real data.

---

## Troubleshooting

**"No emails sent today"** — warmup limit hit; normal, grows weekly.

**"SMTP authentication failed"** — App Password wrong/expired. Make a new one,
update `.env`.

**"Google Places API error"** — check the key and that Places API (New) is
enabled.

**Emails landing in spam** — normal for a new domain's first week or two. Set
up SPF, DKIM, and DMARC on your sending domain (Google "email authentication
for Google Workspace").

**Booking agent replied something odd** — every auto-reply is logged in the
`conversations` table. It escalates to you when unsure and hard-caps at 4
auto-replies per lead. Adjust the cap via `max_auto_replies_per_lead` in
`config.py`.

**Something else broke** — `cat /tmp/com.squeegeeguy.*.err` and send the error
to your developer.

---

## Legal Notes

Designed to comply with the **CAN-SPAM Act**:
- Every cold email includes your physical mailing address
- Every cold email has an unsubscribe instruction ("Reply STOP")
- Unsubscribes are honored immediately and automatically
- No deceptive subject lines

Keep `BUSINESS_ADDRESS` in `.env` accurate. If you move, update it.

## Cost Summary

| Service | Estimated monthly cost |
|---|---|
| Google Workspace (email) | $6 |
| Anthropic API (AI) | $5–15 |
| Google Places API | Free (within free tier) |
| **Total** | **~$11–21/month** |
