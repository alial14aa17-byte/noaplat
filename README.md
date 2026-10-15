# nōa Premium Operations — v0.2

**Mobile-first internal operations app** for nōa. Arabic RTL, responsive desktop and iPhone-sized layouts, red premium dashboard, real API, role-based login, PostgreSQL support.

## What works in this package
- Owner login bootstrap, signed session cookies, hashed passwords, four account roles: owner/admin/assistant/trader.
- Owner can create users, products and expenses; admin can create products and orders; assistant and trader can create orders; trader only sees own orders.
- Create and list products, orders, status updates, expenses, audit log, operational metrics.
- Dashboard with real seven-day order activity and status breakdown (not fake data), latest orders, quick actions, revenue/profit estimates for authorized roles.
- Mobile-first premium RTL UI, bottom navigation, touch-sized controls, modal bottom sheets, PWA manifest.
- Railway configuration with PostgreSQL or local SQLite for development.

## Deploy to Railway
1. Upload the contents of this folder to a **private GitHub repository**.
2. Railway → New Project → Deploy from GitHub repo.
3. Add a PostgreSQL service. Set `DATABASE_URL` in the app service using a **variable reference** to PostgreSQL `DATABASE_URL`.
4. Set `OWNER_EMAIL`, `OWNER_PASSWORD` (12+ chars), `SESSION_SECRET` (32+ random chars), `HTTPS_ONLY=true`.
5. Railway builds the Python app using `requirements.txt` and starts using `railway.json`.
6. Open Railway → Networking → Generate Domain. Attach your custom domain later if desired.
7. Login with the owner credentials. First owner is created only if the users table is empty.

**Do not** upload `.env` or passwords to GitHub. Use Railway Variables. Do not expose a production app with weak credentials.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OWNER_EMAIL=owner@example.com
export OWNER_PASSWORD='replace-with-strong-password'
export SESSION_SECRET='replace-with-a-long-random-string-of-at-least-32-characters'
uvicorn app:app --reload
```
Visit http://127.0.0.1:8000

## Important production limitations
**This is an upgraded runnable foundation, not a completed 170-feature ERP.** It is not yet safe to rely on as the sole source of truth for live inventory or financial settlements. In particular, the following are **not implemented**: image/DTF file upload and durable object storage, purchasing and suppliers, automatic inventory movements, trader settlement ledger, advanced permissions, invite flow, Telegram synchronization, Iraq governorate heatmap, invoice printing, backups/restore, migrations, CSRF protection, login rate limiting, MFA, automated end-to-end tests. These need implementation and security review before live production use.

Revenue currently counts **delivered** orders; costs and profit are preliminary and exclude several settlement scenarios. There are no demo/fake orders. Product imagery is intentionally represented by neutral placeholders until real product assets are uploaded.

## Recommended mobile testing
Test at 320px, 375px, 390px, 430px widths and 768px tablet, plus desktop. Test Safari iOS and Chrome Android, form keyboard behavior, RTL, horizontal scrolling, and access controls.
