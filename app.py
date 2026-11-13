"""Cyber Watch backend.

Fetches many RSS/Atom feeds, caches them, sorts every item into categories
(AI Security, Community, Finance, ...), tags it with the countries it mentions,
tracks per-source health, and extracts article text for the in-app reader.

Run:  python app.py   then open the address it prints.
"""
import gzip
import hashlib
import ipaddress
import os
import re
import socket
import threading
import time
import warnings
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from flask import Flask, Response, abort, g, jsonify, request, send_from_directory
from flask_limiter import Limiter
from readability import Document

from feeds import (AI_TERMS, AISEC_SEC_TERMS, CATEGORY_DESC, CATEGORY_LABELS, COMMUNITY_TERMS,
                   COUNTRIES, CVE_PATTERN, CYBER_TERMS, FEEDS, FINANCE_TERMS, SEVERITY_RULES)

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

CACHE_TTL = int(os.environ.get("REFRESH_SECS", 600))  # seconds between feed refreshes
MIN_RETRY_SECS = 60  # a failed refresh is not retried more often than this
DEFAULT_PER_FEED = 15
MAX_ITEMS = 1500
MAX_WORKERS = 8                 # fewer parallel requests = fewer timeouts on home connections
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 20
RETRY_READ_TIMEOUT = 40         # second attempt is more patient
RETRY_DELAY = 1.5
ARTICLE_TIMEOUT = 6              # connect/read timeout per socket operation
ARTICLE_DEADLINE = 10            # hard limit for the whole download, in seconds
ARTICLE_MAX_BYTES = 1_500_000
ARTICLE_CACHE_MAX = 200
ARTICLE_CACHE_OK_SECS = 6 * 3600
ARTICLE_CACHE_FALLBACK_SECS = 300
# --- abuse protection and hardening
TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", 1))  # proxies in front of the app that append to X-Forwarded-For
LIMIT_NEWS = "60 per minute"
LIMIT_ARTICLE = "20 per minute;200 per hour"
LIMIT_REFRESH = "3 per 10 minutes"
REFRESH_COOLDOWN_SECS = 60       # site-wide: no manual refresh right after any refresh attempt
ARTICLE_MAX_CONCURRENT = 3       # simultaneous article downloads, so slow sites cannot use every thread
ARTICLE_QUEUE_WAIT = 2           # seconds a request waits for a free download slot
MAX_REDIRECTS = 3
ALLOWED_PORTS = {None, 80, 443}
ALLOW_PRIVATE_FETCH = os.environ.get("CYBERWATCH_ALLOW_PRIVATE") == "1"  # tests only
NEWS_CACHE_SECS = 2
USER_AGENT = "Mozilla/5.0 (compatible; CyberWatch/1.2; personal RSS reader)"
ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"
TOTAL_SOURCES = sum(len(v) for v in FEEDS.values())

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.json.sort_keys = False  # keep tab order exactly as defined in feeds.py
app.config["RATELIMIT_HEADERS_ENABLED"] = True


def client_ip():
    """The visitor's address, for rate limiting.

    Behind a proxy every connection looks like it comes from the proxy. The proxy appends the
    real address to X-Forwarded-For, so we take the entry that many trusted proxies from the end.
    Anything a visitor writes into that header sits earlier in the list and is ignored.
    """
    parts = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
    if TRUSTED_PROXIES > 0 and len(parts) >= TRUSTED_PROXIES:
        return parts[-TRUSTED_PROXIES]
    return request.remote_addr or "unknown"


@app.after_request
def _own_retry_after(resp):
    # Registered before the limiter, so it runs after the limiter's own header injection, which
    # would otherwise overwrite a view's Retry-After with the rate-limit window.
    wait = getattr(g, "retry_after", None)
    if wait is not None:
        resp.headers["Retry-After"] = str(wait)
    return resp


limiter = Limiter(client_ip, app=app, storage_uri="memory://", default_limits=[])

_lock = threading.Lock()
_cache = {"items": [], "updated": 0.0, "health": {}}
_refreshing = False
_last_attempt = 0.0
_scheduler_started = False
_news_cache = {}
_news_lock = threading.Lock()
_article_slots = threading.BoundedSemaphore(ARTICLE_MAX_CONCURRENT)

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


def _invalidate_news():
    with _news_lock:
        _news_cache.clear()


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
    _invalidate_news()


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
        if items or not _cache["items"]:
            _publish(items, health, final=True)
        else:
            # Every feed failed (for example a network blip). Keep the stories we already
            # have and record why, instead of replacing the page with nothing.
            with _lock:
                _cache["health"] = dict(health)
            _invalidate_news()
    finally:
        with _lock:
            _refreshing = False
        _invalidate_news()


def start_refresh():
    """Start a background refresh unless one is already running."""
    global _refreshing, _last_attempt
    with _lock:
        if _refreshing:
            return False
        _refreshing = True
        _last_attempt = time.time()
    _invalidate_news()
    threading.Thread(target=_do_refresh, daemon=True).start()
    return True


def _ensure_fresh():
    """Safety net: if the timer below somehow missed, a visit still triggers a refresh."""
    now = time.time()
    if now - _cache["updated"] > CACHE_TTL and now - _last_attempt > MIN_RETRY_SECS:
        start_refresh()


def _scheduler_loop():
    while True:
        try:
            start_refresh()
        except Exception:  # noqa: BLE001  the timer must never die
            pass
        time.sleep(CACHE_TTL)


def start_scheduler():
    """Refresh the feeds on a timer, so visitors always find recent stories.

    Runs once per process. Set CYBERWATCH_NO_SCHEDULER=1 to turn it off (used by tests).
    """
    global _scheduler_started
    if os.environ.get("CYBERWATCH_NO_SCHEDULER") == "1":
        return False
    with _lock:
        if _scheduler_started:
            return False
        _scheduler_started = True
    threading.Thread(target=_scheduler_loop, name="feed-scheduler", daemon=True).start()
    return True


start_scheduler()


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
    if request.is_secure or request.headers.get("X-Forwarded-Proto", "") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resp


@app.errorhandler(429)
def _too_many(_e):
    resp = jsonify({"error": "rate_limited", "message": "Too many requests. Please slow down a little."})
    resp.status_code = 429
    return resp


@app.get("/healthz")
def healthz():
    """Cheap liveness check for the host and uptime monitors. Never touches the network."""
    with _lock:
        stories, updated = len(_cache["items"]), _cache["updated"]
    resp = jsonify({"ok": True, "stories": stories, "updated": updated or None})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


def _news_payload(category):
    with _lock:
        items = list(_cache["items"])
        updated = _cache["updated"]
        health = dict(_cache["health"])
        refreshing = _refreshing
    if category not in ("all", "map"):
        items = [i for i in items if category in i["categories"]]
    return {
        "items": items,
        "updated": datetime.fromtimestamp(updated, timezone.utc).isoformat() if updated else None,
        "refreshing": refreshing,
        "total_sources": TOTAL_SOURCES,
        "health": health,
        "labels": CATEGORY_LABELS,
        "desc": CATEGORY_DESC,
        "countries": [{"name": n, "iso": m["iso"], "flag": m["flag"], "lat": m["lat"], "lon": m["lon"]}
                      for n, m in COUNTRIES.items()],
    }


def _news_body(category, want_gzip):
    """JSON for /api/news, built once per couple of seconds and compressed on demand."""
    known = category in ("all", "map") or category in CATEGORY_LABELS
    now = time.time()
    hit = None
    if known:
        with _news_lock:
            entry = _news_cache.get(category)
            if entry and entry["exp"] > now:
                hit = entry
    if hit is None:
        hit = {"exp": now + NEWS_CACHE_SECS, "raw": app.json.dumps(_news_payload(category)).encode("utf-8"), "gz": None}
        if known:
            with _news_lock:
                _news_cache[category] = hit
    if want_gzip:
        if hit["gz"] is None:
            hit["gz"] = gzip.compress(hit["raw"], 5)
        return hit["gz"], True
    return hit["raw"], False


@app.get("/api/news")
@limiter.limit(lambda: LIMIT_NEWS)
def api_news():
    _ensure_fresh()
    category = request.args.get("category", "all")
    body, zipped = _news_body(category, "gzip" in request.headers.get("Accept-Encoding", ""))
    resp = Response(body, mimetype="application/json")
    resp.headers["Vary"] = "Accept-Encoding"
    if zipped:
        resp.headers["Content-Encoding"] = "gzip"
    return resp


@app.post("/api/refresh")
@limiter.limit(lambda: LIMIT_REFRESH)
def api_refresh():
    # One shared cooldown for everybody: refreshing re-downloads every feed, so it must not
    # be repeatable on demand. The timer already refreshes on its own every few minutes.
    if time.time() - _last_attempt < REFRESH_COOLDOWN_SECS:
        return jsonify({"started": False, "reason": "cooldown"})
    return jsonify({"started": start_refresh()})


# ---- safe downloading for the in-app reader
def _host_is_public(host):
    """True only if every address the host name resolves to is a normal public internet address."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return False
    return True


def _url_allowed(url):
    try:
        parts = urlparse(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return False
    if ALLOW_PRIVATE_FETCH:
        return True
    return port in ALLOWED_PORTS and _host_is_public(parts.hostname)


def _download_limited(url):
    """Download a page with a hard total time limit, even if the site trickles data.

    The download runs in a helper thread. If it is still going after
    ARTICLE_DEADLINE seconds, the caller stops waiting and falls back to the
    feed summary. The helper thread ends itself at its next chunk.
    """
    box = {"chunks": [], "err": None, "resp": None, "encoding": "utf-8"}

    def work():
        try:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                # Every hop is checked, so a redirect cannot lead the server to an internal address.
                if not _url_allowed(current):
                    raise ValueError("blocked address")
                r = requests.get(current, headers={"User-Agent": USER_AGENT}, timeout=ARTICLE_TIMEOUT,
                                 stream=True, allow_redirects=False)
                box["resp"] = r
                if r.is_redirect and r.headers.get("Location"):
                    current = urljoin(current, r.headers["Location"])
                    r.close()
                    continue
                with r:
                    r.raise_for_status()
                    box["encoding"] = r.encoding or "utf-8"
                    size = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        box["chunks"].append(chunk)
                        size += len(chunk)
                        if size >= ARTICLE_MAX_BYTES or box.get("stop"):
                            break
                return
            raise ValueError("too many redirects")
        except Exception as e:  # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(ARTICLE_DEADLINE)
    if t.is_alive():
        box["stop"] = True  # the helper thread gives up at its next chunk
        raise TimeoutError("article download too slow")
    if box["err"]:
        raise box["err"]
    return b"".join(box["chunks"]).decode(box["encoding"], errors="replace")


_article_cache = OrderedDict()
_article_lock = threading.Lock()


@app.get("/api/article/<item_id>")
@limiter.limit(lambda: LIMIT_ARTICLE)
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
    now = time.time()
    with _article_lock:
        hit = _article_cache.get(item_id)
        if hit and hit[0] > now:
            _article_cache.move_to_end(item_id)
            return jsonify(hit[1])
    result = {"id": item["id"], "title": item["title"], "link": item["link"],
              "source": item["source"], "paragraphs": [], "fallback": False}
    if not _article_slots.acquire(timeout=ARTICLE_QUEUE_WAIT):
        resp = jsonify({"error": "busy", "message": "The reader is busy. Try again in a few seconds."})
        resp.status_code = 503
        g.retry_after = 5
        return resp
    try:
        html = _download_limited(item["link"])
        content = Document(html).summary(html_partial=True)
        soup = BeautifulSoup(content, "html.parser")
        paras = [t.get_text(" ", strip=True) for t in soup.find_all(["p", "h2", "h3", "li"])]
        result["paragraphs"] = [p for p in paras if len(p) > 25][:60]
    except Exception:
        pass
    finally:
        _article_slots.release()
    if not result["paragraphs"]:
        # Many sites block scraping. Fall back to the feed summary.
        result["fallback"] = True
        result["paragraphs"] = [item["summary"]] if item["summary"] else []
    ttl = ARTICLE_CACHE_FALLBACK_SECS if result["fallback"] else ARTICLE_CACHE_OK_SECS
    with _article_lock:
        _article_cache[item_id] = (time.time() + ttl, result)
        while len(_article_cache) > ARTICLE_CACHE_MAX:
            _article_cache.popitem(last=False)
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
    app.run(host="127.0.0.1", port=port, debug=False)
