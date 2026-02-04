"""Tests for screenshot path parsing in Telegram responses."""

import re

import pytest


def extract_screenshots(response: str) -> list[str]:
    """Extract screenshot paths from response text (mirrors server.py logic)."""
    screenshots = []

    # Pattern 1: [SCREENSHOT:path]
    pattern1 = r"\[SCREENSHOT:([^\]]+)\]"
    screenshots.extend(re.findall(pattern1, response))

    # Pattern 2: backtick-wrapped paths like `/.../squidbot_screenshot_*.png`
    pattern2 = r"`([^`]*squidbot_screenshot_[^`]+\.png)`"
    screenshots.extend(re.findall(pattern2, response))

    # Pattern 3: plain paths /tmp/squidbot_screenshot_*.png or /var/folders/.../squidbot_screenshot_*.png
    pattern3 = r"(/(?:tmp|var/folders)[^\s`\)]*squidbot_screenshot_[^\s`\)]+\.png)"
    screenshots.extend(re.findall(pattern3, response))

    # Pattern 4: markdown image syntax ![...](path)
    pattern4 = r"!\[[^\]]*\]\(([^)]*squidbot_screenshot_[^)]+\.png)\)"
    screenshots.extend(re.findall(pattern4, response))

    return list(set(screenshots))


class TestScreenshotParsing:
    """Test screenshot path extraction from responses."""

    def test_pattern1_screenshot_tag(self):
        """Test [SCREENSHOT:path] pattern."""
        response = (
            "Here's the screenshot:\n[SCREENSHOT:/tmp/squidbot_screenshot_123.png]"
        )
        screenshots = extract_screenshots(response)
        assert "/tmp/squidbot_screenshot_123.png" in screenshots

    def test_pattern2_backtick_wrapped(self):
        """Test backtick-wrapped path pattern."""
        response = "Screenshot saved at: `/var/folders/abc/squidbot_screenshot_456.png`"
        screenshots = extract_screenshots(response)
        assert "/var/folders/abc/squidbot_screenshot_456.png" in screenshots

    def test_pattern3_plain_tmp_path(self):
        """Test plain /tmp path pattern."""
        response = "Saved to /tmp/squidbot_screenshot_789.png for viewing"
        screenshots = extract_screenshots(response)
        assert "/tmp/squidbot_screenshot_789.png" in screenshots

    def test_pattern3_plain_var_folders_path(self):
        """Test plain /var/folders path pattern."""
        response = "Screenshot: /var/folders/sr/5g9pvgsx2l1_l9_w0l8qndbc0000gn/T/squidbot_screenshot_20260204_203751.png"
        screenshots = extract_screenshots(response)
        assert (
            "/var/folders/sr/5g9pvgsx2l1_l9_w0l8qndbc0000gn/T/squidbot_screenshot_20260204_203751.png"
            in screenshots
        )

    def test_pattern4_markdown_image(self):
        """Test markdown image ![...](path) pattern."""
        response = "Here's the screenshot:\n\n![TechCrunch screenshot](/var/folders/sr/5g9pvgsx2l1_l9_w0l8qndbc0000gn/T/squidbot_screenshot_20260204_203751.png)"
        screenshots = extract_screenshots(response)
        assert (
            "/var/folders/sr/5g9pvgsx2l1_l9_w0l8qndbc0000gn/T/squidbot_screenshot_20260204_203751.png"
            in screenshots
        )

    def test_pattern4_markdown_image_with_alt_text(self):
        """Test markdown image with various alt texts."""
        response = "![Screenshot of website](/tmp/squidbot_screenshot_test.png)"
        screenshots = extract_screenshots(response)
        assert "/tmp/squidbot_screenshot_test.png" in screenshots

    def test_pattern4_markdown_image_empty_alt(self):
        """Test markdown image with empty alt text."""
        response = "![](/tmp/squidbot_screenshot_test.png)"
        screenshots = extract_screenshots(response)
        assert "/tmp/squidbot_screenshot_test.png" in screenshots

    def test_multiple_screenshots(self):
        """Test extracting multiple screenshots from one response."""
        response = """Here are the screenshots:

![First](/tmp/squidbot_screenshot_1.png)

And here's another one:
[SCREENSHOT:/tmp/squidbot_screenshot_2.png]

Also saved at `/var/folders/x/squidbot_screenshot_3.png`
"""
        screenshots = extract_screenshots(response)
        assert len(screenshots) == 3
        assert "/tmp/squidbot_screenshot_1.png" in screenshots
        assert "/tmp/squidbot_screenshot_2.png" in screenshots
        assert "/var/folders/x/squidbot_screenshot_3.png" in screenshots

    def test_deduplication(self):
        """Test that duplicate paths are deduplicated."""
        response = """![Screenshot](/tmp/squidbot_screenshot_dup.png)

Here's the path again: `/tmp/squidbot_screenshot_dup.png`"""
        screenshots = extract_screenshots(response)
        assert len(screenshots) == 1
        assert "/tmp/squidbot_screenshot_dup.png" in screenshots

    def test_no_screenshots(self):
        """Test response with no screenshots."""
        response = "Hello! How can I help you today?"
        screenshots = extract_screenshots(response)
        assert screenshots == []

    def test_non_screenshot_image(self):
        """Test that non-squidbot images are not matched."""
        response = "![Logo](/images/logo.png)"
        screenshots = extract_screenshots(response)
        assert screenshots == []

    def test_real_world_response(self):
        """Test with actual response format from the bot."""
        response = """Here's the Playwright screenshot of TechCrunch (full page):

![TechCrunch screenshot](/var/folders/sr/5g9pvgsx2l1_l9_w0l8qndbc0000gn/T/squidbot_screenshot_20260204_203751.png)"""
        screenshots = extract_screenshots(response)
        assert len(screenshots) == 1
        assert (
            "/var/folders/sr/5g9pvgsx2l1_l9_w0l8qndbc0000gn/T/squidbot_screenshot_20260204_203751.png"
            in screenshots
        )
