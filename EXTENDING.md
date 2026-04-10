# Extending the Market Intelligence System

Adapt and customize the RAG system to your domain or infrastructure.

---

## Add a New Topic

### 1. Update `collect_news.py`

In the `segments` dictionary, add:

```python
"MyNewTopic": {
    "feeds": [
        "https://example.com/rss",
        "https://another-feed.com/feed.xml",
    ],
    "prompt": (
        "Analyze these articles for emerging opportunities in [YOUR_DOMAIN]. "
        "Focus on: [KEY_METRICS]. Flag regulatory changes, competitive moves, "
        "and technology shifts."
    ),
    "recipients": ["person@company.com"],
    "nextcloud_token": "your_channel_token",  # Get from Nextcloud URL
},
```

### 2. Add Raw Data & Summary Files

```bash
touch raw_data_MyNewTopic.txt
touch past_summaries_MyNewTopic.txt
```

### 3. Update `ingest.py` TOPICS list

```python
TOPICS = [
    "IoT_Supply_Chain",
    ...
    "MyNewTopic",  # Add here
]
```

### 4. Restart collection

```bash
python3 collect_news.py
python3 ingest.py --topics MyNewTopic
```

---

## Customize LLM Prompts

Edit the `prompt` in each topic segment.  Make it specific to your use case:

**For competitive intelligence:**
```python
"prompt": (
    "Extract key competitive moves, product launches, and market shifts. "
    "Compare to our capabilities. List 3-5 actionable insights. "
    "Highlight threats and opportunities."
)
```

**For regulatory monitoring:**
```python
"prompt": (
    "Identify regulatory changes, policy shifts, and compliance deadlines. "
    "Assess impact on operations. Recommend actions. "
    "Group by jurisdiction and severity."
)
```

**For financial analysis:**
```python
"prompt": (
    "Track earnings, guidance changes, analyst downgrades/upgrades. "
    "Flag M&A activity and major funding rounds. "
    "Calculate market impact scores."
)
```

---

## Change Embedding Model

### Use OpenAI (Higher Quality)

Edit `.env`:
```bash
EMBED_PROVIDER=openai
EMBED_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-...
```

Then rebuild:
```bash
python3 ingest.py --rebuild
```

**Pros:** Better semantic understanding, supports 1536-dim vectors  
**Cons:** API costs (~$0.02 per 1M tokens)

### Use Different Ollama Model

Edit `.env`:
```bash
EMBED_MODEL=all-minilm
```

Pull the model on `alice`:
```bash
ollama pull all-minilm
```

Rebuild:
```bash
python3 ingest.py --rebuild
```

---

## Integrate with Slack/Teams Instead of Nextcloud

Replace the Nextcloud chat posting with your platform.

### Example: Slack Integration

1. Create a Slack bot and get a **webhook URL**

2. Modify `collect_news.py`, replace `send_to_nextcloud()` with:

```python
def send_to_slack(summary, webhook_url):
    payload = {
        "text": summary,
        "username": "Market Intelligence Bot",
    }
    requests.post(webhook_url, json=payload)
```

3. For bot.py, replace Nextcloud polling with Slack event listener:

```python
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient

slack_client = WebClient(token=SLACK_BOT_TOKEN)
socket_client = SocketModeClient(slack_client, SLACK_APP_TOKEN)

@socket_client.socket_mode_request_listeners("app_mention")
def handle_mentions(ack, body):
    ack()
    text = body["event"]["text"]
    # Query RAG, generate answer, post to Slack channel
```

---

## Build a Web Dashboard

Query Qdrant directly to build custom dashboards.

### Example: Python Flask Dashboard

```python
from flask import Flask, render_template
from qdrant_client import QdrantClient

app = Flask(__name__)
qdrant = QdrantClient("alice", 6333)

@app.route("/search")
def search():
    query = request.args.get("q")
    embedding = embed_query(query)  # Use same embedding model as ingest.py
    
    results = []
    for topic in TOPICS:
        hits = qdrant.search(
            collection_name=f"news_{topic.lower()}",
            query_vector=embedding,
            limit=5,
        )
        for hit in hits:
            results.append({
                "topic": topic,
                "text": hit.payload["text"],
                "score": hit.score,
            })
    
    return render_template("results.html", results=results)
```

---

## Multi-Language Support

Use multilingual embedding models that support your languages.

### Option 1: Ollama Multilingual

```bash
ollama pull multilingual-e5  # Supports 100+ languages
```

Edit `.env`:
```bash
EMBED_MODEL=multilingual-e5
```

### Option 2: OpenAI (Supports 100+ Languages)

```bash
EMBED_MODEL=text-embedding-3-small  # Already multilingual
```

---

## Advanced RAG Patterns

### Hybrid Search (Keyword + Semantic)

Combine BM25 keyword search with semantic search for better recall.

### Query Expansion

Generate related queries to improve retrieval coverage.

### Reranking

Use cross-encoders to improve result ranking after initial retrieval.

### Metadata Filtering

Filter search results by date, geography, severity, or custom fields during ingestion.

---

## Monitoring & Observability

### Log RAG Queries and Responses

```python
import logging
logging.basicConfig(filename="rag.log", level=logging.INFO)
logger = logging.getLogger("RAG")

def log_query(query, topic, results, answer):
    logger.info(f"QUERY: {query} | TOPIC: {topic} | RESULTS: {len(results)}")
```

### Track Metrics

Use Prometheus to monitor query latency, result quality, and coverage.

---

## Docker Deployment

Package the system for easy deployment:

```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "bot.py"]
```

---

## See Also

- [README.md](./README.md) — Quick start & overview
- `.context/` folder — Template files for common patterns
