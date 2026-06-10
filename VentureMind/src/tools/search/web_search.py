import re
import socket
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote
import httpx
from bs4 import BeautifulSoup

def validate_url(url: str) -> None:
    """Validate that the URL is well-formed, uses http/https, and does not access private/local IPs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only HTTP and HTTPS protocols are permitted.")
        if not parsed.netloc:
            raise ValueError("URL host is missing or invalid.")
        
        host = parsed.hostname.lower() if parsed.hostname else ""
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            raise ValueError("Access to local network is forbidden.")

        # Resolve host IP to protect against SSRF on private/link-local address spaces
        try:
            ip = socket.gethostbyname(host)
            ip_parts = list(map(int, ip.split('.')))
            if (
                ip_parts[0] == 10 or
                (ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31) or
                (ip_parts[0] == 192 and ip_parts[1] == 168) or
                (ip_parts[0] == 169 and ip_parts[1] == 254) or
                ip == "127.0.0.1"
            ):
                raise ValueError("Access to private network IP address spaces is forbidden.")
        except socket.gaierror:
            # Let httpx handle host resolution failure naturally
            pass
    except Exception as e:
        raise ValueError(f"URL validation failed: {url} - {str(e)}")

def validate_query(query: str) -> None:
    """Validate that the search query contains no SQL injection patterns."""
    sql_patterns = [
        r"(?i)\bselect\b.*\bfrom\b",
        r"(?i)\bunion\b.*\bselect\b",
        r"(?i)\binsert\b.*\binto\b",
        r"(?i)\bdelete\b.*\bfrom\b",
        r"(?i)\bdrop\b\s+\btable\b",
        r"(?i)\bupdate\b.*\bset\b",
        r"--",
        r"\bOR\b\s+\d+\s*=\s*\d+",
    ]
    for pattern in sql_patterns:
        if re.search(pattern, query):
            raise ValueError("Query rejected: contains potential SQL injection patterns.")

async def search_web(query: str, max_results: int = 10) -> list[dict]:
    """Execute a web search using DuckDuckGo Instant Answer API, falling back to HTML scraping."""
    validate_query(query)
    results = []

    # 1. DuckDuckGo Instant Answer JSON API
    json_url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(json_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Parse abstract
            if data.get("AbstractText") and data.get("AbstractURL"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL"),
                    "snippet": data.get("AbstractText"),
                    "source": "DuckDuckGo Instant Answer"
                })

            # Parse related topics
            for topic in data.get("RelatedTopics", []):
                if len(results) >= max_results:
                    break
                if "Topics" in topic:
                    for subtopic in topic["Topics"]:
                        if len(results) >= max_results:
                            break
                        if subtopic.get("FirstURL") and subtopic.get("Text"):
                            results.append({
                                "title": subtopic.get("Text").split(" - ")[0] if " - " in subtopic.get("Text") else subtopic.get("Text")[:50],
                                "url": subtopic.get("FirstURL"),
                                "snippet": subtopic.get("Text"),
                                "source": "DuckDuckGo Related Topics"
                            })
                elif topic.get("FirstURL") and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text").split(" - ")[0] if " - " in topic.get("Text") else topic.get("Text")[:50],
                        "url": topic.get("FirstURL"),
                        "snippet": topic.get("Text"),
                        "source": "DuckDuckGo Related Topics"
                    })
    except Exception:
        # Ignore errors and fall back to HTML scraping
        pass

    # 2. Fallback to HTML Scraping
    if not results:
        results = await _scrape_ddg_html(query, max_results)

    return results[:max_results]

async def _scrape_ddg_html(query: str, max_results: int) -> list[dict]:
    """Scrape standard search results from html.duckduckgo.com."""
    html_url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    results = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(html_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for r in soup.find_all("div", class_="result"):
                if len(results) >= max_results:
                    break
                title_el = r.find("a", class_="result__a")
                snippet_el = r.find("a", class_="result__snippet")
                
                if title_el:
                    title = title_el.get_text(strip=True)
                    raw_url = title_el.get("href", "")
                    url = raw_url

                    # Resolve DuckDuckGo redirects
                    if "/uddg?uddg=" in raw_url:
                        parsed_url = urlparse(raw_url)
                        qs = parse_qs(parsed_url.query)
                        if "uddg" in qs:
                            url = unquote(qs["uddg"][0])

                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "source": "DuckDuckGo HTML Search"
                    })
    except Exception:
        pass

    return results

async def search_company(company_name: str) -> list[dict]:
    """Search for general startup data (funding, founders, etc.) on a company name."""
    query = f'"{company_name}" startup company funding founders'
    return await search_web(query, max_results=10)

async def fetch_page_text(url: str, max_chars: int = 5000) -> str:
    """Fetch URL contents, strip HTML markup and code blocks, and return cleaned body paragraphs."""
    validate_url(url)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove scripts, styles, headers, and footers
            for elem in soup(["script", "style", "meta", "noscript", "header", "footer", "nav"]):
                elem.decompose()

            # Extract structural paragraph text
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
            cleaned_text = "\n\n".join([p for p in paragraphs if p])

            if not cleaned_text:
                cleaned_text = soup.get_text(separator="\n", strip=True)

            return cleaned_text[:max_chars]
    except Exception as e:
        return f"Error fetching page content: {str(e)}"

async def search_news(query: str, days_back: int = 90) -> list[dict]:
    """Execute news searches with date filtering using DuckDuckGo News endpoint or news search scraper."""
    validate_query(query)
    
    if days_back <= 1:
        df = "d"
    elif days_back <= 7:
        df = "w"
    elif days_back <= 30:
        df = "m"
    else:
        df = "y"

    news_url = f"https://duckduckgo.com/news.js?q={query}&df={df}&o=json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    results = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(news_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            for item in data.get("results", []):
                dt = item.get("date")
                if isinstance(dt, (int, float)):
                    dt_str = datetime.fromtimestamp(dt).isoformat()
                else:
                    dt_str = str(dt)

                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "date": dt_str,
                    "snippet": item.get("excerpt", ""),
                })
    except Exception:
        # Fallback to general HTML search with df filter if JSON news endpoint fails
        html_results = await _scrape_ddg_html(f"{query} news", max_results=10)
        for r in html_results:
            results.append({
                "title": r["title"],
                "url": r["url"],
                "date": datetime.utcnow().isoformat(),
                "snippet": r["snippet"],
            })

    return results
