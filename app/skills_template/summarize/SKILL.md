---
name: summarize
description: Summarize text or web content
---
When user asks to summarize something:

1. If given a URL, use `browser_navigate` to visit it
2. Use `browser_get_text` to extract content
3. Provide a concise summary with key points

Format:
- **TL;DR**: One sentence summary
- **Key Points**: 3-5 bullet points
- **Details**: Brief elaboration if needed
