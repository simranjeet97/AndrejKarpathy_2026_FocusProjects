import re
import socket
import ipaddress
from datetime import datetime
from urllib.parse import urlparse
import httpx
from src.models import IndustryBenchmark

def _is_safe_query(query: str) -> bool:
    """Checks query against common SQL/code injection keywords."""
    forbidden_patterns = [
        r"\bselect\b.*\bfrom\b",
        r"\bunion\b.*\bselect\b",
        r"\bdrop\b\s+\btable\b",
        r"\binsert\b\s+\binto\b",
        r"\bdelete\b\s+\bfrom\b",
        r"\bupdate\b.*\bset\b",
        r"<script.*?>",
        r"javascript:",
        r"\bor\b\s+\d+=\d+",
    ]
    query_lower = query.lower()
    for pattern in forbidden_patterns:
        if re.search(pattern, query_lower):
            return False
    return True

def _is_valid_url(url: str) -> bool:
    """Validates if a string is a well-formed HTTP/HTTPS URL and is safe (non-SSRF)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # Resolve hostname to check for internal/private/loopback IPs (SSRF prevention)
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_link_local:
                return False
        return True
    except Exception:
        return False

def _extract_number(text: str) -> float:
    """Attempts to extract a percentage or decimal value from a text snippet."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return 0.0

async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for current information. Returns list of {title, url, snippet}."""
    if not _is_safe_query(query):
        raise ValueError("Potential code or SQL injection attack detected in query.")

    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": "1"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    results = []

    # Check for instant answer / abstract
    if data.get("AbstractText") and data.get("AbstractURL"):
        results.append({
            "title": data.get("Heading", "Abstract"),
            "url": data.get("AbstractURL"),
            "snippet": data.get("AbstractText")
        })

    # Check results list
    for res in data.get("Results", []):
        if "Text" in res and "FirstURL" in res:
            results.append({
                "title": res["Text"].split(" - ")[0] or res["Text"][:30],
                "url": res["FirstURL"],
                "snippet": res["Text"]
            })

    # Check related topics
    for topic in data.get("RelatedTopics", []):
        if "Text" in topic and "FirstURL" in topic:
            results.append({
                "title": topic["Text"].split(" - ")[0] or topic["Text"][:30],
                "url": topic["FirstURL"],
                "snippet": topic["Text"]
            })
        elif "Topics" in topic:
            for subtopic in topic["Topics"]:
                if "Text" in subtopic and "FirstURL" in subtopic:
                    results.append({
                        "title": subtopic["Text"].split(" - ")[0] or subtopic["Text"][:30],
                        "url": subtopic["FirstURL"],
                        "snippet": subtopic["Text"]
                    })

    return results[:max_results]

async def search_industry_benchmarks(metric: str, industry: str = "saas") -> list[IndustryBenchmark]:
    """Search for industry benchmark data for a specific metric."""
    current_year = datetime.now().year
    query = f"{metric} {industry} benchmark statistics {current_year}"
    
    search_results = await search_web(query)
    benchmarks = []
    
    for res in search_results:
        val = _extract_number(res["snippet"])
        benchmarks.append(
            IndustryBenchmark(
                metric_name=metric,
                value=val,
                source=res["url"],
                retrieved_at=datetime.utcnow()
            )
        )
        
    return benchmarks

async def fetch_page_content(url: str) -> str:
    """Fetch and extract plain text from a webpage. Max 3000 chars."""
    if not _is_valid_url(url):
        raise ValueError("Invalid URL provided")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    # Remove script and style tags
    text = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip HTML tags
    text = re.sub(r"<.*?>", "", text)
    # Normalize whitespaces
    text = re.sub(r"\s+", " ", text).strip()

    return text[:3000]
