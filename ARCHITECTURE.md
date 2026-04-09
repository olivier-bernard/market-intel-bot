# 🏛️ System Architecture

Technical deep-dive into the Market Intelligence RAG System design and components.

---

## High-Level Architecture

```
┌────────────────────────────┐
│   NEWS COLLECTION LAYER    │
│                            │
│ collect_news.py            │
│ - Polls 100+ RSS feeds     │
│ - Fetches arXiv papers     │
│ - Generates summaries      │
│ - Distributes via email    │
│ - Posts to Nextcloud       │
└──────────────┬─────────────┘
               │
               ├─ raw_data_*.txt (raw articles)
               ├─ past_summaries_*.txt (synthesized)
               └─ Email / Nextcloud posts
               
┌────────────────────────────┐
│  KNOWLEDGE ENGINEERING     │
│                            │
│ ingest.py                  │
│ - Chunks raw/summary text  │
│ - Generates embeddings     │
│ - Stores in Qdrant DB      │
└──────────────┬─────────────┘
               │
               └─▶ Qdrant Collections:
                   - news_iot_supply_chain
                   - news_medical_ccs
                   - news_heating_hvac
                   - news_sport_market
                   - news_global_startups_geo

┌────────────────────────────┐
│  INTELLIGENCE RETRIEVAL    │
│                            │
│ bot.py                     │
│ - Semantic search in       │
│   Qdrant                   │
│ - RAG context generation   │
│ - LLM inference            │
│ - Nextcloud responses      │
│                            │
│ (Alternative: OpenWebUI    │
│  for web interface)        │
└────────────────────────────┘
```

---

## Data Flow

### 1. Collection Phase

**Input:** RSS feeds, APIs, web scrapers
**Process:**
```python
for each topic:
  for each feed in topic.feeds:
    articles = fetch_feed(feed)
    raw_data += format_articles(articles)
  
  summary = generate_summary(
    raw_data,
    context=topic.background_context,
    prompt=topic.prompt,
    llm=claude_or_ollama
  )
  
  send_email(summary, to=topic.recipients)
  post_to_nextcloud(summary, channel=topic.channel)
  
  save_raw_data(articles) # append mode
  save_summary(summary)    # append mode
```

**Output:**
- `raw_data_<topic>.txt` — All articles (append-only)
- `past_summaries_<topic>.txt` — Daily summaries (append-only)
- Daily report file: `Final_Market_Screening_<timestamp>.txt`

**Preserves:**
- Historical data for RAG
- Raw articles for re-processing
- Summaries for trend analysis

---

### 2. Ingestion Phase

**Input:** `raw_data_*.txt` and `past_summaries_*.txt`
**Process:**
```python
for each topic:
  raw_chunks = parse_raw_articles(f"raw_data_{topic}.txt")
  summary_chunks = parse_summaries(f"past_summaries_{topic}.txt")
  
  all_chunks = raw_chunks + summary_chunks
  
  for chunk in all_chunks:
    embedding = embed(chunk.text, model="nomic-embed-text")
    chunk.embedding = embedding
  
  qdrant.upsert(
    collection=f"news_{topic}",
    points=[
      {
        "id": hash(chunk),
        "vector": chunk.embedding,
        "payload": chunk.metadata  # topic, date, section, etc
      }
    ]
  )
```

**Chunk Structure:**
```python
@dataclass
class Chunk:
    text: str                    # 50-8000 chars
    topic: str                   # e.g., "IoT_Supply_Chain"
    timestamp: str               # ISO format
    source_type: str             # "raw" or "summary"
    section: str                 # e.g., "Key Findings"
    source_title: str            # Article or section title
    embedding: List[float]       # 768-dim (nomic) or 1536-dim (OpenAI)
```

**Vectorization:**
- Model: `nomic-embed-text` (768 dimensions, MTL trained)
- Alternative: OpenAI `text-embedding-3-small` (1536-dim)
- Each chunk independently embedded
- Metadata preserved for attribution

**Qdrant Storage:**
- Collections: 1 per topic
- Distance metric: COSINE (symmetric, normalized)
- Payload indexing: automatic
- Update strategy: UPSERT (replace if ID exists)

---

### 3. Retrieval Phase (RAG)

**Input:** User question in Nextcloud
**Process:**
```python
def answer_question(question: str):
  # 1. Embed query
  query_embedding = embed(question)
  
  # 2. Search all relevant collections
  search_results = []
  for collection in COLLECTIONS:
    results = qdrant.search(
      collection,
      query_vector=query_embedding,
      limit=5,
      score_threshold=0.4
    )
    search_results.extend(results)
  
  # 3. Sort by relevance
  search_results.sort(key=lambda x: x.score, reverse=True)
  top_results = search_results[:5]
  
  # 4. Format context
  rag_context = format_results_for_llm(top_results)
  
  # 5. Generate answer
  answer = llm.generate(
    question=question,
    context=rag_context,
    system_prompt=SYSTEM_PROMPT
  )
  
  # 6. Post to Nextcloud
  nextcloud.post_message(answer)
```

**Similarity Scoring:**
- Cosine similarity: [-1, 1] range, threshold 0.4
- Scores filtered automatically
- Top 5 per query merged across topics

**Format for LLM:**
```
# Context:
1. [RAW] Section: "Supply Chain Volatility" (Score: 0.87)
   Hyundai is rerouting ships around Africa due to Strait of Hormuz...

2. [SUMMARY] Section: "Key Findings" (Score: 0.81)
   Global supply chains facing unprecedented disruption...

...

# Question:
What are current supply chain risks?

# Answer:
[LLM generates response informed by context]
```

---

## Component Details

### collect_news.py

**Workflow:**
1. **Load configuration** — Topics, feeds, prompts
2. **Fetch news** — Parallel feed polling
3. **Parse articles** — Extract text, clean HTML
4. **Generate summaries** — LLM synthesis
5. **Delta analysis** — Compare with previous summary
6. **Distribution** — Email (Brevo) + Nextcloud
7. **Archive** — Append raw/summary files

**Key Classes:**
- `NewsCollector` — Main orchestrator
- `FeedProcessor` — RSS parsing, article extraction
- `SummaryGenerator` — LLM interface (Claude/Ollama)
- `EmailSender` — Brevo integration
- `NextcloudClient` — Nextcloud Talk API

**Configuration:**
```python
segments = {
    "IoT_Supply_Chain": {
        "feeds": [...20 RSS URLs...],
        "context": "IoT company context...",
        "prompt": "Analyze supply chain trends...",
        "recipients": ["team@company.com"],
        "background_context": "You are analyzing IoT..."
    },
    ...
}
```

---

### ingest.py

**Workflow:**
1. **Load configuration** — LLM provider, Qdrant connection
2. **For each topic:**
   - Parse raw articles
   - Parse summaries
   - Combine chunks
3. **Generate embeddings** — Batch via Ollama/OpenAI
4. **Upsert to Qdrant** — Create/update collections
5. **Report statistics** — Points ingested, timing

**Key Classes:**
- `EmbeddingProvider` (abstract)
  - `OllamaEmbedder` — Local inference
  - `OpenAIEmbedder` — API calls
- `RawDataParser` — Article parsing
- `SummaryParser` — Section extraction
- `QdrantIngestor` — Collection management

**Performance:**
- 100 articles → ~2 minutes (Ollama)
- 100 articles → ~30 seconds (OpenAI)
- Batch size: adaptive based on model

---

### bot.py

**Workflow:**
1. **Connect** — Nextcloud, Qdrant, LLM clients
2. **Monitor channels** — Fetch recent messages
3. **For each question:**
   - Extract topic hint
   - Search Qdrant
   - Generate answer with RAG
   - Post response

**Key Classes:**
- `NextcloudAPI` — Talk API client
- `QdrantRAG` — Semantic search
- `LLMGenerator` — Claude/Ollama inference
- `Bot` — Main controller

**Polling Logic:**
```python
processed_ids = set()

while True:
  for channel in channels:
    messages = get_messages(channel)
    
    for msg in messages:
      if msg.id in processed_ids:
        continue
      if not is_question(msg.text):
        continue
      
      answer = answer_question(msg.text)
      post_message(channel, answer, parent=msg.id)
      processed_ids.add(msg.id)
  
  sleep(poll_interval)  # 30s default
```

---

## Data Models

### Message
```python
@dataclass
class Message:
    id: int
    user: str
    actor_id: str
    message: str
    timestamp: int
    parent_id: Optional[int]
```

### RAGContext
```python
@dataclass
class RAGContext:
    topic: str              # "IoT_Supply_Chain"
    text: str               # Chunk content
    source_type: str        # "raw" or "summary"
    section: str            # "Key Findings"
    timestamp: str          # ISO datetime
    score: float            # Cosine similarity [0, 1]
```

### Chunk (for ingestion)
```python
@dataclass
class Chunk:
    text: str               # Article or section text
    topic: str
    timestamp: str
    source_type: str        # "raw" article or "summary"
    section: str
    source_title: str
    embedding: List[float]
```

---

## API Integrations

### Nextcloud Talk
- **Endpoint:** `{NC_URL}/ocs/v2.php/apps/spreed/api/v4/chat/{token}`
- **Auth:** HTTP Basic (user + password)
- **Methods:** GET (messages), POST (replies)

**Example:**
```bash
curl -u user:pass https://sentinel.synio.dev/ocs/v2.php/apps/spreed/api/v4/chat/token123 \
  -H "OCS-APIRequest: true" \
  -d "message=Hello"
```

### Brevo (Email)
- **Endpoint:** `https://api.brevo.com/v3/smtp/email`
- **Auth:** API key in header
- **Method:** POST JSON

```json
{
  "sender": {"email": "noreply@company.com"},
  "to": [{"email": "team@company.com"}],
  "subject": "Market Intelligence: IoT Supply Chains",
  "htmlContent": "<html>...</html>"
}
```

### Qdrant Vector DB
- **Endpoint:** `http://localhost:6333`
- **Protocol:** HTTP REST (also gRPC available)
- **Operations:** search, upsert, delete, collection management

```json
POST /collections/news_iot_supply_chain/points/search
{
  "vector": [0.1, 0.2, ...],
  "limit": 5,
  "score_threshold": 0.4
}
```

### Claude API
- **Endpoint:** `https://api.anthropic.com/v1/messages`
- **Auth:** Bearer token
- **Model:** `claude-haiku-4-5` (fast, low-cost)

### Ollama API
- **Endpoint:** `http://localhost:11434`
- **Protocol:** HTTP REST
- **Operations:** generate, embed, pull, tags

---

## Deployment Patterns

### Single Machine (Dev)
```
Developer Machine:
- collect_news.py (cron daily)
- ingest.py (cron nightly)
- bot.py (long-running daemon)
- Ollama (local or docker)
- Qdrant (docker)
```

### Distributed (Production)
```
Collection Node:
- collect_news.py (cron)
- Shared volume: raw_data_*, past_summaries_*

Processing Node:
- ingest.py (cron nightly)
- Qdrant connection: alice:6333
- Ollama connection: alice:11434

Bot Node:
- bot.py daemon
- Nextcloud connection
- Qdrant read-only

GPU Node (alice):
- Ollama + models
- Qdrant + storage
- High RAM/VRAM
```

---

## Configuration Hierarchy

1. **System env:** Python, pip, Docker
2. **.env file:** API keys, hosts, ports
3. **Code defaults:** Fallbacks for optional settings
4. **collect_news.py/** `segments` dict:** Per-topic config
5. **Runtime flags:** --topics, --rebuild, --verbose

---

## Error Handling

### Graceful Degradation
- **Qdrant down?** Bot still generates answers (no context)
- **Ollama down?** Falls back to Claude (if available)
- **Email fails?** Still posts to Nextcloud
- **Nextcloud down?** Still saves reports to file

### Logging
- Console output (INFO level by default)
- File logs (if running via cron)
- Errors captured and reported

---

## Scalability Considerations

### Horizontal Scaling
- **Multiple bots:** Each connects independently to Qdrant
- **Load balancing:** Route Nextcloud messages round-robin
- **Stateless design:** bots don't store state

### Vertical Scaling
- **More topics:** Add to segments dict
- **More collections:** Qdrant handles 100s of collections
- **Larger context windows:** Claude supports up to 200K tokens

### Storage Scaling
- **Qdrant:** SSD recommended for <100GB vectors
- **Raw data:** Text files, can be archived to cold storage
- **Embeddings:** ~1 MB per 1000 chunks

---

## Security Considerations

### API Keys
- Store in `.env` (never commit)
- Rotate quarterly
- Use least-privilege tokens

### Nextcloud
- Bot account with minimal permissions
- Separate tokens for public/private channels
- HTTPS only

### Data Privacy
- Raw data stored locally (not in cloud)
- Qdrant on private network
- No data sent to Claude unless enabled

---

## Future Enhancements

### Planned
- [ ] Webhook notifications (instead of polling)
- [ ] Multi-turn conversations (maintain history)
- [ ] Custom RAG ranking (user feedback)
- [ ] Slack/Teams integration
- [ ] REST API for external consumers

### Possible
- [ ] Fine-tuned models per topic
- [ ] Hybrid search (semantic + keyword)
- [ ] Time-based filtering (only recent docs)
- [ ] Citation generation with source links
- [ ] Summarization of search results

---

## Performance Metrics

**Typical Performance (on 16GB RAM machine with GPU):**

| Operation | Time | Notes |
|-----------|------|-------|
| Collect 100 articles | 5-10 min | Depends on feed latency |
| Generate summary | 30-60 sec | Claude: faster; Ollama: depends on model |
| Ingest 100 articles | 2-5 min | Depends on embedding model |
| Query Qdrant | <100 ms | Cached, in-memory |
| Generate answer | 2-5 sec | Claude: 2s; Mistral: 5s |
| Post to Nextcloud | <500 ms | Network dependent |

---

## Monitoring & Observability

### Health Checks
```bash
# Qdrant
curl http://alice:6333/health

# Ollama
curl http://alice:11434/api/tags

# Nextcloud (requires auth)
curl -u user:pass https://sentinel.synio.dev/ocs/v2.php/apps/spreed/api/v1/chat/list
```

### Logs to Monitor
- `bot.log` — Questions, RAG results, errors
- `collect.log` — Feed status, articles, summaries
- `ingest.log` — Chunks embedded, collections updated

---

## References

- Qdrant Docs: https://qdrant.tech/documentation/
- Ollama: https://ollama.ai/
- Claude API: https://anthropic.com/docs/
- Nextcloud: https://nextcloud.com/

---

**Architecture Version:** 1.0 (April 2026)
