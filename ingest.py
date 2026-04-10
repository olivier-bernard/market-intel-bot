#!/usr/bin/env python3
"""
RAG Ingest Pipeline: Chunk, embed, and ingest news data into Qdrant vector database.

This script:
1. Reads raw_data_*.txt and past_summaries_*.txt files
2. Intelligently chunks them with metadata (topic, date, sourceType, section)
3. Generates embeddings via Ollama or OpenAI
4. Stores in Qdrant with full-text search capability
5. Supports incremental updates and batch operations

Usage:
    python3 ingest.py [--rebuild] [--topics IoT_Supply_Chain,Heating_HVAC] [--verbose]
    python3 ingest.py --rebuild       # Full rebuild of all collections
    python3 ingest.py --topics Heating_HVAC  # Ingest only one topic
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import ollama

load_dotenv()

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "ollama").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://alice:11434")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Embedding dimensions based on model
EMBED_DIMS = {
    "nomic-embed-text": 768,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR

# Topics to track — derived from segments.json
def _load_topics(path: str = "segments.json") -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data["segments"].keys())
    except FileNotFoundError:
        logger.error("segments.json not found. Copy segments.json.example to segments.json and configure it.")
        sys.exit(1)

TOPICS = _load_topics()


@dataclass
class Chunk:
    """Represents a chunk of text with metadata."""
    text: str
    topic: str
    timestamp: str  # ISO format
    source_type: str  # "raw" or "summary"
    section: str  # For summaries: section name; for raw: "article"
    source_title: str  # For raw: article title; for summary: "Executive Summary" etc.
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dict for storage."""
        return {
            "text": self.text,
            "topic": self.topic,
            "timestamp": self.timestamp,
            "source_type": self.source_type,
            "section": self.section,
            "source_title": self.source_title,
        }


class EmbeddingProvider:
    """Abstract base for embedding providers."""
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class OllamaEmbedder(EmbeddingProvider):
    """Ollama embedding provider."""
    
    def __init__(self, model: str, host: str):
        self.model = model
        self.client = ollama.Client(host=host)
        logger.info(f"[Ollama] Initialized with model={model}, host={host}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts using Ollama."""
        embeddings = []
        for text in texts:
            try:
                response = self.client.embed(model=self.model, input=text)
                embeddings.append(response["embeddings"][0])
            except Exception as e:
                logger.error(f"[Ollama] Failed to embed text: {e}")
                # Return zero vector as fallback
                embeddings.append([0.0] * EMBED_DIMS.get(self.model, 768))
        return embeddings

    def unload(self):
        """Release the model from GPU memory immediately."""
        try:
            requests.post(
                f"{self.client._client.base_url}api/embed",
                json={"model": self.model, "input": "", "keep_alive": 0},
                timeout=10,
            )
            logger.info(f"[Ollama] Model '{self.model}' unloaded from GPU memory")
        except Exception as e:
            logger.warning(f"[Ollama] Could not unload model: {e}")


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI embedding provider."""
    
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        logger.info(f"[OpenAI] Initialized with model={model}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts using OpenAI API."""
        embeddings = []
        for text in texts:
            try:
                response = requests.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": text}
                )
                response.raise_for_status()
                embeddings.append(response.json()["data"][0]["embedding"])
            except Exception as e:
                logger.error(f"[OpenAI] Failed to embed text: {e}")
                embeddings.append([0.0] * EMBED_DIMS.get(self.model, 1536))
        return embeddings


class RawDataParser:
    """Parse raw_data_*.txt files."""
    
    @staticmethod
    def parse(filepath: Path, topic: str) -> List[Chunk]:
        """Parse raw data file into chunks."""
        chunks = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return chunks
        
        # Extract date from filename patterns or file content
        # Format: raw_data_<topic>.txt
        # We'll use file mtime as timestamp
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        timestamp = mtime.isoformat()
        
        # Split by "SOURCE:" headers
        articles = content.split("SOURCE:")
        
        for article in articles:
            article = article.strip()
            if not article:
                continue
            
            # Extract first line as title, rest as body
            lines = article.split("\n", 1)
            title = lines[0].strip()[:100]  # Limit title length
            body = lines[1].strip() if len(lines) > 1 else ""
            
            # Create chunk (limit text length to ~8000 chars for token efficiency)
            text = f"{title}\n\n{body}"[:8000]
            if len(text.strip()) < 100:
                continue
            
            chunk = Chunk(
                text=text,
                topic=topic,
                timestamp=timestamp,
                source_type="raw",
                section="article",
                source_title=title,
            )
            chunks.append(chunk)
        
        logger.info(f"Parsed {len(chunks)} raw articles from {filepath.name}")
        return chunks


class SummaryParser:
    """Parse past_summaries_*.txt files."""
    
    @staticmethod
    def parse(filepath: Path, topic: str) -> List[Chunk]:
        """Parse summary file into chunks by section."""
        chunks = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return chunks
        
        # Extract timestamp from header
        # Format: # Topic | DD Month YYYY (YYYY-MM-DD HH:MM)
        timestamp = datetime.now().isoformat()
        import re
        header_match = re.search(r'\((\d{4}-\d{2}-\d{2} \d{2}:\d{2})\)', content)
        if header_match:
            try:
                timestamp = datetime.strptime(header_match.group(1), "%Y-%m-%d %H:%M").isoformat()
            except:
                pass
        
        # Split by section headers (lines starting with digits and period)
        section_pattern = r'^(\d+)\.\s+([^\n]+)\n'
        sections = re.split(section_pattern, content)
        
        # Process sections: [text, num, title, text, num, title, ...]
        i = 0
        while i < len(sections):
            if i + 2 < len(sections):
                num = sections[i].strip()
                section_title = sections[i + 1].strip()
                section_body = sections[i + 2].strip()
                
                if section_title and section_body and len(section_body) > 50:
                    text = f"## {section_title}\n\n{section_body}"[:8000]
                    chunk = Chunk(
                        text=text,
                        topic=topic,
                        timestamp=timestamp,
                        source_type="summary",
                        section=section_title,
                        source_title=f"Section {num}: {section_title}",
                    )
                    chunks.append(chunk)
                i += 3
            else:
                break
        
        logger.info(f"Parsed {len(chunks)} summary sections from {filepath.name}")
        return chunks


class QdrantIngestor:
    """Handle Qdrant collection management and ingestion."""
    
    def __init__(self, host: str, port: int):
        self.client = QdrantClient(host=host, port=port)
        logger.info(f"[Qdrant] Connected to {host}:{port}")
    
    def ensure_collection(self, collection_name: str, vector_size: int):
        """Create collection if it doesn't exist."""
        try:
            self.client.get_collection(collection_name)
            logger.info(f"[Qdrant] Collection '{collection_name}' exists")
        except Exception:
            logger.info(f"[Qdrant] Creating collection '{collection_name}'...")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info(f"[Qdrant] Collection '{collection_name}' created")
    
    def ingest_chunks(self, collection_name: str, chunks: List[Chunk]):
        """Ingest chunks into Qdrant."""
        if not chunks:
            logger.warn(f"No chunks to ingest into '{collection_name}'")
            return
        
        # Prepare points for Qdrant
        points = []
        for i, chunk in enumerate(chunks):
            point_id = hash(f"{chunk.topic}_{chunk.timestamp}_{chunk.section}_{i}") % (2**31)
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=chunk.embedding,
                    payload=chunk.to_dict(),
                )
            )
        
        # Batch upsert (replace if exists)
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(f"[Qdrant] Ingested {len(points)} chunks into '{collection_name}'")
        except Exception as e:
            logger.error(f"[Qdrant] Failed to ingest chunks: {e}")
    
    def delete_collection(self, collection_name: str):
        """Delete a collection (for full rebuild)."""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"[Qdrant] Deleted collection '{collection_name}'")
        except Exception as e:
            logger.error(f"[Qdrant] Failed to delete collection: {e}")
    
    def get_collection_stats(self, collection_name: str) -> Dict:
        """Get collection statistics."""
        try:
            collection_info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "points_count": collection_info.points_count,
            }
        except Exception as e:
            logger.error(f"[Qdrant] Failed to get stats: {e}")
            return {}


def main():
    parser = argparse.ArgumentParser(description="Ingest news data into Qdrant vector database")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild all collections from scratch")
    parser.add_argument("--topics", type=str, default=None, help="Comma-separated topics to ingest (default: all)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine topics to ingest
    topics_to_ingest = TOPICS
    if args.topics:
        topics_to_ingest = [t.strip() for t in args.topics.split(",")]
    
    # Initialize embedding provider
    logger.info(f"Embedding provider: {EMBED_PROVIDER}")
    if EMBED_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not set in .env")
            sys.exit(1)
        embedder = OpenAIEmbedder(EMBED_MODEL, OPENAI_API_KEY)
    else:
        embedder = OllamaEmbedder(EMBED_MODEL, OLLAMA_HOST)
    
    vector_size = EMBED_DIMS.get(EMBED_MODEL, 768)
    
    # Initialize Qdrant
    qdrant = QdrantIngestor(QDRANT_HOST, QDRANT_PORT)
    
    # Process each topic
    for topic in topics_to_ingest:
        logger.info(f"\n=== Processing topic: {topic} ===")
        
        collection_name = f"news_{topic.lower()}"
        
        # Delete collection if rebuild requested
        if args.rebuild:
            qdrant.delete_collection(collection_name)
        
        # Ensure collection exists
        qdrant.ensure_collection(collection_name, vector_size)
        
        # Parse raw data
        raw_data_file = DATA_DIR / f"raw_data_{topic}.txt"
        raw_chunks = []
        if raw_data_file.exists():
            raw_chunks = RawDataParser.parse(raw_data_file, topic)
        else:
            logger.warn(f"Raw data file not found: {raw_data_file}")
        
        # Parse summary
        summary_file = DATA_DIR / f"past_summaries_{topic}.txt"
        summary_chunks = []
        if summary_file.exists():
            summary_chunks = SummaryParser.parse(summary_file, topic)
        else:
            logger.warn(f"Summary file not found: {summary_file}")
        
        # Combine chunks
        all_chunks = raw_chunks + summary_chunks
        if not all_chunks:
            logger.warn(f"No chunks found for topic {topic}")
            continue
        
        logger.info(f"Total chunks for {topic}: {len(all_chunks)} (raw={len(raw_chunks)}, summary={len(summary_chunks)})")
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
        texts = [chunk.text for chunk in all_chunks]
        embeddings = embedder.embed(texts)
        
        # Assign embeddings to chunks
        for chunk, embedding in zip(all_chunks, embeddings):
            chunk.embedding = embedding
        
        # Ingest into Qdrant
        qdrant.ingest_chunks(collection_name, all_chunks)
        
        # Print stats
        stats = qdrant.get_collection_stats(collection_name)
        if stats:
            logger.info(f"Collection stats: {stats}")
    
    # Unload embedding model from GPU so the LLM can load without contention
    if isinstance(embedder, OllamaEmbedder):
        embedder.unload()

    logger.info("\n✓ Ingestion complete!")


if __name__ == "__main__":
    main()
