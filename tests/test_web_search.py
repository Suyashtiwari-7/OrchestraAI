"""
OrchestraAI — Web Search Tests
==============================
Tests for the DuckDuckGo web search tool and integration.
"""

import pytest
from unittest.mock import patch, MagicMock
from orchestra.tools.web_search import search_duckduckgo, execute_web_search

MOCK_DDG_HTML = """
<html>
<body>
    <div class="result__body">
        <a class="result__url" href="https://example.com/foo">Example Foo</a>
        <a class="result__snippet" href="#">Snippet for example foo.</a>
    </div>
    <div class="result__body">
        <a class="result__url" href="//duckduckgo.com/l/?uddg=https://example.org/bar">Example Bar</a>
        <a class="result__snippet" href="#">Snippet for example bar.</a>
    </div>
</body>
</html>
"""

class TestWebSearch:
    """Test DuckDuckGo scraping and integration parsing."""

    @patch("orchestra.tools.web_search.httpx.get")
    def test_search_duckduckgo_success(self, mock_get):
        """Test successful DuckDuckGo HTML scraping and query parameter parsing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_DDG_HTML
        mock_get.return_value = mock_response

        results = search_duckduckgo("test query", num_results=2)

        assert len(results) == 2
        assert results[0]["title"] == "Example Foo"
        assert results[0]["url"] == "https://example.com/foo"
        assert results[0]["snippet"] == "Snippet for example foo."
        
        # Verify redirect parameter uddg is correctly unpacked
        assert results[1]["title"] == "Example Bar"
        assert results[1]["url"] == "https://example.org/bar"
        assert results[1]["snippet"] == "Snippet for example bar."

    @patch("orchestra.tools.web_search.httpx.get")
    def test_search_duckduckgo_http_error(self, mock_get):
        """Test search error handling when DDG returns non-200."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        results = search_duckduckgo("test query")
        assert results == []

    @patch("orchestra.tools.web_search.scrape_url")
    @patch("orchestra.tools.web_search.search_duckduckgo")
    def test_execute_web_search(self, mock_search, mock_scrape):
        """Test execution and grounding compilation of top web search results."""
        mock_search.return_value = [
            {"title": "Result 1", "url": "https://url1.com", "snippet": "Snippet 1"},
            {"title": "Result 2", "url": "https://url2.com", "snippet": "Snippet 2"},
            {"title": "Result 3", "url": "https://url3.com", "snippet": "Snippet 3"},
        ]
        
        # Scraper returns success for url1, fail or empty for url2
        mock_scrape.side_effect = lambda url: {
            "success": True,
            "url": url,
            "content": f"Scraped text for {url}",
        } if url == "https://url1.com" else {"success": False, "error": "failed"}

        result = execute_web_search("grounded query")

        assert result["success"] is True
        assert len(result["results"]) == 3
        assert len(result["scraped_sources"]) == 1
        assert result["scraped_sources"][0]["url"] == "https://url1.com"
        
        # Verify compiled context includes scrape result for url1
        assert "Scraped text for https://url1.com" in result["context_text"]
        # Verify snippet from url2 is in context text even though scrape failed
        assert "Snippet 2" in result["context_text"]
