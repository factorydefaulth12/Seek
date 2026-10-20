# Seek

**Seek is becoming a crawler-backed search engine, with The Seeker AI and customizable fandom context.**

This repository contains the public-facing search homepage and a separate Python API that crawls public pages, stores them in Seek's own full-text index, and serves ranked search results. The crawler is respectful by design: it checks robots.txt, uses a descriptive user agent, limits pages per run, applies a per-domain delay, and skips private/local network addresses.

## What is implemented

- **Seek Index:** SQLite FTS5 full-text index and relevance-ranked `/search` endpoint. Results are from pages Seek itself has crawled, not a third-party search API.
- **SeekBot:** bounded crawler starting from a broad seed list and following public links. It skips non-HTML responses and large pages, respects robots.txt, and is designed to expand over repeated runs.
- **API endpoints:** `/health`, `/stats`, `/search?q=...`, `/admin/status`, and token-protected `POST /admin/crawl`.
- **Cloud deployment blueprint:** `render.yaml` provisions a Render web service and a persistent 1 GB index disk.
- **Scheduled growth:** `.github/workflows/crawl-index.yml` can request an index crawl every six hours after you configure two repository Actions secrets.
- **Homepage:** responsive interface, themes, local history, fandom customization, The Seeker AI panel, external provider options, and a new **Seek Index** mode.

## Deploy the search API

The API is configured for Render. You must connect this repository to a Render account to create the live cloud service. I cannot create a Render account, accept terms, or authorize paid hosting on your behalf.

1. Sign in to [Render](https://render.com/).
2. Choose **New → Blueprint** and connect the public repository `factorydefaulth12/Seek`.
3. Render should detect `render.yaml`. Review the blueprint before applying it. It creates a web service named `seek-engine-api`, a generated `SEEK_CRAWL_TOKEN` secret, and a persistent 1 GB disk mounted at `/var/data`.
4. Apply the blueprint and wait for the service deployment to finish.
5. Open the service's **Environment** page and copy the generated `SEEK_CRAWL_TOKEN` value. Keep it private.
6. Visit `https://seek-engine-api.onrender.com/health`. If Render assigns a different URL, use that URL instead. A healthy response should include `"ok": true` and `"indexed_pages": 0` before the first crawl.

### Cost and storage warning

The blueprint deliberately uses Render's **Starter** web-service plan because a durable search index needs persistent storage. Render lists Starter compute at **US$7/month**, plus persistent SSD storage at **US$0.25/GB/month**. The 1 GB disk therefore adds about **US$0.25/month**, for an expected starting total around **US$7.25/month**, before taxes, bandwidth overages, or plan changes. Check [Render's current pricing](https://render.com/pricing) before deploying. Free Render web services do not support persistent disks and lose local filesystem changes on restarts/redeploys, so they are not suitable for this SQLite-backed persistent index. See [Render's free service limits](https://render.com/docs/free) and [persistent disk documentation](https://render.com/docs/disks).

You can stop before applying the blueprint if you do not want paid hosting. Do not enter payment details unless you are comfortable with the provider's terms and costs.

## Connect the homepage to the API

The homepage is published separately through GitHub Pages.

1. Deploy the API as described above.
2. Open the [Seek homepage](https://factorydefaulth12.github.io/Seek/) after the Pages deployment succeeds.
3. Open **Customize** and set **Seek Search API URL** to the actual Render service URL, without a trailing slash. The default value is `https://seek-engine-api.onrender.com`.
4. Save the settings.
5. Choose **✦ Seek Index**, search a term, and confirm the result says it is from Seek's own index.

If the Pages website has not been published yet, open repository **Settings → Pages** and select **GitHub Actions** as the source. Then check the **Actions** tab for **Deploy Seek to GitHub Pages**.

## Start the first crawl

The API's admin endpoint requires the private crawl token. The repository includes a scheduled GitHub Actions workflow, but it will not work until you configure the secrets.

1. In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
2. Add `SEEK_API_URL` with your public Render service URL, for example `https://seek-engine-api.onrender.com`.
3. Add `SEEK_CRAWL_TOKEN` with the generated value from Render's Environment page. Never commit this value into a file.
4. Open **Actions → Grow Seek's web index → Run workflow** to start the first crawl. The scheduled workflow also requests a crawl every six hours.
5. Check `https://YOUR-RENDER-SERVICE-URL/stats` for the indexed page count and crawl status. A normal crawl run is capped at 200 pages.

The crawler begins with a curated mix of reference, science, news, education, technology, literature, culture, and fandom sites, then follows links it discovers. It does not index the whole web instantly. Search coverage grows over time, depends on site access and robots.txt, and is limited by the crawl budget and hosting resources.

## Local development

From the repository root:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r api/requirements.txt
# For local use, override the database path and token if desired.
# Windows PowerShell: $env:SEEK_DB_PATH="./seek.db"; $env:SEEK_CRAWL_TOKEN="local-test-token"
# macOS/Linux: export SEEK_DB_PATH=./seek.db; export SEEK_CRAWL_TOKEN=local-test-token
cd api
uvicorn app:app --reload --port 8000
```

Check `http://127.0.0.1:8000/docs` for the API interface and `http://127.0.0.1:8000/health` for health status.

## The Seeker AI

The existing homepage can connect to an OpenAI-compatible chat endpoint using a key entered in Customize. Provider access may cost money and browser CORS restrictions may apply. The key stays in the current tab's session storage, not in this repository, but this browser-only setup is not appropriate for shared devices or high-value secrets. A future production version should proxy AI calls through the backend.

## Honest scope and privacy

- Seek's own index only contains pages it has discovered and successfully crawled. It is not Google-scale, and missing results do not mean a page does not exist.
- The crawler is deliberately bounded and polite; it is not a tool for bypassing logins, paywalls, robots rules, or anti-bot controls.
- Search queries are sent to the Seek API you configure. The API stores indexed public page content and metadata on its persistent disk.
- Browser search history and preferences remain in local browser storage unless cleared.
- The Seeker AI remains optional and uses the provider you configure.
- No existing repository other than `factorydefaulth12/Seek` is changed by these instructions.
