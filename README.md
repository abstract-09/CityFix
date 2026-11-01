# CityFix: Civic Grievance Intelligence

CityFix lets residents report a road, water, drainage, waste or lighting problem with a photo or voice note.
It reads the GPS location, classifies the issue, works out which authority is responsible, and gives the
reporter a tracking code. Officers work a queue and must upload photo proof to close a ticket. Anyone can see a
public map and each department's response times.

This is a working end-to-end MVP: Flask API, SQLite database, and a dependency-free web client.

## Quick start

Requirements: Python 3.10+ (Node 18+ is optional).

```bash
pip install -r requirements.txt
python run.py
```

Open <http://localhost:8000>. On first start CityFix creates the database, loads the three sample reports and
the demo boundaries, and **prints demo logins** (also saved to `instance/demo_credentials.txt`):

| Account | Role |
|---|---|
| `officer_rcd` | Officer, Road Construction Department Bihar |
| `officer_nhai` | Officer, National Highways Authority of India |
| `officer_municipal` | Officer, Municipal Corporation |
| `officer_general` | Officer, General Municipal Services |
| `admin` | System administrator |

All five share one random password per install. Set `DEMO_USER_PASSWORD` to choose it. These are demo
accounts only; never expose them on a public server.

Useful flags: `python run.py --reseed --extra 40` resets to the sample data and adds 40 random reports so the map
and heat layer look lively. `--no-build` skips the optional frontend build.

### Try it in two minutes
1. **Report an issue** (`/`): allow location, or open *Enter coordinates by hand* and press *Use the demo location (Bihta)*. Add any JPG or PNG.
2. Note the code (like `CIV-2026-0004`) and open **Track Ticket**.
3. Sign in at **Officer portal** as `officer_rcd`, set the ticket to *In Progress*, then *Resolved* with a photo.
4. Watch the **Public Dashboard** update. Sign in as `admin` to see AI output and contact details.

## Configuration

Copy `.env.example` to `.env`. Variables from the specification:

| Variable | Default | Purpose |
|---|---|---|
| `AI_SERVICE_API_KEY` | `stub_key` | `stub_key` runs fully offline. A real key enables photo classification. |
| `GIS_MAP_API_KEY` | `stub_key` | Reserved for an external GIS provider. Routing uses local GeoJSON today. |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite:///./cityfix.db` | SQLite only in this MVP |
| `MAX_UPLOAD_SIZE_MB` | `10` | Per-file upload limit |

Optional extras are listed in `.env.example` (AI model/URL/timeout, allowed CORS origins, rate limits, secrets).
API keys are read only by the backend; the browser never sees them.

### Using real AI triage
Set `AI_SERVICE_API_KEY` to a real key. `backend/services/ai_service.py` (the only module that calls an AI
provider) sends the photo to an Anthropic-compatible Messages endpoint (`AI_SERVICE_URL`, `AI_MODEL`) with a 4 s
timeout. Results at or above 0.70 confidence are used; lower confidence becomes *Other / Medium / Needs manual
review*; a provider failure becomes *Other / Medium / Manual review required* (HTTP 503 from `/triage`, while
ticket creation still succeeds). Audio files and photos over 5 MB are not sent to the vision API and are flagged
for manual review.

## How it fits together

```
frontend/   ES-module web client (no packages to install). build.mjs checks and copies it to dist/
backend/    Flask app: api/ (HTTP), services/ (rules), models/ (SQL), utils/ (validation, crypto, geo)
shared/     constants.json (enums), demo boundaries, sample tickets
scripts/    test.sh (everything), smoke.sh (end-to-end)
run.py      one-command start
```

Routing rules (`backend/services/routing_service.py`): within 50 m of a national or state highway line goes to
NHAI or RCD Bihar (nearest wins); otherwise inside a ward polygon goes to the Municipal Corporation; otherwise
General Municipal Services. Admins can replace the GeoJSON from the console; invalid GeoJSON is rejected.

Status flow is `Received → In Progress → Resolved`, never backwards. Closing requires an uploaded photo, and
`resolved_at` is set by the server.

## API summary (`/api/v1`)

| Method and path | Who | Notes |
|---|---|---|
| `GET /health` | anyone | database and AI status |
| `POST /triage` | anyone | multipart `media`, `latitude`, `longitude`; returns category, severity, description |
| `POST /tickets` | anyone | multipart; adds optional `category`, `contact`, `accuracy`. `201` created, `200` merged duplicate |
| `GET /tickets/:id` | anyone | status, details, history. Never includes contact details |
| `GET /public/dashboard` | anyone | map points, SLA metrics, boundaries; filters `category`, `status` |
| `GET /route-preview` | anyone | which department a location maps to |
| `POST /auth/login`, `GET /auth/me` | staff | bearer token |
| `GET /authority/tickets` | officer | own department only, most urgent first |
| `PATCH /authority/tickets/:id` | officer | `{"status": "In Progress"}` |
| `PATCH /authority/tickets/:id/resolve` | officer | multipart `resolution_proof` photo (required) |
| `POST /authority/tickets/:id/info-request` | officer | public question shown on the ticket |
| `GET /admin/tickets`, `GET/PUT /admin/boundaries`, `GET/PUT /admin/departments/:name`, `POST /admin/seed` | admin | AI output, contact details, routing, demo data |
| `POST /notifications/subscribe` | anyone | stores a phone number; see limitations |

Errors are JSON: `{"status":"error","code":413,"message":"Please use a file smaller than 10 MB"}`.

## Testing

```bash
scripts/test.sh                      # everything below
python -m unittest discover -s backend/tests -t .   # 75 backend tests
cd frontend && node --test tests/*.test.mjs         # 13 frontend unit tests
node frontend/build.mjs                              # production build
scripts/smoke.sh                                     # 16-step end-to-end run against a live server
```

The acceptance criteria AC1 to AC9 each map to a test in `backend/tests/test_acceptance.py`; AC10 is the whole
script above.

## Privacy and security

- Contact details are encrypted at rest (Fernet), shown only to administrators, stripped from every public and
  officer response, and masked out of logs.
- Uploads are checked on the server for size and real file type (content sniffing, not the browser's claim).
- All user text is rendered as text, never HTML. The server sends a strict Content-Security-Policy.
- Officer and admin endpoints need a signed token; officers see only their own department. Login and
  report endpoints are rate limited per IP.
- CORS is limited to `ALLOWED_ORIGINS`.
- CityFix never contacts outside agencies or dispatches anyone automatically. Resolution always needs an
  officer's manual action with photo proof.
- Secrets are never committed: `.env` and `instance/` are git-ignored, and signing and encryption keys are
  generated on first run if you do not provide them.

## Assumptions where the specification was silent or inconsistent

1. **Departments:** the routing rules name "General Municipal Services" but the ticket enum omitted it, so it is a fourth allowed value.
2. **Status name:** the lifecycle says *Received* and the lookup endpoint said *Pending*. *Received* is used everywhere.
3. **Highway precedence:** a point inside a ward that is also within 50 m of a highway routes to the highway authority, since a highway is not municipal. Sample ticket 1 depends on this.
4. **415 message:** kept word-for-word from the spec (JPG, PNG, or MP3) although WAV and M4A are also accepted.
5. **Authentication:** unspecified, so officers and admins sign in with a username and password and receive a signed 12-hour token.
6. **Boundaries:** no real GeoJSON was provided, so `shared/boundaries.demo.geojson` is synthetic.
7. **Duplicates (F11):** implemented. Same category within 50 m of an unresolved ticket merges and raises `report_count`. A merged reporter's contact is not stored.
8. **Proof upload:** proof must be an uploaded JPG or PNG; a text URL is refused so no one can attach an arbitrary link.
9. **Sample media URLs:** the three sample tickets use the spec's `storage.cityfix.local` URLs, which do not resolve, so the UI shows a placeholder.
10. **Manual coordinates:** the report form also accepts typed coordinates, so the demo works on a laptop without GPS. A report still needs a location.
11. **Extra endpoints:** `/route-preview` (shows the responsible department as you report) and the admin demo-data and department-email endpoints go beyond the spec.

## Known limitations

- **Not tested in a real browser.** The development sandbox had no browser. The page code is verified by the
  16-step smoke test (real modules, real server, minimal DOM) and unit tests, but layout, the visual design, the
  map's drag and zoom gestures and the camera/geolocation prompts have not been seen on a screen. Expect to do a
  visual pass.
- **Live AI is tested with mocks only.** The sandbox had no network, so the live-provider call has never reached
  a real service. Try it with a real key before relying on it.
- **SMS and WhatsApp (F10)** are not connected. `/notifications/subscribe` stores an encrypted number and says
  plainly that delivery is not configured.
- Department emails are stored for officers; nothing is ever sent automatically.
- The built-in Werkzeug server, in-memory rate limiter and local-disk uploads suit a demo. For production run behind
  gunicorn or waitress and a TLS proxy, use a shared rate-limit store, and scan uploads.
- No user-management screen, password reset or audit-log viewer. Event history is on each ticket.
- Map tiles are not used: the map draws your boundaries and reports on a plain canvas, so it works offline.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: flask` | `pip install -r requirements.txt` |
| Port 8000 busy | `PORT=8010 python run.py` |
| Can't sign in | Passwords are printed on first start and saved in `instance/demo_credentials.txt`, or set `DEMO_USER_PASSWORD` and run `python run.py --reseed` after deleting `cityfix.db` |
| "Location access is blocked" | Allow location for the site, or use *Enter coordinates by hand*. Browsers only share location on `localhost` or HTTPS |
| Fonts look different offline | The Atkinson font loads from Google Fonts; system fonts are the fallback |
| Reset everything | Stop the server, delete `cityfix.db` and `instance/`, start again |
| Frontend build says Node not found | Fine: the backend serves `frontend/` directly |
