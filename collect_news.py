import feedparser
import arxiv
import json
import ollama
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from newspaper import Article

import requests
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
BREVO_EMAIL_API_URL = os.getenv("BREVO_EMAIL_API_URL")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "marketbot@example.com")

# --- LLM CONFIGURATION ---
# Choose which LLM to use: 'ollama' or 'claude'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
if LLM_PROVIDER == "claude" and not CLAUDE_API_KEY:
    raise ValueError("LLM_PROVIDER set to 'claude' but CLAUDE_API_KEY not found in .env")

if LLM_PROVIDER == "claude":
    claude_client = Anthropic(api_key=CLAUDE_API_KEY)
    print(f"[INFO] Using Claude as LLM provider")
else:
    print(f"[INFO] Using Ollama as LLM provider")

# OLLAMA CONFIGURATION
# OLLAMA_MODEL = 'qwen35-35b-iq3s'
# OLLAMA_MODEL = 'gemma3:12b'
OLLAMA_MODEL = 'VladimirGav/gemma4-26b-16GB-VRAM'
OLLAMA_HOST = 'http://alice:11434'

if LLM_PROVIDER == "ollama":
    ollama_client = ollama.Client(host=OLLAMA_HOST)

# --- OLLAMA OPTIONS ---
OLLAMA_OPTIONS = {
    "num_ctx": 16384,      # Context window — increased to handle multiple feeds per segment
    "temperature": 0.4,   # Lower = more factual and consistent for intelligence briefs
    "top_p": 0.9,
}

# --- CLAUDE OPTIONS ---
CLAUDE_MODEL = "claude-haiku-4-5"  # Latest Claude model
CLAUDE_OPTIONS = {
    "max_tokens": 2048,
    "temperature": 0.4,  # Same low temperature for consistency
}

# --- BACKGROUND CONTEXT ---
# Static background injected into every analysis to ground the AI in your business context
BACKGROUND_CONTEXT = (
    "You are a Senior Market Intelligence Agent working for a technology company that builds digital solutions "
    "across four specialist domains: (1) IoT and cold-chain / temperature-controlled supply chains, "
    "(2) pharmaceutical contamination control and quality management, "
    "(3) sports event and club management platforms, and "
    "(4) residential and SMB heating installation design tools. "
    "Your mission is to monitor global news, research, regulation, and startup activity in each domain, "
    "identify emerging opportunities and competitive threats, and produce actionable recommendations "
    "that help the company develop and position its products. "
    "Always connect findings to concrete business impact and flag high-priority signals clearly."
)

# --- CONVERSATION HISTORY (optional, populated at runtime) ---
# Add prior messages here to give the model memory across segments or runs.
# Format: [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
CONVERSATION_HISTORY = []


def _load_segments(path="segments.json"):
    """Load segment configuration from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    defaults = data.get("_defaults", {})
    segments = {}
    for name, cfg in data["segments"].items():
        # Merge defaults into each segment; segment-level keys take precedence
        merged = {**defaults, **cfg}
        segments[name] = merged
    return segments, defaults


SEGMENTS, NC_DEFAULTS = _load_segments()


def send_to_nextcloud(content, config):
    """Post a message to the Nextcloud Talk channel defined in the segment config."""
    nc_url  = config.get("nc_url",  NC_DEFAULTS.get("nc_url",  ""))
    nc_user = config.get("nc_user", NC_DEFAULTS.get("nc_user", ""))
    nc_pass = config.get("nc_pass", NC_DEFAULTS.get("nc_pass", ""))
    nc_token = config.get("nc_token", "")

    if not nc_token:
        print("  [Nextcloud] No token configured for this segment — skipping.")
        return

    print(f"Sending summary to Nextcloud Talk ({nc_url})...")
    endpoint = f"{nc_url}/ocs/v2.php/apps/spreed/api/v1/chat/{nc_token}"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "message": content,
        "actorDisplayName": "Market Intelligence Bot"
    }
    try:
        response = requests.post(endpoint, auth=(nc_user, nc_pass), headers=headers, json=payload)
        if response.status_code == 201:
            print("Successfully posted to Nextcloud!")
        else:
            print(f"Failed to post. Status: {response.status_code}, Error: {response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

# --- 2. CORE FUNCTIONS ---

def load_previous_summary(segment_name):
    """Load the most recent summary from the past summaries file."""
    fname = f"past_summaries_{segment_name}.txt"
    try:
        with open(fname, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return None
        # Extract the last block (split by ########)
        blocks = content.split("#" * 60)
        if len(blocks) >= 2:
            last_block = blocks[-1].strip()
            return last_block
    except FileNotFoundError:
        pass
    return None


def save_current_summary(segment_name, summary, date_str):
    """Append today's summary to the past summaries file with a date header."""
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    chunk_header = f"\n{'#'*60}\n# {segment_name} | {date_str} ({run_ts})\n{'#'*60}\n"
    fname = f"past_summaries_{segment_name}.txt"
    with open(fname, "a", encoding="utf-8") as f:
        f.write(chunk_header + summary)


def fetch_content(config):
    """Gathers data from RSS and ArXiv for a specific segment."""
    segment_text = ""
    
    # Fetch RSS News
    for url in config["feeds"]:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # Limit to top 3 for speed/token limits
            try:
                article = Article(entry.link)
                article.download()
                article.parse()
                segment_text += f"SOURCE: {entry.title}\n{article.text[:1500]}\n\n"
            except: continue

    # Fetch ArXiv Papers (if query exists)
    if config.get("arxiv_query"):
        client = arxiv.Client()
        search = arxiv.Search(query=config["arxiv_query"], max_results=2)
        for result in client.results(search):
            segment_text += f"PAPER: {result.title}\nABSTRACT: {result.summary}\n\n"
            
    return segment_text

def generate_newsletter(segment_name, content, prompt, history=None, previous_summary=None):
    """Generate intelligence brief using either Claude or Ollama based on LLM_PROVIDER config."""
    system_msg = (
        f"{BACKGROUND_CONTEXT}\n\n"
        f"{prompt}\n\n"
        "INSTRUCTIONS FOR YOUR RESPONSE:\n"
        "- Produce a SYNTHETIC intelligence brief. Do NOT list or repeat individual source titles or URLs.\n"
        "- Do NOT include email-style headers (From:, Date:, Subject:, etc.). Start directly with the numbered sections.\n"
        "- Merge and distil findings across all sources into coherent insights. If multiple sources confirm "
        "the same trend, state the trend with confidence — not each individual article.\n"
        "- Be concise: each section should be 3–6 punchy bullet points maximum.\n"
        "- Write for a senior business reader who needs findings and decisions, not a reading list.\n"
        "- Write in an objective, third-party analytical tone. Do NOT use 'we', 'our team', or 'our company'. "
        "Instead use phrases like 'there is an opportunity to', 'it is recommended that the team', "
        "'the market signals indicate', 'a competitive risk exists', 'this could be leveraged by'.\n"
        "- Raw source data is archived separately; your job is interpretation and signal extraction only.\n\n"
        "Structure your response with exactly these numbered sections:\n"
        "1. Executive Summary (2–3 sentences max — the single most important thing to know this week)\n"
        "2. Key Findings (top signals and confirmed trends)\n"
        "3. Technology & Innovation Watch (notable technical developments or research)\n"
        "4. Competitor & Startup Radar (new entrants, funding rounds, product launches)\n"
        "5. Actionable Recommendations (concrete next steps for the team)\n"
        "6. Risks & Opportunities (emerging threats or market gaps to monitor)"
    )

    # Build user message based on whether we have previous summary
    if previous_summary:
        user_msg = (
            "CONTEXT FROM PREVIOUS ANALYSIS (for reference):\n"
            "---\n"
            f"{previous_summary}\n"
            "---\n\n"
            "Now, analyze TODAY's data:\n\n"
            f"{content}\n\n"
            "FLAG NEW SIGNALS: In your 'Key Findings' section, prioritize and highlight what is NEW or has changed "
            "since the previous brief. Only re-report ongoing trends if they have materially evolved. "
            "Use phrases like 'NEW SIGNAL:' or 'ESCALATION:' to mark novel items."
        )
    else:
        user_msg = f"Analyze this data for the {segment_name} segment:\n\n{content}"

    if LLM_PROVIDER == "claude":
        return _generate_with_claude(system_msg, user_msg, history)
    else:
        return _generate_with_ollama(system_msg, user_msg, history)


def _generate_with_claude(system_msg, user_msg, history=None):
    """Generate summary using Claude API."""
    messages = list(history or CONVERSATION_HISTORY)
    messages.append({"role": "user", "content": user_msg})
    
    response = claude_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_OPTIONS["max_tokens"],
        temperature=CLAUDE_OPTIONS["temperature"],
        system=system_msg,
        messages=messages,
    )
    return response.content[0].text


def _generate_with_ollama(system_msg, user_msg, history=None):
    """Generate summary using Ollama API."""
    messages = [
        {'role': 'system', 'content': system_msg},
        *(history or CONVERSATION_HISTORY),
        {'role': 'user', 'content': user_msg}
    ]

    response = ollama_client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        options=OLLAMA_OPTIONS
    )
    return response['message']['content']


# --- 3. FORMATTING & DISTRIBUTION ---


SECTION_ICONS = ["\ud83d\udccb", "\ud83d\udcf0", "\ud83d\udd2c", "\ud83d\udc41\ufe0f", "\u26a1", "\u26a0\ufe0f"]

# Utility to get the model name used for generation
def get_model_name():
    if LLM_PROVIDER == "ollama":
        return OLLAMA_MODEL
    elif LLM_PROVIDER == "claude":
        return CLAUDE_MODEL
    else:
        return "Unknown"


def clean_summary(text):
    """Remove any email-like headers (From:, Date:, Subject:) that the model may have generated."""
    lines = text.split('\n')
    # Skip any lines that start with email headers
    cleaned_lines = []
    for line in lines:
        if line.strip().startswith(('From:', 'Date:', 'Subject:', 'To:')):
            continue  # Skip email headers
        cleaned_lines.append(line)
    result = '\n'.join(cleaned_lines).strip()
    # Also remove any leading blank lines
    while result.startswith('\n'):
        result = result[1:]
    return result


def markdown_to_html(text):
    """Convert markdown formatting to HTML tags."""
    # Convert bold **text** to <strong>text</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Convert italic *text* to <em>text</em> (but not already processed **text**)
    text = re.sub(r'(?<!\*)\*(.*?)\*(?!\*)', r'<em>\1</em>', text)
    # Convert heading ### text to <h4>text</h4>
    text = re.sub(r'^###\s+(.+)$', r'<h4 style="margin:12px 0 8px;font-size:16px;font-weight:600;color:#1f2937;">\1</h4>', text, flags=re.MULTILINE)
    # Convert heading ## text to <h3>text</h3>
    text = re.sub(r'^##\s+(.+)$', r'<h3 style="margin:12px 0 8px;font-size:18px;font-weight:700;color:#111827;">\1</h3>', text, flags=re.MULTILINE)
    # Convert unordered list items * text to <li>text</li>
    lines = text.split('\n')
    result = []
    in_list = False
    for line in lines:
        if re.match(r'^\s*[-*]\s+', line):
            item = re.sub(r'^\s*[-*]\s+', '', line)
            if not in_list:
                result.append('<ul style="margin:8px 0;padding-left:20px;">')
                in_list = True
            result.append(f'<li style="margin:6px 0;padding-left:4px;">{item}</li>')
        else:
            if in_list and line.strip():
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')
    text = '\n'.join(result)
    return text


def parse_sections(text):
    pattern = re.compile(r'^(\d+\.\s+[^\n]+)', re.MULTILINE)
    matches = list(pattern.finditer(text))
    result = []
    for i, match in enumerate(matches):
        title = re.sub(r'^\d+\.\s+', '', match.group(1)).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        result.append((title, content))
    if not result:
        result = [("Summary", text.strip())]
    return result


def format_html_email(segment_name, summary, date_str):
    """Render the newsletter summary as a styled HTML email (inline CSS, email-client safe)."""
    color = SEGMENTS[segment_name].get("color", "#6b7280")
    icon = SEGMENTS[segment_name].get("icon", "\ud83d\udcca")
    title = segment_name.replace("_", " ")
    sections = parse_sections(summary)

    cards_html = ""
    for idx, (sec_title, sec_content) in enumerate(sections):
        sec_icon = SECTION_ICONS[idx] if idx < len(SECTION_ICONS) else "\u2022"
        # Escape HTML entities first
        safe_content = sec_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Convert markdown to HTML
        safe_content = markdown_to_html(safe_content)
        # Convert remaining newlines to <br>, but not inside list tags
        parts = re.split(r'(<ul[\s\S]*?</ul>)', safe_content)
        safe_content = ''.join(
            part if part.startswith('<ul') else part.replace('\n', '<br>')
            for part in parts
        )
        cards_html += (
            f'<div style="border-left:4px solid {color};background:#f8fafc;'
            f'border-radius:0 8px 8px 0;padding:16px 18px;margin-bottom:18px;">'
            f'<div style="color:{color};font-size:12px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin-bottom:8px;">{sec_icon}&nbsp;{sec_title}</div>'
            f'<div style="color:#374151;line-height:1.7;font-size:14px;">{safe_content}</div>'
            f'</div>'
        )

    return (
        '<!DOCTYPE html><html><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '</head>'
        f'<body style="font-family:\'Segoe UI\',Arial,sans-serif;background:#f0f4f8;margin:0;padding:20px;">'
        f'<div style="max-width:680px;margin:auto;background:white;border-radius:12px;overflow:hidden;'
        f'box-shadow:0 4px 16px rgba(0,0,0,0.12);">'
        f'<div style="background:{color};color:white;padding:32px 28px;">'
        f'<div style="font-size:36px;margin-bottom:8px;">{icon}</div>'
        f'<h1 style="margin:0;font-size:22px;font-weight:700;">Market Intelligence &mdash; {title}</h1>'
        f'<div style="margin-top:6px;opacity:0.88;font-size:13px;">{date_str}</div>'
        f'</div>'
        f'<div style="padding:24px;">{cards_html}</div>'
        f'<div style="padding:14px 24px;background:#f8fafc;border-top:1px solid #e5e7eb;'
        f'color:#9ca3af;font-size:12px;text-align:center;">'
        f'Generated by Market Intelligence Bot &bull; Model: {get_model_name()} &bull; {date_str}'
        f'</div></div></body></html>'
    )


def format_nextcloud_message(segment_name, summary, date_str):
    """Render the newsletter summary as a formatted Nextcloud Talk message."""
    icon = SEGMENTS[segment_name].get("icon", "\ud83d\udcca")
    title = segment_name.replace("_", " ").upper()
    sections = parse_sections(summary)

    lines = [
        f"{icon} **MARKET INTELLIGENCE \u2014 {title}**",
        f"\ud83d\udcc5 {date_str}",
        "\u2500" * 32,
        "",
    ]
    for idx, (sec_title, sec_content) in enumerate(sections):
        sec_icon = SECTION_ICONS[idx] if idx < len(SECTION_ICONS) else "\u2022"
        lines.append(f"{sec_icon} **{sec_title}**")
        lines.append(sec_content)
        lines.append("")
    lines += [
        "\u2500" * 32,
        f"_Generated by Market Intelligence Bot | Model: {get_model_name()}_",
    ]
    return "\n".join(lines)


def send_email(recipient, subject, html_body):
    """Send formatted newsletter via Brevo transactional email API."""
    if not BREVO_API_KEY or not BREVO_EMAIL_API_URL:
        print(f"  [Email] Brevo credentials missing (API_KEY={bool(BREVO_API_KEY)}, URL={bool(BREVO_EMAIL_API_URL)}) — skipping.")
        return

    if not recipient or recipient == "olivier@sapiochain.io":
        print(f"  [Email] WARNING: recipient '{recipient}' may be invalid or not configured.")

    payload = {
        "sender": {"name": "Market Intelligence Bot", "email": EMAIL_SENDER},
        "to": [{"email": recipient}],
        "subject": subject,
        "htmlContent": html_body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY,
    }
    try:
        print(f"  [Email] Attempting to send from {EMAIL_SENDER} to {recipient}...")
        response = requests.post(BREVO_EMAIL_API_URL, json=payload, headers=headers, timeout=10)
        if response.status_code in (200, 201):
            print(f"  [Email] ✓ Sent to {recipient}")
        else:
            print(f"  [Email] ✗ Failed ({response.status_code}): {response.text[:200]}")
    except Exception as e:
        print(f"  [Email] ✗ Exception: {e}")


# --- 4. EXECUTION ---

def run_agent():
    consolidated_report = ""
    date_str = datetime.now().strftime("%d %B %Y")

    for name, config in SEGMENTS.items():
        print(f"\n--- Processing {name} ---")
        raw_data = fetch_content(config)

        if raw_data:
            # Load previous summary for delta analysis
            previous_summary = load_previous_summary(name)
            if previous_summary:
                print(f"  [Context] Loaded previous summary for delta analysis")
            
            summary = generate_newsletter(name, raw_data, config["prompt"], previous_summary=previous_summary)
            summary = clean_summary(summary)  # Remove any email headers the model may have generated
            
            # Save this summary for tomorrow's comparison
            save_current_summary(name, summary, date_str)
            
            section_header = f"\n{'='*30}\nSEGMENT: {name.replace('_', ' ')}\n{'='*30}\n"
            consolidated_report += section_header + summary

            # Append raw data with a dated separator — accumulates daily for RAG/embedding ingestion
            run_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            chunk_header = f"\n{'#'*60}\n# SEGMENT: {name} | DATE: {run_ts}\n{'#'*60}\n"
            with open(f"raw_data_{name}.txt", "a", encoding="utf-8") as f:
                f.write(chunk_header + raw_data)

            # Format and send to Nextcloud Talk (per-topic channel)
            nc_message = format_nextcloud_message(name, summary, date_str)
            send_to_nextcloud(nc_message, config)

            # Format and send HTML email via Brevo
            subject = f"[Market Intel] {name.replace('_', ' ')} \u2014 {date_str}"
            html_body = format_html_email(name, summary, date_str)
            send_email(config["recipient"], subject, html_body)

    # Final consolidated save — timestamped so multiple daily runs don't overwrite each other
    run_ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    report_filename = f"Final_Market_Screening_{run_ts}.txt"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(consolidated_report)

    print(f"\nProcess Complete. Report saved as '{report_filename}'.")

if __name__ == "__main__":
    run_agent()
