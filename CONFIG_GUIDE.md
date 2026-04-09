# ⚙️ Configuration Guide

Complete reference for all configuration options and environment variables.

---

## Environment Variables (.env)

Create or update `.env` in the project root:

```bash
# Copy template
cp .env.example .env

# Edit
nano .env
```

---

## LLM Configuration

### Claude (Recommended for Quality)

```bash
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-api03-xxxx...

# Optional: override default model
CLAUDE_MODEL=claude-haiku-4-5       # Default: haiku-4-5 (fast)
# Alternative: claude-3-sonnet-20241022  # Higher quality
# Alternative: claude-3-opus-20240229    # Best quality (slower)

# Optional: context window and temperature
CLAUDE_CONTEXT_WINDOW=4096          # Default: 4096 tokens
CLAUDE_TEMPERATURE=0.4              # Default: 0.4 (factual)
```

**Get API Key:**
1. Login to console.anthropic.com
2. Settings → API Keys → Create key
3. Copy and paste to .env
4. Fund your account (pay-as-you-go)

**Cost:** ~$0.03-0.10 per briefing (depends on model and length)

---

### Ollama (Free, Local)

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434   # or http://alice:11434
OLLAMA_MODEL=mistral                 # Default fast: 7B, good quality

# Popular models:
# mistral                    - Fast, 7B, recommended default
# neural-chat:7b             - Balanced, better quality
# mixtral:8x7b               - Best quality, needs strong GPU
# qwen2.5-coder              - Good for technical content
```

**Setup:**
```bash
# Install
wget https://ollama.ai/download/ollama-linux-amd64
chmod +x ollama-linux-amd64
sudo ./ollama-linux-amd64  # Starts server

# Pull models
ollama pull mistral
ollama pull neural-chat:7b

# Test
curl http://localhost:11434/api/tags
```

**Cost:** Free (requires GPU or <2min response times on CPU)

---

## Embedding Configuration

### Ollama Embeddings (Free)

```bash
EMBED_PROVIDER=ollama
EMBED_MODEL=nomic-embed-text         # Default: 768-dimensional
OLLAMA_HOST=http://alice:11434

# Alternative models:
# all-minilm                 - Small, fast (384-dim)
# mxbai-embed-large          - Better quality (1024-dim)
```

### OpenAI Embeddings (Paid)

```bash
EMBED_PROVIDER=openai
EMBED_MODEL=text-embedding-3-small   # or text-embedding-3-large
OPENAI_API_KEY=sk-proj-xxxx...

# Models:
# text-embedding-3-small     - 1536-dim, recommended
# text-embedding-3-large     - 3072-dim, best quality
```

**Cost:** ~$0.02 per 1M tokens (~500K embeddings)

---

## Vector Database Configuration

### Qdrant

```bash
QDRANT_HOST=localhost                # or alice, sentinel.example.com
QDRANT_PORT=6333                     # Default REST API port
QDRANT_GRPC_PORT=6334                # Optional gRPC port (for scaling)
QDRANT_API_KEY=xxxx                  # If using Qdrant Cloud (optional)

# Optional: connection timeout
QDRANT_TIMEOUT=30                    # Seconds
```

**Docker Setup:**
```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

**Connection Verification:**
```bash
curl http://{QDRANT_HOST}:{QDRANT_PORT}/health
# Expected: {"status":"ok"}
```

---

## Nextcloud Integration

### Chat Bot Configuration

```bash
NEXTCLOUD_URL=https://sentinel.synio.dev
NEXTCLOUD_USER=marketbot
NEXTCLOUD_PASS=your-password-or-token

# Channel tokens (copy from channel URL)
# Format: https://sentinel.synio.dev/call/{TOKEN}
NC_BOT_CHANNEL_PRIVATE=4spz2ath      # Private channel (team only)
NC_BOT_CHANNEL_PUBLIC=public-xyz     # Public channel (open discussion)

# Optional: separate tokens for different topics
NC_CHANNEL_HEATING=heating-token
NC_CHANNEL_IOT=iot-token
```

**Get Channel Token:**
1. Open Nextcloud Talk
2. Right-click channel → Copy link
3. Extract `{TOKEN}` from URL
4. Add to .env

**Verify Connection:**
```bash
curl -u "marketbot:password" \
  https://sentinel.synio.dev/ocs/v2.php/apps/spreed/api/v4/chat/TOKEN \
  -H "OCS-APIRequest: true" \
  -H "Accept: application/json"
```

---

## Email Distribution (Brevo)

### Sending Reports via Email

```bash
# Brevo (formerly Sendinblue)
BREVO_EMAIL_API_URL=https://api.brevo.com/v3/smtp/email
BREVO_API_KEY=xkeysib-c0266bb75...

EMAIL_SENDER=noreply@company.com     # From address
EMAIL_SENDER_NAME=Market Intelligence # Display name

# Optional: default recipients (override per-topic in code)
DEFAULT_EMAIL_RECIPIENTS=team@company.com,cto@company.com
```

**Get Brevo API Key:**
1. Login to brevo.com
2. Settings → API & Apps → API Keys
3. Create key (Copy & save)
4. Add to .env

**Verify:**
```bash
curl -X GET https://api.brevo.com/v3/account \
  -H "api-key: $BREVO_API_KEY"
```

---

## Collection & Ingestion Settings

### In collect_news.py

```python
# News source configuration per topic
segments = {
    "IoT_Supply_Chain": {
        "feeds": [
            "https://feeds.supply-chain.com/...",
            "https://logistics-times.com/feed",
            # ... 15+ feeds per topic
        ],
        
        "background_context": (
            "You are a Senior Market Analyst specializing in "
            "IoT and cold-chain logistics..."
        ),
        
        "prompt": (
            "Synthesize today's developments into an "
            "executive intelligence report on supply chains..."
        ),
        
        "recipients": [
            "ops@company.com",
            "strategy@company.com",
        ],
        
        "nextcloud_token": "4spz2ath",  # Channel to post
    },
    # ... more topics
}

# Context window and generation settings
BACKGROUND_CONTEXT = "..."            # Injected into every prompt
CONVERSATION_HISTORY = []             # Multi-turn conversation memory (optional)

# LLM Options (per-provider)
OLLAMA_OPTIONS = {
    "num_ctx": 16384,                 # Context window in tokens
    "temperature": 0.4,               # 0.0 (factual) to 1.0 (creative)
    "top_p": 0.9,                     # Nucleus sampling
    "top_k": 40,                      # Top-K sampling
}

CLAUDE_OPTIONS = {
    "max_tokens": 2048,               # Max response
    "temperature": 0.4,               # Same scale
}
```

---

## Bot Configuration

### In bot.py

```python
# Bot behavior
BOT_NAME = "Market Intelligence Bot"
BOT_CONTEXT_WINDOW = 4               # Previous messages to include

# RAG settings
RAG_SEARCH_LIMIT = 5                 # Results per query
RAG_SIMILARITY_THRESHOLD = 0.4        # Min score (0-1)

# Polling behavior
POLL_INTERVAL = 30                   # Seconds between channel checks

# Topics available for Q&A
TOPICS = [
    "IoT_Supply_Chain",
    "Medical_CCS",
    "Heating_HVAC",
    "Sport_Market",
    "Global_Startups_Geo",
]
```

---

## Advanced: Per-Topic Configuration

### Separate Files per Topic (Optional)

Create `topics.json`:

```json
{
  "IoT_Supply_Chain": {
    "feeds": [
      "https://supply-chain-times.com/feed",
      "https://logistics-ai.com/rss",
      "https://iot-news.com/feed"
    ],
    "context": "You are a supply chain expert...",
    "prompt": "Analyze supply chain developments...",
    "recipients": ["ops@company.com"],
    "nextcloud_token": "4spz2ath",
    "keywords": ["supply", "chain", "logistics", "cold-chain"],
    "update_frequency": "daily",
    "llm_model": "claude",
    "embedding_model": "openai",
    "rag_threshold": 0.5
  },
  "Heating_HVAC": {
    "feeds": [...],
    "context": "...",
    "prompt": "...",
    "recipients": [...],
    "nextcloud_token": "heating-channel",
    "keywords": ["heating", "hvac", "thermostats"],
    "update_frequency": "weekly",
    "llm_model": "ollama",
    "embedding_model": "ollama"
  }
}
```

Load in code:

```python
import json

with open("topics.json") as f:
    segments = json.load(f)
```

---

## Scheduling & Cron

### Daily Collection

```bash
# Edit crontab
crontab -e

# Run at 9 AM daily
0 9 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 collect_news.py >> logs/collect.log 2>&1

# Run at 9 AM on weekdays only
0 9 * * 1-5 cd /home/olivier/scripts/news && ...

# Run every 6 hours
0 */6 * * * cd /home/olivier/scripts/news && ...
```

### Nightly Ingestion

```bash
# Rebuild vector database nightly (11 PM)
0 23 * * * cd /home/olivier/scripts/news && source .venv/bin/activate && python3 ingest.py --rebuild >> logs/ingest.log 2>&1
```

### Bot Daemon

```bash
# Start bot at boot (systemd service)
cat > /etc/systemd/system/market-bot.service << 'EOF'
[Unit]
Description=Market Intelligence Bot
After=network.target

[Service]
Type=simple
User=olivier
WorkingDirectory=/home/olivier/scripts/news
ExecStart=/home/olivier/scripts/news/.venv/bin/python3 /home/olivier/scripts/news/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable market-bot
sudo systemctl start market-bot
```

---

## Logging Configuration

### Log Levels

```python
import logging

# In your scripts
logging.basicConfig(
    level=logging.INFO,    # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
```

### Log Files

```bash
# Create logs directory
mkdir -p logs

# Capture stderr/stdout
nohup python3 bot.py > logs/bot.log 2>&1 &

# Monitor in real-time
tail -f logs/bot.log

# View only errors
grep ERROR logs/bot.log
```

---

## Performance Tuning

### For Speed

```bash
# Use fast models
OLLAMA_MODEL=mistral
EMBED_MODEL=all-minilm

# Reduce context window
OLLAMA_OPTIONS.num_ctx=4096

# Lower similarity threshold (faster, less accurate)
RAG_SIMILARITY_THRESHOLD=0.3
```

### For Quality

```bash
# Use better models
OLLAMA_MODEL=neural-chat:7b
EMBED_MODEL=text-embedding-3-large

# Increase context
OLLAMA_OPTIONS.num_ctx=32768

# Higher similarity threshold (slower, better accuracy)
RAG_SIMILARITY_THRESHOLD=0.6
```

### For Cost

```bash
# Use Ollama (free)
LLM_PROVIDER=ollama
EMBED_PROVIDER=ollama

# Batch jobs
# Reduce poll frequency (bot)
# Collect less frequently (daily vs. hourly)
```

---

## Security Best Practices

### .env Protection

```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo "*.log" >> .gitignore
echo "__pycache__/" >> .gitignore

# Set restrictive permissions
chmod 600 .env

# Never commit secrets
git add --all --dry-run  # Verify before committing
```

### API Key Rotation

Set calendar reminders to rotate:
- **Claude API Key:** Quarterly
- **Brevo API Key:** Quarterly
- **Nextcloud Password:** Quarterly
- **OpenAI API Key:** Quarterly

---

## Monitoring & Health Checks

### Endpoint Health

```bash
# Qdrant
curl http://alice:6333/health

# Ollama
curl http://alice:11434/api/tags

# Nextcloud (requires auth)
curl -u user:pass https://sentinel.synio.dev/ocs/v2.php/apps/spreed/api/v1/avatar/marketbot
```

### System Metrics

```bash
# Disk usage
du -sh /home/olivier/scripts/news

# Database size
du -sh /path/to/qdrant_storage

# Memory usage
ps aux | grep python3
```

---

## Troubleshooting Configuration

### Issue: "Model not found"
```bash
# Verify model installed
ollama list

# Pull model
ollama pull mistral
ollama pull nomic-embed-text
```

### Issue: "Connection refused"
```bash
# Check if service is running
netstat -tln | grep 6333  # Qdrant
netstat -tln | grep 11434 # Ollama

# Restart
docker restart qdrant
pkill ollama && ollama serve &
```

### Issue: "API key invalid"
```bash
# Verify format
echo $CLAUDE_API_KEY | head -c 20
# Should start with: sk-ant-api03-

# Test with curl
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $CLAUDE_API_KEY"
```

---

## Configuration Checklist

- [ ] `.env` created with all required variables
- [ ] Qdrant running and accessible
- [ ] Ollama running (if using)
- [ ] Claude API key configured (if using)
- [ ] Brevo API key configured (if using email)
- [ ] Nextcloud channel tokens added
- [ ] Collection `segments` configured in code
- [ ] Cron jobs scheduled
- [ ] Logs directory created
- [ ] Health checks passing
- [ ] First run completed successfully

---

## Reference: Environment Variables Summary

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `LLM_PROVIDER` | ollama | Yes | Which LLM to use |
| `CLAUDE_API_KEY` | - | If Claude | Claude API authentication |
| `OLLAMA_HOST` | http://localhost:11434 | If Ollama | Ollama server location |
| `QDRANT_HOST` | localhost | Yes | Vector DB server |
| `QDRANT_PORT` | 6333 | Yes | Vector DB port |
| `EMBED_PROVIDER` | ollama | Yes | Embedding provider |
| `EMBED_MODEL` | nomic-embed-text | Yes | Embedding model |
| `BREVO_API_KEY` | - | If email | Email service authentication |
| `EMAIL_SENDER` | noreply@company.com | If email | From address |
| `NEXTCLOUD_URL` | - | If bot | Nextcloud instance URL |
| `NEXTCLOUD_USER` | - | If bot | Bot username |
| `NEXTCLOUD_PASS` | - | If bot | Bot password |
| `NC_BOT_CHANNEL_PRIVATE` | - | If bot | Private channel token |

---

For more information, see [ARCHITECTURE.md](./ARCHITECTURE.md) or [EXTENDING.md](./EXTENDING.md).
