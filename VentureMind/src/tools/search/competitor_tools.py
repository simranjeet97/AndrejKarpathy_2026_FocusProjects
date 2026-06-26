import asyncio
import re
import urllib.parse
import logging
from urllib.parse import urlparse
import httpx
from .web_search import search_web, fetch_page_text, validate_url

logger = logging.getLogger("VentureMind.CompetitorTools")

# Share a single connection-pooled AsyncClient for competitor tools
_client = None

def get_competitor_client() -> httpx.AsyncClient:
    """Retrieve or initialize the shared pooled async HTTP client for competitor tools."""
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
        _client = httpx.AsyncClient(timeout=10.0, limits=limits)
    return _client

async def find_competitors(startup_name: str, industry: str) -> list[dict]:
    """Search for direct and indirect competitor alternatives in the industry and deduplicate them."""
    query1 = f"{startup_name} competitors alternatives {industry} 2024"
    query2 = f"top {industry} startups companies"
    
    try:
        r1, r2 = await asyncio.gather(
            search_web(query1, max_results=5),
            search_web(query2, max_results=5)
        )
    except Exception as e:
        logger.warning(f"Failed to find competitors for {startup_name}: {e}")
        return []

    all_results = r1 + r2
    deduped = []
    seen_domains = set()

    for item in all_results:
        url = item.get("url", "")
        if not url:
            continue
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        
        # Avoid listing the target startup itself as its own competitor
        if startup_name.lower() in domain or "duckduckgo" in domain or "wikipedia" in domain:
            continue
            
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            
            # Extract clean display name from search title
            title = item.get("title", "")
            name = title.split(" - ")[0].split(" | ")[0].split(":")[0].strip()
            # If name is generic, use domain without extension
            if len(name) > 30 or not name:
                name = domain.split(".")[0].capitalize()

            deduped.append({
                "name": name,
                "website": url,
                "snippet": item.get("snippet", "")
            })

    return deduped

async def get_company_info(company_name: str) -> dict:
    """Retrieve general corporate registration metadata from OpenCorporates and web search."""
    info = {
        "name": company_name,
        "website": "",
        "description": "",
        "founded_year": None,
        "jurisdiction": ""
    }

    # 1. Search DuckDuckGo for general company page
    try:
        search_results = await search_web(company_name, max_results=1)
        if search_results:
            info["website"] = search_results[0].get("url", "")
            info["description"] = search_results[0].get("snippet", "")
    except Exception as e:
        logger.warning(f"Failed to get web presence info for {company_name}: {e}")

    # 2. Try OpenCorporates API
    try:
        url = f"https://api.opencorporates.com/v0.4/companies/search?q={urllib.parse.quote(company_name)}"
        validate_url(url)
        client = get_competitor_client()
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            companies = data.get("results", {}).get("companies", [])
            if companies:
                best = companies[0].get("company", {})
                info["jurisdiction"] = best.get("jurisdiction_code", "")
                inc_date = best.get("incorporation_date", "")
                if inc_date and len(inc_date) >= 4:
                    try:
                        info["founded_year"] = int(inc_date[:4])
                    except ValueError:
                        pass
    except Exception as e:
        logger.warning(f"OpenCorporates API lookup failed for {company_name}: {e}")

    return info

async def get_funding_info(company_name: str) -> dict:
    """Extract estimate funding amount and latest funding round info by scraping web results."""
    default_res = {
        "company_name": company_name,
        "total_funding_estimate": "Not found",
        "last_round": "Not found",
        "sources": []
    }
    query = f"{company_name} funding raised series venture capital"

    try:
        search_results = await search_web(query, max_results=3)
        if not search_results:
            return default_res

        urls = [r["url"] for r in search_results]
        tasks = [fetch_page_text(url) for url in urls]
        pages_text = await asyncio.gather(*tasks)

        funding_pattern = r'(?i)\$[\d,.]+\s*(?:million|billion|M|B)\b'
        round_pattern = r'(?i)\b(?:Series\s+[A-F]|Seed\s+round|Pre-seed|Angel\s+round|venture\s+round|debt\s+financing)\b'
        
        found_funding = []
        found_rounds = []
        sources = []

        for url, text in zip(urls, pages_text):
            if text.startswith("Error fetching page content:"):
                continue
            
            matches_f = re.findall(funding_pattern, text)
            matches_r = re.findall(round_pattern, text)
            
            if matches_f:
                found_funding.extend(matches_f)
                sources.append(url)
            if matches_r:
                found_rounds.extend(matches_r)

        total_est = found_funding[0] if found_funding else "Not found"
        last_r = found_rounds[0] if found_rounds else "Not found"

        return {
            "company_name": company_name,
            "total_funding_estimate": total_est,
            "last_round": last_r,
            "sources": list(set(sources))
        }
    except Exception as e:
        logger.warning(f"Funding info search failed for {company_name}: {e}")
        return default_res

async def get_company_linkedin_signals(company_name: str) -> dict:
    """Fetch employee headcount estimate indications from LinkedIn search result descriptions."""
    default_res = {
        "company_name": company_name,
        "employee_estimate": "Not found",
        "source": ""
    }
    query = f"site:linkedin.com/company/ {company_name}"

    try:
        results = await search_web(query, max_results=3)
        employee_pattern = r'(?i)(\b[\d,+-]+\s+employees\b|\b[\d,+-]+\s+members\b)'
        
        for r in results:
            snippet = r.get("snippet", "")
            match = re.search(employee_pattern, snippet)
            if match:
                return {
                    "company_name": company_name,
                    "employee_estimate": match.group(1).strip(),
                    "source": r.get("url", "")
                }
    except Exception as e:
        logger.warning(f"LinkedIn signals fetch failed for {company_name}: {e}")

    return default_res
