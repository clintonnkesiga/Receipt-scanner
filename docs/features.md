# Feature Roadmap

Status of features for ReceiptScanner. Checked items are shipped; the rest are
proposed, grouped by theme and rough priority.

## ✅ Done

- **Server-side pagination** — list endpoint with `limit/offset/q/category/sort` plus total count + summed total across the whole filtered set.
- **Per-user categories** — shared/system defaults (seeded) plus categories each user owns and manages.
- **Batch upload** — scan queue, sequential OCR, per-item review before saving.
- **Manual rotate** in the image viewer, with the rotation persisted on the receipt.
- **Re-scan / re-run OCR** on an existing receipt.
- **Edit receipt** after saving.
- **OCR orientation auto-correction** — probes 0/90/180/270 and keeps the highest-confidence read (fixes sideways phone photos).
- **Gallery view + filters** — table/gallery toggle, merchant search, category filter, sort, image viewer with prev/next.
- **Dashboard** — colored stat cards (total, receipts, avg, this-month trend, recent, last receipt, largest), plus by-category / top-merchant / by-currency / by-month charts.

## High-impact (core value) — remaining

- ~~**Budgets & alerts**~~ ✅ — monthly limit per category, current-month spend computed in stats, progress bars on dashboard and dedicated `/budgets` management page (create / edit / delete); over-budget highlighted in red.
- ~~**Date-range & amount filters**~~ ✅ — `date_from`, `date_to`, `amount_min`, `amount_max` query params on list endpoint; filter inputs in the receipts toolbar; pagination properly server-side.
- ~~**Multi-currency normalization**~~ ✅ — `fx_rate` field per receipt; `normalized_sum` (sum of `total × fx_rate`) returned in list response; fx_rate editable in scan review and edit modal.
- ~~**Capture tax/VAT**~~ ✅ — `tax_amount` auto-extracted from OCR (VAT / GST / HST keywords), `net_amount = total − tax`; both fields stored, editable, and shown in the receipts table and edit modal.
- ~~**Editable line items in review**~~ ✅ — line items editable in both the scan-review panel and the edit modal; saved via PATCH.

## Analytics & reporting ✅

- ~~Date-range reports + spend-over-time line chart~~ ✅ — `/reports` page with from/to date pickers + day/week/month granularity, backed by a `GET /api/reports/timeseries` endpoint; rendered as an SVG line/area chart.
- ~~Recurring-expense detection~~ ✅ — `GET /api/reports/recurring` flags merchants paid on a regular cadence (≥3 times, ~weekly-to-monthly interval, low variation), with avg amount, interval, and an estimated next date; shown as a table on the reports page.
- ~~Export to Excel / PDF~~ ✅ — `GET /api/reports/export.xlsx` (openpyxl) and `export.pdf` (reportlab), both honoring an optional date range and including tax/net/fx columns. CSV/Excel/PDF buttons on the reports page.
- ~~Scheduled weekly email digest~~ ✅ — `app/digest.py` builds a per-user HTML summary of the last 7 days; `python -m app.digest` (cron-friendly, `--dry-run` supported) emails all active users via SMTP. `GET /api/reports/digest/preview` + `POST /api/reports/digest/send` let a user preview/email it from the reports page. Requires `SMTP_*` config in `.env` to actually send.
- ~~Duplicate detection~~ ✅ — primary match on the receipt's unique **fiscal/transaction number** (`fiscal_id`, parsed from "Fiscal Doc No / CashSale / Receipt / Invoice No / Verification Code"), immune to OCR date/total wobble; fallback to merchant + total within ±3 days. Detected duplicates **block saving** (`POST /receipts` returns 409) unless the user ticks "Save anyway" (`force: true`).

## Account & security ✅

- ~~Self-service password reset / email verification~~ ✅ — `POST /forgot-password` generates a 1-hour reset token + emails a link; `POST /reset-password` validates + sets new password. Email verification: `send-verification` + `verify-email` token flow. Frontend pages at `/forgot-password` and `/reset-password?token=…`; email links work out of the box when `SMTP_*` is configured.
- ~~2FA (TOTP)~~ ✅ — `GET /api/2fa/setup` returns QR code + secret; `POST /api/2fa/enable` confirms + activates; `POST /api/2fa/disable` deactivates. Login returns 403 `mfa_required` when 2FA is on and no code supplied; login page shows TOTP step automatically. Backed by `pyotp`.
- ~~Audit log~~ ✅ — `audit_logs` table records every login, password change, 2FA toggle, and receipt/budget create/delete. `GET /api/audit` returns paginated log (own entries for users, all entries for admins). Frontend at `/audit` linked from Account page.
- ~~Profile (display name, avatar)~~ ✅ — `PATCH /api/auth/profile` updates `full_name` and `avatar_url`; reflected in the sidebar initials/avatar and Account page.

## Platform / UX

- ~~**Mobile camera capture (PWA)**~~ ✅ — installable web app (`manifest.webmanifest` + generated icons + `src/service-worker.js` caching the app shell, network-only for `/api`); a **"📷 Take photo"** capture button (`capture="environment"`) alongside the file picker; the sidebar collapses to a hamburger drawer below `md` so it's usable as an installed phone app.
- ~~Dark mode~~ ✅ — manual toggle in the sidebar, persisted to `localStorage`, defaults to the OS preference, with a no-flash init script in `app.html`. Tailwind `darkMode: "class"` + a small dark-token remap in `app.css` (plus `dark:` variants on the shell/components).
- ~~Soft-delete / trash + restore~~ ✅ — deleting moves a receipt to the **Trash** (`deleted_at` column); `GET /api/receipts/trash`, `POST /{id}/restore`, `DELETE /{id}/permanent`. Trashed receipts are excluded from all lists/stats/reports/digests. Frontend `/trash` page (restore / delete-permanently) linked from the sidebar.
- ~~Deep-linkable receipt detail page~~ ✅ — every receipt has its own URL at `/receipts/[id]` (image with zoom + rotate, all fields, line items, edit/delete/restore actions). Gallery cards and table rows link to it; the edit form is now a shared `ReceiptEditModal` reused by the list and detail pages.
- Cloud backup of original images.

## Technical debt — remaining

- **Exports stream the full result set in one response** — fine for now (the new Excel/PDF exports accept a date range to bound it); revisit if datasets get large.
- Dashboard `top_merchants` / totals still **sum mixed currencies** (the receipts list now also returns a `normalized_sum` via `fx_rate`; the dashboard cards could adopt it).

## Recommended next 3

1. **Dashboard currency normalization** — surface `normalized_sum` on the dashboard so totals stop mixing currencies.
2. **Cloud backup of originals** — the last remaining Platform/UX item; mirror SeaweedFS originals off-site (e.g. an S3-compatible bucket) for durability.
3. **Auto-purge for Trash** — optionally empty trashed receipts after N days (today restore / permanent-delete are manual only).

The "High-impact (core value)", "Analytics & reporting", "Account & security", and most of "Platform / UX" (PWA, dark mode, soft-delete/trash, deep-linkable detail) are now complete. The main remaining items are dashboard currency normalization and cloud backup of originals.
