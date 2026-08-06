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

The public API can read the validated JSON snapshot without a database. The
administrator console requires persistent services before it can be used in
production:

1. Create a Neon PostgreSQL database and set its pooled connection string as
   `DATABASE_URL` in Render.
2. Create a private Cloudflare R2 bucket for uploaded case images, connect a
   public media domain, and set `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, and `R2_PUBLIC_BASE_URL` in Render.
3. Keep `ADMIN_JWT_SECRET` as a generated Render secret and never expose it to
   the frontend.

The API refuses production image uploads if R2 is incomplete. This prevents
administrator media from being written to Render's temporary filesystem.

After `DATABASE_URL` is configured, initialize the database from a trusted
machine and create the only administrator account using the hidden password
prompt:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://..."
cd backend
.\.venv\Scripts\python.exe scripts\sync_database.py
.\.venv\Scripts\python.exe scripts\create_admin.py --email you@example.com
```

Do not pass the password with `--password` in a shared shell or CI log. Open
`https://reward-watch.pages.dev/admin`, sign in, create a notice as a hidden
draft, verify its public source and images, then set it visible and published.

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
