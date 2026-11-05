"""Cyber Watch backend.

Fetches many RSS/Atom feeds, caches them, sorts every item into categories
(AI Security, Community, Finance, ...), tags it with the countries it mentions,
tracks per-source health, and extracts article text for the in-app reader.

Run:  python app.py   then open the address it prints.
"""
import hashlib
import os
import re
import socket
import threading
import time
import warnings
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from flask import Flask, abort, jsonify, request, send_from_directory
from readability import Document

from feeds import (AI_TERMS, AISEC_SEC_TERMS, CATEGORY_DESC, CATEGORY_LABELS, COMMUNITY_TERMS,
                   COUNTRIES, CVE_PATTERN, CYBER_TERMS, FEEDS, FINANCE_TERMS, SEVERITY_RULES)

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

CACHE_TTL = 600  # seconds between feed refreshes
DEFAULT_PER_FEED = 15
MAX_ITEMS = 1500
MAX_WORKERS = 8                 # fewer parallel requests = fewer timeouts on home connections
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 20
RETRY_READ_TIMEOUT = 40         # second attempt is more patient
RETRY_DELAY = 1.5
ARTICLE_TIMEOUT = 12
ARTICLE_MAX_BYTES = 3_000_000
USER_AGENT = "Mozilla/5.0 (compatible; CyberWatch/1.2; personal RSS reader)"
ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"
TOTAL_SOURCES = sum(len(v) for v in FEEDS.values())

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.json.sort_keys = False  # keep tab order exactly as defined in feeds.py

_lock = threading.Lock()
_cache = {"items": [], "updated": 0.0, "health": {}}
_refreshing = False

# ------------------------------------------------------------ classification
_RE = {
    "ai": re.compile(AI_TERMS, re.I),
    "aisec": re.compile(AISEC_SEC_TERMS, re.I),
    "community": re.compile(COMMUNITY_TERMS, re.I),
    "finance": re.compile(FINANCE_TERMS, re.I),
    "cyber": re.compile(CYBER_TERMS, re.I),
}

_COUNTRY_RE = {
    name: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(k) for k in meta["keywords"]) + r")(?!\w)", re.I)
    for name, meta in COUNTRIES.items()
}


def classify(primary, title, summary):
    """Return a list of categories. The first one is the badge shown in the UI."""
    text = f"{title} {summary}"
    cats = [primary]

    about_ai = primary in ("ai", "aisec") or bool(_RE["ai"].search(text))
    if primary == "aisec":
        pass  # dedicated AI security source, always counts
    elif about_ai and _RE["aisec"].search(text):
        if primary == "ai":
            cats = ["aisec"]  # keep the AI tab for general AI news
        else:
            cats.append("aisec")

    if primary != "community" and _RE["community"].search(text):
        cats.append("community")
    if primary == "community" and _RE["cyber"].search(text):
        cats.append("cyber")
    if primary != "finance" and _RE["finance"].search(text):
        cats.append("finance")

    seen, out = set(), []
    for c in cats:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


_SEV_RULES = [(label, level, re.compile(rx, re.I)) for label, level, rx in SEVERITY_RULES]
_CVE_RE = re.compile(CVE_PATTERN, re.I)


def assess(title, summary):
    """Return (level, badges, cves). level is "urgent", "high" or None."""
    text = f"{title} {summary}"
    badges, level = [], None
    for label, lvl, rx in _SEV_RULES:
        if rx.search(text):
            badges.append({"label": label, "level": lvl})
            if lvl == "urgent" or level is None:
                level = lvl
    cves = list(dict.fromkeys(c.upper() for c in _CVE_RE.findall(text)))[:3]
    return level, badges[:2], cves


def detect_countries(title, summary):
    """Countries mentioned. Headline mentions come first, then summary-only ones."""
    found = []
    for text in (title, summary):
        hits = []
        for name, pat in _COUNTRY_RE.items():
            m = pat.search(text)
            if m:
                hits.append((m.start(), name))
        for _, name in sorted(hits):
            if name not in found:
                found.append(name)
    return found


# ------------------------------------------------------------------ fetching
def _strip_html(text):
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _entry_time(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    return timegm(parsed) if parsed else 0


def _short_error(exc):
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, requests.Timeout):
        return "Timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "SSL error"
    if isinstance(exc, requests.ConnectionError):
        return "Connection failed"
    return type(exc).__name__


def _retryable(exc):
    """Timeouts, dropped connections and server-side errors are worth a second try."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return False


def _fetch_feed(category, feed, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)):
    started = time.time()
    resp = requests.get(feed["url"], headers={"User-Agent": USER_AGENT, "Accept": ACCEPT}, timeout=timeout)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    limit = feed.get("limit", DEFAULT_PER_FEED)
    items = []
    for e in parsed.entries[:limit]:
        link = e.get("link")
        title = _strip_html(e.get("title", "")).strip()
        # Only plain web links are allowed (blocks javascript:, data: and file: links from a hostile feed).
        if not link or not link.lower().startswith(("http://", "https://")) or not title:
            continue
        summary = _strip_html(e.get("summary", ""))[:500]
        cats = classify(category, title, summary)
        level, badges, cves = assess(title, summary)
        items.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:16],
            "title": title,
            "link": link,
            "summary": summary,
            "source": feed["name"],
            "official": bool(feed.get("official")),
            "category": cats[0],
            "categories": cats,
            "ts": _entry_time(e),
            "countries": detect_countries(title, summary),
            "severity": level,
            "badges": badges,
            "cves": cves,
        })
    return items, int((time.time() - started) * 1000)


def _fetch_with_retry(category, feed):
    try:
        return _fetch_feed(category, feed, (CONNECT_TIMEOUT, READ_TIMEOUT))
    except Exception as exc:
        if not _retryable(exc):
            raise
        time.sleep(RETRY_DELAY)
        return _fetch_feed(category, feed, (CONNECT_TIMEOUT + 4, RETRY_READ_TIMEOUT))


def _publish(items, health, final=False):
    now = time.time()
    seen, unique = set(), []
    for it in sorted(items, key=lambda i: i["ts"], reverse=True):
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        if it["ts"] > now + 3600:  # clamp future-dated items
            it["ts"] = int(now)
        unique.append(it)
    with _lock:
        _cache["items"] = unique[:MAX_ITEMS]
        _cache["health"] = dict(health)
        if final:
            _cache["updated"] = time.time()


def _do_refresh():
    global _refreshing
    try:
        # First load: show stories as sources arrive. Later refreshes swap in at the end
        # so the list never shrinks while it is working.
        progressive = not _cache["items"]
        jobs = [(cat, f) for cat, feeds in FEEDS.items() for f in feeds]
        items, health = [], {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_with_retry, cat, f): (cat, f) for cat, f in jobs}
            for fut in as_completed(futures):
                cat, f = futures[fut]
                try:
                    got, ms = fut.result()
                    if got:
                        health[f["name"]] = {"ok": True, "count": len(got), "ms": ms, "category": cat}
                        items.extend(got)
                    else:
                        health[f["name"]] = {"ok": False, "error": "Empty or invalid feed",
                                             "count": 0, "ms": ms, "category": cat}
                except Exception as exc:  # one bad feed must not break the rest
                    health[f["name"]] = {"ok": False, "error": _short_error(exc), "count": 0, "category": cat}
                if progressive:
                    _publish(items, health)
        _publish(items, health, final=True)
    finally:
        with _lock:
            _refreshing = False


def start_refresh():
    """Start a background refresh unless one is already running."""
    global _refreshing
    with _lock:
        if _refreshing:
            return False
        _refreshing = True
    threading.Thread(target=_do_refresh, daemon=True).start()
    return True


def _ensure_fresh():
    if time.time() - _cache["updated"] > CACHE_TTL:
        start_refresh()


# -------------------------------------------------------------------- routes
@app.after_request
def _headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "media-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    return resp


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/news")
def api_news():
    _ensure_fresh()
    category = request.args.get("category", "all")
    with _lock:
        items = list(_cache["items"])
        updated = _cache["updated"]
        health = dict(_cache["health"])
        refreshing = _refreshing
    if category not in ("all", "map"):
        items = [i for i in items if category in i["categories"]]
    return jsonify({
        "items": items,
        "updated": datetime.fromtimestamp(updated, timezone.utc).isoformat() if updated else None,
        "refreshing": refreshing,
        "total_sources": TOTAL_SOURCES,
        "health": health,
        "labels": CATEGORY_LABELS,
        "desc": CATEGORY_DESC,
        "countries": [{"name": n, "iso": m["iso"], "flag": m["flag"], "lat": m["lat"], "lon": m["lon"]}
                      for n, m in COUNTRIES.items()],
    })


@app.post("/api/refresh")
def api_refresh():
    return jsonify({"started": start_refresh()})


@app.get("/api/article/<item_id>")
def api_article(item_id):
    """Extract readable text for the in-app reader.

    Only URLs that came from our own feed cache can be fetched. This stops the
    endpoint being used as an open proxy (SSRF). Output is plain text
    paragraphs, never HTML, so the frontend cannot be tricked into running
    scripts from a third party page.
    """
    with _lock:
        item = next((i for i in _cache["items"] if i["id"] == item_id), None)
    if not item:
        abort(404)
    parts = urlparse(item["link"])
    if parts.scheme not in ("http", "https"):
        abort(400)
    result = {"id": item["id"], "title": item["title"], "link": item["link"],
              "source": item["source"], "paragraphs": [], "fallback": False}
    try:
        with requests.get(item["link"], headers={"User-Agent": USER_AGENT}, timeout=ARTICLE_TIMEOUT,
                          stream=True) as r:
            r.raise_for_status()
            body = r.raw.read(ARTICLE_MAX_BYTES, decode_content=True)
            encoding = r.encoding or "utf-8"
        html = body.decode(encoding, errors="replace")
        content = Document(html).summary(html_partial=True)
        soup = BeautifulSoup(content, "html.parser")
        paras = [t.get_text(" ", strip=True) for t in soup.find_all(["p", "h2", "h3", "li"])]
        result["paragraphs"] = [p for p in paras if len(p) > 25][:60]
    except Exception:
        pass
    if not result["paragraphs"]:
        # Many sites block scraping. Fall back to the feed summary.
        result["fallback"] = True
        result["paragraphs"] = [item["summary"]] if item["summary"] else []
    return jsonify(result)


def _pick_port():
    """Use PORT from the environment if set, else the first free port from a list.

    Windows often blocks or reserves 5000, so we test-bind before starting.
    """
    if os.environ.get("PORT"):
        return int(os.environ["PORT"])
    for port in (5000, 5050, 8000, 8080, 8765, 9000):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise SystemExit("No free port found. Set one yourself, for example: set PORT=8123")


if __name__ == "__main__":
    port = _pick_port()
    print(f"\n  Cyber Watch running. Open http://127.0.0.1:{port}\n")
    start_refresh()
    app.run(host="127.0.0.1", port=port, debug=False)
