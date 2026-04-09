# 🛠️ Setup Guide

Complete step-by-step instructions for deploying the Market Intelligence RAG System.

## Prerequisites

### System Requirements
- **OS:** Linux, macOS, or WSL2 on Windows
- **Python:** 3.9+ (check with `python3 --version`)
- **Disk Space:** 10GB+ (for embeddings, data, vectors)
- **RAM:** 8GB minimum (16GB+ recommended)
- **GPU:** Optional but recommended for Ollama performance

### External Services
- **Qdrant Vector Database** (self-hosted via Docker)
- **Ollama** (local LLM inference) OR **Claude API Key**
- **Nextcloud** instance (optional, for team collaboration)
- **Brevo/Sendinblue** account (optional, for email)

---

## Step 1: Clone/Copy Repository

```bash
# If cloning from Git
git clone https://github.com/your-org/market-intelligence-rag.git /home/olivier/scripts/news
cd /home/olivier/scripts/news

# Or navigate to existing directory
cd /home/olivier/scripts/news
```

---

## Step 2: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt
```

**Verify installation:**
```bash
python3 -c "import feedparser, ollama, qdrant_client, anthropic; print('✓ All dependencies installed')"
```

---

## Step 3: Set Up External Services

### Option A: Qdrant + Ollama on Remote Machine (Recommended)

**On machine with GPU/resources (e.g., `alice`):**

```bash
# Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo bash get-docker.sh

# Start Qdrant
docker run -d --name qdrant \
  -p 6333:6333 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest

# Start Ollama (or install locally)
docker run -d --name ollama \
  -p 11434:11434 \
  -v ollama_models:/root/.ollama \
  ollama/ollama

# Pull embedding model
docker exec ollama ollama pull nomic-embed-text

# Pull LLM (pick one)
docker exec ollama ollama pull mistral      # Fast, 7B
# OR
docker exec ollama ollama pull neural-chat:7b  # Better quality
```

**Verify:**
```bash
curl http://localhost:6333/health     # Qdrant
curl http://localhost:11434/api/tags  # Ollama
```

### Option B: Local Setup (Single Machine)

```bash
# Install Ollama
wget https://ollama.ai/download/ollama-linux-amd64
chmod +x ollama-linux-amd64
./ollama-linux-amd64  # Starts server on port 11434

# In another terminal: Pull models
ollama pull nomic-embed-text
ollama pull mistral

# Start Qdrant (Docker)
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:latest
```

---

## Step 4: Configure Environment

Create `.env` file in project root:

```bash
cp .env.example .env  # If provided
# OR create from scratch
cat > .env << 'EOF'
# ===== LLM Configuration =====
LLM_PROVIDER=ollama                    # "ollama" or "claude"
CLAUDE_API_KEY=sk-ant-...              # Only if LLM_PROVIDER=claude
OLLAMA_HOST=http://alice:11434         # Ollama server address
OLLAMA_MODEL=mistral                   # or neural-chat:7b, etc.

# ===== Vector Database =====
QDRANT_HOST=alice                      # localhost if local
QDRANT_PORT=6333

# ===== Embeddings =====
EMBED_PROVIDER=ollama                  # "ollama" or "openai"
EMBED_MODEL=nomic-embed-text           # or text-embedding-3-small
OPENAI_API_KEY=sk-...                  # Only if EMBED_PROVIDER=openai

# ===== Email / Newsletter =====
BREVO_EMAIL_API_URL=https://api.brevo.com/v3/smtp/email
BREVO_API_KEY=xkeysib-...              # From Brevo dashboard
EMAIL_SENDER=noreply@company.com

# ===== Nextcloud Integration =====
NEXTCLOUD_URL=https://sentinel.synio.dev
NEXTCLOUD_USER=marketbot
NEXTCLOUD_PASS=your-password-here
NC_BOT_CHANNEL_PRIVATE=channel-id-1    # Channel token/ID
NC_BOT_CHANNEL_PUBLIC=channel-id-2     # Channel token/ID
EOF
```

**Verify connectivity:**
```bash
source .venv/bin/activate

# Test Ollama
python3 -c "import ollama; c = ollama.Client(host='http://alice:11434'); print(c.list())"

# Test Qdrant
python3 -c "from qdrant_client import QdrantClient; c = QdrantClient('alice', 6333); print(c.get_collections())"

# Test Claude (if using)
python3 -c "from anthropic import Anthropic; c = Anthropic(api_key='sk-...'); print('✓ Claude OK')"
```

---

## Step 5: Test News Collection

```bash
source .venv/bin/activate

# Run once to generate initial data
python3 collect_news.py

# Check output
ls -lh Final_Market_Screening*.txt
head -50 Final_Market_Screening*.txt
```

**Expected output:**
- `Final_Market_Screening_2026-04-09_....txt` — Daily report
- Email sent (if BREVO configured)
- Nextcloud post (if NC configured)
- `raw_data_*.txt` and `past_summaries_*.txt` updated

---

## Step 6: Ingest Data into Vector Database

```bash
source .venv/bin/activate

# Full ingestion (all topics)
python3 ingest.py --verbose

# Check Qdrant collections
python3 -c "from qdrant_client import QdrantClient; c = QdrantClient('alice', 6333); [print(col) for col in c.get_collections().collections]"
```

**Expected output:**
- Qdrant collections created: `news_iot_supply_chain`, `news_heating_hvac`, etc.
- 20-50 chunks per collection
- Embeddings computed

---

## Step 7: Test the Bot

```bash
source .venv/bin/activate

# Single query test
python3 bot.py --test-query "What are key IoT supply chain challenges?"

# Should print:
# ================================================================================
# QUESTION: What are key IoT supply chain challenges?
# ================================================================================
# ANSWER: [Generated response with RAG context]
# ================================================================================
```

---

## Step 8: Deploy & Schedule

### Option A: Continuous Bot (Nextcloud Monitoring)

```bash
# Run in background
nohup python3 bot.py --channel both --poll-interval 30 > bot.log 2>&1 &

# Monitor output
tail -f bot.log

# Stop
pkill -f "python3 bot.py"
```

### Option B: Daily News Collection (Cron)

```bash
# Edit crontab
crontab -e

# Add line (runs at 9 AM daily)
0 9 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 collect_news.py >> logs/collect.log 2>&1

# Verify
crontab -l
```

### Option C: Nightly Re-ingestion (Keep Embeddings Fresh)

```bash
# Add to crontab (daily at 11 PM)
0 23 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 ingest.py >> logs/ingest.log 2>&1
```

---

## Step 9: Verify Full Pipeline

```bash
# 1. Check collection sizes
python3 ingest.py --verbose

# 2. Test bot query
python3 bot.py --test-query "Tell me about recent supply chain disruptions"

# 3. Check latest report
cat Final_Market_Screening_*.txt | head -100

# 4. Monitor logs
tail -f bot.log collect.log ingest.log
```

---

## Troubleshooting

### Issue: "Connection refused" (Qdrant/Ollama)
```bash
# Check if services are running
curl http://alice:6333/health
curl http://alice:11434/api/tags

# Restart Qdrant
docker restart qdrant

# Restart Ollama
pkill ollama && ollama serve &
```

### Issue: "model not found" (Ollama)
```bash
# Pull the model
ollama pull nomic-embed-text
ollama pull mistral
```

### Issue: "CLAUDE_API_KEY not found"
```bash
# Check .env
grep CLAUDE_API_KEY .env

# Ensure it's exported
export CLAUDE_API_KEY=sk-ant-...
```

### Issue: No Nextcloud messages appear
```bash
# Verify tokens in .env
grep NC_BOT_CHANNEL .env

# Test API directly
curl -u marketbot:password https://sentinel.synio.dev/ocs/v2.php/apps/spreed/api/v4/chat/YOUR_TOKEN \
  -H "OCS-APIRequest: true"

# Check bot logs
tail -100 bot.log | grep -i nextcloud
```

### Issue: Slow bot responses
```bash
# Use faster model
export OLLAMA_MODEL=mistral

# Or switch to Claude (if budget allows)
export LLM_PROVIDER=claude
```

---

## Performance Tuning

### For Speed
- Use `mistral` instead of larger models (7B vs 13B+)
- Deploy Ollama on GPU machine
- Use faster embedding: `openai text-embedding-3-small`

### For Quality
- Use `neural-chat:7b` or `mixtral`
- Increase Claude context window (in `.env`)
- Use `openai text-embedding-3-large` for semantic search

### For Cost
- Use Ollama (free, local)
- Limit Brevo emails to key stakeholders
- Batch news collection (1x daily vs. hourly)

---

## Next Steps

1. **Start bot:** `python3 bot.py --channel both`
2. **Ask questions** in Nextcloud channels
3. **Monitor trends** in daily reports
4. **Customize topics** (see [EXTENDING.md](./EXTENDING.md))
5. **Add integrations** (Slack, Teams, etc.)

---

## Support

For issues or questions:
- Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Review [ARCHITECTURE.md](./ARCHITECTURE.md)
- Check logs: `bot.log`, `collect.log`, `ingest.log`

Happy monitoring! 🚀
