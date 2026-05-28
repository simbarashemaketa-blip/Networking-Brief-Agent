# IntelBrief — Setup Guide
*One-time setup. Estimated time: 45 minutes.*

---

## What You're Building

An automated agent that:
1. Reads your contacts Excel directly from your GitHub repo
2. Searches for recent news relevant to each contact's company and role
3. Generates a personalized intel brief + draft outreach email per contact
4. Delivers everything to your inbox — Mon, Wed, Fri at 6 AM Central

To update your contacts weekly: drag and drop a new Excel file into GitHub. That's it.

---

## What You Need (Accounts / Keys)

| Service | What For | Cost |
|---|---|---|
| GitHub (free) | Stores your code + contacts file + runs the agent | Free |
| Anthropic API | Claude generates the briefs and emails | ~$8–15/month |
| Exa AI | Searches the web for contact-relevant news | Free tier |
| Gmail App Password | Sends emails from your Gmail | Free |

No Google Cloud. No service accounts. No JSON credentials.

---

## Your Repo Structure

After setup, your GitHub repo should look like this:

```
intelbrief/
├── .github/
│   └── workflows/
│       └── intelbrief.yml     ← the scheduler
├── data/
│   └── contacts.xlsx          ← YOUR CONTACTS FILE (update this weekly)
├── src/
│   └── agent.py               ← the agent logic
└── requirements.txt
```

---

## Step 1: Create a GitHub Account and Repository

1. Go to **github.com** → create a free account
2. Click **"New repository"** (green button, top right)
3. Name it: `intelbrief`
4. Set to **Private**
5. Check **"Add a README file"** (makes the next step easier)
6. Click **"Create repository"**

---

## Step 2: Upload Your Files

### Upload the code files
1. In your repo, click **"Add file"** → **"Upload files"**
2. Drag and drop everything from the ZIP *except* the `data/` folder:
   - The `src/` folder
   - The `requirements.txt` file
   - The `.github/` folder

   > **Mac users:** The `.github` folder is hidden by default. Press **Cmd+Shift+Period** in Finder to reveal hidden files before dragging.

3. Click **"Commit changes"**

### Create the data folder and upload your contacts
GitHub can't create empty folders via drag-and-drop, so do this:

1. Click **"Add file"** → **"Create new file"**
2. In the filename box type: `data/contacts.xlsx`
   - Typing the `/` automatically creates the folder
3. GitHub will tell you it can't preview the file — that's fine
4. Delete what you typed and instead use **"Upload files"** after navigating into `data/`

**Easier method:** Click into your repo → navigate to where you want the file → **"Add file"** → **"Upload files"** → upload `contacts.xlsx` from the template provided.

---

## Step 3: Get Your API Keys

### Anthropic (Claude)
1. Go to **console.anthropic.com** → sign up
2. Click **API Keys** → **Create Key**
3. Copy it — starts with `sk-ant-...`
4. Add $10–20 in credits under **Billing**

### Exa AI
1. Go to **exa.ai** → sign up free
2. Dashboard → **API Keys** → **Create**
3. Copy the key

---

## Step 4: Get a Gmail App Password

This lets the script send from your Gmail without exposing your real password.

1. Go to **myaccount.google.com** → **Security**
2. Make sure **2-Step Verification** is ON
3. In the search bar on that page, search **"App Passwords"**
4. App: **Mail** · Device: **Other** · Name it: `intelbrief`
5. Google gives you a 16-character password — copy it immediately

---

## Step 5: Add Secrets to GitHub

Secrets store your keys securely. The script reads them at runtime — never visible in code.

1. In your GitHub repo: **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"** for each:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key |
| `EXA_API_KEY` | Your Exa AI key |
| `SENDER_EMAIL` | Your Gmail address |
| `SENDER_PASSWORD` | The 16-character App Password |
| `RECIPIENT_EMAIL` | Where you want briefs delivered |

That's 5 secrets total. Much simpler than before.

---

## Step 6: Test It

1. Go to your repo → **Actions** tab
2. Click **"IntelBrief Agent"** in the left sidebar
3. Click **"Run workflow"** → **"Run workflow"** (green button)
4. Click into the running job to watch the logs live
5. Check your inbox in 2–3 minutes

Green checkmark = you're live.

---

## Step 7: Update Your Contacts Weekly

1. Open `contacts.xlsx` on your computer, make your changes
2. Go to your GitHub repo → navigate to `data/` folder
3. Click **"Add file"** → **"Upload files"**
4. Drag in your updated Excel — GitHub will replace the old one
5. Click **"Commit changes"**

Done. Next scheduled run picks up the new data automatically.

---

## Contacts File Column Names

The script expects these exact column headers (already set up in the template):

| Column | What to Put |
|---|---|
| `person` | Full name |
| `role` | Their title |
| `company` | Their firm |
| `takeaways_from_previous_meeting` | Notes from your last conversation |
| `date_last_contacted` | Date of last touchpoint (any format) |

---

## Schedule

Runs automatically at **6:00 AM Central**:
- Monday — Capital markets + macro
- Wednesday — Company intel
- Friday — Deal flow + trends

To change days/times, edit the `cron` lines in `.github/workflows/intelbrief.yml`.

---

## Estimated Monthly Cost

| | Cost |
|---|---|
| Anthropic API (20 contacts × 3 runs/week) | ~$8–15/month |
| Exa AI | Free tier |
| GitHub Actions | Free |
| **Total** | **~$8–15/month** |

---

## Common Issues

**"No module named X"** — check that `requirements.txt` uploaded correctly

**Gmail authentication failed** — make sure you're using the App Password (16 chars), not your Gmail login password

**Contacts not loading** — confirm the file is at `data/contacts.xlsx` exactly, and column names match the table above

**Actions tab not showing the workflow** — confirm the `.github/workflows/intelbrief.yml` file uploaded correctly; the `.github` folder must be at the root of the repo
