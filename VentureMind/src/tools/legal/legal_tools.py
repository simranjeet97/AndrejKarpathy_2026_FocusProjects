import asyncio
import re
import urllib.parse
import logging
import httpx
from ..search.web_search import search_web, fetch_page_text, validate_url

logger = logging.getLogger("VentureMind.LegalTools")

# Share a single connection-pooled AsyncClient for OpenCorporates and legal APIs
_client = None

def get_legal_client() -> httpx.AsyncClient:
    """Retrieve or initialize the shared pooled async HTTP client for legal tools."""
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
        _client = httpx.AsyncClient(timeout=10.0, limits=limits)
    return _client

async def search_litigation(company_name: str) -> list[dict]:
    """Search for public court filings, SEC investigations, or other regulatory actions filed against the company."""
    results = []
    q1 = f'"{company_name}" lawsuit filed court 2020 2021 2022 2023 2024'
    q2 = f'"{company_name}" SEC investigation regulatory action'

    try:
        r1, r2 = await asyncio.gather(
            search_web(q1, max_results=3),
            search_web(q2, max_results=3)
        )
        all_res = r1 + r2

        litigation_keywords = ["sued", "lawsuit", "complaint", "litigation", "investigation", "court", "settlement", "fine", "penalty"]

        for item in all_res:
            snippet = item.get("snippet", "")
            if any(kw in snippet.lower() for kw in litigation_keywords):
                # Classify severity hint
                severity = "low"
                if any(kw in snippet.lower() for kw in ["fraud", "sec", "criminal", "investigation", "million", "billion", "severe"]):
                    severity = "high"
                elif any(kw in snippet.lower() for kw in ["class action", "breach", "patent infringement"]):
                    severity = "medium"

                date_match = re.search(r'\b(20\d{2})\b', snippet)
                date_str = date_match.group(1) if date_match else "unknown"

                results.append({
                    "description": snippet,
                    "source_url": item.get("url", ""),
                    "date_str": date_str,
                    "severity_hint": severity
                })
    except Exception as e:
        logger.warning(f"Litigation search failed for {company_name}: {e}")

    return results

async def check_patent_activity(company_name: str) -> dict:
    """Scrape patent ownership indications from Google Patents and DuckDuckGo searches."""
    default_res = {
        "patent_count_estimate": 0,
        "recent_patents": [],
        "source": "Google Patents Search"
    }

    try:
        # Search site:patents.google.com
        results = await search_web(f"site:patents.google.com {company_name}", max_results=5)
        patents = []
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            cleaned_title = title.split(" - ")[0].strip()
            if cleaned_title and cleaned_title not in patents:
                patents.append(f"{cleaned_title}: {url}")

        default_res["patent_count_estimate"] = len(patents)
        default_res["recent_patents"] = patents
        default_res["source"] = "DuckDuckGo Patents Search"
    except Exception as e:
        logger.warning(f"Patent activity check failed for {company_name}: {e}")

    return default_res

async def check_trademark_status(company_name: str) -> dict:
    """Identify registered trademarks from USPTO online database search signals."""
    default_res = {
        "trademark_count_estimate": 0,
        "status": "unknown",
        "source": "USPTO"
    }

    try:
        # Avoid tsdr.uspto.gov site: search which is not supported well; use general uspto.gov
        results = await search_web(f"site:uspto.gov {company_name}", max_results=3)
        if not results:
            results = await search_web(f'"{company_name}" trademark registered USPTO', max_results=3)

        count = len(results)
        status = "active" if count > 0 else "unknown"
        
        return {
            "trademark_count_estimate": count,
            "status": status,
            "source": results[0].get("url", "USPTO Fallback") if results else "USPTO"
        }
    except Exception as e:
        logger.warning(f"Trademark check failed for {company_name}: {e}")

    return default_res

async def check_incorporation_status(company_name: str) -> dict:
    """Query state registries using OpenCorporates to check incorporation legality and status."""
    default_res = {
        "incorporated": False,
        "jurisdiction": "unknown",
        "incorporation_date": "unknown",
        "company_number": "unknown"
    }

    try:
        url = f"https://api.opencorporates.com/v0.4/companies/search?q={urllib.parse.quote(company_name)}"
        validate_url(url)
        client = get_legal_client()
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            companies = data.get("results", {}).get("companies", [])
            
            # Check for first US jurisdiction company first
            target_company = None
            for c in companies:
                comp = c.get("company", {})
                j_code = comp.get("jurisdiction_code", "")
                if j_code.startswith("us"):
                    target_company = comp
                    break
            if not target_company and companies:
                target_company = companies[0].get("company", {})

            if target_company:
                return {
                    "incorporated": not target_company.get("inactive", False),
                    "jurisdiction": target_company.get("jurisdiction_code", "unknown"),
                    "incorporation_date": target_company.get("incorporation_date", "unknown"),
                    "company_number": target_company.get("company_number", "unknown")
                }
    except Exception as e:
        logger.warning(f"OpenCorporates incorporation lookup failed for {company_name}: {e}")

    return default_res

async def search_regulatory_issues(company_name: str, industry: str) -> list[dict]:
    """Retrieve news and articles detailing FTC, GDPR, or CCPA compliance violations in the sector."""
    results = []
    query = f'"{company_name}" {industry} FTC GDPR CCPA compliance violation 2023 2024'

    try:
        search_res = await search_web(query, max_results=3)
        compliance_keywords = ["fine", "violation", "breach", "penalty", "ftc", "gdpr", "ccpa", "settlement", "compliant", "non-compliance"]

        for item in search_res:
            snippet = item.get("snippet", "")
            if any(kw in snippet.lower() for kw in compliance_keywords):
                found_keywords = [kw for kw in compliance_keywords if kw in snippet.lower()]
                results.append({
                    "issue_description": snippet,
                    "source": item.get("url", ""),
                    "severity_keywords": found_keywords
                })
    except Exception as e:
        logger.warning(f"Regulatory issues search failed for {company_name}: {e}")

    return results
