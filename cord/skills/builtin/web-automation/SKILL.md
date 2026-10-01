---
name: web-automation
description: Web scraping, HTTP API querying, REST payload testing, automated browser interactions, and network diagnostics.
category: Network & Web
---

# Web Automation & API Testing Skill

Guidelines for performing robust network requests, web scraping, and API verification.

## Principles

1. **HTTP Testing**:
   - Prefer standard non-blocking Python scripts (`httpx` or `requests`) or curl/powershell Invoke-RestMethod for API diagnostics.
   - Always validate status codes (2xx vs 4xx/5xx) and print structured JSON responses.

2. **Scraping & Data Extraction**:
   - Use `BeautifulSoup` or clean regex for extracting structured tags from HTML pages.
   - Handle rate limiting gracefully with backoff delays.

3. **Authentication**:
   - Always pass auth headers via Bearer tokens or environment variables. Never hardcode credentials in public outputs.
