"""Retrieve current official guideline text; never derive diagnoses from a local graph."""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .llm_service import ClinicalModelError


ORIGIN = "https://www.nice.org.uk"
GUIDANCE_PATH = re.compile(r"^/guidance/((?:ng|cg)\d+)$", re.I)
SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    return SPACE.sub(" ", text).strip()


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.netloc == "www.nice.org.uk"
            and (parsed.path == "/search" or re.fullmatch(
                r"/guidance/(ng|cg)\d+(/chapter/[a-zA-Z0-9-]+)?/?", parsed.path, re.I) is not None))


def parse_search(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    result, seen = [], set()
    for link in soup.select('a[href]'):
        url = urljoin(ORIGIN, link["href"])
        match = GUIDANCE_PATH.fullmatch(urlparse(url).path)
        if not official_url(url) or not match:
            continue
        code = match[1].lower()
        title = normalize(link.get_text(" ", strip=True))
        if code in seen or len(title) < 15 or title.lower() == "overview":
            continue
        seen.add(code)
        result.append({"code": code, "url": f"{ORIGIN}/guidance/{code}/chapter/recommendations"})
    return result[:2]


def parse_guideline(html: str, url: str, code: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h1")
    if not title or not official_url(url):
        return []
    notices = " ".join(n.get_text(" ", strip=True) for n in soup.select('.alert, .notice, .message'))
    if re.search(r"withdrawn|replaced by|no longer current", notices, re.I):
        return []
    dates = [t.get("datetime", "") for t in soup.select('time[datetime]')]
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = []
    for article in soup.select('article.recommendation[id]'):
        body = article.select_one('.recommendation__body')
        number = article.select_one('.recommendation__number')
        if body is None or number is None:
            continue
        text = normalize(body.get_text(" ", strip=True))
        if not 35 <= len(text) <= 2500 or re.search(r"recommendation has been removed", text, re.I):
            continue
        result.append({
            "source_id": f"nice:{code}:{article['id']}",
            "title": normalize(title.get_text(" ", strip=True)),
            "publisher": "NICE（英国国家卫生与临床优化研究所）",
            "guideline_code": code.upper(),
            "published_date": dates[0] if dates else "",
            "updated_date": dates[1] if len(dates) > 1 else "",
            "checked_at": checked,
            "section": normalize(number.get_text(" ", strip=True)),
            "source_url": f"{url}#{article['id']}",
            "text": text,
        })
    return result


class GuidelineService:
    def __init__(self, transport=None):
        self.transport = transport
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    async def _get(self, client: httpx.AsyncClient, url: str) -> str:
        for _ in range(3):
            if not official_url(url):
                raise ValueError("Unsupported guideline URL")
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", ""):
                    raise ValueError("Expected official HTML")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 2_000_000:
                        raise ValueError("Guideline page is too large")
                return content.decode("utf-8")
        raise ValueError("Too many redirects")

    async def search(self, query: str) -> list[dict]:
        # Only a generic English clinical term is sent, never patient records or answers.
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ()/'-]{2,99}", query):
            return []
        cached = self._cache.get(query)
        if cached and time.monotonic() - cached[0] < 3600:
            return cached[1]
        async with httpx.AsyncClient(timeout=8, transport=self.transport, follow_redirects=False) as client:
            search_url = str(httpx.URL(f"{ORIGIN}/search", params={"q": query}))
            candidates = parse_search(await self._get(client, search_url))
            responses = await asyncio.gather(*[
                self._get(client, item["url"]) for item in candidates
            ], return_exceptions=True)
            rows = []
            failures = 0
            for candidate, html in zip(candidates, responses):
                if isinstance(html, Exception):
                    failures += 1
                    continue
                rows.extend(parse_guideline(html, candidate["url"], candidate["code"]))
            if failures and not rows:
                raise ValueError("Official sources unavailable")
        terms = set(re.findall(r"[a-z]{3,}", query.lower())) - {"and", "the", "with", "disease"}
        rows.sort(key=lambda row: (
            sum(term in row["text"].lower() for term in terms)
            + sum(term in row["text"].lower() for term in ("diagnos", "assess", "suspect", "confirm"))
        ), reverse=True)
        rows = rows[:8]
        if len(self._cache) >= 64:
            self._cache.pop(next(iter(self._cache)))
        self._cache[query] = (time.monotonic(), rows)
        return rows

    async def annotate(self, report: dict, case: dict, llm) -> None:
        diagnoses = report.get("diagnoses", [])
        if not diagnoses:
            return
        for item in diagnoses:
            item["references"] = []
            item["guideline_status"] = "not_found"
        try:
            results = await asyncio.wait_for(asyncio.gather(*[
                self.search(item.get("guideline_query", "")) for item in diagnoses
            ], return_exceptions=True), timeout=18)
        except asyncio.TimeoutError:
            for item in diagnoses:
                item["guideline_status"] = "unavailable"
            return
        lookup, context = {}, []
        for index, (diagnosis, rows) in enumerate(zip(diagnoses, results)):
            if isinstance(rows, Exception):
                diagnosis["guideline_status"] = "unavailable"
                continue
            for row in rows:
                lookup[(index, row["source_id"])] = row
                context.append({"diagnosis_index": index, **row})
        if not context:
            return
        try:
            linked = await asyncio.wait_for(llm.link_guidelines(case, diagnoses, context), timeout=25)
        except (ClinicalModelError, asyncio.TimeoutError):
            for index, item in enumerate(diagnoses):
                if any(key[0] == index for key in lookup):
                    item["guideline_status"] = "unavailable"
            return
        seen, words = set(), {}
        for citation in linked.citations:
            key = (citation.diagnosis_index, citation.source_id)
            row = lookup.get(key)
            quote = normalize(citation.quote)
            if not row or key in seen or quote not in row["text"] or not 3 <= len(quote.split()) <= 25:
                continue
            page = row["source_url"].split('#')[0]
            if words.get(page, 0) + len(quote.split()) > 25:
                continue
            target = diagnoses[citation.diagnosis_index]
            if len(target["references"]) >= 2:
                continue
            seen.add(key)
            words[page] = words.get(page, 0) + len(quote.split())
            # Display a short exact excerpt; preserve the official section URL for its full context.
            target["references"].append({
                **{k: v for k, v in row.items() if k != "text"},
                "quote": quote, "highlights": [quote],
                "translation": citation.translation,
                "applicability": citation.applicability,
                "limitations": citation.limitations,
                "relation": citation.relation,
            })
            target["guideline_status"] = "matched"
