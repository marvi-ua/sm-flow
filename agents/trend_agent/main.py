"""
AutoFlow Social — Trend Agent
Fetches trending signals from Google Trends, YouTube, and NewsAPI.
Scores them with Claude Haiku and returns top 5 topics.

TikTok Research API: stubbed — wire in when/if API access is approved.
Reddit API: stubbed — requires pre-approval as of Nov 2025.
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic

from sources import fetch_google_trends, fetch_youtube_trending, fetch_news_headlines

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trend_agent")

app = FastAPI(
    title="AutoFlow Trend Agent",
    description="Scores daily topics for the AutoFlow content pipeline.",
    version="0.2.0",
)

# ── Niche configuration ───────────────────────────────────────────────────────
# Change these keywords to shift the content niche without touching any logic.
NICHE_KEYWORDS = os.getenv("NICHE_KEYWORDS", "viral video,trending content,entertainment").split(",")
NICHE_CONTEXT = os.getenv("NICHE_CONTEXT", "short-form entertainment video content for TikTok and Instagram")

# ── Models ────────────────────────────────────────────────────────────────────

class Topic(BaseModel):
    title: str
    score: float          # 0.0 – 1.0 confidence
    source: str           # google_trends | youtube | newsapi | tiktok_stub | reddit_stub
    category: str         # claude-assigned category
    rationale: str        # claude's one-line reason for the score
    generated_at: datetime

class TopicsResponse(BaseModel):
    topics: list[Topic]
    run_id: str
    generated_at: datetime
    sources_used: list[str]

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime

# ── Claude scoring ────────────────────────────────────────────────────────────

async def score_topics_with_claude(raw_topics: list[dict]) -> list[Topic]:
    """
    Sends raw topic list to Claude Haiku for scoring.
    Returns top 5 topics with confidence scores and categories.
    """
    if not raw_topics:
        logger.warning("No raw topics to score")
        return []

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Deduplicate by title before sending to Claude
    seen = set()
    unique_topics = []
    for t in raw_topics:
        if t["title"] not in seen:
            seen.add(t["title"])
            unique_topics.append(t)

    topics_json = json.dumps(unique_topics, indent=2)
    now = datetime.now(timezone.utc).isoformat()

    prompt = f"""You are a trend analyst for an automated short-form video content pipeline.
The niche is: {NICHE_CONTEXT}
Today's date/time UTC: {now}

Below is a list of trending topics pulled from Google Trends, YouTube, and news headlines.
Your job is to score each topic for its potential as short-form video content.

Scoring criteria:
- Virality potential (0–40 pts): Is this topic spreading fast? Will people share a video about it?
- Audience fit (0–30 pts): Does it fit the niche and appeal to a broad entertainment audience?
- Content feasibility (0–30 pts): Can this be turned into a compelling 30–75 second video using only original graphics, data, and narration (no broadcast footage)?

Return ONLY a JSON array of the top 5 topics. No preamble, no markdown, no explanation outside the JSON.

Each object must have exactly these fields:
- "title": string — the topic title (can be reworded for clarity)
- "score": float between 0.0 and 1.0
- "source": string — copy from input
- "category": string — one of: facts, comparison, prediction, analysis, historical, news_reaction
- "rationale": string — one sentence explaining the score

Input topics:
{topics_json}"""

    logger.info(f"Sending {len(unique_topics)} topics to Claude Haiku for scoring")

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_response = message.content[0].text.strip()

    # Strip markdown fences if Claude wraps in ```json
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
        raw_response = raw_response.strip()

    scored = json.loads(raw_response)

    topics = []
    for item in scored[:5]:
        topics.append(Topic(
            title=item["title"],
            score=float(item["score"]),
            source=item["source"],
            category=item["category"],
            rationale=item["rationale"],
            generated_at=datetime.now(timezone.utc),
        ))

    # Sort descending by score
    topics.sort(key=lambda t: t.score, reverse=True)
    logger.info(f"Claude scored {len(topics)} topics. Top: {topics[0].title} ({topics[0].score})")
    return topics

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check():
    """Liveness probe for Docker and n8n."""
    return HealthResponse(
        status="ok",
        version=app.version,
        timestamp=datetime.now(timezone.utc),
    )

@app.post("/run", response_model=TopicsResponse, tags=["pipeline"])
async def run_trend_scan():
    """
    Triggers a full trend scan across all active sources.
    Called daily by n8n master workflow at 06:00 UTC.
    Returns top 5 Claude-scored topics.
    """
    run_id = str(uuid.uuid4())
    logger.info(f"Trend scan started. run_id={run_id}")

    # ── Fetch from all sources in parallel ───────────────────────────────────
    import asyncio
    google_topics, youtube_topics, news_topics = await asyncio.gather(
        fetch_google_trends(NICHE_KEYWORDS),
        fetch_youtube_trending(NICHE_KEYWORDS),
        fetch_news_headlines(NICHE_KEYWORDS),
    )

    # ── STUB SOURCES (wire in when API access granted) ────────────────────────
    tiktok_stub = []   # TODO: TikTok Research API — awaiting access approval
    reddit_stub = []   # TODO: Reddit API — awaiting access approval

    all_topics = google_topics + youtube_topics + news_topics + tiktok_stub + reddit_stub

    sources_used = []
    if google_topics:  sources_used.append("google_trends")
    if youtube_topics: sources_used.append("youtube")
    if news_topics:    sources_used.append("newsapi")

    if not all_topics:
        raise HTTPException(
            status_code=503,
            detail="All data sources returned empty. Check API keys and connectivity."
        )

    # ── Score with Claude ─────────────────────────────────────────────────────
    scored_topics = await score_topics_with_claude(all_topics)

    response = TopicsResponse(
        topics=scored_topics,
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        sources_used=sources_used,
    )
    logger.info(f"Trend scan complete. run_id={run_id}, sources={sources_used}")
    return response


@app.get("/topics/latest", response_model=TopicsResponse, tags=["pipeline"])
async def get_latest_topics():
    """
    Returns most recent topic set.
    Used by Script Agent to pick up the winning topic.
    Note: re-runs the scan until a database/cache layer is added in Block 11.
    """
    return await run_trend_scan()
