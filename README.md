# Seek

**Seek, your customizable AI-powered search companion.**

Seek is a responsive, static search homepage with provider-backed web searches, customizable fandom context, local search history, themes, and an optional AI chat connection called **The Seeker**.

## What works

- Search handoff to DuckDuckGo, Google, Bing, or Brave.
- Web, Images, Videos, News, Maps, and Scholar search categories. Some categories use specialist destinations such as OpenStreetMap or Google Scholar.
- Custom fandoms and interests. The included starter list is a starter set, not a claim to contain every fandom ever created.
- The Seeker chat panel. For live model responses, configure your own OpenAI-compatible API endpoint, model, and key in **Customize**.
- Violet, Rosewater, Enchanted Forest, Midnight, and Daylight themes.
- Recent searches and preferences saved in this browser.
- Responsive desktop and mobile layout. No build step or framework required.

## Run locally

Open \`index.html\` in a modern browser, or serve this directory with any static web server.

## Publish with GitHub Pages

This repository includes a GitHub Actions workflow at \`.github/workflows/pages.yml\`.

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, select **GitHub Actions** as the source.
3. Open **Actions** and confirm that **Deploy Seek to GitHub Pages** completes successfully.
4. The Pages URL will appear in **Settings → Pages** after GitHub publishes it. For a user repository named \`Seek\`, it will typically be \`https://YOUR-USERNAME.github.io/Seek/\`; use the URL GitHub actually shows.

## Configure The Seeker AI

1. Get an API key from a provider that supports OpenAI-compatible chat completions.
2. In Seek, open **Customize**.
3. Choose the provider or custom endpoint, enter the model ID, and paste the key.
4. Save settings and send a test prompt.

**Important:** this is a client-only static app. The key is kept in the current tab's \`sessionStorage\` and sent from your browser directly to the endpoint you configure. It is not committed to this repository, but browser-based keys are not appropriate for shared/public computers and may be exposed to browser extensions or local access. Provider calls may cost money. Some providers block browser requests using CORS. A production version should send AI requests through a server-side proxy and keep secrets in server environment variables.

## Honest scope

Seek does not operate its own crawler or search index. Search results come from the selected external search provider. The Seeker only gives live AI answers when a compatible endpoint and valid key are configured and reachable. Fandom customization supports any title typed by the user; no finite preset list can truthfully include every fandom.

## Privacy

Search history and preferences stay in local browser storage on the device unless the user clears them. API keys are held in tab session storage and are cleared when that browser session ends. Searches open external providers, which have their own privacy policies.
