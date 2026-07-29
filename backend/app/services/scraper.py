import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

async def scrape_article_url(url: str) -> dict:
    """Scrapes news article content, headline, and domain metadata from a URL."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        
        # Remove unwanted script, style, header, footer elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()

        # Extract title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.h1:
            title = soup.h1.get_text().strip()

        # Extract main body text
        article_body = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|article|body|post", re.I))
        if article_body:
            paragraphs = article_body.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        text_content = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])

        if not text_content:
            # Fallback to body text
            text_content = soup.get_text(separator=" ", strip=True)

        # Truncate text content to prevent extreme token usage
        if len(text_content) > 12000:
            text_content = text_content[:12000] + "..."

        domain = urlparse(url).netloc

        return {
            "url": url,
            "title": title or "Untitled Article",
            "text": text_content,
            "domain": domain
        }
    except Exception as e:
        return {
            "url": url,
            "title": "Error Scraping Page",
            "text": f"Could not scrape article directly ({str(e)}). Analysis will rely on user payload.",
            "domain": urlparse(url).netloc if url else "unknown"
        }
