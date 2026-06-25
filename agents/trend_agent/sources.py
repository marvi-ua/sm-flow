"""
AutoFlow Social — Trend Agent: Data Sources
Fetches raw trending signals from Google Trends, YouTube, and NewsAPI.
Each function returns a list of raw topic strings for Claude to score.
"""

import os
import logging
import httpx
from pytrends.request import TrendReq

logger = logging.getLogger("trend_agent.sources")


async def fetch_google_trends(niche_keywords: list[str]) -> list[dict]:
    """
    Pulls trending search queries related to the niche keywords.
    Returns list of {"title": str, "source": "google_trends"}
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=0)
        results = []

        for keyword in niche_keywords[:3]:  # limit to 3 to avoid rate limiting
            pytrends.build_payload([keyword], timeframe="now 1-d", geo="")
            related = pytrends.related_queries()

            if keyword in related and related[keyword]["top"] is not None:
                top_df = related[keyword]["top"].head(5)
                for _, row in top_df.iterrows():
                    results.append({
                        "title": row["query"],
                        "source": "google_trends",
                    })

        logger.info(f"Google Trends: fetched {len(results)} topics")
        return results

    except Exception as e:
        logger.warning(f"Google Trends fetch failed: {e}")
        return []


async def fetch_youtube_trending(niche_keywords: list[str]) -> list[dict]:
    """
    Fetches trending YouTube videos matching niche keywords.
    Returns list of {"title": str, "source": "youtube"}
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("YOUTUBE_API_KEY not set — skipping YouTube source")
        return []

    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for keyword in niche_keywords[:3]:
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "q": keyword,
                        "type": "video",
                        "videoDuration": "short",  # short = under 4 min, relevant for our format
                        "order": "viewCount",
                        "publishedAfter": _yesterday_iso(),
                        "maxResults": 5,
                        "key": api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    title = item["snippet"]["title"]
                    results.append({
                        "title": title,
                        "source": "youtube",
                    })

        logger.info(f"YouTube: fetched {len(results)} topics")
        return results

    except Exception as e:
        logger.warning(f"YouTube fetch failed: {e}")
        return []


async def fetch_news_headlines(niche_keywords: list[str]) -> list[dict]:
    """
    Fetches top news headlines matching niche keywords via NewsAPI.
    Returns list of {"title": str, "source": "newsapi"}
    """
    api_key = os.getenv("NEWSAPI_API_KEY")
    if not api_key:
        logger.warning("NEWSAPI_API_KEY not set — skipping NewsAPI source")
        return []

    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for keyword in niche_keywords[:3]:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": keyword,
                        "sortBy": "publishedAt",
                        "pageSize": 5,
                        "language": "en",
                        "apiKey": api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for article in data.get("articles", []):
                    if article.get("title") and article["title"] != "[Removed]":
                        results.append({
                            "title": article["title"],
                            "source": "newsapi",
                        })

        logger.info(f"NewsAPI: fetched {len(results)} topics")
        return results

    except Exception as e:
        logger.warning(f"NewsAPI fetch failed: {e}")
        return []


def _yesterday_iso() -> str:
    """Returns yesterday's date in ISO 8601 format for YouTube API filter."""
    from datetime import datetime, timedelta, timezone
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")
