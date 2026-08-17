"""
OrchestraAI — DuckDuckGo Web Search Tool
=========================================
Keyless, free web search tool using DuckDuckGo HTML endpoint and BeautifulSoup
to gather real-time page content for LLM grounding.
"""

import httpx
import urllib.parse
from bs4 import BeautifulSoup
from typing import List, Dict, Any

from .web_scraper import scrape_url

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def search_duckduckgo(query: str, num_results: int = 4) -> List[Dict[str, str]]:
    """
    Perform a keyless search on DuckDuckGo and parse top results.
    
    Returns a list of dicts: [{'title': ..., 'url': ..., 'snippet': ...}]
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    try:
        response = httpx.get(url, headers=HEADERS, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Parse search results
        result_elements = soup.find_all("div", class_="result__body")
        for elem in result_elements[:num_results]:
            title_elem = elem.find("a", class_="result__url")
            snippet_elem = elem.find("a", class_="result__snippet")
            
            if title_elem and title_elem.get("href"):
                raw_url = title_elem.get("href")
                # Parse redirect url if it starts with //duckduckgo.com/l/?uddg=
                parsed_url = raw_url
                if "uddg=" in raw_url:
                    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    if "uddg" in query_params:
                        parsed_url = query_params["uddg"][0]
                
                results.append({
                    "title": title_elem.get_text(strip=True),
                    "url": parsed_url,
                    "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                })
        
        return results
    except Exception:
        return []

def execute_web_search(query: str) -> Dict[str, Any]:
    """
    Searches DuckDuckGo, scrapes the top 2 web pages, and compiles a combined context payload.
    """
    search_results = search_duckduckgo(query, num_results=4)
    if not search_results:
        return {
            "success": False,
            "error": "No search results found or DuckDuckGo is currently unreachable.",
            "results": []
        }
        
    compiled_context = []
    scraped_sources = []
    
    # Scrape the top 2 pages for deeper context
    pages_to_scrape = search_results[:2]
    for i, res in enumerate(search_results):
        source_info = f"Source [{i+1}]: {res['title']} ({res['url']})\nSnippet: {res['snippet']}"
        
        if res in pages_to_scrape:
            # Attempt to scrape full page text
            scrape_res = scrape_url(res["url"])
            if scrape_res["success"] and scrape_res.get("content"):
                # Clean and limit size of text
                text_content = scrape_res["content"][:3000].strip() # Limit to first 3000 chars
                source_info += f"\nFull Text Snippet:\n{text_content}\n"
                scraped_sources.append(res)
            
        compiled_context.append(source_info)
        
    full_context_text = "\n\n=========================================\n".join(compiled_context)
    
    return {
        "success": True,
        "query": query,
        "results": search_results,
        "context_text": full_context_text,
        "scraped_sources": scraped_sources
    }
