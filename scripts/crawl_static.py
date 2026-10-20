#!/usr/bin/env python3
"""Incremental, robots-aware crawler that builds a static Seek search index for GitHub Pages."""
import ipaddress
import json
import os
import re
import socket
import time
from collections import deque
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "seek-index.json"
FRONTIER_PATH = ROOT / "seek-frontier.json"
USER_AGENT = "SeekBot/0.2 (+https://github.com/factorydefaulth12/Seek; respectful public-web indexing)"
MAX_PAGES = max(1, min(int(os.getenv("MAX_PAGES", "500")), 500))
MAX_PROCESSED = MAX_PAGES * 5
MAX_BYTES = 1_000_000
MAX_DOCS = 10000
TEXT_LIMIT = 1800
DELAY = 1.0
SEEDS = [
    "https://en.wikipedia.org/wiki/Main_Page",
    "https://www.britannica.com/",
    "https://www.nasa.gov/",
    "https://www.noaa.gov/",
    "https://www.science.org/",
    "https://www.nature.com/",
    "https://www.nationalgeographic.com/",
    "https://www.khanacademy.org/",
    "https://www.openstreetmap.org/",
    "https://www.python.org/",
    "https://developer.mozilla.org/",
    "https://www.w3.org/",
    "https://www.loc.gov/",
    "https://www.si.edu/",
    "https://www.metmuseum.org/",
    "https://www.poetryfoundation.org/",
    "https://www.gutenberg.org/",
    "https://www.un.org/",
    "https://www.who.int/",
    "https://www.unesco.org/",
    "https://www.npr.org/",
    "https://www.theguardian.com/international",
    "https://arxiv.org/",
    "https://www.eff.org/",
    "https://www.nigerianstat.gov.ng/",
]

def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback

def normalize(raw, base=None):
    if not raw:
        return None
    url = urljoin(base, raw) if base else raw
    url, _ = urldefrag(url.strip())
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.lower()
        if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
            return None
        try:
            ip = ipaddress.ip_address(host)
            if not ip.is_global:
                return None
        except ValueError:
            pass
        path = p.path or "/"
        if any(path.lower().endswith(ext) for ext in (
            ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip",
            ".gz", ".mp4", ".mp3", ".woff", ".woff2", ".css", ".js", ".xml",
        )):
            return None
        return p._replace(fragment="", query="", path=path).geturl()
    except ValueError:
        return None

def public_host(url):
    host = urlparse(url).hostname or ""
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        try:
            addresses = socket.getaddrinfo(host, urlparse(url).port or (443 if url.startswith("https:") else 80), type=socket.SOCK_STREAM)
            return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
        except (socket.gaierror, OSError, ValueError):
            return False

def main():
    old = load_json(INDEX_PATH, {"version": 1, "updated_at": None, "coverage_note": "", "results": []})
    docs = {d.get("url"): d for d in old.get("results", []) if d.get("url")}
    frontier_data = load_json(FRONTIER_PATH, {"pending": SEEDS, "seen": []})
    seen = set(frontier_data.get("seen", [])) | set(docs)
    queue = deque()
    queued = set()
    # Pending URLs are already in seen by design; re-queue them after workflow restarts.
    for item in frontier_data.get("pending", []):
        url = normalize(item)
        if url and url not in queued:
            queued.add(url)
            seen.add(url)
            queue.append(url)
    for item in SEEDS:
        url = normalize(item)
        if url and url not in seen and url not in queued:
            queued.add(url)
            seen.add(url)
            queue.append(url)
    robots_cache = {}
    host_last = {}
    indexed_now = 0
    processed = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}, timeout=12, follow_redirects=False) as client:
        while queue and indexed_now < MAX_PAGES and processed < MAX_PROCESSED:
            url = queue.popleft()
            processed += 1
            if not public_host(url):
                continue
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in robots_cache:
                try:
                    rr = client.get(origin + "/robots.txt")
                    if rr.status_code == 404:
                        robots_cache[origin] = RobotFileParser()
                        robots_cache[origin].parse([])
                    elif rr.status_code == 200:
                        rp = RobotFileParser()
                        rp.set_url(origin + "/robots.txt")
                        rp.parse(rr.text.splitlines())
                        robots_cache[origin] = rp
                    else:
                        robots_cache[origin] = False
                except httpx.HTTPError:
                    robots_cache[origin] = False
            rp = robots_cache[origin]
            if not rp or not rp.can_fetch(USER_AGENT, url):
                continue
            delay = DELAY - (time.time() - host_last.get(origin, 0))
            if delay > 0:
                time.sleep(delay)
            try:
                response = client.get(url)
                host_last[origin] = time.time()
                if response.status_code in (301, 302, 303, 307, 308):
                    target = normalize(response.headers.get("location", ""), url)
                    if target and target not in seen:
                        seen.add(target)
                        queue.append(target)
                    continue
                if response.status_code != 200 or "text/html" not in response.headers.get("content-type", "").lower() or len(response.content) > MAX_BYTES:
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
                    tag.decompose()
                title = unescape((soup.title.get_text(" ", strip=True) if soup.title else "")[:250])
                description = ""
                meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
                if meta and meta.get("content"):
                    description = meta["content"].strip()[:400]
                text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
                if not title and not text:
                    continue
                links = []
                for a in soup.find_all("a", href=True):
                    candidate = normalize(a.get("href"), str(response.url))
                    if candidate and candidate not in seen:
                        seen.add(candidate)
                        links.append(candidate)
                        if len(links) >= 500:
                            break
                docs[str(response.url)] = {
                    "url": str(response.url),
                    "domain": urlparse(str(response.url)).hostname or "",
                    "title": title or str(response.url),
                    "snippet": description or text[:TEXT_LIMIT],
                    "text": text[:TEXT_LIMIT],
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                }
                indexed_now += 1
                queue.extend(links[:500])
                if len(docs) > MAX_DOCS:
                    # Keep the newest bounded collection so the static index remains deployable.
                    docs = dict(list(docs.items())[-MAX_DOCS:])
            except (httpx.HTTPError, UnicodeError, ValueError):
                continue
    output = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "indexed_pages": len(docs),
        "coverage_note": f"SeekBot's own index: {len(docs)} pages indexed so far; {indexed_now} added in this run. Coverage is partial and grows with future crawls.",
        "results": list(docs.values())[-MAX_DOCS:],
    }
    INDEX_PATH.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    FRONTIER_PATH.write_text(json.dumps({"pending": list(queue)[:20000], "seen": list(seen)[-100000:]}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"SeekBot processed {processed} URLs and indexed {indexed_now} new pages. Total indexed: {len(docs)}. Frontier: {len(queue)} pending.")

if __name__ == "__main__":
    main()
