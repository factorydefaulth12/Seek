# Seek

**Seek is an independent, crawler-backed search engine project with The Seeker AI and customizable fandom context.**

Seek now has two search paths: a static index hosted alongside the website on GitHub Pages, and an optional FastAPI/SQLite backend for a larger persistent index. The GitHub-only path is designed to work without a separate hosting account or paid service. Seek can also be installed as a web app, cache its index for offline use after the first load, and be added as a browser search provider.

## What is implemented

- **Seek Index:** the homepage fetches `seek-index.json` and ranks matching indexed pages in the browser when the optional API is unavailable.
- **SeekBot:** `scripts/crawl_static.py` discovers and indexes public HTML pages, follows links, observes robots.txt, waits between requests to the same domain, and blocks non-public host addresses.
- **Persistent crawl frontier:** `seek-frontier.json` stores queued URLs between GitHub Actions runs, allowing later crawls to continue discovering pages.
- **Automated growth:** `.github/workflows/crawl-index.yml` runs on demand or every six hours, updates the static index, and commits the new index/frontier to `main`. The Pages workflow then publishes the updated files.
- **Optional API:** `api/app.py` offers a FastAPI service with a SQLite full-text index, search and health endpoints, and a token-protected crawl endpoint. `render.yaml` is an optional paid Render deployment blueprint.
- **Fandom multiverse:** a searchable, category-filtered directory of 1,000+ anime, animation, TV/film, book, game, comic, music, webtoon, creator, aesthetic, sports, mythology, and internet-culture fandoms. Choosing any entry applies a deterministic custom colour palette and saves it to the local fandom constellation. Users can type any fandom name to generate a custom theme. For the full live catalogue, links open Fandom's official Explore/search experience. Cards attempt to load live reference thumbnails from Wikipedia's public page-summary endpoint and fall back to emoji artwork when a page has no suitable image. Every entry also has a direct link to search Fandom's official community catalogue. This is not a copy of every Fandom community. For anything missing, type its name to create a custom theme and open a direct Fandom search.
- **Installable app:** `manifest.webmanifest`, `sw.js`, and `icon.svg` enable installation and cached offline search after the first successful load.
- **Browser search provider:** `opensearch.xml` supports adding Seek to compatible browsers; the search URL accepts `?q=your+terms`.
- **Homepage:** themes, local search history, fandom customization, The Seeker AI panel, external search provider options, and the independent **Seek Index** mode.

## Publish the website and first index

The site uses GitHub Pages, so the frontend and static search index do not need a separate hosting provider.

1. Open [Seek Actions](https://github.com/factorydefaulth12/Seek/actions).
2. If GitHub Pages is not already configured, open **Settings → Pages** and set the build/deployment source to **GitHub Actions**.
3. In Actions, choose **Grow Seek's web index**.
4. Click **Run workflow**, keep the default page limit (500), and start it. The first run can take several minutes while SeekBot checks sites and indexes pages.
5. Wait for the run to finish. The workflow commits `seek-index.json` and `seek-frontier.json`; that commit triggers the Pages deployment workflow.
6. Open [https://factorydefaulth12.github.io/Seek/](https://factorydefaulth12.github.io/Seek/), choose **✦ Seek Index**, and search a term. You can inspect the public index at [seek-index.json](https://github.com/factorydefaulth12/Seek/blob/main/seek-index.json).

After the first manual run, scheduled crawls are configured for every six hours. GitHub scheduled workflows are best-effort and can be delayed. If the crawl fails, open the run in Actions to read its logs and rerun it.

**The first index is intentionally small.** Each run is capped at 500 newly indexed pages, and the default is 500. The current static index retains up to 2,500 pages with a short text excerpt per page so the public JSON file remains manageable. The crawler follows links over time, but many sites block crawlers, require JavaScript, use rate limits, or disallow indexing. The index is capped at 10,000 pages and may not contain everything you search for. This is an evolving independent index, not Google's entire web index.

## Install Seek and use it as your browser search engine

**Install as an app (Chrome on desktop):**
1. Open [Seek](https://factorydefaulth12.github.io/Seek/) while online.
2. Click **Install Seek** in the top bar if Chrome offers it. If the button gives you the menu route instead, open Chrome's **⋮ → Cast, save, and share → Install page as app** (the wording may vary).
3. Open Seek once while connected so the current site and index can be cached. Later, the installed app can search the cached index offline; new pages and fresh external searches still need internet.

**Make Seek your Chrome address-bar search engine:**
1. Open Chrome **Settings → Search engine → Manage search engines and site search**.
2. Under Site search, choose **Add**.
3. Set name to `Seek`, shortcut to `seek`, and URL to `https://factorydefaulth12.github.io/Seek/?q=%s`.
4. Save it, then choose Seek as the default if you want searches from the address bar to open Seek. Chrome menus can vary by version.

This is a web app hosted on GitHub Pages, not a Chrome Web Store listing. You can also download the project source using GitHub's **Code → Download ZIP** menu.

## Optional API backend

The optional API is useful if you later want server-side ranking, a larger index, and a persistent database independent of a JSON file. It is not required for the static GitHub Pages search path.

### Local development

From the repository root:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r api/requirements.txt
# Windows PowerShell: $env:SEEK_DB_PATH="./seek.db"; $env:SEEK_CRAWL_TOKEN="local-test-token"
# macOS/Linux: export SEEK_DB_PATH=./seek.db; export SEEK_CRAWL_TOKEN=local-test-token
cd api
uvicorn app:app --reload --port 8000
```

Visit `http://127.0.0.1:8000/docs` for API documentation and `http://127.0.0.1:8000/health` for a health check.

### Optional cloud hosting and costs

If you want the persistent API online as well, the repository includes `render.yaml` for Render. That blueprint is separate from the GitHub-only setup and may incur charges. Render's Starter compute and persistent disk pricing can change, so check [Render pricing](https://render.com/pricing) before applying it. You must personally connect the GitHub repository to Render and approve any billing or account terms. No external hosting is required to use the static index.

## The Seeker AI

The homepage can connect to an OpenAI-compatible chat endpoint using a key entered in Customize. Provider access may cost money, and browser CORS restrictions may apply. The key is kept in the current tab's session storage rather than committed to this repository. This browser-only setup is not appropriate for high-value secrets; a production version should proxy AI calls through a secured backend.

## Honest scope, safety, and privacy

- Search results come from pages Seek has actually indexed. Missing results do not mean a page does not exist.
- The crawler is bounded and polite. It does not bypass logins, paywalls, robots rules, or anti-bot controls.
- The static index and crawl frontier are committed to this public repository, so their page URLs and short public-page excerpts are publicly visible.
- Search history and preferences remain in local browser storage unless cleared.
- The Seeker AI remains optional and uses the provider you configure.
- **Offline mode:** install Seek and open it at least once while online so the current shell and index can be cached. Offline search only covers the last cached index; fresh web results still require a connection.
- **School use:** Seek can be used as a study tool, but use it during exams only when your school or exam rules explicitly allow search tools.
- GitHub Actions and Pages have usage limits; this design is for an early-stage project and will need architectural changes to scale to millions of pages.
- No existing repository other than `factorydefaulth12/Seek` is changed.
