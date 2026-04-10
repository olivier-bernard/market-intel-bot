# 🚀 Quick Start Checklist

Complete this checklist to deploy the Market Intelligence RAG system.

## Prerequisites

- [ ] Python 3.9+ installed
- [ ] Git access to repository
- [ ] Access to machine running Ollama/Qdrant (or local setup)
- [ ] API keys (see below)

## API Keys & Credentials

Gather these before starting:

- [ ] **Claude API Key** (from console.anthropic.com) — Optional but recommended
- [ ] **Brevo API Key** (from app.brevo.com) — For email distribution
- [ ] **Nextcloud credentials** — Bot username/password
- [ ] **Nextcloud channel tokens** — Copy from channel URLs
- [ ] **OpenAI API Key** — Only if using OpenAI embeddings
- [ ] **Slack Bot Token** — Only if using Slack instead of Nextcloud

## Setup (30 minutes)

### Step 1: Clone Repository
```bash
git clone https://github.com/your-org/market-intel-bot.git
cd market-intel-bot
# (or your project directory)
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
- [ ] Complete

### Step 3: Configure Environment
```bash
cp .env.example .env
nano .env
# Add API keys, hosts, tokens
```
- [ ] `.env` created and populated
- [ ] All required fields filled
- [ ] API keys are valid

### Step 4: Verify External Services
```bash
# Qdrant
curl http://alice:6333/health

# Ollama
curl http://alice:11434/api/tags

# Claude (if using)
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $CLAUDE_API_KEY"
```
- [ ] Qdrant responding
- [ ] Ollama responding
- [ ] Claude API responding (if applicable)

## First Run

### Step 5: Collect News
```bash
python3 collect_news.py
```
- [ ] Runs without errors
- [ ] Creates `Final_Market_Screening_<timestamp>.txt`
- [ ] Creates/updates `raw_data_*.txt` files
- [ ] Creates/updates `past_summaries_*.txt` files
- [ ] Email sent (check inbox)
- [ ] Nextcloud message posted (check channel)

### Step 6: Ingest Data
```bash
python3 ingest.py --verbose
```
- [ ] Runs without errors
- [ ] Reports chunks ingested per topic
- [ ] Collections created in Qdrant
- [ ] No memory errors

### Step 7: Test Bot
```bash
python3 bot.py --test-query "What are supply chain challenges?"
```
- [ ] Runs without errors
- [ ] Returns an answer with context
- [ ] Cites sources from knowledge base

## Deployment

### Step 8: Schedule Collection (Cron)
```bash
crontab -e
# Add: 0 9 * * * cd ~/market-intel-bot && source .venv/bin/activate && python3 collect_news.py >> logs/collect.log 2>&1
```
- [ ] Cron job created
- [ ] Verified with `crontab -l`
- [ ] `logs/` directory created

### Step 9: Schedule Re-ingestion (Cron)
```bash
# Add: 0 23 * * * cd ~/market-intel-bot && source .venv/bin/activate && python3 ingest.py >> logs/ingest.log 2>&1
```
- [ ] Ingestion scheduled for nightly

### Step 10: Run Bot Continuously
```bash
# Option A: Terminal with nohup
nohup python3 bot.py --channel both > logs/bot.log 2>&1 &

# Option B: Systemd service (see SETUP_GUIDE.md)
```
- [ ] Bot running in background
- [ ] Logs accessible at `bot.log`

## Validation

### Health Checks
```bash
# Verify services running
ps aux | grep "python3 bot.py"
ps aux | grep "ollama"
docker ps | grep qdrant

# Verify logs
tail -20 logs/bot.log | grep -v DEBUG
tail -20 logs/collect.log

# Verify latest report
ls -lh Final_Market_Screening_*.txt | tail -1
```

- [ ] Bot process running
- [ ] Qdrant container running
- [ ] Ollama service running (if using)
- [ ] Latest collection report recent (<24h)

### Manual Testing

**Test news collection:**
```bash
python3 collect_news.py
# Should complete in 2-5 minutes
```
- [ ] Completes successfully
- [ ] Report generated
- [ ] Email sent
- [ ] Nextcloud message posted

**Test ingestion:**
```bash
python3 ingest.py --topics IoT_Supply_Chain
# Should complete in 1-2 minutes
```
- [ ] Completes successfully
- [ ] Collection updated in Qdrant

**Test Q&A:**
```bash
python3 bot.py --test-query "What are key market trends?"
# Should respond in 2-5 seconds
```
- [ ] Returns answer with sources

## Post-Deployment

### Monitor
- [ ] Check `logs/bot.log` daily for errors
- [ ] Monitor Qdrant collection sizes monthly
- [ ] Test email delivery regularly
- [ ] Verify Nextcloud messages posting

### Maintain
- [ ] Rotate API keys quarterly
- [ ] Review and update RSS feeds monthly
- [ ] Archive old data annually
- [ ] Update documentation after customizations

### Scale
Once comfortable, consider:
- [ ] Adding new topics (see CUSTOM_TOPICS_TEMPLATE.py)
- [ ] Switching to Slack/Teams (see templates)
- [ ] Building web dashboard (see dashboard template)
- [ ] Implementing multi-turn conversations
- [ ] Adding hybrid search (keyword + semantic)

## Configuring Segments (`segments.json`)

All topics, feeds, emails, and Nextcloud routing are defined in `segments.json` at the root of the script directory. The Python script never needs to be edited to add or modify a topic.

### Getting started

```bash
# Copy the template to your local config
cp segments.json.example segments.json

# Edit with your feeds, prompts, and Nextcloud tokens
nano segments.json
```

### File structure

```json
{
  "_defaults": {
    "nc_url":  "https://your-nextcloud.example.com",
    "nc_user": "botuser",
    "nc_pass": "bot-app-password"
  },
  "segments": {
    "My_Topic": {
      "feeds":        ["https://example.com/feed/"],
      "arxiv_query":  "keywords for arxiv search, or null to skip",
      "prompt":       "System persona and focus areas for the LLM summary.",
      "recipient":    "you@example.com",
      "color":        "#hexcolor",
      "icon":         "🔎",
      "nc_token":     "nextcloud-talk-channel-token"
    }
  }
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `feeds` | yes | List of RSS/Atom feed URLs to collect articles from |
| `arxiv_query` | yes | Keyword query for arXiv preprint search; set to `null` to skip arXiv |
| `prompt` | yes | LLM system prompt — defines the analyst persona and focus |
| `recipient` | yes | Email address to send the HTML newsletter to |
| `color` | yes | Hex color used as the card accent in the HTML email |
| `icon` | yes | Emoji displayed in the email card header |
| `nc_token` | yes | Nextcloud Talk channel token (copy from the channel URL) |
| `nc_url` | no | Override Nextcloud server URL for this segment only |
| `nc_user` | no | Override Nextcloud bot username for this segment only |
| `nc_pass` | no | Override Nextcloud bot password for this segment only |

### `_defaults` block

`_defaults` holds the shared Nextcloud server credentials used by every segment that does **not** provide its own `nc_url` / `nc_user` / `nc_pass`. Fill it in once and all segments inherit it.

### Overriding the Nextcloud server per segment

If one of your channels lives on a **different Nextcloud instance**, add `nc_url`, `nc_user`, and `nc_pass` directly inside that segment's object. They override the `_defaults` for that segment only:

```json
"Medical_CCS": {
  "feeds": ["..."],
  "nc_token": "abc123",
  "nc_url":  "https://other-server.example.com",
  "nc_user": "otherbot",
  "nc_pass": "other-app-password"
}
```

### Adding a new segment

1. Open `segments.json`.
2. Copy any existing segment block and paste it as a new key under `"segments"`.
3. Change the key name (e.g. `"Finance_AI"`), update all fields, and save.
4. Run `python3 collect_news.py` — the new segment is picked up automatically.

No restart, no code change required.

---

## Support

If something breaks:
1. Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
2. Review logs: `tail -100 logs/bot.log | grep ERROR`
3. Test components independently
4. Refer to [CONFIG_GUIDE.md](../CONFIG_GUIDE.md) for settings

## Customization Ideas (Later)

- [ ] Add a new topic (Legal, Finance, Real Estate)
- [ ] Integrate Slack instead of Nextcloud
- [ ] Build web dashboard for Q&A
- [ ] Implement hybrid search (keyword + semantic)
- [ ] Add multi-turn conversation memory
- [ ] Create custom chunking for specialized content
- [ ] Deploy with Docker

See [EXTENDING.md](../EXTENDING.md) for recipes.

---

## Quick Reference

| Task | Command |
|------|---------|
| Start bot | `python3 bot.py --channel both` |
| Test bot | `python3 bot.py --test-query "..."` |
| Collect news | `python3 collect_news.py` |
| Ingest all | `python3 ingest.py` |
| Ingest one topic | `python3 ingest.py --topics IoT_Supply_Chain` |
| View logs | `tail -f logs/bot.log` |
| Check health | `curl http://alice:6333/health` |
| Stop bot | `pkill -f "python3 bot.py"` |

---

**Completion:** Once all checkboxes checked, your system is live! 🎉

**Next:** Read [EXTENDING.md](../EXTENDING.md) to customize for your domain.
