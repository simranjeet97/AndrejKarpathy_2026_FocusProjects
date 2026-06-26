import asyncio
import re
import urllib.parse
import logging
import httpx
from ..search.web_search import search_web, fetch_page_text, validate_url

logger = logging.getLogger("VentureMind.FinancialTools")

# Share a single connection-pooled AsyncClient for financial tool requests
_client = None

def get_financial_client() -> httpx.AsyncClient:
    """Retrieve or initialize the shared pooled async HTTP client for financial tools."""
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
        _client = httpx.AsyncClient(timeout=10.0, limits=limits)
    return _client

async def get_sec_edgar_filings(company_name: str) -> list[dict]:
    """Retrieve filing documents from the SEC EDGAR search index with fallback web search."""
    headers = {
        "User-Agent": "VentureMind DueDiligence contact@venturemind.ai",
        "Content-Type": "application/json"
    }
    
    # Attempt 1: POST request to EFTS search index (modern Elasticsearch API)
    url_post = "https://efts.sec.gov/LATEST/search-index"
    payload = {
        "q": f'"{company_name}"',
        "dateRange": "custom",
        "startdt": "2020-01-01"
    }
    
    client = get_financial_client()
    
    try:
        response = await client.post(url_post, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                return _parse_efts_hits(hits)
    except Exception as e:
        logger.warning(f"SEC EFTS POST request failed: {e}. Trying GET...")

    # Attempt 2: GET request to EFTS search index (fallback endpoint)
    query_quoted = urllib.parse.quote(f'"{company_name}"')
    url_get = f"https://efts.sec.gov/LATEST/search-index?q={query_quoted}&dateRange=custom&startdt=2020-01-01"
    try:
        validate_url(url_get)
        response = await client.get(url_get, headers=headers)
        if response.status_code == 200:
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                return _parse_efts_hits(hits)
    except Exception as e:
        logger.warning(f"SEC EFTS GET request failed: {e}. Falling back to web search scraping.")

    # Attempt 3: Fallback web search scrape of SEC.gov filings
    filings = []
    try:
        web_results = await search_web(f"site:sec.gov \"{company_name}\" filing", max_results=5)
        for r in web_results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            
            # Extract form type (e.g. S-1, 10-K, 10-Q) from snippet/title
            form_match = re.search(r"\b(10-K|10-Q|S-1|8-K|Form\s+4)\b", f"{title} {snippet}", re.IGNORECASE)
            form_type = form_match.group(1).upper() if form_match else "Other"
            
            filings.append({
                "form_type": form_type,
                "filed_at": "unknown",
                "url": r.get("url", ""),
                "description": title
            })
    except Exception as fallback_err:
        logger.error(f"Fallback filings search failed: {fallback_err}")

    return filings

def _parse_efts_hits(hits: list) -> list[dict]:
    """Helper to parse raw elasticsearch hits into standard due diligence filing dictionaries."""
    filings = []
    for hit in hits:
        source = hit.get("_source", {})
        form_type = source.get("form", "")
        filed_at = source.get("file_date", "")
        cik = source.get("cik", "")
        adsh = source.get("adsh", "").replace("-", "")
        filename = source.get("filename", "")
        
        # Build standard URL to access the document in EDGAR archive
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/{filename}"
        desc = source.get("title", "") or source.get("root_form", "")
        
        filings.append({
            "form_type": form_type,
            "filed_at": filed_at,
            "url": doc_url,
            "description": desc
        })
    return filings

async def get_crunchbase_signals(company_name: str) -> dict:
    """Gather funding, valuation, and employee signals from Crunchbase profile search snippets."""
    default_res = {
        "funding_mentions": [],
        "employee_mentions": [],
        "source": "crunchbase_search"
    }

    try:
        results = await search_web(f"site:crunchbase.com {company_name}", max_results=3)
        if not results:
            return default_res

        funding_mentions = []
        employee_mentions = []

        funding_pattern = r'(?i)(?:raised|funding|valuation|raised\s+\$[\d,.]+\s*(?:million|billion|M|B))'
        employee_pattern = r'(?i)(?:\b[\d,+-]+\s+employees|\b[\d,+-]+\s+people\b)'

        for r in results:
            snippet = r.get("snippet", "")
            sentences = re.split(r'(?<=[.!?])\s+', snippet)
            for sent in sentences:
                if re.search(funding_pattern, sent):
                    funding_mentions.append(sent.strip())
                if re.search(employee_pattern, sent):
                    employee_mentions.append(sent.strip())

        default_res["funding_mentions"] = list(set(funding_mentions))
        default_res["employee_mentions"] = list(set(employee_mentions))
    except Exception as e:
        logger.warning(f"Crunchbase signals fetch failed for {company_name}: {e}")

    return default_res

async def get_pitchbook_signals(company_name: str) -> dict:
    """Retrieve private round funding statistics and insights from PitchBook search profiles."""
    default_res = {
        "funding_mentions": [],
        "source": "pitchbook_search"
    }

    try:
        results = await search_web(f"site:pitchbook.com {company_name} funding", max_results=3)
        if not results:
            return default_res

        funding_mentions = []
        funding_pattern = r'(?i)(?:raised|funding|valuation|[\d,.]+\s*(?:million|billion|M|B))'

        for r in results:
            snippet = r.get("snippet", "")
            sentences = re.split(r'(?<=[.!?])\s+', snippet)
            for sent in sentences:
                if re.search(funding_pattern, sent):
                    funding_mentions.append(sent.strip())

        default_res["funding_mentions"] = list(set(funding_mentions))
    except Exception as e:
        logger.warning(f"PitchBook signals fetch failed for {company_name}: {e}")

    return default_res

async def estimate_revenue(company_name: str, industry: str) -> dict:
    """Estimate annual recurring revenue (ARR) from general web pages and press releases."""
    default_res = {
        "revenue_estimate": "Not found",
        "confidence": "low",
        "sources": []
    }
    query = f"{company_name} revenue annual recurring ARR 2024"

    try:
        results = await search_web(query, max_results=3)
        if not results:
            return default_res

        urls = [r["url"] for r in results]
        tasks = [fetch_page_text(url) for url in urls]
        pages_text = await asyncio.gather(*tasks)

        revenue_pattern = r'(?i)(?:ARR|revenue|recurring\s+revenue|annual\s+revenue)\b.*?\b(\$[\d,.]+\s*(?:million|billion|M|B)?)\b'
        currency_pattern = r'(?i)\$[\d,.]+\s*(?:million|billion|M|B)\b'
        
        found_rev = []
        sources = []

        for url, text in zip(urls, pages_text):
            if text.startswith("Error fetching"):
                continue
            
            match = re.search(revenue_pattern, text)
            if match:
                found_rev.append(match.group(1).strip())
                sources.append(url)
            else:
                matches = re.findall(currency_pattern, text)
                if matches:
                    found_rev.append(matches[0])
                    sources.append(url)

        if not found_rev:
            for r in results:
                match = re.search(revenue_pattern, r.get("snippet", ""))
                if match:
                    found_rev.append(match.group(1).strip())
                    sources.append(r.get("url", ""))

        if found_rev:
            return {
                "revenue_estimate": found_rev[0],
                "confidence": "medium" if len(sources) > 1 else "low",
                "sources": list(set(sources))
            }
    except Exception as e:
        logger.warning(f"Revenue estimation failed for {company_name}: {e}")

    return default_res

async def get_job_posting_signals(company_name: str) -> dict:
    """Check active recruitment listings as an indicator for operational expansion and cash burn."""
    default_res = {
        "active_roles_estimate": 0,
        "hiring_signal": "stable",
        "source": ""
    }
    query = f'"{company_name}" jobs hiring (site:linkedin.com OR site:greenhouse.io)'

    try:
        results = await search_web(query, max_results=3)
        if not results:
            return default_res

        # Count references matching recruitment patterns
        job_urls = [
            r.get("url", "") for r in results 
            if "jobs" in r.get("url", "") or "greenhouse.io" in r.get("url", "")
        ]
        roles_est = len(job_urls)
        hiring_sig = "stable"

        for r in results:
            snippet = r.get("snippet", "")
            match = re.search(r'(\d+)\s+(?:openings|jobs|roles|positions|open)', snippet, re.IGNORECASE)
            if match:
                roles_est = max(roles_est, int(match.group(1)))

        if roles_est > 10:
            hiring_sig = "growing"
        elif roles_est == 0:
            hiring_sig = "contracting"

        return {
            "active_roles_estimate": roles_est,
            "hiring_signal": hiring_sig,
            "source": results[0].get("url", "") if results else ""
        }
    except Exception as e:
        logger.warning(f"Hiring signal tracking failed for {company_name}: {e}")

    return default_res
