# Market Intelligence RAG System

News collection → semantic indexing → RAG-powered Q&A. Automates market monitoring with AI summarization and team intelligence retrieval via Nextcloud.

**Core features:**
- Multi-source news collection (100+ RSS feeds, arXiv) across 5 business domains
- Claude/Ollama summarization with delta analysis (flags new signals)
- Semantic embedding + vector indexing in Qdrant
- Email distribution (Brevo) + Nextcloud Talk posting
- RAG-powered chatbot for team Q&A

---

## Quick Start (5 minutes)

```bash
# 1. Setup
cd /home/olivier/scripts/news
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit: LLM_PROVIDER, CLAUDE_API_KEY, QDRANT_HOST, NC_BOT_CHANNEL_*, etc.

# 3. Collect & ingest
python3 collect_news.py
python3 ingest.py --verbose

# 4. Test the bot
python3 bot.py --test-query "What are IoT supply chain risks?"

# 5. Run bot (continuous)
python3 bot.py --channel both --poll-interval 30
```

---

## Architecture

```
RSS Feeds + arXiv
       │
       ▼
[collect_news.py]  ──→  Claude/Ollama Summarization
       │
       ├──→  Email (Brevo)
       ├──→  Nextcloud Talk
       └──→  raw_data_*.txt + past_summaries_*.txt
              │
              ▼
          [ingest.py]  ──→  Embed + Chunk
              │
              ▼
           ┌─────────┐
           │ Qdrant  │
           │ (alice) │
           └────┬────┘
                │
                ▼
            [bot.py]  ──→  Semantic Search + RAG
                │
                ▼
         Nextcloud Q&A
```

---

## Components

| Script | Role |
|--------|------|
| **collect_news.py** | Polls feeds, generates summaries (Claude/Ollama), sends emails & Nextcloud posts |
| **ingest.py** | Chunks data, generates embeddings, stores in Qdrant collections |
| **bot.py** | Monitors Nextcloud channels, retrieves context, answers with RAG |

### collect_news.py
Runs on schedule (daily cron). Configurable per-topic:
- Custom RSS feeds + arXiv queries
- LLM prompts & background context
- Delta analysis (flags new signals)
- Email recipients + Nextcloud channels

```bash
python3 collect_news.py
# Output: Final_Market_Screening_<timestamp>.txt, emails sent, Nextcloud posts
```

### ingest.py
Embeds raw data and summaries into searchable vectors.

```bash
python3 ingest.py --rebuild              # Full rebuild
python3 ingest.py --topics IoT_Supply_Chain  # Single topic
python3 ingest.py --verbose              # Debug mode
```

### bot.py
Live Q&A in Nextcloud. Polls channels, detects questions, retrieves RAG context, answers intelligently.

**Smart behavior:**
- **Private channel** (1-on-1): Answers all questions
- **Public channel** (group): Answers only questions with `@marketbot` mention (to avoid spam)

```bash
python3 bot.py --channel both --poll-interval 30  # Monitor all channels continuously
python3 bot.py --test-query "Your question?"      # Test single query (offline)

# Run in background:
nohup python3 bot.py --channel both > bot.log 2>&1 &
```

**See [BOT_DEPLOYMENT_GUIDE.md](.context/BOT_DEPLOYMENT_GUIDE.md) for production setup & background execution.**

---

## Setup & Deployment

### Prerequisites
- Python 3.10+
- Ollama on `alice:11434` (or local)
- Qdrant on `alice:6333` (or local)
- Nextcloud instance
- Claude API key (optional; falls back to Ollama)

### Installation
```bash
cd /home/olivier/scripts/news
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration
Edit `.env`:
```bash
# LLM
LLM_PROVIDER=claude              # or "ollama"
CLAUDE_API_KEY=sk-ant-...

# Vector DB (on alice)
QDRANT_HOST=alice
QDRANT_PORT=6333

# Embedding
EMBED_PROVIDER=ollama            # or "openai"
EMBED_MODEL=nomic-embed-text

# Nextcloud
NC_BOT_CHANNEL_PRIVATE=xxxxx
NC_BOT_CHANNEL_PUBLIC=xxxxx

# Email (Brevo)
BREVO_API_KEY=xkeysib-...
EMAIL_SENDER=feedback@sapiochain.io
```

### Scheduling (Production)
Add to crontab:
```bash
# Daily 9 AM
0 9 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 collect_news.py

# Ingest daily 10 AM (after collection)
0 10 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 ingest.py

# Bot runs continuously in background
@reboot nohup python3 /home/olivier/scripts/news/bot.py > /home/olivier/scripts/news/bot.log 2>&1 &
```

---

## Topics

- **IoT_Supply_Chain**: Cold-chain, RFID, logistics, real-time visibility
- **Medical_CCS**: Pharma contamination control, GLP-1, quality
- **Heating_HVAC**: Residential heating, SMB systems, efficiency
- **Sport_Market**: Event management, club tech, fan engagement
- **Global_Startups_Geo**: VC funding, early-stage, geography

Each has curated feeds, custom prompts, and email/Nextcloud recipients.

---

## RAG Q&A Example

```bash
$ python3 bot.py --test-query "What are latest supply chain risks?"
```

Bot retrieves top-5 relevant chunks from Qdrant, injects into Claude prompt:

> Based on current market data:
> 1. Geopolitical tensions raise fuel costs 15-25%
> 2. Companies rerouting around Strait of Hormuz
> 3. Real-time inventory visibility now business-critical
>
> **Sources:**
> 1. Supply Chain Volatility (IoT_Supply_Chain) - Score: 0.87
> 2. Logistics Cost (IoT_Supply_Chain) - Score: 0.81

---

## Monitoring

**Health checks:**
```bash
curl http://alice:6333/health              # Qdrant
curl http://alice:11434/api/tags          # Ollama
```

**Maintenance:**
- Weekly: Check collection sizes
- Monthly: Rebuild if search slows
- Quarterly: Rotate API keys

---

## Extending

See [EXTENDING.md](./EXTENDING.md) to:
- Add new topics & feeds
- Customize LLM prompts
- Change embedding models
- Integrate Slack/Teams
- Build RAG dashboards
- Multi-language support

---

## For Customers: Adapt & Deploy

This is a **blueprint** for market intelligence. Customize:

1. **Topics**: Define your domains (legal, finance, health, retail)
2. **Sources**: Curate RSS feeds for your industry
3. **Prompts**: Write analysis instructions for your use case
4. **Branding**: Deploy under your identity

**Example adaptations:**
- Legal: Monitor legislation, court rulings
- Finance: Track market movements, earnings
- Healthcare: Clinical trials, FDA approvals
- Retail: Competitor pricing, supply chain
