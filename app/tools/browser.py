"""Browser automation tools using Playwright."""

import base64
from typing import Optional

from playwright.async_api import Browser, Page, async_playwright

from tools.base import Tool


class BrowserManager:
    """Manages browser instance and pages."""

    _instance: Optional["BrowserManager"] = None
    _browser: Optional[Browser] = None
    _page: Optional[Page] = None
    _playwright = None

    @classmethod
    async def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_page(self) -> Page:
        """Get or create browser page."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)

        if self._page is None or self._page.is_closed():
            self._page = await self._browser.new_page()

        return self._page

    async def close(self):
        """Close browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


class BrowserNavigateTool(Tool):
    """Navigate to a URL."""

    @property
    def name(self) -> str:
        return "browser_navigate"

    @property
    def description(self) -> str:
        return "Navigate the browser to a specific website URL. USE THIS when you need to visit a specific website (like techcrunch.com, news sites, etc.) to read its actual current content. After navigating, use browser_get_text to read the page content."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"}
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> str:
        try:
            manager = await BrowserManager.get_instance()
            page = await manager.get_page()
            await page.goto(url, wait_until="domcontentloaded")
            return f"Navigated to: {page.url}\nTitle: {await page.title()}"
        except Exception as e:
            return f"Navigation error: {str(e)}"


class BrowserScreenshotTool(Tool):
    """Take a screenshot of the current page."""

    @property
    def name(self) -> str:
        return "browser_screenshot"

    @property
    def description(self) -> str:
        return "Take a screenshot of the current browser page. Returns base64 encoded image."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": "Capture full page (default false)",
                    "default": False,
                }
            },
            "required": [],
        }

    async def execute(self, full_page: bool = False) -> str:
        try:
            import tempfile
            from datetime import datetime

            manager = await BrowserManager.get_instance()
            page = await manager.get_page()
            screenshot = await page.screenshot(full_page=full_page)

            # Save to temp file for Telegram
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_path = tempfile.gettempdir() + f"/squidbot_screenshot_{timestamp}.png"
            with open(temp_path, "wb") as f:
                f.write(screenshot)

            # Return special format that server can detect
            return (
                f"[SCREENSHOT:{temp_path}] Screenshot saved ({len(screenshot)} bytes)"
            )
        except Exception as e:
            return f"Screenshot error: {str(e)}"


class BrowserSnapshotTool(Tool):
    """Get accessibility tree snapshot of the page."""

    @property
    def name(self) -> str:
        return "browser_snapshot"

    @property
    def description(self) -> str:
        return "Get a text snapshot of the current page content (accessibility tree). Use this to understand page structure before interacting."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> str:
        try:
            manager = await BrowserManager.get_instance()
            page = await manager.get_page()

            # Get simplified page content
            content = await page.evaluate(
                """() => {
                const walk = (node, depth = 0) => {
                    let result = [];
                    const indent = '  '.repeat(depth);

                    if (node.nodeType === Node.TEXT_NODE) {
                        const text = node.textContent.trim();
                        if (text) result.push(indent + text);
                    } else if (node.nodeType === Node.ELEMENT_NODE) {
                        const tag = node.tagName.toLowerCase();
                        const role = node.getAttribute('role') || '';
                        const name = node.getAttribute('aria-label') || node.getAttribute('name') || '';
                        const href = node.getAttribute('href') || '';

                        let info = tag;
                        if (role) info += ` [${role}]`;
                        if (name) info += ` "${name}"`;
                        if (href && tag === 'a') info += ` -> ${href}`;

                        if (['script', 'style', 'noscript'].includes(tag)) return result;

                        if (['button', 'a', 'input', 'select', 'textarea', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
                            result.push(indent + info);
                        }

                        for (const child of node.childNodes) {
                            result = result.concat(walk(child, depth + 1));
                        }
                    }
                    return result;
                };
                return walk(document.body).slice(0, 100).join('\\n');
            }"""
            )

            title = await page.title()
            url = page.url
            return f"Page: {title}\nURL: {url}\n\nContent:\n{content}"
        except Exception as e:
            return f"Snapshot error: {str(e)}"


class BrowserClickTool(Tool):
    """Click an element on the page."""

    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return "Click an element on the page by text content or CSS selector."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or text to click (e.g., 'button.submit' or 'text=Sign In')",
                }
            },
            "required": ["selector"],
        }

    async def execute(self, selector: str) -> str:
        try:
            manager = await BrowserManager.get_instance()
            page = await manager.get_page()

            # Try as text selector first if no CSS chars
            if not any(c in selector for c in ".#[]>+~:"):
                try:
                    await page.get_by_text(selector).first.click(timeout=5000)
                    return f"Clicked element with text: {selector}"
                except:
                    pass

            await page.click(selector, timeout=5000)
            return f"Clicked: {selector}"
        except Exception as e:
            return f"Click error: {str(e)}"


class BrowserTypeTool(Tool):
    """Type text into an input field."""

    @property
    def name(self) -> str:
        return "browser_type"

    @property
    def description(self) -> str:
        return "Type text into an input field."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the input field",
                },
                "text": {"type": "string", "description": "Text to type"},
                "submit": {
                    "type": "boolean",
                    "description": "Press Enter after typing (default false)",
                    "default": False,
                },
            },
            "required": ["selector", "text"],
        }

    async def execute(self, selector: str, text: str, submit: bool = False) -> str:
        try:
            manager = await BrowserManager.get_instance()
            page = await manager.get_page()
            await page.fill(selector, text)
            if submit:
                await page.press(selector, "Enter")
            return f"Typed '{text}' into {selector}" + (
                " and submitted" if submit else ""
            )
        except Exception as e:
            return f"Type error: {str(e)}"


class BrowserGetTextTool(Tool):
    """Get text content from the page."""

    @property
    def name(self) -> str:
        return "browser_get_text"

    @property
    def description(self) -> str:
        return "Get the actual text content from the current browser page. Use this after browser_navigate to read and extract information from the website. Returns the full page text for summarization or analysis."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector (optional, defaults to body)",
                }
            },
            "required": [],
        }

    async def execute(self, selector: str = "body") -> str:
        try:
            manager = await BrowserManager.get_instance()
            page = await manager.get_page()
            text = await page.inner_text(selector)
            # Limit output
            if len(text) > 5000:
                text = text[:5000] + "\n...(truncated)"
            return text
        except Exception as e:
            return f"Get text error: {str(e)}"
