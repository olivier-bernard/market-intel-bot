# 🔧 Troubleshooting Guide

Common issues and solutions.

---

## Connection Issues

### Qdrant Connection Refused

**Error:**
```
[ERROR] [Qdrant] Connection failed: Connection refused
```

**Causes & Solutions:**

1. **Qdrant not running**
```bash
# Check if running
curl http://localhost:6333/health

# Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# Or restart
docker restart qdrant
```

2. **Wrong host/port**
```bash
# Verify in .env
grep QDRANT_HOST .env
grep QDRANT_PORT .env

# Should be (examples):
# QDRANT_HOST=alice
# QDRANT_PORT=6333
```

3. **Network connectivity**
```bash
# Test from your machine
ping alice
telnet alice 6333
nc -zv alice 6333  # netcat
```

---

### Ollama Connection Refused

**Error:**
```
[ERROR] Failed to connect to Ollama at http://alice:11434
```

**Solutions:**

1. **Ollama not running**
```bash
# On alice machine
ps aux | grep ollama

# Start it
ollama serve

# Or with Docker
docker run -d --name ollama -p 11434:11434 ollama/ollama
```

2. **Wrong host**
```bash
# Verify in .env
grep OLLAMA_HOST .env

# Test connection
curl http://alice:11434/api/tags
```

3. **Models not pulled**
```bash
# On alice, pull models
ollama pull nomic-embed-text
ollama pull mistral

# Verify
ollama list
```

---

### Claude API Failed

**Error:**
```
anthropic.NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-...'}}
```

**Solutions:**

1. **Invalid model name**
```bash
# Check available models
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $CLAUDE_API_KEY"

# Update in .env
CLAUDE_MODEL=claude-haiku-4-5  # Use valid model
```

2. **API key invalid**
```bash
# Verify format
echo $CLAUDE_API_KEY | head -c 20
# Should start with: sk-ant-api03-

# Test
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $CLAUDE_API_KEY"
```

3. **API quota exceeded**
```bash
# Check usage at console.anthropic.com
# Refund or add payment method
```

---

## Model Issues

### Model Not Found

**Error (Ollama):**
```
model "mistral" not found, try pulling it first
```

**Solution:**
```bash
# Pull the model
ollama pull mistral

# Or use a different model
export OLLAMA_MODEL=neural-chat:7b

# List available
ollama list
```

### Model Too Large for Memory

**Error:**
```
[MEMORY] Model requires 16GB but only 8GB available
```

**Solutions:**

1. **Use smaller model**
```bash
# Instead of mixtral (45GB), use:
ollama pull mistral         # 4GB
ollama pull neural-chat:7b  # 4GB
```

2. **Use API service (Claude)**
```bash
export LLM_PROVIDER=claude
export CLAUDE_API_KEY=sk-...
```

3. **Add swap (temporary)**
```bash
# Add 8GB swap (Linux)
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Data & Ingestion Issues

### No News Articles Collected

**Error:**
```
[INFO] Collected 0 articles
```

**Causes:**

1. **Feed URLs are broken**
```bash
# Test each feed manually
curl "https://feed-url 2>&1 | head
# Should return XML

# Check in code
grep "feeds" collect_news.py
```

2. **Feeds are empty**
```bash
# Some feeds may not update daily
# Add more feeds per topic
# Or make some feeds optional (try-catch)
```

3. **Parsing error**
```bash
# Enable verbose logging
python3 collect_news.py 2>&1 | grep -i error
```

**Solutions:**

```python
# In collect_news.py, add error handling
def fetch_feed(url):
    try:
        return feedparser.parse(url)
    except Exception as e:
        logger.warn(f"Feed failed: {url}: {e}")
        return None
```

---

### Chunks Not Embedding

**Error:**
```
[ERROR] [RAG] Failed to embed query: model "nomic-embed-text" not found
```

**Solution:**
```bash
# Pull embedding model
ollama pull nomic-embed-text

# Or use OpenAI
export EMBED_PROVIDER=openai
export EMBED_MODEL=text-embedding-3-small
export OPENAI_API_KEY=sk-...
```

---

### Qdrant Collection Not Created

**Error:**
```
[ERROR] [Qdrant] Creating collection 'news_iot_supply_chain'...
[ERROR] Failed to create collection
```

**Solutions:**

1. **Qdrant not running**
```bash
curl http://alice:6333/health
# If fails, restart Qdrant
```

2. **Permission denied**
```bash
# Check Qdrant logs
docker logs qdrant | tail -20
```

3. **Full disk**
```bash
# Check space
df -h
du -sh /qdrant_storage

# Clean up old collections
# Or expand disk
```

---

## Bot Issues

### Bot Not Receiving Messages

**Error:**
```
[INFO] Processing topic: IoT_Supply_Chain
[INFO] No messages to process
```

**Causes:**

1. **Channel token incorrect**
```bash
# Verify token in .env
grep NC_BOT_CHANNEL_PRIVATE .env

# Get correct token from Nextcloud:
# Click channel → Copy invite link → extract {TOKEN}
```

2. **Bot account permission issues**
```bash
# Verify bot can access channel
# In Nextcloud: Add marketbot to channel as member
```

3. **Nextcloud authentication failed**
```bash
# Test credentials
curl -u marketbot:password https://sentinel.synio.dev/ocs/v2.php/apps/spreed/api/v1/avatar/marketbot \
  -H "OCS-APIRequest: true"

# Should return 200, not 401
```

---

### Bot Not Posting Responses

**Error (Silent - no error, but no message appears):**

**Debug:**
```bash
# Check logs
tail -50 bot.log | grep -i "post\|nextcloud\|error"

# Test manually
python3 -c "
from bot import NextcloudAPI
nc = NextcloudAPI('https://sentinel.synio.dev', 'marketbot', 'password')
nc.post_message('token123', 'Test message')
"
```

**Common causes:**

1. **Channel is read-only**
```bash
# In Nextcloud: Edit channel permissions
```

2. **Rate limiting**
```bash
# Increase poll interval
python3 bot.py --poll-interval 60

# Or add delay between posts
import time; time.sleep(2)
```

3. **HTML formatting issues**
```bash
# Test with plain text first
message = "Test message"  # No markdown, no HTML
```

---

## Email Issues

### Emails Not Sending

**Error:**
```
[ERROR] [Email] Failed to send email: Auth failed
```

**Solutions:**

1. **Brevo API key invalid**
```bash
# Verify in .env
grep BREVO_API_KEY .env

# Test with curl
curl -X GET https://api.brevo.com/v3/account \
  -H "api-key: $BREVO_API_KEY"

# Should return 200 with account info
```

2. **Email address rejected**
```bash
# Verify sender
grep EMAIL_SENDER .env

# Make sure it's a valid email address
# Email_Sender=noreply@company.com  # ✓ Valid
# EMAIL_SENDER=no-reply  # ✗ Invalid
```

3. **Recipient list empty**
```bash
# Check configuration
grep recipients collect_news.py

# Add test recipient
segments["IoT_Supply_Chain"]["recipients"] = ["test@gmail.com"]
```

**Debug:**
```python
# In collect_news.py, add logging
import smtplib
smtplib.debuglevel = 1  # Enable SMTP debug
```

---

## Performance Issues

### Slow Response Times

**Symptoms:**
```
Question asked → 30+ seconds before response
```

**Causes:**

1. **Slow model**
```bash
# Current: mixtral (15s) or neural-chat:7b (7s)
# Use faster: mistral (5s) or Claude (2s)

export OLLAMA_MODEL=mistral
# OR
export LLM_PROVIDER=claude
```

2. **Slow embedding**
```bash
# Use faster embedding
export EMBED_MODEL=all-minilm  # 384-dim, very fast

# Or use OpenAI (parallel)
export EMBED_PROVIDER=openai
export EMBED_MODEL=text-embedding-3-small
```

3. **Network latency**
```bash
# Test latency to alice
ping alice
# Should be <10ms

# If >100ms, consider local Qdrant
```

4. **Qdrant search slow**
```bash
# Reduce search limit
RAG_SEARCH_LIMIT = 3  # instead of 5

# Or increase similarity threshold
RAG_SIMILARITY_THRESHOLD = 0.6  # fewer results, faster
```

---

### High Memory Usage

**Symptoms:**
```
Bot process using 8GB+ RAM
```

**Solutions:**

1. **Reduce model**
```bash
export OLLAMA_MODEL=mistral  # 4GB vs 13GB
```

2. **Limit context window**
```python
OLLAMA_OPTIONS = {
    "num_ctx": 4096,  # instead of 16384
}
```

3. **Batch ingestion**
```bash
# Ingest in batches instead of all at once
python3 ingest.py --topics IoT_Supply_Chain
python3 ingest.py --topics Medical_CCS
# (separate batches)
```

---

## Logging & Debugging

### Enable Debug Logging

```bash
# In terminal
python3 bot.py --verbose

# Or in code
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### View Logs

```bash
# Real-time
tail -f bot.log

# Search for errors
grep ERROR bot.log

# Last 100 lines
tail -100 bot.log

# Specific time
grep "2026-04-09 14:5" bot.log
```

### Create Detailed Debug Output

```python
# Add to your scripts
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
```

---

## Environment & Dependency Issues

### Requirements Not Installed

**Error:**
```
ModuleNotFoundError: No module named 'qdrant_client'
```

**Solution:**
```bash
# Activate venv
source .venv/bin/activate

# Install missing package
pip install qdrant-client

# Or reinstall all
pip install -r requirements.txt
```

### Python Version Too Old

**Error:**
```
SyntaxError: invalid syntax (dataclass, type hints require 3.7+)
```

**Solution:**
```bash
# Check version
python3 --version
# Should be 3.9+

# Install newer Python
python3.11 -m venv .venv
source .venv/bin/activate
```

### Virtual Environment Broken

**Solution:**
```bash
# Remove and recreate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## File & Path Issues

### File Not Found

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'raw_data_IoT_Supply_Chain.txt'
```

**Solution:**
```bash
# Check current directory
pwd

# Should be /home/olivier/scripts/news/
cd /home/olivier/scripts/news

# Check files exist
ls -la raw_data_*.txt

# If missing, collect first
python3 collect_news.py
```

### Permission Denied

**Error:**
```
PermissionError: [Errno 13] Permission denied: '.env'
```

**Solution:**
```bash
# Fix permissions
chmod 644 .env
chmod 755 .

# Or run as correct user
# Avoid running as root
```

---

## Getting Help

### Check Logs First
```bash
tail -100 bot.log | tail -ERROR
# or
grep -i "error\|traceback" *.log
```

### Minimal Reproduction

```bash
# Test components independently
python3 bot.py --test-query "test question"
python3 collect_news.py
python3 ingest.py --verbose
```

### Verify Configuration

```bash
# Check all env variables
printenv | grep -E "QDRANT|OLLAMA|CLAUDE|BREVO|NEXTCLOUD"
```

### Contact Support

If issue persists:
1. Save logs to file
2. Collect configuration (without secrets)
3. Describe steps to reproduce
4. Contact implementation team

---

## Quick Reference: Common Commands

```bash
# Start bot
python3 bot.py --channel both

# Test bot
python3 bot.py --test-query "..."

# Collect news
python3 collect_news.py

# Ingest (all topics)
python3 ingest.py

# Ingest (specific topic)
python3 ingest.py --topics IoT_Supply_Chain

# Verbose logging
python3 ingest.py --verbose

# Rebuild collections
python3 ingest.py --rebuild

# Check syntax
python3 -m py_compile bot.py

# View logs
tail -f bot.log

# Monitor Qdrant
curl http://alice:6333/health

# Monitor Ollama
curl http://alice:11434/api/tags
```

---

For more help, see [CONFIG_GUIDE.md](./CONFIG_GUIDE.md) or [ARCHITECTURE.md](./ARCHITECTURE.md).
