"""
Google Docs fetcher for sheetwatch.

Fetches public Google Docs content using the export endpoint:
  https://docs.google.com/document/d/{doc_id}/export?format=...

Supports:
- Markdown export (format=md): preserves heading structure for cleaner parsing.
- Plain text export (format=txt): fallback if md fails.

Notes:
- This is NOT authenticated; it works only for docs that are publicly viewable.
- Uses the bot-wide aiohttp session (bot.session).
"""

from __future__ import annotations

import aiohttp


EXPORT_URL = "https://docs.google.com/document/d/{doc_id}/export?format={fmt}"


class GoogleDocsFetcher:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _fetch(self, doc_id: str, fmt: str, timeout_s: int = 20) -> str:
        url = EXPORT_URL.format(doc_id=doc_id, fmt=fmt)

        async with self.session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout_s),
            headers={
                # Helps avoid some odd content negotiation edge cases
                "User-Agent": "sheetwatch-bot/1.0",
                "Accept": "text/plain,text/markdown,text/*;q=0.9,*/*;q=0.1",
            },
            allow_redirects=True,
        ) as resp:
            body = await resp.text(errors="replace")

            if resp.status != 200:
                # Include small snippet for debugging
                snippet = (body[:200] + "...") if len(body) > 200 else body
                raise RuntimeError(f"HTTP {resp.status} fetching Google Doc export ({fmt}). Snippet: {snippet}")

            # Basic "is this HTML/login page?" detection
            lower = body.lower()
            if "<html" in lower and ("accounts.google.com" in lower or "sign in" in lower):
                raise RuntimeError("Doc export returned an HTML sign-in page. Is the doc set to public view?")

            return body

    async def fetch_md(self, doc_id: str, timeout_s: int = 20) -> str:
        return await self._fetch(doc_id, "md", timeout_s=timeout_s)

    async def fetch_txt(self, doc_id: str, timeout_s: int = 20) -> str:
        return await self._fetch(doc_id, "txt", timeout_s=timeout_s)

    async def fetch_best(self, doc_id: str, timeout_s: int = 20) -> tuple[str, str]:
        """
        Returns (content, fmt_used) where fmt_used is 'md' or 'txt'.
        Tries Markdown first for better structure; falls back to plain text.
        """
        try:
            return await self.fetch_md(doc_id, timeout_s=timeout_s), "md"
        except Exception:
            # Fallback to txt if md not available for some reason
            return await self.fetch_txt(doc_id, timeout_s=timeout_s), "txt"
