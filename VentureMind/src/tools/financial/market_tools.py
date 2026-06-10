import asyncio
import re
import urllib.parse
import httpx
from ..search.web_search import search_web, fetch_page_text, validate_url

async def get_industry_market_size(industry: str) -> dict:
    """Gather industry market size (TAM, SAM, SOM) data by scraping DuckDuckGo results."""
    # Using TAM SAM SOM (industry standard terms)
    query = f"{industry} market size TAM SAM SOM 2024 billion"
    default_result = {"tam_estimate": "Not found", "sources": [], "raw_snippets": []}

    try:
        search_results = await search_web(query, max_results=3)
        if not search_results:
            return default_result

        urls = [r["url"] for r in search_results]
        tasks = [fetch_page_text(url) for url in urls]
        pages_text = await asyncio.gather(*tasks)

        sources = []
        raw_snippets = []
        found_estimates = []
        
        # Pattern to capture currency values in millions/billions/trillions (e.g. $5.2 billion)
        estimate_pattern = r'(?i)\$[\d,.]+\s*(?:billion|million|trillion)'

        for url, text in zip(urls, pages_text):
            if text.startswith("Error fetching page content:"):
                continue
            
            matches = re.findall(estimate_pattern, text)
            if matches:
                found_estimates.extend(matches)
                sources.append(url)
                
                # Extract surrounding context for the first few matches
                for match in matches[:3]:
                    idx = text.find(match)
                    if idx != -1:
                        start = max(0, idx - 100)
                        end = min(len(text), idx + len(match) + 100)
                        raw_snippets.append(text[start:end].strip())

        tam_estimate = found_estimates[0] if found_estimates else "Not found"
        return {
            "tam_estimate": tam_estimate,
            "sources": sources,
            "raw_snippets": raw_snippets
        }
    except Exception:
        return default_result

async def get_market_growth_rate(industry: str) -> dict:
    """Retrieve market Compound Annual Growth Rate (CAGR) and forecast periods."""
    query = f"{industry} market CAGR growth rate forecast 2024 2025"
    default_result = {"cagr_estimate": "Not found", "forecast_period": "2024-2030 (Estimated)", "sources": []}

    try:
        search_results = await search_web(query, max_results=3)
        if not search_results:
            return default_result

        urls = [r["url"] for r in search_results]
        tasks = [fetch_page_text(url) for url in urls]
        pages_text = await asyncio.gather(*tasks)

        sources = []
        found_estimates = []
        cagr_pattern = r'[\d.]+\s*%'

        for url, text in zip(urls, pages_text):
            if text.startswith("Error fetching page content:"):
                continue
            
            matches = re.findall(cagr_pattern, text)
            if matches:
                found_estimates.extend(matches)
                sources.append(url)

        cagr_estimate = found_estimates[0] if found_estimates else "Not found"
        return {
            "cagr_estimate": cagr_estimate,
            "forecast_period": "2024-2030 (Estimated)",
            "sources": sources
        }
    except Exception:
        return default_result

async def get_market_trends(industry: str, max_trends: int = 5) -> list[str]:
    """Identify emerging industry trends and technological shifts from web search text."""
    query = f"{industry} market trends 2024 emerging technology"
    trends = []

    try:
        search_results = await search_web(query, max_results=3)
        if not search_results:
            return trends

        urls = [r["url"] for r in search_results]
        tasks = [fetch_page_text(url) for url in urls]
        pages_text = await asyncio.gather(*tasks)

        bullet_pattern = r'(?m)^\s*[-*•\d+\.]\s+(.+)$'
        for text in pages_text:
            if text.startswith("Error fetching page content:"):
                continue
            
            matches = re.findall(bullet_pattern, text)
            for m in matches:
                cleaned = m.strip()
                if 20 < len(cleaned) < 200 and cleaned not in trends:
                    trends.append(cleaned)
                    if len(trends) >= max_trends:
                        break
            if len(trends) >= max_trends:
                break

        # Fallback to extracting sentences containing keyword patterns if no list bullets found
        if not trends:
            all_text = " ".join([t for t in pages_text if not t.startswith("Error fetching")])
            sentences = re.split(r'(?<=[.!?])\s+', all_text)
            for sent in sentences:
                sent_clean = sent.strip()
                if any(keyword in sent_clean.lower() for keyword in ["trend", "emerging", "technology", "adoption"]):
                    if 30 < len(sent_clean) < 150 and sent_clean not in trends:
                        trends.append(sent_clean)
                        if len(trends) >= max_trends:
                            break

        return trends[:max_trends]
    except Exception:
        return []

async def get_wikipedia_industry_overview(industry: str) -> str:
    """Fetch summary extraction details of an industry via Wikipedia REST API."""
    try:
        formatted_industry = industry.strip().replace(" ", "_")
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(formatted_industry)}"
        validate_url(wiki_url)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(wiki_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("extract", "")
    except Exception:
        pass
    return ""
