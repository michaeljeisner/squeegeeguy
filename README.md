# SqueegeeGuy Lead-Gen

Every morning at 7 AM, this system automatically:

1. Searches Google for commercial businesses in Tucson (restaurants, dental offices, car dealerships, hotels, etc.)
2. Finds their contact email addresses
3. Has AI score each business on how good a fit they are for window cleaning or pressure washing
4. Has AI write a personalized cold email for every good prospect
5. Sends those emails from your business address
6. Emails **you** a daily summary of everything it did

You wake up to a digest in your inbox telling you who it reached out to, who scored highest, and whether anyone replied.

---

## Before You Start: What You Need

You'll need accounts and API keys from three services. All are either free or very cheap.

| What | Cost | Why |
|---|---|---|
| Google Workspace email (`@gosqueegeeguy.com`) | ~$6/mo | Sends the outreach emails and receives replies |
| Google Places API key | Free (up to ~5,000 searches/month) | Finds businesses in Tucson |
| Anthropic API key | ~$5–15/mo depending on volume | AI that scores leads and writes emails |

> **Important:** Do NOT use a personal Gmail to send cold outreach. You need an email on your own domain (like `michael@gosqueegeeguy.com`) so emails don't land in spam and your domain reputation stays clean.

---

## One-Time Setup

### Step 1 — Install Python and uv

Open Terminal (press `Cmd + Space`, type "Terminal", hit Enter).

Paste this and hit Enter:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close Terminal and reopen it. Verify it worked:
```
uv --version
```
You should see a version number like `uv 0.5.x`.

---

### Step 2 — Download this project

```
cd ~/Dev/Projects
git clone https://github.com/michaeljeisner/squeegeeguy.git
cd squeegeeguy
uv sync
```

---

### Step 3 — Get your API keys

**Google Places API key:**
1. Go to https://console.cloud.google.com
2. Create a new project called "SqueegeeGuy"
3. Go to **APIs & Services → Enable APIs** and enable **Places API (New)**
4. Go to **APIs & Services → Credentials → Create Credentials → API Key**
5. Copy the key — it looks like `AIzaSy...`

**Anthropic API key:**
1. Go to https://console.anthropic.com
2. Sign up / log in
3. Go to **API Keys → Create Key**
4. Copy the key — it looks like `sk-ant-...`
5. Add $10 in credits under **Billing** — that'll last several months

**Google Workspace App Password** (for sending email):
1. Log into your `@gosqueegeeguy.com` Google account at https://myaccount.google.com
2. Go to **Security → 2-Step Verification** and make sure it's turned on
3. Go to **Security → App Passwords**
4. Create a new app password for "Mail" → "Mac"
5. Copy the 16-character password it gives you

---

### Step 4 — Create your secrets file

In Terminal, from the project folder:
```
cp .env.example .env
open -e .env
```

This opens a plain text file. Fill in every blank line:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_PLACES_API_KEY=AIzaSy-your-key-here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=michael@gosqueegeeguy.com
SMTP_PASSWORD=your-16-char-app-password
IMAP_HOST=imap.gmail.com
IMAP_USER=michael@gosqueegeeguy.com
IMAP_PASSWORD=your-16-char-app-password
OWNER_EMAIL=michael@squeegeeguy.com
```

Save and close the file. **Never share this file or commit it to GitHub — it contains your passwords.**

---

### Step 5 — Fill in your business details

Open `config.py` in a text editor and update the `BusinessProfile` section at the top:

```python
@dataclass(frozen=True)
class BusinessProfile:
    name: str = "SqueegeeGuy"
    owner_name: str = "Michael"
    ...
    phone: str = "(520) 555-0000"          # ← your real phone number
    website: str = "https://squeegeeguy.com"
    physical_address: str = "123 Your St, Tucson, AZ 85701"  # ← required by law (CAN-SPAM)
    sending_domain: str = "gosqueegeeguy.com"                # ← your sending domain
```

> **The physical address is legally required** on every cold email you send (CAN-SPAM Act). It doesn't have to be your home — a P.O. box or UPS Store address works fine.

---

### Step 6 — Do a dry run (no emails sent)

This runs the full pipeline but doesn't actually send anything. Good way to make sure everything is connected before going live.

```
cd ~/Dev/Projects/squeegeeguy
uv run python run.py --dry-run
```

You'll see output like:
```
[run] Step 1: Prospecting...
[prospect] restaurants: 20 found, 20 new
[prospect] car dealerships: 18 found, 18 new
...
[run] Step 2: Enriching...
[run] Step 3: Scoring...
[run] Step 4: Drafting...
--- DRY RUN EMAIL ---
To: info@somerestaurant.com
Subject: Quick question about your windows
...
[run] Done in 142.3s
      prospects=280 enriched=87 scored=62 drafted=45 sent=0
```

Check the drafted emails look good. If anything looks off, let your developer know before going live.

---

### Step 7 — Schedule it to run every morning

This installs the daily 7 AM job:

```
bash setup.sh
```

That's it. It will now run automatically every morning while your Mac is on and awake.

---

## Daily Usage

### Your morning digest

Every morning after the pipeline runs, you'll get an email at `michael@squeegeeguy.com` with a subject like:

```
SqueegeeGuy Daily Digest — 2025-07-15
```

It tells you:
- How many businesses were found and emailed
- The top-scoring prospects (restaurants, dental offices, etc.)
- Exactly which emails went out and to whom
- Any errors if something went wrong

### When someone replies

If a prospect replies to an outreach email:
- **Interested or has a question:** You'll get an instant alert email with their message and contact info. Reply directly from your email client — it threads naturally.
- **"Not interested" or "Stop":** The system handles it automatically. They're added to a do-not-contact list and won't hear from you again.

### Checking the database

If you want to see what's in the system, you can download [DB Browser for SQLite](https://sqlitebrowser.org) (free) and open `squeegeeguy.db`. The `leads` table has every prospect; `outreach` has every email sent.

---

## Adjusting How It Behaves

All settings are in `config.py`. The most useful ones:

**Change the minimum score to target (default: 60 out of 100):**
```python
min_fit_score: int = 60   # raise to 75 to only email the best prospects
```

**Change how many emails it sends per day (warmup schedule):**
```python
warmup_schedule: dict[int, int] = {
    1: 5,    # Week 1: max 5/day
    2: 10,   # Week 2: max 10/day
    3: 20,   # Week 3: max 20/day
    4: 30,   # Week 4: max 30/day
    5: 50,   # Week 5+: max 50/day
}
```
Start slow. Jumping straight to 50/day from a new email address will get you flagged as spam.

**Add or remove business categories to target:**
```python
categories: tuple[str, ...] = (
    "restaurants",
    "car dealerships",
    # add more here, or remove ones you don't want
)
```

---

## Manually Blocking Someone

If you ever want to make sure a specific email address never gets contacted again:

```
cd ~/Dev/Projects/squeegeeguy
uv run python -c "import db; db.add_suppression('someone@example.com', 'manual')"
```

---

## Stopping and Starting

**Pause the daily job** (it won't run until you re-enable it):
```
launchctl unload ~/Library/LaunchAgents/com.squeegeeguy.leadgen.plist
```

**Re-enable it:**
```
launchctl load ~/Library/LaunchAgents/com.squeegeeguy.leadgen.plist
```

**Run it manually right now:**
```
cd ~/Dev/Projects/squeegeeguy
uv run python run.py
```

**Check the logs from the last run:**
```
cat /tmp/squeegeeguy-leadgen.log
cat /tmp/squeegeeguy-leadgen.err
```

---

## Troubleshooting

**"No emails sent today"**
The warmup limit was hit. Normal behavior — it will send more as the weeks go on.

**"SMTP authentication failed"**
Your App Password is wrong or expired. Go back to Step 3 and create a new one, then update `.env`.

**"Google Places API error"**
Check that your Places API key is correct and the Places API (New) is enabled in Google Cloud Console.

**Emails landing in spam**
This is normal for the first week or two on a new domain. Make sure you have SPF, DKIM, and DMARC records set up on `gosqueegeeguy.com` — ask your developer or Google "how to set up email authentication for Google Workspace."

**Something else broke**
Check the error log:
```
cat /tmp/squeegeeguy-leadgen.err
```
Copy the error and send it to your developer.

---

## Legal Notes

This system is designed to comply with the **CAN-SPAM Act**:
- Every email includes your physical mailing address
- Every email has an unsubscribe instruction ("Reply STOP")
- Unsubscribe requests are honored immediately and automatically
- No deceptive subject lines

You are responsible for ensuring your business address in `config.py` is accurate and current. If you move, update it.

---

## Cost Summary

| Service | Estimated monthly cost |
|---|---|
| Google Workspace (email) | $6 |
| Anthropic API (AI) | $5–15 |
| Google Places API | Free (within free tier) |
| **Total** | **~$11–21/month** |
