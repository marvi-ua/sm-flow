"""
AutoFlow Social — Trend Agent
Scores daily topics by virality + recency + audience fit.
Output: Top 5 topics with confidence scores.
Stub implementation — real API calls added in Block 5.
"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trend_agent")

app = FastAPI(
    title="AutoFlow Trend Agent",
    description="Scores daily topics for the AutoFlow content pipeline.",
    version="0.1.0",
)

# ── Models ────────────────────────────────────────────────────────────────────

class Topic(BaseModel):
    title: str
    score: float          # 0.0 – 1.0 confidence
    source: str           # google_trends | reddit | tiktok
    category: str         # player_stats | match_prediction | facts | tactical_analysis | historical_milestones
    generated_at: datetime

class TopicsResponse(BaseModel):
    topics: list[Topic]
    run_id: str
    generated_at: datetime

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime

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
    Trigger a full trend scan.
    Called daily by n8n master workflow at 06:00 UTC.
    Returns top 5 scored topics.
    STUB: returns mock data until Block 5.
    """
    logger.info("Trend scan triggered")

    stub_topics = [
        Topic(
            title="Mbappe vs Ronaldo at age 25 — who had the better stats?",
            score=0.94,
            source="google_trends",
            category="player_stats",
            generated_at=datetime.now(timezone.utc),
        ),
        Topic(
            title="Why Argentina is the favourite for the 2026 World Cup",
            score=0.87,
            source="reddit",
            category="match_prediction",
            generated_at=datetime.now(timezone.utc),
        ),
        Topic(
            title="The fastest red card in World Cup history",
            score=0.81,
            source="tiktok",
            category="facts",
            generated_at=datetime.now(timezone.utc),
        ),
        Topic(
            title="How Morocco stopped Spain's press — tactical breakdown",
            score=0.76,
            source="reddit",
            category="tactical_analysis",
            generated_at=datetime.now(timezone.utc),
        ),
        Topic(
            title="Most goals in a single World Cup — records that still stand",
            score=0.71,
            source="google_trends",
            category="historical_milestones",
            generated_at=datetime.now(timezone.utc),
        ),
    ]

    response = TopicsResponse(
        topics=stub_topics,
        run_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc),
    )
    logger.info(f"Run complete. run_id={response.run_id}, topics={len(stub_topics)}")
    return response

@app.get("/topics/latest", response_model=TopicsResponse, tags=["pipeline"])
async def get_latest_topics():
    """
    Returns most recent topic set without triggering a new scan.
    Used by Script Agent to pick up the winning topic.
    STUB: reads from DB/R2 cache in Block 5.
    """
    return await run_trend_scan()
