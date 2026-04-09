#!/usr/bin/env python3
"""
RAG-Powered Nextcloud Q&A Bot

This bot:
1. Monitors Nextcloud Talk channels for questions
2. Retrieves relevant context from Qdrant vector database
3. Generates answers using Claude/Ollama with RAG
4. Posts responses back to Nextcloud channels

Usage:
    python3 bot.py [--channel private|public|both] [--poll-interval 30] [--verbose]
    python3 bot.py                    # Monitor all channels, poll every 30s
    python3 bot.py --channel private  # Monitor only private channel
    python3 bot.py --verbose          # Enable debug logging
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import ollama
from anthropic import Anthropic

load_dotenv()

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# --- NEXTCLOUD CONFIG ---
NC_URL = os.getenv("NEXTCLOUD_URL", "https://sentinel.synio.dev")
NC_USER = os.getenv("NEXTCLOUD_USER", "marketbot")
NC_PASS = os.getenv("NEXTCLOUD_PASS", "DZ393-BJPtZ-nPg3q-5oFfN-B7GbL")
NC_CHANNEL_PRIVATE = os.getenv("NC_BOT_CHANNEL_PRIVATE", "4spz2ath")  # Private channel token
NC_CHANNEL_PUBLIC = os.getenv("NC_BOT_CHANNEL_PUBLIC", "public-token")  # Public channel token

# --- QDRANT CONFIG ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "alice")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

# --- LLM CONFIG ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = "claude-haiku-4-5"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://alice:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "VladimirGav/gemma4-26b-16GB-VRAM")

# --- BOT CONFIG ---
BOT_NAME = "Market Intelligence Bot"
BOT_CONTEXT_WINDOW = 4  # Number of previous messages to include in context
RAG_SEARCH_LIMIT = 5    # Number of Qdrant results to use as context
RAG_SIMILARITY_THRESHOLD = 0.4  # Minimum similarity score for relevance

# Topics available for Q&A
TOPICS = [
    "IoT_Supply_Chain",
    "Medical_CCS",
    "Heating_HVAC",
    "Sport_Market",
    "Global_Startups_Geo",
]

# Initialize clients
if LLM_PROVIDER == "claude":
    if not CLAUDE_API_KEY:
        logger.error("CLAUDE_API_KEY not set in .env")
        sys.exit(1)
    llm_client = Anthropic(api_key=CLAUDE_API_KEY)
    logger.info(f"[LLM] Using Claude ({CLAUDE_MODEL})")
else:
    llm_client = ollama.Client(host=OLLAMA_HOST)
    logger.info(f"[LLM] Using Ollama ({OLLAMA_MODEL})")

try:
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    logger.info(f"[Qdrant] Connected to {QDRANT_HOST}:{QDRANT_PORT}")
except Exception as e:
    logger.error(f"[Qdrant] Connection failed: {e}")
    sys.exit(1)


@dataclass
class Message:
    """Represents a Nextcloud message."""
    id: int
    user: str
    actor_id: str
    message: str
    timestamp: int
    parent_id: Optional[int] = None


@dataclass
class RAGContext:
    """Represents retrieved RAG context."""
    topic: str
    text: str
    source_type: str  # "raw" or "summary"
    section: str
    timestamp: str
    score: float


class NextcloudAPI:
    """Nextcloud Talk API client."""
    
    def __init__(self, url: str, user: str, password: str):
        self.url = url
        self.user = user
        self.password = password
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({"OCS-APIRequest": "true"})
        logger.info(f"[Nextcloud] Initialized for {url}")
    
    def get_messages(self, token: str, limit: int = 50) -> List[Message]:
        """Fetch messages from a channel."""
        endpoint = f"{self.url}/ocs/v2.php/apps/spreed/api/v4/chat/{token}"
        
        try:
            response = self.session.get(endpoint, params={"limit": limit})
            response.raise_for_status()
            data = response.json()
            
            messages = []
            if "ocs" in data and "data" in data["ocs"]:
                for msg_data in data["ocs"]["data"]:
                    # Skip system messages and bot's own messages
                    if msg_data.get("systemMessage"):
                        continue
                    if msg_data.get("actorDisplayName") == BOT_NAME:
                        continue
                    
                    msg = Message(
                        id=msg_data["id"],
                        user=msg_data.get("actorDisplayName", "Unknown"),
                        actor_id=msg_data.get("actorId", ""),
                        message=msg_data.get("message", ""),
                        timestamp=msg_data.get("timestamp", 0),
                        parent_id=msg_data.get("parentId"),
                    )
                    messages.append(msg)
            
            return messages
        except Exception as e:
            logger.error(f"[Nextcloud] Failed to fetch messages: {e}")
            return []
    
    def post_message(self, token: str, message: str, parent_id: Optional[int] = None) -> bool:
        """Post a message to a channel."""
        endpoint = f"{self.url}/ocs/v2.php/apps/spreed/api/v4/chat/{token}"
        
        payload = {
            "message": message,
            "actorDisplayName": BOT_NAME,
        }
        
        if parent_id:
            payload["parentId"] = parent_id
        
        try:
            response = self.session.post(endpoint, data=payload)
            response.raise_for_status()
            logger.info(f"[Nextcloud] Posted message to {token}")
            return True
        except Exception as e:
            logger.error(f"[Nextcloud] Failed to post message: {e}")
            return False


class QdrantRAG:
    """Qdrant-based RAG retriever."""
    
    def __init__(self, client: QdrantClient):
        self.client = client
    
    def search(self, query: str, topic: Optional[str] = None, limit: int = RAG_SEARCH_LIMIT) -> List[RAGContext]:
        """
        Search Qdrant for relevant context.
        
        Args:
            query: User question or search text
            topic: Specific topic to search (or None for all)
            limit: Number of results
        
        Returns:
            List of RAGContext objects
        """
        results = []
        
        # Determine which collections to search
        if topic and topic in TOPICS:
            collections = [f"news_{topic.lower()}"]
        else:
            collections = [f"news_{t.lower()}" for t in TOPICS]
        
        # Embed the query using Ollama (consistent with ingest)
        try:
            embed_response = ollama.Client(host=OLLAMA_HOST).embed(
                model="nomic-embed-text",
                input=query
            )
            query_embedding = embed_response["embeddings"][0]
        except Exception as e:
            logger.error(f"[RAG] Failed to embed query: {e}")
            return results
        
        # Search each collection
        for collection in collections:
            try:
                search_results = self.client.search(
                    collection_name=collection,
                    query_vector=query_embedding,
                    limit=limit,
                    score_threshold=RAG_SIMILARITY_THRESHOLD,
                )
                
                for scored_point in search_results:
                    payload = scored_point.payload
                    context = RAGContext(
                        topic=payload.get("topic", ""),
                        text=payload.get("text", ""),
                        source_type=payload.get("source_type", ""),
                        section=payload.get("section", ""),
                        timestamp=payload.get("timestamp", ""),
                        score=scored_point.score,
                    )
                    results.append(context)
            except Exception as e:
                logger.warn(f"[RAG] Search failed for {collection}: {e}")
        
        # Sort by score and limit total results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class LLMGenerator:
    """Generate answers using Claude or Ollama with RAG context."""
    
    def __init__(self, provider: str):
        self.provider = provider
    
    def generate(self, question: str, rag_context: List[RAGContext], conversation_history: List[Dict] = None) -> str:
        """
        Generate an answer using RAG context.
        
        Args:
            question: User's question
            rag_context: Retrieved context from Qdrant
            conversation_history: Previous messages for context
        
        Returns:
            Generated answer
        """
        # Build RAG context string
        context_str = self._format_rag_context(rag_context)
        
        # Build system message
        system_msg = (
            f"You are the {BOT_NAME}, an expert market intelligence analyst. "
            "You help answer questions about IoT supply chains, pharmaceutical quality control, "
            "heating systems, sports events, and global startup activity. "
            "Use the provided context to answer accurately and cite sources when relevant. "
            "Be concise, factual, and actionable."
        )
        
        if context_str:
            system_msg += f"\n\nRELEVANT CONTEXT:\n{context_str}"
        else:
            system_msg += "\n\nNote: No relevant context found in knowledge base. Answer from general knowledge."
        
        # Build conversation history if provided
        messages = conversation_history or []
        messages.append({"role": "user", "content": question})
        
        try:
            if self.provider == "claude":
                response = llm_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=1024,
                    system=system_msg,
                    messages=messages,
                )
                return response.content[0].text
            else:  # Ollama
                # Format for Ollama (no system role support in some versions)
                full_prompt = f"{system_msg}\n\nUser: {question}"
                response = llm_client.generate(
                    model=OLLAMA_MODEL,
                    prompt=full_prompt,
                    stream=False,
                )
                return response["response"]
        except Exception as e:
            logger.error(f"[LLM] Generation failed: {e}")
            return "I encountered an error processing your question. Please try again."
    
    @staticmethod
    def _format_rag_context(contexts: List[RAGContext]) -> str:
        """Format RAG contexts for inclusion in prompt."""
        if not contexts:
            return ""
        
        formatted = []
        for i, ctx in enumerate(contexts, 1):
            source_label = f"[{ctx.source_type.upper()}]" if ctx.source_type else ""
            snippet = ctx.text[:500] + "..." if len(ctx.text) > 500 else ctx.text
            formatted.append(
                f"{i}. {source_label} ({ctx.topic} / {ctx.section})\n"
                f"   Score: {ctx.score:.2f}\n"
                f"   {snippet}\n"
            )
        
        return "\n".join(formatted)


class Bot:
    """Main bot coordinator."""
    
    def __init__(self):
        self.nc = NextcloudAPI(NC_URL, NC_USER, NC_PASS)
        self.rag = QdrantRAG(qdrant_client)
        self.llm = LLMGenerator(LLM_PROVIDER)
        self.processed_message_ids = set()
    
    def is_question(self, text: str) -> bool:
        """Determine if a message is a question."""
        text = text.strip().lower()
        question_indicators = ['?', 'what ', 'how ', 'why ', 'when ', 'where ', 'who ', 
                              'which ', 'can you', 'could you', 'would you', 'should',
                              'is there', 'are there', 'do you', 'does', 'tell me']
        return any(text.endswith('?') or text.startswith(ind) for ind in question_indicators)
    
    def extract_topic(self, question: str) -> Optional[str]:
        """Try to detect topic from question."""
        question_lower = question.lower()
        for topic in TOPICS:
            topic_lower = topic.lower()
            if topic_lower.replace('_', ' ') in question_lower:
                return topic
        return None
    
    def process_channel(self, token: str, channel_name: str):
        """Monitor and respond to messages in a channel."""
        messages = self.nc.get_messages(token)
        
        for msg in messages:
            # Skip already processed messages
            if msg.id in self.processed_message_ids:
                continue
            
            # Skip own messages
            if msg.actor_id == NC_USER:
                continue
            
            # Check if it's a question
            if not self.is_question(msg.message):
                logger.debug(f"[{channel_name}] Skipping non-question: {msg.message[:50]}")
                continue
            
            logger.info(f"[{channel_name}] Processing question from {msg.user}: {msg.message[:80]}")
            
            # Extract topic hint
            topic = self.extract_topic(msg.message)
            
            # Retrieve RAG context
            rag_results = self.rag.search(msg.message, topic=topic)
            logger.info(f"[RAG] Retrieved {len(rag_results)} context chunks (score threshold: {RAG_SIMILARITY_THRESHOLD})")
            
            # Generate answer
            answer = self.llm.generate(msg.message, rag_results)
            
            # Format answer with context attribution
            if rag_results:
                answer += "\n\n**Knowledge Base Sources:**"
                for i, ctx in enumerate(rag_results[:3], 1):  # Show top 3
                    answer += f"\n{i}. {ctx.section} ({ctx.topic}) - Score: {ctx.score:.2f}"
            
            # Post response (as reply if supported)
            self.nc.post_message(token, answer, parent_id=msg.id)
            
            # Mark as processed
            self.processed_message_ids.add(msg.id)
    
    def run(self, channels: str = "both", poll_interval: int = 30):
        """
        Main bot loop.
        
        Args:
            channels: "private", "public", or "both"
            poll_interval: Seconds between polls
        """
        logger.info(f"Starting bot (polling every {poll_interval}s, channels: {channels})")
        
        channels_to_monitor = []
        if channels in ("private", "both"):
            channels_to_monitor.append(("private", NC_CHANNEL_PRIVATE))
        if channels in ("public", "both"):
            channels_to_monitor.append(("public", NC_CHANNEL_PUBLIC))
        
        if not channels_to_monitor:
            logger.error("No channels to monitor")
            return
        
        try:
            while True:
                for channel_name, token in channels_to_monitor:
                    self.process_channel(token, channel_name)
                
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")


def main():
    parser = argparse.ArgumentParser(description="RAG-powered Nextcloud Q&A bot")
    parser.add_argument("--channel", choices=["private", "public", "both"], default="both",
                       help="Which Nextcloud channel(s) to monitor")
    parser.add_argument("--poll-interval", type=int, default=30,
                       help="Seconds between polls (default: 30)")
    parser.add_argument("--test-query", type=str, help="Test with a single query (no polling)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Test mode
    if args.test_query:
        logger.info(f"Test mode: {args.test_query}")
        bot = Bot()
        rag_results = bot.rag.search(args.test_query)
        logger.info(f"RAG results: {len(rag_results)}")
        answer = bot.llm.generate(args.test_query, rag_results)
        print(f"\n{'='*80}")
        print(f"QUESTION: {args.test_query}")
        print(f"{'='*80}")
        print(f"ANSWER:\n{answer}")
        print(f"{'='*80}")
        return
    
    # Normal polling mode
    bot = Bot()
    bot.run(channels=args.channel, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
