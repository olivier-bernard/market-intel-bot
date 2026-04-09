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
cd /home/olivier/scripts/news
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
# Add: 0 9 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 collect_news.py >> logs/collect.log 2>&1
```
- [ ] Cron job created
- [ ] Verified with `crontab -l`
- [ ] `logs/` directory created

### Step 9: Schedule Re-ingestion (Cron)
```bash
# Add: 0 23 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 ingest.py >> logs/ingest.log 2>&1
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
