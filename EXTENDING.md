# 🎨 Extending & Customizing the RAG System

Guide for adapting the system to new domains, topics, and use cases.

---

## Adding a New Topic

### Step 1: Define the Topic

Decide:
- **Name:** e.g., `Financial_Markets`, `Legal_Compliance`
- **Focus area:** What news/research to monitor
- **Target audience:** Who needs this intelligence
- **Update frequency:** Daily, weekly, or hourly

### Step 2: Curate News Sources

Create a list of RSS feeds, APIs, or websites:

```python
# Example: Legal Compliance topic
"Legal_Compliance": {
    "feeds": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.reuters.com/finance.rss",
        "https://www.sec.gov/feeds/news.xml",
        "https://feeds.ft.com/home/page/uk",
        # Add 10-15 more relevant feeds
    ]
}
```

**Finding feeds:**
- Look for `/feeds` or `/rss` endpoints
- Use feed discovery tools: Feedly, Inoreader
- Check GitHub repos for curated feed lists
- Industry news aggregators often have feed APIs

### Step 3: Write Topic-Specific Prompts

Edit `collect_news.py`:

```python
segments = {
    "Legal_Compliance": {
        "feeds": [...],
        
        # Background context for this topic
        "context": (
            "You are a Senior Legal Compliance Analyst. "
            "Monitor regulatory changes, court rulings, enforcement actions, "
            "and compliance recommendations across financial services, "
            "healthcare, and technology sectors."
        ),
        
        # Custom prompt for summary generation
        "prompt": (
            "Synthesize today's legal and compliance news into an executive brief. "
            "Focus on: (1) New regulations or rulings, (2) Enforcement actions, "
            "(3) Compliance risks for financial institutions, (4) Industry-specific "
            "guidance. Be specific and cite sources. Flag high-priority legal changes."
        ),
        
        # Recipients for email
        "recipients": ["legal@company.com", "compliance@company.com"],
        
        # Nextcloud channel for posting
        "nextcloud_token": "legal-channel-token",
    }
}
```

### Step 4: Add to Code

1. **Update TOPICS list in `bot.py`:**
```python
TOPICS = [
    "IoT_Supply_Chain",
    "Medical_CCS",
    "Heating_HVAC",
    "Sport_Market",
    "Global_Startups_Geo",
    "Legal_Compliance",  # NEW
]
```

2. **Run collection:**
```bash
python3 collect_news.py
# Creates: raw_data_Legal_Compliance.txt, past_summaries_Legal_Compliance.txt
```

3. **Ingest:**
```bash
python3 ingest.py --topics Legal_Compliance
# Creates: news_legal_compliance collection in Qdrant
```

4. **Test:**
```bash
python3 bot.py --test-query "What are recent compliance changes affecting banking?"
```

---

## Customizing LLM Behavior

### Per-Topic Background Context

Make summaries domain-specific:

```python
"Heating_HVAC": {
    "context": (
        "You are an expert in heating, ventilation, and air conditioning systems "
        "for residential and SMB markets. Focus on: installation best practices, "
        "energy efficiency standards, regulatory changes (EU Energy Efficiency "
        "Directive), market consolidation, and emerging heat pump technologies."
    ),
}
```

### Adjusting Temperature & Quality

In `collect_news.py`, modify OLLAMA_OPTIONS:

```python
OLLAMA_OPTIONS = {
    "num_ctx": 16384,      # Context window
    "temperature": 0.4,    # Lower = more factual, 0.7 = more creative
    "top_p": 0.9,         # Nucleus sampling (0.9 = default)
}
```

Or for Claude:

```python
CLAUDE_OPTIONS = {
    "max_tokens": 2048,
    "temperature": 0.3,   # Lower = more focused
}
```

### Multi-Language Support

```python
# In collect_news.py, for a French topic:
"Markets_France": {
    "context": "...",
    "prompt": "Synthétiser les actualités du marché français...",
    "recipients": ["team@fr.company.com"],
    # Articles will be in French, summaries in French
}
```

---

## Switching LLM Providers

### Configure in .env

```bash
# Use Claude (high quality, costs ~$0.03/briefing)
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-...

# OR use Ollama (free, local, needs GPU)
LLM_PROVIDER=ollama
OLLAMA_HOST=http://alice:11434
OLLAMA_MODEL=mistral  # Fast, 7B
# OR
OLLAMA_MODEL=neural-chat:7b  # Better quality
```

### Quality vs Cost Comparison

| Model | Speed | Quality | Cost | Best For |
|-------|-------|---------|------|----------|
| Claude Haiku | 2s | Excellent | $0.03/briefing | Default choice |
| **mistral:7b** (Ollama) | 5s | Good | Free | Cost-sensitive, local |
| neural-chat:7b | 7s | Very Good | Free | Quality-focused, local |
| mixtral:8x7b | 15s | Excellent | Free | Best quality, needs GPU |
| Claude Sonnet | 3s | Excellent | $0.10/briefing | Premium use cases |

---

## Advanced: Custom Chunking Strategy

### For Different Content Types

Edit `ingest.py` to handle specialized sources:

```python
class SpecializedParser(RawDataParser):
    """Custom parser for scientific papers."""
    
    @staticmethod
    def parse(filepath: Path, topic: str) -> List[Chunk]:
        chunks = []
        
        with open(filepath, "r") as f:
            papers = parse_arxiv_json(f.read())  # Custom format
        
        for paper in papers:
            # Abstract as chunk
            chunk_abs = Chunk(
                text=f"# {paper.title}\n\nAbstract: {paper.abstract}",
                topic=topic,
                timestamp=paper.published_date,
                source_type="research_abstract",
                section="Abstract",
                source_title=paper.title,
            )
            chunks.append(chunk_abs)
            
            # Conclusions as chunk
            if paper.conclusion:
                chunk_con = Chunk(
                    text=f"# {paper.title}\n\nConclusion: {paper.conclusion}",
                    topic=topic,
                    timestamp=paper.published_date,
                    source_type="research_conclusion",
                    section="Conclusion",
                    source_title=paper.title,
                )
                chunks.append(chunk_con)
        
        return chunks
```

### Hierarchical Chunking

```python
class HierarchicalChunker:
    """Create chunks at multiple levels of granularity."""
    
    @staticmethod
    def chunk_with_hierarchy(text: str, max_chunk=8000):
        """
        Create overlapping chunks at different levels:
        - Section level (whole sections)
        - Paragraph level (detailed)
        - Sentence level (keyword search)
        """
        sections = text.split("\n##")
        chunks = []
        
        for section in sections:
            # Section-level chunk
            chunks.append(section[:max_chunk])
            
            # Paragraph-level chunks
            paragraphs = section.split("\n\n")
            for para in paragraphs:
                if len(para) > 100:
                    chunks.append(para[:max_chunk])
        
        return chunks
```

---

## Integration: Replace Nextcloud with Slack

### Step 1: Install Slack SDK

```bash
pip install slack-sdk
```

### Step 2: Create `slack_integration.py`

```python
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackBot:
    def __init__(self, token: str):
        self.client = WebClient(token=token)
    
    def get_messages(self, channel: str, limit: int = 50):
        """Fetch recent messages from channel."""
        try:
            result = self.client.conversations_history(
                channel=channel,
                limit=limit
            )
            return result['messages']
        except SlackApiError as e:
            print(f"Error: {e}")
            return []
    
    def post_message(self, channel: str, text: str, thread_ts: str = None):
        """Post message to channel or thread."""
        try:
            self.client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts
            )
            return True
        except SlackApiError as e:
            print(f"Error: {e}")
            return False
```

### Step 3: Adapt `bot.py` to use SlackBot

```python
from slack_integration import SlackBot

slack_bot = SlackBot(os.getenv("SLACK_TOKEN"))

def process_channel(channel_id):
    messages = slack_bot.get_messages(channel_id)
    for msg in messages:
        if is_question(msg['text']):
            answer = generate_answer(msg['text'])
            slack_bot.post_message(channel_id, answer, thread_ts=msg['ts'])
```

---

## Integration: Custom Web Dashboard

### Simple Flask Dashboard

```python
# dashboard.py
from flask import Flask, request, jsonify
from typing import List
import json

app = Flask(__name__)

@app.route('/api/search', methods=['POST'])
def search_api():
    """Search knowledge base."""
    data = request.json
    query = data.get('query')
    topic = data.get('topic')
    
    rag = QdrantRAG(qdrant_client)
    results = rag.search(query, topic=topic, limit=10)
    
    return jsonify({
        'query': query,
        'results': [
            {
                'text': r.text[:200],
                'topic': r.topic,
                'score': r.score,
                'source': r.section
            }
            for r in results
        ]
    })

@app.route('/api/ask', methods=['POST'])
def ask_api():
    """Ask a question with RAG."""
    data = request.json
    question = data.get('question')
    
    rag = QdrantRAG(qdrant_client)
    results = rag.search(question)
    
    llm = LLMGenerator(LLM_PROVIDER)
    answer = llm.generate(question, results)
    
    return jsonify({
        'question': question,
        'answer': answer,
        'sources': len(results)
    })

@app.route('/api/topics', methods=['GET'])
def list_topics():
    """List available topics."""
    return jsonify({'topics': TOPICS})

if __name__ == '__main__':
    app.run(debug=False, port=5000)
```

**Usage:**
```bash
python3 dashboard.py
curl http://localhost:5000/api/ask -X POST -d '{"question": "..."}' -H "Content-Type: application/json"
```

---

## Advanced: Hybrid Search (Semantic + Keyword)

### BM25 + Vector Similarity

```python
class HybridSearch:
    """Combine keyword (BM25) and semantic (vector) search."""
    
    def __init__(self, qdrant_client, bm25_index=None):
        self.qdrant = qdrant_client
        self.bm25 = bm25_index  # Initialize separately
    
    def search(self, query: str, weights=(0.5, 0.5)):
        """
        Returns: Hybrid score = 0.5*vector_score + 0.5*bm25_score
        """
        # Vector search
        embedding = embed(query)
        vector_results = self.qdrant.search(query_vector=embedding, limit=20)
        
        # BM25 search (keyword)
        bm25_results = self.bm25.search(query, limit=20)
        
        # Combine and normalize scores
        combined = {}
        for r in vector_results:
            combined[r.id] = {'vector_score': r.score}
        
        for r in bm25_results:
            if r.id in combined:
                combined[r.id]['bm25_score'] = r.score
            else:
                combined[r.id] = {'bm25_score': r.score}
        
        # Calculate hybrid score
        results = []
        for id, scores in combined.items():
            hybrid = (
                weights[0] * scores.get('vector_score', 0) +
                weights[1] * scores.get('bm25_score', 0)
            )
            results.append({'id': id, 'score': hybrid})
        
        return sorted(results, key=lambda x: x['score'], reverse=True)[:5]
```

---

## Performance Optimization

### Caching Frequent Queries

```python
from functools import lru_cache
import hashlib

class CachedRAG(QdrantRAG):
    def __init__(self, client, cache_ttl=3600):
        super().__init__(client)
        self.cache_ttl = cache_ttl
        self.cache = {}
    
    def search(self, query: str, topic: Optional[str] = None):
        """Cached search."""
        cache_key = hashlib.md5(f"{query}:{topic}".encode()).hexdigest()
        
        if cache_key in self.cache:
            cached_time, results = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return results
        
        # Fetch fresh results
        results = super().search(query, topic)
        self.cache[cache_key] = (time.time(), results)
        return results
```

### Batch Processing for Large Imports

```python
def ingest_large_batch(chunks: List[Chunk], batch_size=1000):
    """Process chunks in batches to avoid memory issues."""
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        
        # Embed batch
        texts = [c.text for c in batch]
        embeddings = embedder.embed(texts)
        
        # Store batch
        qdrant.ingest_chunks(collection_name, batch)
        print(f"Ingested {i+len(batch)}/{len(chunks)}")
```

---

## Adding Metadata Filters

### Time-Based Filtering

```python
from datetime import datetime, timedelta

def search_recent(query: str, days: int = 30):
    """Search only in recent documents."""
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    results = qdrant.search(
        query_vector=embed(query),
        query_filter={
            "timestamp": {"range": {"gte": cutoff_date}}
        }
    )
    return results
```

### Topic-Specific Filtering

```python
def search_by_topic(query: str, topics: List[str]):
    """Search specific topics only."""
    results = qdrant.search(
        query_vector=embed(query),
        query_filter={
            "topic": {"in": topics}
        }
    )
    return results
```

---

## Testing & Validation

### Unit Tests for Custom Components

```python
import unittest

class TestCustomChunker(unittest.TestCase):
    def test_chunk_size(self):
        chunker = SpecializedParser()
        chunks = chunker.parse("test_file.txt", "TestTopic")
        
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), 8000)
            self.assertGreater(len(chunk.text), 50)
    
    def test_metadata_preservation(self):
        chunks = chunker.parse("test_file.txt", "TestTopic")
        
        for chunk in chunks:
            self.assertEqual(chunk.topic, "TestTopic")
            self.assertIsNotNone(chunk.timestamp)
```

---

## Publishing & Sharing

### Package for Distribution

```bash
# Create setup.py
pip install setuptools wheel
python3 setup.py sdist bdist_wheel

# Share on PyPI or internal package registry
twine upload dist/*
```

### Docker Image for Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python3", "bot.py", "--channel", "both"]
```

Build & push:
```bash
docker build -t market-intelligence-rag:latest .
docker push registry.company.com/market-intelligence-rag:latest
```

---

## Questions?

See [ARCHITECTURE.md](./ARCHITECTURE.md) for technical details or [SETUP_GUIDE.md](./SETUP_GUIDE.md) for deployment instructions.
