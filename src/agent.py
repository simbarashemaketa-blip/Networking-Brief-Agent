"""
IntelBrief Agent
----------------
Reads your contacts Excel directly from the GitHub repository,
searches for relevant market/company news per contact, then generates
a personalized intel brief + draft outreach email for each one.
Delivers everything to your inbox.

To update contacts: drag and drop a new Excel file into your
GitHub repo (data/contacts.xlsx) — no other changes needed.
"""

import os
import json
import smtplib
import anthropic
import pandas as pd
import requests
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
EXA_API_KEY       = os.environ["EXA_API_KEY"]
SENDER_EMAIL      = os.environ["SENDER_EMAIL"]      # Your Gmail address
SENDER_PASSWORD   = os.environ["SENDER_PASSWORD"]   # Gmail App Password
RECIPIENT_EMAIL   = os.environ["RECIPIENT_EMAIL"]   # Where briefs land (your inbox)

# Path to your contacts file inside the repo
# When GitHub Actions runs your script, it downloads your entire repo
# first — so this file is already sitting right next to your code.
CONTACTS_FILE = "data/contacts.xlsx"

NEWS_LOOKBACK_DAYS = 7
MAX_CONTACTS       = 20


# ── Step 1: Read Excel from repo ─────────────────────────────────────────────

def load_contacts() -> pd.DataFrame:
    """
    Reads contacts.xlsx directly from the repo folder.
    No API calls, no authentication — the file is just there.
    """
    df = pd.read_excel(CONTACTS_FILE)

    # Normalize column names: strip whitespace, lowercase, spaces to underscores
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    print(f"Loaded {len(df)} contacts from {CONTACTS_FILE}.")
    return df


# ── Step 2: Search for news per contact ──────────────────────────────────────

def search_news_for_contact(name: str, role: str, company: str) -> tuple:
    """
    Uses Exa AI to find recent news relevant to this contact's
    company and role.

    Returns a tuple of:
      - news_text (str): raw text block passed to Claude for synthesis
      - sources (list): [{"title": ..., "url": ...}] for citation rendering
    """

    cutoff = (datetime.utcnow() - timedelta(days=NEWS_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    queries = [
        f"{company} real estate news acquisitions strategy",
        f"{role} CRE market trends {datetime.utcnow().strftime('%B %Y')}",
    ]

    all_results = []
    sources     = []  # Keep title + URL separately for citation rendering
    seen_urls   = set()

    for query in queries:
        response = requests.post(
            "https://api.exa.ai/search",
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "x-api-key": EXA_API_KEY,
            },
            json={
                "query": query,
                "num_results": 3,
                "start_published_date": cutoff,
                "use_autoprompt": True,
                "contents": {"text": {"max_characters": 800}},
            },
        )

        if response.status_code == 200:
            results = response.json().get("results", [])
            for r in results:
                title = r.get("title", "Untitled")
                url   = r.get("url", "")
                snippet = r.get("text", "")[:600]

                # Deduplicate by URL
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Text block for Claude — include URL so it can reference it
                all_results.append(
                    f"SOURCE: {title}\nURL: {url}\nSNIPPET: {snippet}"
                )

                # Clean source list for rendering
                sources.append({"title": title, "url": url})

    if not all_results:
        return "No recent news found.", []

    news_text = "\n\n---\n\n".join(all_results)
    return news_text, sources


# ── Step 3: Generate brief + email draft via Claude ───────────────────────────

def generate_brief_and_email(contact: dict, news: str) -> dict:
    """
    Passes contact context + news to Claude.
    Returns a dict with: brief_items (insight + so_what + source_url per item),
    email_subject, email_body.
    """

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    last_contacted = contact.get("date_last_contacted", "unknown date")
    meeting_notes  = contact.get("takeaways_from_previous_meeting", "No prior meeting notes.")
    name           = contact.get("person", "")
    role           = contact.get("role", "")
    company        = contact.get("company", "")

    prompt = f"""
You are an assistant helping a CRE financial analyst named Simba prepare personalized outreach.
Simba has 2 years of experience as a financial analyst with experience in industrial and MF acquisitions, fund analytics, and development
underwriting across DFW and Sunbelt markets. He is building his network strategically and wants
every message to add genuine value — not ask for anything.

CONTACT INFORMATION:
- Name: {name}
- Role: {role}
- Company: {company}
- Last contacted: {last_contacted}
- Meeting notes: {meeting_notes}

RECENT NEWS ABOUT THEIR COMPANY / ROLE (each item includes a SOURCE URL):
{news}

YOUR TASK:
1. Write an INTEL BRIEF of 4-6 items. For each item produce THREE things:
   - "insight": the actual finding — specific, data-driven, no generic commentary.
     Reference real numbers, company names, or market moves where available.
   - "so_what": 1-2 sentences explaining WHY this matters. Alternate perspective:
     sometimes "so what for the recipient" (how it affects their business/role),
     sometimes "so what for Simba" (why this is a useful conversation hook or
     signals a networking opportunity). Be direct and commercial — no fluff.
   - "source_url": the URL from the source that most directly supports this insight.
     Use the exact URL from the news text provided. If no URL applies, use "".

2. Write a DRAFT EMAIL Simba can send to this contact. Rules:
   - Subject line: specific — reference something real from the news
   - Opening: reference the previous meeting naturally, not robotically
   - Body: share 1-2 specific insights directly relevant to THEIR world. Frame it
     as Simba noticing something and thinking of them — not showing off.
   - NO ask. No "let's grab coffee." This email purely delivers value.
   - Closing: leave the door open naturally, one sentence.
   - Tone: professional but human. Sharp junior colleague, not a sales rep.
   - Length: under 150 words total.

Return ONLY valid JSON in this exact format, nothing else:
{{
  "brief_items": [
    {{
      "insight": "specific finding here",
      "so_what": "why this matters — for them or for Simba",
      "source_url": "https://..."
    }}
  ],
  "email_subject": "subject line here",
  "email_body": "full email body here"
}}
"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── Step 4: Build HTML email ──────────────────────────────────────────────────

def build_email_html(contact: dict, brief_items: list, sources: list,
                     email_subject: str, email_body: str) -> str:
    """
    Renders the intel brief + draft email into a clean HTML email.
    Each brief item shows: insight, so what, and a source link.
    Sources section at the bottom lists all articles found.
    """

    name      = contact.get("person", "Contact")
    role      = contact.get("role", "")
    company   = contact.get("company", "")
    body_html = email_body.replace("\n", "<br>")

    # Build brief items HTML — insight + so what + source link per item
    items_html = ""
    for item in brief_items:
        insight    = item.get("insight", "")
        so_what    = item.get("so_what", "")
        source_url = item.get("source_url", "")

        source_link = ""
        if source_url:
            source_link = f"""
            <div style="margin-top:4px;">
                <a href="{source_url}"
                   style="font-size:10px;color:#007a6e;font-family:monospace;
                          text-decoration:none;letter-spacing:0.5px;">
                    ↗ Source
                </a>
            </div>"""

        items_html += f"""
        <div style="padding:14px 0;border-bottom:1px solid #e8e4dc;">
            <div style="font-size:14px;color:#1a1a1a;line-height:1.5;font-weight:600;">
                {insight}
            </div>
            <div style="margin-top:6px;padding:8px 12px;background:#f0faf8;
                        border-left:3px solid #007a6e;border-radius:0 2px 2px 0;">
                <span style="font-family:monospace;font-size:9px;text-transform:uppercase;
                             letter-spacing:1.5px;color:#007a6e;font-weight:600;">
                    So What →
                </span>
                <span style="font-size:12px;color:#2a4a44;line-height:1.6;margin-left:6px;">
                    {so_what}
                </span>
            </div>
            {source_link}
        </div>"""

    # Build sources footer — all articles found this run
    sources_html = ""
    if sources:
        source_links = "".join(
            f'<div style="padding:4px 0;">'
            f'<a href="{s["url"]}" style="font-size:11px;color:#007a6e;text-decoration:none;">'
            f'↗ {s["title"]}</a></div>'
            for s in sources if s.get("url")
        )
        sources_html = f"""
        <div style="padding:20px 28px;background:#f9f7f3;border-top:1px solid #d8d3c8;">
            <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;
                        color:#888;margin-bottom:12px;">Sources This Run</div>
            {source_links}
        </div>"""

    return f"""
    <html><body style="font-family:Georgia,serif;max-width:680px;margin:0 auto;color:#1a1a1a;">

    <div style="background:#0e0e10;color:#fff;padding:20px 28px;border-bottom:3px solid #007a6e;">
        <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;
                    color:#888;margin-bottom:6px;">
            IntelBrief · {datetime.now().strftime('%A, %B %d %Y')}
        </div>
        <div style="font-size:22px;font-family:Georgia,serif;">{name}</div>
        <div style="font-size:13px;color:#aaa;margin-top:4px;">{role} · {company}</div>
    </div>

    <div style="padding:28px;background:#f9f7f3;border-bottom:1px solid #d8d3c8;">
        <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;
                    color:#888;margin-bottom:4px;">Intel Brief</div>
        <div style="font-size:11px;color:#aaa;font-family:monospace;margin-bottom:16px;">
            Insight · So What · Source
        </div>
        {items_html}
    </div>

    <div style="padding:28px;background:#fff;border-bottom:1px solid #d8d3c8;">
        <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;
                    color:#c97c1e;margin-bottom:14px;">Draft Outreach Email</div>
        <div style="background:#fdf9f3;border:1px solid #f0d590;
                    border-left:4px solid #c97c1e;padding:20px 22px;border-radius:2px;">
            <div style="font-size:12px;color:#888;margin-bottom:10px;font-family:monospace;">
                SUBJECT: {email_subject}
            </div>
            <div style="font-size:14px;line-height:1.8;color:#2a1a08;">{body_html}</div>
        </div>
    </div>

    {sources_html}

    <div style="padding:16px 28px;background:#f0f0f0;font-size:11px;
                color:#888;font-family:monospace;">
        Generated by IntelBrief · Auto-run · Review before sending
    </div>

    </body></html>
    """


# ── Step 5: Send email ────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str):
    """Sends a single email to your inbox via Gmail SMTP."""

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())


# ── Main Orchestrator ─────────────────────────────────────────────────────────

def run():
    print(f"\n{'='*60}")
    print(f"IntelBrief run started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # 1. Load contacts from repo
    df = load_contacts()
    df = df[df["company"].notna()].head(MAX_CONTACTS)

    results = []

    for _, row in df.iterrows():
        contact = row.to_dict()
        name    = contact.get("person", "Unknown")
        company = contact.get("company", "")
        role    = contact.get("role", "")

        print(f"Processing: {name} @ {company}...")

        try:
            # 2. Search for relevant news — returns text for Claude + source list for rendering
            news, sources = search_news_for_contact(name, role, company)

            # 3. Generate brief + email draft
            output = generate_brief_and_email(contact, news)

            # 4. Build + send
            html = build_email_html(
                contact,
                output["brief_items"],
                sources,
                output["email_subject"],
                output["email_body"]
            )

            send_email(
                subject=f"IntelBrief · {name} @ {company} · {output['email_subject']}",
                html_body=html
            )

            print(f"  ✓ Sent brief for {name}")
            results.append({"contact": name, "status": "sent"})

        except Exception as e:
            print(f"  ✗ Failed for {name}: {e}")
            results.append({"contact": name, "status": f"error: {e}"})

    sent   = sum(1 for r in results if r["status"] == "sent")
    errors = len(results) - sent
    print(f"\nRun complete: {sent} briefs sent, {errors} errors.")


if __name__ == "__main__":
    run()

