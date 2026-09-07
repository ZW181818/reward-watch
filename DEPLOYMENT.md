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
2. Create a Cloudinary Free product environment for uploaded case images and
   set its server-side `CLOUDINARY_URL` in Render. Keep the API secret out of
   source control and frontend builds.
3. Keep `ADMIN_JWT_SECRET` as a generated Render secret and never expose it to
   the frontend.

The API refuses production image uploads if Cloudinary is incomplete. This prevents
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

The first database synchronization also builds the reviewed `public_cases`
catalog and its region, source, and legacy-ID indexes. Public list requests then
read only the requested page and aggregate facets in PostgreSQL; detail requests
read one exact case. Hidden and draft records never enter this projection.
Repeated public queries and shared facets are cached in the Render process for
five minutes, while administrator edits invalidate that cache as soon as their
transaction commits. Public reads also skip schema introspection; table creation
is handled by synchronization and administrator initialization paths. Successful
public GET responses advertise a one-minute browser cache with five minutes of
stale-while-revalidate coverage.

Snapshot synchronization stores canonical fingerprints for merged case payloads
and normally reads only IDs and hashes before updating changed rows. Per-source
normalized payloads remain in the versioned `source_cases.json` artifact instead
of being duplicated in Neon; the first catalog migration removes legacy copies.
PostgreSQL connections share one small application pool, and synchronization
history is capped at the latest 500 runs to protect the Neon Free allowance.

When the reviewed projection is ready, a database failure returns a temporary
503 instead of falling back to the raw JSON snapshot. This fail-closed behavior
prevents a database outage from making hidden/draft records public or dropping
manual administrator notices from the effective catalog.

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
