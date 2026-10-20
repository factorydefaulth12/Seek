import os
import re
import json
import time
import socket
import ipaddress
import threading
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Header, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_NAME = "Seek Search API"
DB_PATH = os.getenv("SEEK_DB_PATH", "./seek.db")
CRAWL_TOKEN = os.getenv("SEEK_CRAWL_TOKEN", "")
USER_AGENT = "SeekBot/0.1 (+https://github.com/factorydefaulth12/Seek; respectful public-web indexing)"
MAX_HTML_BYTES = 1_500_000
MAX_TEXT_CHARS = 30_000
DOMAIN_DELAY_SECONDS = float(os.getenv("SEEK_DOMAIN_DELAY", "1.0"))
CRAWL_LOCK = threading.Lock()
STATUS_LOCK = threading.Lock()
CRAWL_STATUS = {"running": False, "started_at": None, "finished_at": None, "pages_indexed": 0, "error": None}

SEEDS = [
    "https://www.wikipedia.org/", "https://en.wikipedia.org/wiki/Main_Page",
    "https://www.britannica.com/", "https://www.nationalgeographic.com/",
    "https://www.nasa.gov/", "https://www.noaa.gov/", "https://www.science.org/",
    "https://www.scientificamerican.com/", "https://www.bbc.com/", "https://www.reuters.com/",
    "https://apnews.com/", "https://www.theguardian.com/international",
    "https://www.aljazeera.com/", "https://www.dw.com/", "https://www.voanews.com/",
    "https://www.npr.org/", "https://www.pbs.org/", "https://www.cbc.ca/",
    "https://www.nytimes.com/", "https://www.washingtonpost.com/",
    "https://www.mozilla.org/", "https://developer.mozilla.org/", "https://www.python.org/",
    "https://docs.python.org/3/", "https://developer.chrome.com/", "https://web.dev/",
    "https://www.w3.org/", "https://www.rfc-editor.org/", "https://stackoverflow.com/",
    "https://github.com/explore", "https://git-scm.com/doc",
    "https://www.khanacademy.org/", "https://openstax.org/", "https://www.coursera.org/",
    "https://ocw.mit.edu/", "https://www.edx.org/", "https://www.un.org/",
    "https://www.who.int/", "https://data.worldbank.org/", "https://www.unesco.org/",
    "https://www.loc.gov/", "https://www.si.edu/", "https://www.metmuseum.org/",
    "https://www.gutenberg.org/", "https://standardebooks.org/", "https://archive.org/",
    "https://www.poetryfoundation.org/", "https://www.goodreads.com/",
    "https://www.imdb.com/", "https://www.letterboxd.com/", "https://www.commonsensemedia.org/",
    "https://www.allrecipes.com/", "https://www.seriouseats.com/", "https://www.bbcgoodfood.com/",
    "https://www.health.harvard.edu/", "https://medlineplus.gov/",
    "https://www.energy.gov/", "https://www.nist.gov/", "https://www.eff.org/",
    "https://www.consumerreports.org/", "https://www.investopedia.com/",
    "https://www.nigerianstat.gov.ng/", "https://www.britishcouncil.org/",
    "https://www.africanews.com/", "https://techcrunch.com/", "https://arstechnica.com/",
    "https://www.theverge.com/", "https://www.wired.com/", "https://www.polygon.com/",
    "https://www.fandom.com/", "https://archiveofourown.org/", "https://www.webtoons.com/",
]

app = FastAPI(title=APP_NAME, version="0.1.0", description="Seek's own crawler-backed search index. Coverage is limited to pages Seek has discovered and indexed.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def connect_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=20000")
    return db

def init_db():
    with connect_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS pages (
            url TEXT PRIMARY KEY, canonical_url TEXT, title TEXT, description TEXT,
            body TEXT, domain TEXT, status_code INTEGER, indexed_at TEXT,
            content_hash TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain)")
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            url UNINDEXED, title, description, body, content='pages', content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        )""")
        # Rebuild triggers keep the full-text index in sync with page inserts/updates/deletes.
        db.executescript("""
        CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
          INSERT INTO pages_fts(rowid,url,title,description,body) VALUES(new.rowid,new.url,new.title,new.description,new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
          INSERT INTO pages_fts(pages_fts,rowid,url,title,description,body) VALUES('delete',old.rowid,old.url,old.title,old.description,old.body);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
          INSERT INTO pages_fts(pages_fts,rowid,url,title,description,body) VALUES('delete',old.rowid,old.url,old.title,old.description,old.body);
          INSERT INTO pages_fts(rowid,url,title,description,body) VALUES(new.rowid,new.url,new.title,new.description,new.body);
        END;
        """)
        # Repair the index if a previous deployment interrupted its initial setup.
        count = db.execute("SELECT count(*) FROM pages").fetchone()[0]
        fts_count = db.execute("SELECT count(*) FROM pages_fts").fetchone()[0]
        if count and not fts_count:
            db.execute("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')")

init_db()

def normalize_url(url):
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return None
        if p.username or p.password or (p.port and p.port not in (80, 443)):
            return None
        host = p.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".local", ".internal")):
            return None
        # Prevent SSRF into private, loopback, link-local, multicast, and reserved addresses.
        try:
            ip = ipaddress.ip_address(host)
            if not ip.is_global:
                return None
        except ValueError:
            try:
                infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
                if not infos:
                    return None
                for info in infos:
                    addr = ipaddress.ip_address(info[4][0])
                    if not addr.is_global:
                        return None
            except (socket.gaierror, OSError):
                return None
        path = p.path or "/"
        clean = urlunparse((p.scheme, p.netloc.lower(), path, "", p.query, ""))
        return urldefrag(clean)[0]
    except (ValueError, TypeError):
        return None

def get_domain(url):
    return (urlparse(url).hostname or "").lower()

def is_probably_html(response):
    ctype = response.headers.get("content-type", "").lower()
    return "text/html" in ctype or "application/xhtml+xml" in ctype

def extract_page(url, html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe", "form", "nav", "footer"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    description = desc_tag.get("content", "").strip() if desc_tag else ""
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical_url = urljoin(url, canonical.get("href", "")) if canonical and canonical.get("href") else url
    body = " ".join(soup.get_text(" ", strip=True).split())[:MAX_TEXT_CHARS]
    links = []
    for a in soup.find_all("a", href=True):
        target = normalize_url(urljoin(url, a["href"]))
        if target and get_domain(target) and target not in links:
            links.append(target)
        if len(links) >= 100:
            break
    return title[:500] or url, description[:1500], body, canonical_url[:2000], links

def robots_allowed(client, url, cache):
    p = urlparse(url)
    origin = f"{p.scheme}://{p.netloc}"
    if origin not in cache:
        robots_url = origin + "/robots.txt"
        try:
            resp = client.get(robots_url, follow_redirects=False, timeout=8)
            if resp.status_code == 200:
                from urllib.robotparser import RobotFileParser
                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(resp.text[:200_000].splitlines())
                cache[origin] = parser
            elif resp.status_code in (401, 403):
                cache[origin] = False
            else:
                cache[origin] = None
        except Exception:
            # If robots.txt cannot be reached, skip this origin rather than guessing.
            cache[origin] = False
    parser = cache[origin]
    return True if parser is None else bool(parser and parser.can_fetch(USER_AGENT, url))

def save_page(url, title, description, body, status, canonical):
    import hashlib
    digest = hashlib.sha256((title + "\n" + description + "\n" + body).encode("utf-8", "ignore")).hexdigest()
    with connect_db() as db:
        db.execute("""INSERT INTO pages(url,canonical_url,title,description,body,domain,status_code,indexed_at,content_hash)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(url) DO UPDATE SET canonical_url=excluded.canonical_url,title=excluded.title,
        description=excluded.description,body=excluded.body,status_code=excluded.status_code,
        indexed_at=excluded.indexed_at,content_hash=excluded.content_hash""",
        (url, canonical, title, description, body, get_domain(url), status, datetime.now(timezone.utc).isoformat(), digest))

def crawl_worker(max_pages=80, extra_seeds=None):
    with STATUS_LOCK:
        CRAWL_STATUS.update({"running": True, "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None, "pages_indexed": 0, "error": None})
    indexed = 0
    queue = list(dict.fromkeys(SEEDS + (extra_seeds or [])))
    seen = set()
    robots_cache = {}
    last_hit = {}
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}, follow_redirects=False, timeout=12) as client:
            while queue and indexed < max(1, min(int(max_pages), 200)):
                raw = queue.pop(0)
                url = normalize_url(raw)
                if not url or url in seen:
                    continue
                seen.add(url)
                domain = get_domain(url)
                if not robots_allowed(client, url, robots_cache):
                    continue
                wait = DOMAIN_DELAY_SECONDS - (time.time() - last_hit.get(domain, 0))
                if wait > 0:
                    time.sleep(min(wait, 3))
                try:
                    response = client.get(url, timeout=12)
                    last_hit[domain] = time.time()
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if location:
                            target = normalize_url(urljoin(url, location))
                            if target and target not in seen:
                                queue.append(target)
                        continue
                    if response.status_code != 200 or not is_probably_html(response):
                        continue
                    if len(response.content) > MAX_HTML_BYTES:
                        continue
                    title, desc, body, canonical, links = extract_page(str(response.url), response.text)
                    if not body and not title:
                        continue
                    save_page(str(response.url), title, desc, body, response.status_code, canonical)
                    indexed += 1
                    # Prioritize links from this page but bound the frontier to keep a crawl run finite.
                    for link in links:
                        if link not in seen and len(queue) < 3000:
                            queue.append(link)
                except (httpx.HTTPError, UnicodeError, ValueError):
                    continue
        with STATUS_LOCK:
            CRAWL_STATUS["pages_indexed"] = indexed
            CRAWL_STATUS["finished_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        with STATUS_LOCK:
            CRAWL_STATUS["error"] = str(exc)[:500]
            CRAWL_STATUS["finished_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        with STATUS_LOCK:
            CRAWL_STATUS["running"] = False
        CRAWL_LOCK.release()

class CrawlRequest(BaseModel):
    max_pages: int = Field(default=80, ge=1, le=200)
    seed_urls: list[str] = Field(default_factory=list, max_length=50)

@app.get("/")
def root():
    return {"service": APP_NAME, "status": "online", "docs": "/docs", "search": "/search?q=example"}

@app.get("/health")
def health():
    with connect_db() as db:
        count = db.execute("SELECT count(*) FROM pages").fetchone()[0]
    return {"ok": True, "service": APP_NAME, "indexed_pages": count, "index_type": "Seek-owned SQLite FTS5 index"}

@app.get("/stats")
def stats():
    with connect_db() as db:
        pages = db.execute("SELECT count(*) FROM pages").fetchone()[0]
        domains = db.execute("SELECT count(DISTINCT domain) FROM pages").fetchone()[0]
        updated = db.execute("SELECT max(indexed_at) FROM pages").fetchone()[0]
    with STATUS_LOCK:
        status = dict(CRAWL_STATUS)
    return {"indexed_pages": pages, "indexed_domains": domains, "last_indexed_at": updated, "crawler": status, "coverage_note": "Results only include public pages Seek has discovered and indexed; this is not a complete copy of the web."}

@app.get("/search")
def search(q: str = Query(..., min_length=1, max_length=300), limit: int = Query(default=10, ge=1, le=30)):
    terms = re.findall(r"[\w]{2,}", q.lower(), flags=re.UNICODE)[:12]
    if not terms:
        return {"query": q, "results": [], "total": 0, "source": "Seek's own index"}
    # Build a safe FTS expression from tokens, never pass raw user syntax into MATCH.
    expression = " AND ".join('"' + t.replace('"', '""') + '"*' for t in terms)
    try:
        with connect_db() as db:
            rows = db.execute("""SELECT p.url,p.title,p.description,p.body,p.domain,p.indexed_at,
                bm25(pages_fts, 0.0, 8.0, 4.0, 1.0) AS score
                FROM pages_fts JOIN pages p ON p.rowid=pages_fts.rowid
                WHERE pages_fts MATCH ?
                ORDER BY score LIMIT ?""", (expression, limit)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    results = []
    for row in rows:
        body = row["body"] or ""
        terms_for_snippet = [t for t in terms if t in body.lower()]
        snippet = row["description"] or body[:320]
        if terms_for_snippet and not row["description"]:
            low = body.lower()
            pos = min([low.find(t) for t in terms_for_snippet if low.find(t) >= 0] or [0])
            snippet = ("…" if pos > 70 else "") + body[max(0, pos-70):pos+250].strip() + ("…" if pos+250 < len(body) else "")
        results.append({"title": row["title"] or row["url"], "url": row["url"], "snippet": snippet[:420], "domain": row["domain"], "indexed_at": row["indexed_at"]})
    return {"query": q, "results": results, "total": len(results), "source": "Seek's own index", "coverage_note": "These are results from pages Seek has crawled. Missing results do not mean a page does not exist."}

@app.get("/admin/status")
def admin_status():
    with STATUS_LOCK:
        return dict(CRAWL_STATUS)

@app.post("/admin/crawl", status_code=202)
def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks, authorization: str | None = Header(default=None)):
    if not CRAWL_TOKEN or authorization != "Bearer " + CRAWL_TOKEN:
        raise HTTPException(status_code=401, detail="A valid SEEK_CRAWL_TOKEN bearer token is required.")
    if not CRAWL_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A crawl is already running.")
    seeds = []
    for raw in request.seed_urls:
        normalized = normalize_url(raw)
        if normalized:
            seeds.append(normalized)
    background_tasks.add_task(crawl_worker, request.max_pages, seeds)
    return {"accepted": True, "message": "Crawl queued. Check GET /stats for progress.", "max_pages": request.max_pages}
