# Reward Watch

Reward Watch is an Expo + FastAPI MVP for browsing official public reward and wanted notices. It is designed for searching, saving, and opening official source links, not for approaching, tracking, or detaining anyone.

## Project Structure

- `mobile`: Expo Router app for iOS, Android, and web preview.
- `backend`: FastAPI API with PostgreSQL persistence and JSON snapshot fallback.
- `sample_cases.json`: fictional fallback data for offline MVP work.
- `backend/data/cases.json`: generated official-source data, when imported.

## Run The API

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API endpoints:

- `GET /health`
- `GET /cases` (paginated; supports `q`, `country`, `region`, `status`, `source`, reward range, and sorting)
- `GET /cases/{id}`
- `GET /settings/home`

`GET /cases` returns `items`, `total`, `page`, `pageSize`, `totalPages`, and
filter facets. The app requests only the page it needs instead of downloading
the complete catalog.

## PostgreSQL And Hourly Sync

Copy `.env.example` to `.env`, replace every development secret, then run:

```powershell
docker-compose up -d postgres api scheduler
```

The scheduler refreshes official sources at minute 20 of every hour. Validated
records are written to PostgreSQL while JSON files remain the last-known-good
recovery snapshots. In GitHub Actions, add a `DATABASE_URL` repository secret
to synchronize the validated hourly snapshot after tests pass.

## Operations Console

Create the first administrator from the server. There is no public administrator
registration endpoint.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://reward_watch:password@localhost:5432/reward_watch"
cd backend
.\.venv\Scripts\python.exe scripts\create_admin.py --email you@example.com
```

Open `http://localhost:8081/admin`. The console provides source-health status,
case search, display overrides, image selection, hide/draft controls, manual
sync, and an audit log. It can also create a source-backed public notice with a
broad jurisdiction, reward amount, and up to eight uploaded images. Every new
notice starts hidden and in draft review. Source refreshes update raw records
without overwriting administrator display overrides or deleting manual notices.

There is no public administrator registration route. Uploaded images are
validated, resized, re-encoded, and stripped of metadata. Development stores
them below `backend/data/media`; production requires Cloudflare R2 because the
Render filesystem is not durable. The form is intentionally for public,
source-backed notices only: do not publish live locations, private addresses,
tracking history, or instructions to approach or detain anyone.

Home subtitle, safety copy, recent-case count, and featured cases use a separate
draft and publish workflow. Saving a draft does not change the public app;
`Publish` copies the reviewed draft to the public `GET /settings/home` response.

## Run Web Preview

```powershell
cd mobile
$env:EXPO_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run web -- --port 8081 --host localhost
```

Open `http://localhost:8081`.

## Zero-cost Web Deployment

The MVP can run on provider subdomains without purchasing a domain. See
[`DEPLOYMENT.md`](DEPLOYMENT.md) for the Cloudflare Pages frontend and Render
FastAPI setup.

## Update Official Data

The importer combines every publishable record from the official FBI Wanted
API, Ontario Provincial Police public investigations, the current Saskatchewan
RCMP monthly wanted-persons release, and the active Fugitifs Quebec provincial
wanted list, plus Edmonton Police Service's current most-wanted list. British
Columbia coverage combines explicit active wanted releases from the BC RCMP,
Vancouver Police Department, and CFSEU-BC. Cash-reward coverage also includes
the U.S. Department of State Rewards for Justice catalog, reward-bearing U.S.
Marshals profiled fugitives, and the Government of Nova Scotia Rewards for
Major Unsolved Crimes program. The U.S. Postal Inspection Service adapter also
follows its nationwide Wanted Poster directory by state and imports notices
that state a cash reward. Texas coverage also includes the Texas Department of
Public Safety active Most Wanted, wanted sex offender, criminal illegal
immigrant, and Still Wanted reward directories. It writes normalized records to
`backend/data/cases.json`.

The updater also writes `backend/data/source_cases.json` as the per-source
fallback snapshot and `backend/data/data_quality_report.json` as an auditable
summary. Exact-name overlaps between FBI and Rewards for Justice records are
merged conservatively for the app while every official source URL remains on
the canonical case. Published rewards carry an explicit `USD` or `CAD`
currency; an absent official amount is stored as `null`, not as a zero-dollar
reward.

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\update_cases.py --strict
```

The default update is a full sync. Positive `--fbi-limit`, `--opp-limit`,
`--canada-limit`, `--quebec-limit`, and `--edmonton-limit` values can be used
for development samples, along with `--bc-rcmp-limit`, `--vancouver-limit`, and
`--cfseu-bc-limit`. The cash-reward sources support
`--rewards-for-justice-limit`, `--us-marshals-limit`, and
`--nova-scotia-limit`, plus `--uspis-limit` and `--texas-dps-limit`. The update is source-safe: when one
official source is temporarily unavailable, only that source's previous records
are retained. The latest outcome is stored in
`backend/data/update_status.json`.

`.github/workflows/update-official-data.yml` runs the same update at 20 minutes
past every hour, tests it, synchronizes PostgreSQL when `DATABASE_URL` is
configured, and commits changed recovery snapshots. It becomes active after
this project is pushed to a GitHub repository with Actions enabled and workflow
write access.

Only official public-safety sources are imported. The Canada adapters ignore
inactive or arrested notices, unrelated missing-person entries, records without
a real source image, and generic "no photo" placeholders. The three dedicated
reward catalogs additionally require a cash amount stated by the official
source. U.S. Marshals profiles with explicit apprehended or deceased updates are
retained as `Closed` instead of being presented as active notices.

Texas DPS embeds official profile photos directly in its pages. The importer
stores those images under `backend/data/media/texas-dps`, and the API serves
them from `/media/texas-dps`. Texas DPS does not publish a reliable posting date
on these profiles, so `publishedDate` records when Reward Watch first observed
the profile and remains stable across later refreshes.

BC newsroom adapters only accept explicit wanted or warrant notices. They use
newer arrest, custody, located, surrendered, extradited, and deceased posts as
lifecycle closures when the official source identifies the same person.

Each normalized record includes explicit source attribution and zero or more
`regions`. Canada records are classified by province. US records use the
official FBI field office mapping, with a title-based state fallback when the
source does not publish a field office. Records without a reliable state remain
available under the country-wide view instead of being assigned speculatively.

### RCMP content permission

RCMP terms permit non-commercial reproduction when accuracy, the complete
material title, author, and original URL are provided. Commercial redistribution
requires prior written permission from the RCMP. Reward Watch keeps agency and
official-source attribution, but written permission must be obtained before a
commercial release that republishes RCMP text or imagery. Do not reproduce RCMP
or Government of Canada official symbols without separate authorization.
