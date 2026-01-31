"""Web search tool using DuckDuckGo."""

from duckduckgo_search import DDGS

from tools.base import Tool


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for general information using DuckDuckGo. Use this for general queries. For visiting a SPECIFIC website (like techcrunch.com), use browser_navigate + browser_get_text instead."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5) -> str:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return f"No results found for: {query}"

            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   URL: {r['href']}")
                lines.append(f"   {r['body']}\n")

            return "\n".join(lines)
        except Exception as e:
            return f"Search error: {str(e)}"
