# Zero-cost MVP deployment

Reward Watch can use provider subdomains during MVP0:

- Web: `https://reward-watch.pages.dev`
- API: `https://reward-watch-api.onrender.com`

## 1. Publish the repository

Create a Git repository for this folder and push it to GitHub. Keep the
repository public if the hosting provider requires public access on its free
plan. Never commit `.env` files or administrator credentials.

## 2. Deploy the FastAPI service on Render

In Render, create a Blueprint from the GitHub repository. Render reads the
root-level `render.yaml` and creates the free `reward-watch-api` Docker web
service. Confirm that this endpoint returns an HTTP 200 response:

```text
https://reward-watch-api.onrender.com/health
```

The public API can read the validated JSON snapshot without a database. Add a
Neon `DATABASE_URL` later when administrator changes and hourly database sync
need to persist independently of deployments.

## 3. Deploy the Expo web app on Cloudflare Pages

Create a Pages project connected to the same GitHub repository and use:

```text
Project name:       reward-watch
Root directory:    mobile
Build command:     npm run build:web
Build output:      dist
Environment name: EXPO_PUBLIC_API_BASE_URL
Environment value:https://reward-watch-api.onrender.com
```

Cloudflare Pages serves unmatched browser routes from the application entry
page. Public links use the statically exported `/cases/detail?id=...` route so
case detail refreshes do not depend on dynamic-path rewrites.

## 4. Verify the public deployment

Check the home page, country selector, search, All Cases pagination, one direct
case-detail refresh, image loading, official-source links, and phone-width
layout. Render free services sleep when idle, so the first API request after an
idle period can be slower.
