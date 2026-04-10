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
git clone https://github.com/your-org/market-intel-bot.git
cd market-intel-bot
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
python3 bot.py --poll-interval 30  # Monitor all channels continuously
python3 bot.py --test-query "Your question?"      # Test single query (offline)

# Run in background:
nohup python3 bot.py > bot.log 2>&1 &
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
cd ~/market-intel-bot
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
0 9 * * * cd ~/market-intel-bot && source .venv/bin/activate && python3 collect_news.py

# Ingest daily 10 AM (after collection)
0 10 * * * cd ~/market-intel-bot && source .venv/bin/activate && python3 ingest.py

# Bot runs continuously in background
@reboot nohup python3 ~/market-intel-bot/bot.py > ~/market-intel-bot/bot.log 2>&1 &
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

To add a new topic: open `segments.json`, copy an existing segment block, change the key name and fields. No code change needed.

To change LLM or embedding model: update `OLLAMA_MODEL` / `LLM_PROVIDER` in `.env`.

---

## Troubleshooting

**Qdrant or Ollama not responding**
```bash
curl http://alice:6333/health
curl http://alice:11434/api/tags
docker restart qdrant          # restart Qdrant
pkill ollama && ollama serve & # restart Ollama
```

**"model not found"**
```bash
ollama pull nomic-embed-text
ollama pull VladimirGav/gemma4-26b-16GB-VRAM  # or whichever model you use
```

**LLM fails to load after ingest** — the embedding model occupies GPU memory. `ingest.py` unloads it automatically when finished. If you get a 500 from Ollama, wait a moment and retry.

**No Nextcloud messages appear**
```bash
# Test channel token directly
curl -u botuser:password https://your-nextcloud/ocs/v2.php/apps/spreed/api/v4/chat/TOKEN \
  -H "OCS-APIRequest: true"
```
Check `nc_token`, `nc_url`, `nc_user`, `nc_pass` in `segments.json`.

**CLAUDE_API_KEY not found** — ensure it is set in `.env` with no extra spaces or quotes.

---

## Adapt & Deploy

This is a blueprint for any market intelligence use case. Customize `segments.json` for your domains:

- **Legal**: legislation, court rulings
- **Finance**: market movements, earnings reports
- **Healthcare**: clinical trials, FDA approvals
- **Retail**: competitor pricing, supply chain
