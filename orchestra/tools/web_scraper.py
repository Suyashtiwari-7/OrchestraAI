"""
OrchestraAI — Web Scraper Tool
=================================
Fetches content from URLs, strips HTML to extract clean text,
and feeds it to the router for summarization or analysis.
"""

import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel

console = Console()

# Reasonable limits
MAX_CONTENT_LENGTH = 15000  # Max characters to extract from a page
REQUEST_TIMEOUT = 15        # Seconds
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OrchestraAI/1.0"
)


def extract_url(text: str) -> Optional[str]:
    """
    Extract the first URL from a text string.

    Handles inputs like:
        - "https://example.com"
        - "/scrape https://example.com"
        - "Summarize this: https://example.com/article"

    Returns:
        The extracted URL or None.
    """
    pattern = r'(https?://[^\s<>"\']+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None


def validate_url(url: str) -> bool:
    """Check if a URL is valid and uses http/https."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def scrape_url(url: str) -> dict:
    """
    Fetch a URL and extract its text content.

    Args:
        url: The URL to scrape.

    Returns:
        Dict with 'success', 'url', 'title', 'content', 'word_count',
        and 'error' keys.
    """
    if not validate_url(url):
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "word_count": 0,
            "error": f"Invalid URL: {url}",
        }

    try:
        console.print(f"  [dim]🌐 Fetching {url}...[/dim]")

        with httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(url)
            response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header",
                            "aside", "form", "iframe", "noscript"]):
            element.decompose()

        # Extract text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        # Truncate if too long
        if len(cleaned_text) > MAX_CONTENT_LENGTH:
            cleaned_text = cleaned_text[:MAX_CONTENT_LENGTH] + "\n\n[...content truncated...]"

        word_count = len(cleaned_text.split())

        console.print(
            f"  [green]✓ Fetched successfully[/green] — "
            f"[dim]{word_count} words extracted[/dim]"
        )

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": cleaned_text,
            "word_count": word_count,
            "error": None,
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "word_count": 0,
            "error": f"Request timed out after {REQUEST_TIMEOUT}s.",
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "word_count": 0,
            "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "title": "",
            "content": "",
            "word_count": 0,
            "error": f"Scraping failed: {str(e)}",
        }


def format_scraped_content(scrape_result: dict) -> str:
    """
    Format scraped content into a prompt for the LLM to summarize.

    Args:
        scrape_result: The result dict from scrape_url().

    Returns:
        A formatted string to send to the LLM.
    """
    if not scrape_result["success"]:
        return f"Failed to scrape URL: {scrape_result['error']}"

    return (
        f"I scraped the following webpage. Please provide a comprehensive summary.\n\n"
        f"**URL:** {scrape_result['url']}\n"
        f"**Title:** {scrape_result['title']}\n"
        f"**Word Count:** {scrape_result['word_count']}\n\n"
        f"---\n\n"
        f"{scrape_result['content']}"
    )
