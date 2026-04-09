# 📊 Market Intelligence RAG System

A **production-grade, AI-powered news intelligence platform** that automates market monitoring, synthesis, and knowledge retrieval across multiple business domains.

## 🎯 Overview

This system combines:
- **Automated news collection** from 100+ sources across 5 business domains
- **AI-powered synthesis** using Claude or Ollama for intelligent summaries
- **Vector database storage** (Qdrant) for semantic search
- **Send summary by email** using brevo API 
- **Nextcloud integration** for team chat and collaborative intelligence
- **RAG-powered Q&A bot** that retrieves and synthesizes knowledge on demand

**Use cases:**
- Market surveillance for competitive intelligence
- Regulatory & technology trend monitoring
- Automated intelligence briefings
- Real-time Q&A about market developments
- Historical data archival and retrieval

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA COLLECTION                          │
│  collect_news.py                                                │
│  - Polls 100+ RSS feeds, arXiv, news APIs                      │
│  - Segments: IoT, Pharma, HVAC, Sports, Startups              │
│  - Hourly/Daily/Weekly schedules                               │
└────────────────────────┬────────────────────────────────────────┘
                         │ Raw data + Summaries
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE ENGINEERING                        │
│  ingest.py                                                      │
│  - Chunks & embeds articles (nomic-embed-text 768-dim)        │
│  - Stores in Qdrant with rich metadata                         │
│  - Enables semantic search across knowledge base               │
└────────────────────────┬────────────────────────────────────────┘
                         │ Vector embeddings
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE RETRIEVAL                       │
│  bot.py (Nextcloud)          OpenWebUI / Custom Apps           │
│  - RAG-powered Q&A            - Web search interface            │
│  - Live monitoring            - Shareable insights             │
│  - Team collaboration         - Custom integrations            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Components

### 1. **collect_news.py** — News Collection & Synthesis
Automatically gathers news from multiple sources and generates intelligence briefings.

**Features:**
- Multi-topic coverage (IoT Supply Chains, Pharma, HVAC, Sports, Startups)
- Delta analysis: flags *new* signals vs. previous runs
- Email distribution via Brevo (Sendinblue)
- Nextcloud Talk posting with markdown formatting
- Configurable LLM: Claude or Ollama
- Per-segment background context and custom prompts
- Timestamp-based reporting (no overwrites)

**Usage:**
```bash
# Run once
python3 collect_news.py

# Schedule daily at 9 AM
0 9 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 collect_news.py

# Check .env for API keys and configuration
```

**Output:**
- `Final_Market_Screening_<timestamp>.txt` — Daily report
- `raw_data_*.txt` — Raw articles (append mode)
- `past_summaries_*.txt` — Historical summaries (append mode)
- Email sent to configured recipients
- Posted to Nextcloud channel

---

### 2. **ingest.py** — Embedding & Vector Storage
Transforms raw data and summaries into searchable vectors in Qdrant.

**Features:**
- Intelligent chunking (8000-char limit, metadata-aware)
- Dual embedding support: Ollama (nomic-embed-text) or OpenAI
- Batch operations for efficiency
- Collections auto-created per topic
- Support for selective ingestion and full rebuilds

**Usage:**
```bash
# Ingest all topics
python3 ingest.py

# Ingest only one topic
python3 ingest.py --topics IoT_Supply_Chain

# Full rebuild (delete & recreate collections)
python3 ingest.py --rebuild

# Debug mode
python3 ingest.py --verbose
```

**Output:**
- Qdrant collections: `news_iot_supply_chain`, `news_heating_hvac`, etc.
- Each collection indexed for semantic search
- Metadata preserved (topic, date, source type, section)

---

### 3. **bot.py** — RAG-Powered Q&A Bot
Live intelligent assistant that answers questions using real knowledge base context.

**Features:**
- Monitors Nextcloud Talk channels (private + public)
- Detects questions automatically
- Semantic search in Qdrant (5 top results per query)
- Generative answer with RAG context
- Source attribution (cites knowledge base)
- Configurable polling interval
- Test mode for single queries

**Usage:**
```bash
# Monitor channels (continuous polling)
python3 bot.py --channel both --poll-interval 30

# Monitor only private channel
python3 bot.py --channel private

# Test a single query
python3 bot.py --test-query "What are emerging threats in IoT?"

# Run in background
nohup python3 bot.py > bot.log 2>&1 &
```

**Example:**
```
User in Nextcloud: "What are the key challenges in cold-chain logistics?"

Bot (after RAG search):
"Based on current market intelligence:
1. Geopolitical volatility is driving fuel costs up 15-25%
2. Companies like Hyundai are rerouting around the Strait of Hormuz
3. Real-time inventory visibility is moving from 'nice-to-have' to critical...

Knowledge Base Sources:
1. Supply Chain Volatility (IoT_Supply_Chain) - Score: 0.87
2. Logistics Cost Pressure (IoT_Supply_Chain) - Score: 0.81
3. Inventory Visibility (IoT_Supply_Chain) - Score: 0.78
"
```

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Python 3.9+
- Ollama running on `alice:11434` (or local)
- Qdrant running on `alice:6333` (or local)
- Nextcloud instance (for Team/Bot features)

### 1. Setup
```bash
cd /home/olivier/scripts/news
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure
Edit `.env`:
```bash
# LLM Choice
LLM_PROVIDER=claude              # or "ollama"
CLAUDE_API_KEY=sk-ant-...        # if using Claude

# Vector DB
QDRANT_HOST=alice
QDRANT_PORT=6333

# Embedding Model
EMBED_PROVIDER=ollama            # or "openai"
EMBED_MODEL=nomic-embed-text

# Nextcloud (for bot)
NC_BOT_CHANNEL_PRIVATE=xxxxx
NC_BOT_CHANNEL_PUBLIC=xxxxx

# Email (for newsletters)
BREVO_API_KEY=xkeysib-...
EMAIL_SENDER=feedback@sapiochain.io
```

### 3. Collect News
```bash
python3 collect_news.py
# Check: Final_Market_Screening_<timestamp>.txt
```

### 4. Ingest into Qdrant
```bash
python3 ingest.py --verbose
# Check: 25+ chunks per topic
```

### 5. Test the Bot
```bash
python3 bot.py --test-query "What are IoT supply chain risks?"
```

### 6. Run the Bot (Continuous)
```bash
python3 bot.py --channel both --poll-interval 30
```

---

## 📊 Topics Covered

| Topic | Focus Area | Sources |
|-------|-----------|---------|
| **IoT_Supply_Chain** | Cold-chain, logistics, RFID, real-time visibility | 15+ feeds |
| **Medical_CCS** | Contamination control, pharma quality, GLP-1 | 12+ feeds |
| **Heating_HVAC** | Residential heating, SMB systems, efficiency | 10+ feeds |
| **Sport_Market** | Event management, club tech, fan engagement | 10+ feeds |
| **Global_Startups_Geo** | VC funding, early-stage companies, geography-specific | 15+ feeds |

**To add a new topic:** See [EXTENDING.md](./EXTENDING.md)

---

## 🔧 Configuration & Customization

### Per-Topic Settings
Edit `collect_news.py` to customize:
- RSS feeds & sources
- Prompts & background context
- Recipient emails
- Nextcloud channels

Example:
```python
segments = {
    "IoT_Supply_Chain": {
        "feeds": [...list of RSS URLs...],
        "prompt": "Summarize emerging threats and opportunities...",
        "recipients": ["team@company.com"],
        "nextcloud_token": "xxx",
    },
    ...
}
```

### LLM Options
- **Claude:** Best for quality. Requires API key. Costs ~$0.03 per briefing.
- **Ollama:** Free, local. Requires 16GB+ RAM. Runs on same machine as Qdrant.

### Embedding Models
- **nomic-embed-text** (768-dim): Fast, good quality, free via Ollama
- **OpenAI text-embedding-3-small** (1536-dim): Superior quality, costs ~$0.02 per 1M tokens

---

## 📈 Scaling & Deployment

### Single Machine (Dev/Demo)
- Ollama + Qdrant on shared hardware
- All scripts running locally
- Email + Nextcloud integration

### Distributed (Production)
```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  News Collector │────▶│  Ollama/GPU  │────▶│  Qdrant     │
│  (Daily cron)   │     │  (alice)     │     │  (alice)    │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                    ▲
                                                    │
                            ┌───────────────────────┤
                            │                       │
                        ┌───────────┐         ┌──────────┐
                        │  Nextcloud│         │OpenWebUI │
                        │   Bot     │         │(Optional)│
                        └───────────┘         └──────────┘
```

**Recommendations:**
- Qdrant: persistent volume (SSD for <50GB)
- Ollama: GPU optional but recommended for <2s response times
- Make `raw_data_*.txt` and `past_summaries_*.txt` shared storage

---

## 🔍 Monitoring & Maintenance

### Health Checks
```bash
# Qdrant connection
curl http://alice:6333/health

# Ollama availability
curl http://alice:11434/api/tags

# Qdrant collection stats
python3 -c "from qdrant_client import QdrantClient; c = QdrantClient('alice', 6333); print(c.get_collection('news_iot_supply_chain').points_count)"
```

### Logs
- `bot.log` — Bot runtime (if using `nohup`)
- `.env` should be kept secure (add to `.gitignore`)

### Maintenance
- **Weekly:** Check Qdrant collection sizes
- **Monthly:** Rebuild collections if searching feels slow
- **Quarterly:** Rotate API keys (Claude, Brevo, Nextcloud)

---

## 📚 Documentation

- [SETUP_GUIDE.md](./SETUP_GUIDE.md) — Step-by-step installation
- [ARCHITECTURE.md](./ARCHITECTURE.md) — Technical deep-dive
- [CONFIG_GUIDE.md](./CONFIG_GUIDE.md) — All configuration options
- [EXTENDING.md](./EXTENDING.md) — Add new topics, customize prompts
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — Common issues & fixes

---

## 🎓 For Customers: Use as a Blueprint

This system is **fully open** for customization:

### Adapt to Your Domain
1. Define your **topics** (not just tech)
2. Curate **news sources** (RSS feeds, APIs)
3. Write **prompts** for your use case
4. Deploy with your **branding**

### Example Customizations
- **For Legal:** Monitor regulatory changes, court rulings, legislation
- **For Finance:** Track market movements, earnings, bonds, crypto
- **For Healthcare:** Monitor clinical trials, FDA approvals, hospital trends
- **For Retail:** Monitor competitor pricing, supply chain, consumer trends

### Integration Points
- **Slack/Teams** instead of Nextcloud (easy adaptation)
- **Custom dashboards** (query Qdrant directly)
- **Webhook notifications** (replace polling)
- **LangChain/LlamaIndex** for advanced RAG patterns

See [EXTENDING.md](./EXTENDING.md) for recipes.

---

## 📄 License & Support

This system is provided as-is for demonstration and customization.

**Questions?** Contact your implementation team.

---

## 🎯 Next Steps

1. **Deploy locally** following [SETUP_GUIDE.md](./SETUP_GUIDE.md)
2. **Test with sample queries** using `bot.py --test-query "..."`
3. **Customize topics** in `collect_news.py`
4. **Schedule daily runs** with cron
5. **Monitor Nextcloud** for bot responses

Good luck! 🚀
