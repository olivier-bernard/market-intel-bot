import feedparser
import arxiv
import ollama
import smtplib

from email.message import EmailMessage
from newspaper import Article

import requests



# OLLAMA_MODEL = 'qwen35-35b-iq3s'
OLLAMA_MODEL = 'gemma3:12b'
OLLAMA_HOST = 'http://ollamaserver:11434'

ollama_client = ollama.Client(host=OLLAMA_HOST)


# --- 1. SEGMENTED CONFIGURATION ---
# We define each newsletter topic with its specific sources and AI "focus"
SEGMENTS = {
    "IoT_Supply_Chain": {
        "feeds": [
            "https://www.iotworldtoday.com/feed/", 
            "https://www.supplychainbrain.com/rss/articles"
        ],
        "arxiv_query": "iot supply chain sensor temperature humidity",
        "prompt": "Focus on IoT sensors (temp/hydrometry/GPS) and platforms for transportation and warehouse. Analyze the evolution of usage and platform integration ideas.",
        "recipient": "iot-team@yourcompany.com"
    },
    "Medical_CCS": {
        "feeds": ["https://www.cleanroomtechnology.com/rss/"],
        "arxiv_query": "contamination control strategy annex 1 pharmaceutical",
        "prompt": "Analyze CCS (Contamination Control Strategy), Annex 1 regulation updates, and competitors providing medical/sterile services.",
        "recipient": "medical-dept@yourcompany.com"
    },
    "Sport_Market": {
        "feeds": ["https://www.sporttechie.com/feed/"],
        "arxiv_query": "sports management app motivation engagement",
        "prompt": "Analyze advances in sports apps for event/club management and digital techniques for user motivation.",
        "recipient": "sport-app-dev@yourcompany.com"
    },
    "Heating_HVAC": {
        "feeds": ["https://achrnews.com/rss/articles"],
        "arxiv_query": "residential heating design software heat pump calculation",
        "prompt": "Focus on 'l'installation de chauffage' for residential/SMBs. Identify apps helping installers calculate/engineer systems vs. customers needing solutions.",
        "recipient": "hvac-sales@yourcompany.com"
    },
    "Global_Startups_Geo": {
        "feeds": [
            "https://techcrunch.com/startups/feed/", # US
            "https://sifted.eu/feed/",              # EMEA
            "https://www.reutersagency.com/feed/"   # Geopolitics
        ],
        "arxiv_query": None,
        "prompt": "Summarize US/EMEA startup trends and geopolitical events affecting business evolution.",
        "recipient": "strategy@yourcompany.com"
    }
}

# --- 2. CORE FUNCTIONS ---

def fetch_content(config):
    """Gathers data from RSS and ArXiv for a specific segment."""
    segment_text = ""
    
    # Fetch RSS News
    for url in config["feeds"]:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # Limit to top 3 for speed/token limits
            try:
                article = Article(entry.link)
                article.download()
                article.parse()
                segment_text += f"SOURCE: {entry.title}\n{article.text[:1500]}\n\n"
            except: continue

    # Fetch ArXiv Papers (if query exists)
    if config.get("arxiv_query"):
        client = arxiv.Client()
        search = arxiv.Search(query=config["arxiv_query"], max_results=2)
        for result in client.results(search):
            segment_text += f"PAPER: {result.title}\nABSTRACT: {result.summary}\n\n"
            
    return segment_text

def generate_newsletter(segment_name, content, prompt):
    """Uses Ollama to create the formal summary."""
    system_msg = (
        "You are a Senior Market Intelligence Agent. Summarize the provided news and papers. "
        f"{prompt} "
        "Structure the output with the following numbered sections using a formal, professional tone:\n"
        "1. Executive Summary\n"
        "2. Key Updates\n"
        "3. Key Technical Trends\n"
        "4. Competitor Watch\n"
        "5. Actionable Insights\n"
        "6. Market Risks / Opportunities"
    )
    
    response = ollama_client.chat(model=OLLAMA_MODEL, messages=[
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': f"Analyze this data for the {segment_name} segment:\n\n{content}"}
    ])
    return response['message']['content']

# --- 3. EXECUTION ---

def run_agent():
    consolidated_report = ""

    for name, config in SEGMENTS.items():
        print(f"--- Processing {name} ---")
        raw_data = fetch_content(config)
        
        if raw_data:
            summary = generate_newsletter(name, raw_data, config["prompt"])
            section_header = f"\n{'='*30}\nSEGMENT: {name.replace('_', ' ')}\n{'='*30}\n"
            consolidated_report += section_header + summary
            
            # Save raw data for auditing (as requested in point 3 of your goal)
            with open(f"raw_data_{name}.txt", "w", encoding="utf-8") as f:
                f.write(raw_data)

    # Final Save
    with open("Final_Market_Screening.txt", "w", encoding="utf-8") as f:
        f.write(consolidated_report)
    
    print("\nProcess Complete. File 'Final_Market_Screening.txt' is ready.")

if __name__ == "__main__":
    run_agent()
