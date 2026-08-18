# v31 — Full UI rebuild ("Anodized Bench")

Complete visual overhaul of every screen. **No routes, forms, field names,
JavaScript hooks, database calls, or business logic were changed.** The full
existing test suite (154 tests) passes unmodified.

---

## Design direction

Grounded in the shop the software actually runs in — anodized-aluminium
greys, hi-vis tool amber for anything you act on, and a single instrument
teal reserved for the Shop Pulse and nothing else.

| | |
|---|---|
| **Surfaces** | `#0B0D12` base → `#12151D` cards → `#181C26` raised → `#212633` hover, hairline `#232936` borders |
| **Accent** | Tool amber `#FFC53D` (dark) / `#F0A81E` (light) |
| **Telemetry** | Teal `#4FD8C4` — Shop Pulse only |
| **Display / UI type** | Archivo (400–800) |
| **Data type** | IBM Plex Mono, tabular figures — money, SKUs, ticket numbers |

Both fonts load from Google Fonts with `display=swap` and a full system
fallback stack, so a shop with no internet still gets correct layout and
weights — just the fallback face.

---

## What changed

### Theming
- Complete design-token system in `static/style.css`: semantic colour,
  type scale, radii, shadows, and motion timing.
- **Light theme added** alongside dark, both first-class. Toggle sits in
  the top bar. Choice persists in `localStorage` and is applied by a tiny
  inline script in `<head>` before first paint, so there is no flash of
  the wrong theme on load.
- Dark remains the default for a fresh install — the counter machine
  lives in dark.
- ~500 hardcoded hex colours across the templates were converted to
  theme tokens, so both themes flow through inline styles too.

### Navigation
- Sidebar regrouped into **Counter / Workshop / Inventory / People /
  Business** with section labels, a brand mark, and a staff avatar block
  pinned to the bottom.
- Active item gets a tinted pill plus an accent rail; role-gated links
  behave exactly as before.
- Mobile: frosted top bar and bottom tab bar, off-canvas drawer with a
  scrim. Duplicate controls (two theme toggles, the `Ctrl K` hint) are
  hidden on small screens.

### Components rebuilt
Cards, tables (uppercase micro-headers, row hover, tabular numerics),
forms and focus rings, the full button set, badges, chips, the kanban
repair board, tabs and range tabs, checklist, activity feed, empty
states, notification dropdown, and the PIN lock screen.

### Shop Pulse
The signature element, kept and upgraded. It now carries a scope-style
readout — **peak day** and **daily average**, both computed from the same
real series the trace is drawn from. Trace, fill gradient, and glow are
all theme-driven, so it reads correctly on white as well as black.

### Keyboard
- `Ctrl` / `Cmd` + `K` focuses global search.
- `Esc` closes the drawer and the notification dropdown, and blurs search.

### Print
A global print stylesheet now hides app chrome (sidebar, top bar, bottom
nav, util bar, action buttons) and resets the page to black on white.
Printing from any page behaves. The paper invoice, thermal receipt, EOD
report, and label sheet templates were deliberately left untouched.

---

## Bugs fixed along the way

**1. The POS depended on `cdn.tailwindcss.com` at runtime.**
With no internet the entire till rendered as unstyled text — and that CDN
build is explicitly not intended for production. Every utility class the
POS relied on is now defined natively in section 21 of `style.css` and the
`<script>` tag is gone. The POS renders identically with the network
unplugged, and loads faster.

**2. Broken search inputs on Products, Customers, and Invoices.**
An inline SVG icon was being interpolated into a `placeholder=""`
attribute (`placeholder="{{ icon('search') }} Search by…"`). The `<svg`
broke out of the attribute and leaked raw markup onto the page. All three
are now proper search fields with the icon as a sibling element.

**3. PWA manifest colours** still referenced the old palette; updated,
along with light/dark `theme-color` meta tags.

---

## Files touched

| File | Change |
|---|---|
| `static/style.css` | Rewritten |
| `static/manifest.json` | Colours |
| `templates/base.html` | New app shell |
| `templates/login.html` | New lock screen |
| `templates/pos.html` | Tailwind CDN removed, tokenised |
| `templates/products.html`, `customers.html`, `invoices.html` | Search field bug fixed, tokenised |
| `templates/dashboard.html` | Pulse readout added, tokenised |
| `cashup / customer_detail / eod_report / layaway_detail / reports / settings / smtp_diagnose / staff` | Tokenised |
| `app/icons.py` | Added `sun` and `moon` icons |

`app/icons.py` is the only Python file changed, and the change is purely
additive — two new entries in the `ICONS` dict.

---

## Notes for deployment

- The stylesheet link carries `?v=31` so shop machines pick up the new CSS
  without a hard refresh.
- The service worker does not cache assets, so nothing else is stale.
- If you would rather the app follow the operating system's light/dark
  setting instead of defaulting to dark, change one line in the head
  script of `templates/base.html`:

  ```js
  if(!t) t = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  ```

- To reskin the whole app to a different accent, edit `--accent`,
  `--accent-hover`, `--on-accent`, `--accent-text`, `--accent-soft`,
  `--accent-border`, and `--accent-glow` in the two theme blocks at the
  top of `style.css`. Nothing else needs touching.

---

## Brand assets (v31.1)

The real **tech-pro+** wordmark is now in the product, not a stand-in
wrench glyph.

### Two colourways, one artwork

The supplied logo is white-and-red on a solid black field. Shipping that
file as-is only works on a black background, so the black was keyed out
(brightest-channel alpha, un-premultiplied so the antialiased edges don't
fringe grey) and two transparent colourways were produced:

| File | Marks | Used by |
|---|---|---|
| `static/logo-light.png` | White + red plus | Dark theme UI |
| `static/logo-dark.png` | Ink `#101520` + red plus | Light theme UI, invoices, receipts |

Both are in the page; CSS shows exactly one based on `data-theme`, so the
logo switches with the theme and never disappears into its background.
The red plus is untouched in both.

### Where it appears

- Sidebar header (links to the dashboard), above a "Repair & Retail" line
- Mobile top bar
- PIN lock screen
- A4 invoice and thermal receipt

### App icons regenerated

The old `icon-192.png` / `icon-512.png` were the wordmark squeezed into a
square — it cropped mid-word to "ech-pr" and was unreadable at any size.
Replaced with the distinctive plug-**e** glyph, extracted from the
wordmark by column-profiling the artwork, set on a `#0B0D12` tile with the
red plus, and sized to sit inside the maskable safe circle.

### Print fix

The invoice and thermal receipt were both pulling `static/logo.jpg` — the
black-background version. On white paper that printed as a solid black
rectangle, and on a thermal printer it burned a full-width black band on
every single receipt. Both now use the ink colourway on transparency.
`logo.jpg` is left in place, unused, in case anything else references it.

---

## v32 — POS: no more full-page reloads

Every cart-mutating action on the POS screen — add, remove, change qty,
apply a discount, attach a customer, redeem points/credit, hold/recall a
cart, scan a barcode — used to be a full page `POST` → `303 redirect` →
full `GET` reload. That's now a `fetch()` that swaps just the cart panel
back in. Verified end-to-end in a real browser: **zero page navigations**
across a full session (add → qty → discount → payment switch → remove →
scan success → scan failure → hold → recall).

**Checkout and "Start Layaway" still do a real navigation** — on purpose,
since they take you to a different page (the invoice, the layaway) to
show the result of the sale. Nothing else about POS behavior changed:
same routes, same validation, same session model, same audit logging.

### How it works
- `templates/partials/pos_cart.html` is the cart/payment column, rendered
  from a new shared `pos_cart_context()` helper in `app/main.py`.
- Every mutating POS route now ends in `pos_response(request, db)`
  instead of an unconditional redirect: if the request carries an
  `X-Pos-Ajax` header (the till's own JS sets this), it returns just that
  partial as HTML; otherwise it does the exact original full-page
  redirect. **This means the app works identically with JavaScript off**
  — nothing here is JS-only, the AJAX path is additive.
- The front-end is a single delegated `submit` listener (survives every
  DOM swap without re-binding), plus a `posAjaxSubmit()` that does the
  fetch, swaps `#cart-panel`, and resyncs the handful of client-side-only
  state that lives outside the swapped markup: the `TOTAL` JS variable,
  the active payment-pill highlight, and (new, wasn't preserved even
  before) the tendered/split-payment amounts and cart scroll position.

### Bug caught during this pass
The qty +/- buttons carry their value via `<button name="qty"
value="...">`, not a real input field — that's normal for a plain HTML
form submit, but a bare `new FormData(form)` in JS does **not** include a
clicked button's name/value (only real fields). Missing that would have
sent qty updates with no `qty` field, silently falling back to a real
navigation on every single tap of the + or − button — i.e., the exact
thing this change was meant to eliminate, on the single most-used control
on the screen. Fixed by capturing the native `SubmitEvent.submitter` and
folding its name/value into the FormData manually.

---

## v37 — Scan now opens a price-check step, not a direct add

Scanning a barcode used to add straight to the cart at whatever price was
on file — no chance to catch a wrong price, and no way to apply an
on-the-spot discount without going back and editing the line afterward.
It now hands the scanned product to the exact same price-check modal a
tapped tile already opens: price field pre-selected and editable, "Add to
Cart" only fires once confirmed. A customer asking for a better price on
a case is now a normal part of the scan flow, not a workaround.

This only changes the AJAX (JS-enabled) path — the real, everyday one.
The non-AJAX fallback (JS failed, a stale tab, curl) still adds directly,
unchanged, since there's no way to show a modal at all without JS.

**Also included in this build:** every round of work from this project so
far — v31 through v36 (full UI redesign, real branding, instant POS,
payment reconciliation, the checkout-order reminder, the error-handling
sweep, and the embedded email receipt logo) — confirmed present via a
full recursive content diff against the working copy before packaging,
not just a filename check (a filename-only check is exactly what let a
stale copy slip through once already this round).

### Files touched
| File | Change |
|---|---|
| `app/main.py` | `/pos/scan` forks on the AJAX header — JSON lookup response instead of a direct cart mutation for the JS path; non-AJAX path unchanged |
| `templates/pos.html` | New `#scan-feedback` banner, `handleScanSubmit()`, delegated listener special-cases the scan form, dead `isScan` branch in `posAjaxSubmit()` removed |
| `tests/test_ui_improvements.py` | 4 new tests covering the AJAX scan path specifically, since every existing scan test only ever exercised the non-AJAX fallback |

---

## v38 — Add new phone models to the checklist yourself

The Bulk-Create Variants checklist was a fixed list baked into the code
— new phones ship every year, and the only way to include one not
already on the list was retyping it into the free-text box, every
single time, for every batch. It never became a real checkbox.

Now there's an "Add to checklist" box right in the Phone Models section:
type a brand and a model — including one that hasn't launched yet, like
an upcoming iPhone or Galaxy S series — and it's a permanent checkbox
from then on, indistinguishable from the built-in ones, with a small "✕"
to remove it if it was a mistake. Stored in the existing Settings table,
not a new database table — no migration needed.

A real bug surfaced while writing tests for this: the add-model route
declared its fields as strictly required (`Form(...)`), which meant a
genuinely blank submission crashed into FastAPI's raw JSON 422 instead of
a friendly message — the exact class of thing `settings_save()` elsewhere
in this app already deliberately avoids. Fixed to match.

Verified in an actual browser, not just the test suite: added a model,
confirmed it's a real checkbox, confirmed it survives a full page reload
(not just a JS trick), removed it, confirmed it's gone after reload too.

### Files touched
| File | Change |
|---|---|
| `app/main.py` | `get_custom_phone_models()`, `merged_phone_models()`, two new routes (add/remove), `bulk_variants_form()` now serves the merged list |
| `templates/bulk_variants.html` | New add-model box, per-model "✕" for custom entries, two standalone forms (can't nest inside the existing generate-variants form) |
| `tests/test_bulk_variants.py` | 12 new tests — add, persistence, duplicate/case-insensitive detection, remove, built-in models staying protected, permissions, and a full end-to-end variant generation using a freshly-added model |

---

## v39 — Automatic weekly backup, emailed as an attachment

The manual "Download Full Backup" button already existed and already
worked correctly regardless of database (SQLite locally, Postgres on
Render or Railway — it's plain SQLAlchemy queries, nothing platform-
specific). What didn't exist: anything automatic. Someone had to
remember to click it.

Now there's a second option, additive to the first: a scheduled job that
runs every Sunday (same hour as the existing daily digest) and emails a
full backup as a real attachment — products, customers, repairs,
invoices, settings — through whichever email path is already configured,
SMTP or Brevo. A "Send Test Backup Now" button in Settings confirms the
whole pipeline actually works today, rather than finding out in a week
whether it does.

Also fixed in passing: the Data tab told people their backup was "one
SQLite file, just copy it" — true for local testing, actively wrong
advice once deployed to Postgres. Replaced with a pointer to the two
real options.

**Two bugs caught while building this, not after:**
- A `str_replace` boundary mistake left `/export/backup`'s route
  decorator sitting on top of a plain helper function instead of the
  actual route handler — would have silently broken the existing manual
  backup button. Caught immediately by checking the diff right after the
  edit, before moving on to anything else.
- Leftover draft code (an `if False else None` placeholder, a shadowed
  local import) from mid-edit fumbling with a missing `datetime` import
  — not a functional bug, but cleaned up rather than left in.

Verified past the mock layer where it mattered: decoded an actual MIME
message built by the SMTP path and confirmed the attachment survives
real email encoding intact, not just that a function got called.

### Files touched
| File | Change |
|---|---|
| `app/notifications.py` | `send_backup_email()`; attachment support added to `_send_via_brevo_api()` |
| `app/main.py` | `build_backup_json()`/`backup_filename()` (shared by both the manual button and the new job — one place decides what a backup contains), `run_weekly_backup_email_job()`, `_schedule_background_jobs()` (renamed from `_schedule_digest()`, now registers both jobs), new `/settings/send-test-backup` route, two new Settings fields |
| `templates/settings.html` | Weekly Data Backup Email section, Send Test Backup card, corrected the stale "copy the SQLite file" line |
| `tests/test_backup_email.py` | New — 16 tests covering the send logic (both email paths, MIME-decoded), the routes, permissions, settings persistence, and the scheduled job's own conditional logic |

---

## v40 — Printable receipt for trade-ins

Trade-Ins had no printable document at all — every other transaction
type (a sale, a layaway) gets something to hand the customer; trade-ins
didn't. Added a "Print" link on every row of the Trade-Ins table, opening
a receipt in the same warm-paper, forest-green visual language as the
invoice print view, so every printed document in this shop looks like it
came from the same place.

Also gave trade-ins a real reference number (`TR-1000`, `TR-1001`, ...),
matching how invoices, layaways, and purchase orders already work —
previously a trade-in had only its internal database id, which is not
something you'd want printed on a customer-facing receipt or referenced
later if a trade-in ever needed to be looked up. Existing trade-ins from
before this change fall back to a shortened version of their id, so
nothing breaks for records that predate the new number field.

**A real bug in my own test script, caught and fixed before it could
produce a false result:** the first end-to-end browser check opened the
receipt page in `browser.new_page()` — a fresh, separate context with no
login session — so the receipt correctly redirected to the login page,
and every content assertion failed as a result. Diagnosed by checking
the page's actual URL after navigation rather than assuming the content
checks were reporting on the app; fixed by reusing the same authenticated
page instead of opening an unauthenticated one.

### Files touched
| File | Change |
|---|---|
| `app/models.py` | `TradeIn.number` |
| `app/seed.py` | Migration default for the new column |
| `app/main.py` | `next_trade_in_number()`, `trade_in_add()` now sets it, new `/trade-ins/{id}/print` route |
| `templates/trade_in_receipt.html` | New — reuses the invoice print view's exact CSS classes and visual language |
| `templates/trade_ins.html` | New "Print" link per row |
| `tests/test_new_features.py` | 16 new tests — sequential numbering, receipt content, the bad-id/login-required guards, and the pre-migration blank-number fallback |

---

## v40 — Trade-ins get a real receipt

Trade-ins had no printable document at all — accept one, and there was
nothing to hand the customer. Fixed with the same "eco-elegant" paper
look already used for invoices, since this is equally something handed
across the counter, not an internal document.

Found this partially built already (the model field, the number
generator, and the print route existed, but the template the route
pointed at didn't — a live TemplateNotFound waiting to happen the moment
anyone clicked it). Finished it properly rather than leaving a route that
crashes on first use:
- Every trade-in gets a real reference number (TR-1000, TR-1001, ...)
  instead of a raw internal ID
- A prominent "Print This Receipt" banner appears right after accepting
  one — no hunting through the table for the row that was just added
- A persistent "Print" link on every row, for reprinting an older one
  anytime
- The reference number is now visible in the list table itself, not just
  on the printed receipt — otherwise "can you check on TR-1004" would
  have nowhere to be looked up

A real bug in my own test, caught before it could hide anything: the
first version of the "banner shows right after adding" test used
`TestClient.post()`, which follows redirects by default — meaning the
POST call itself already reached `/trade-ins` and consumed the one-time
banner internally, before the test's own separate `.get()` call ran
against an already-consumed session flag. The app was correct throughout;
the test was checking the wrong response.

### Files touched
| File | Change |
|---|---|
| `templates/trade_ins.html` | "#" reference-number column, "Print This Receipt" banner tied to the just-added trade-in |
| `tests/test_new_features.py` | 3 new tests for the banner and the number column, on top of the substantial existing trade-in coverage |

---

## v41 — Trade-ins in Reports and Month-End, plus Send Test SMS

Trade-ins were invisible everywhere outside their own page. Now:

- **Reports page**: a "Trade-Ins — this month" card — accepted count,
  cash paid out, store credit issued, total. Kept deliberately separate
  from revenue/profit above it, matching the TradeIn model's own existing
  design: a trade-in isn't a sale.
- **Month-End Workbook**: a fourth sheet, "Trade-Ins", listing every one
  for the selected month with a Cash Paid Out / Store Credit Issued
  totals footer — the same level of detail a bookkeeper already gets for
  invoices.
- **Send Test SMS**: mirrors the existing Send Test Email button, in
  Settings → Notifications, next to the Twilio fields.

**A real, connected bug found and fixed while doing this, not left for
later:** Cash Up's drawer reconciliation never accounted for cash
trade-in payouts — real money leaving the till that wasn't in either of
its two existing sources (Invoice cash_amount, LayawayPayment rows).
Without this, a $75 cash trade-in would have shown up at close-out as an
unexplained $75 shortage that wasn't a shortage at all. Confirmed live,
not just in tests: Cash Sales read $0.00 before a $75 cash trade-in,
-$75.00 (correctly styled as a net outflow) after it. Store-credit
payouts correctly don't touch this at all — they show up in
Reports/Month-End instead, as a liability rather than a cash movement.

Verified past the test suite: hit the real routes with curl, downloaded
the actual Month-End workbook, and parsed it with openpyxl to confirm
the sheet, the row, and the totals footer all came back correct.

### Files touched
| File | Change |
|---|---|
| `app/main.py` | `todays_cash_card_totals()` now subtracts today's cash trade-in payouts; `reports_page()` computes the trade-in summary; `export_month_end_xlsx()` gets a fourth sheet; new `/settings/send-test-sms` route |
| `templates/reports.html` | New Trade-Ins summary card |
| `templates/settings.html` | New Send Test SMS card |
| `tests/test_reports_trade_ins.py` | New — 9 tests covering the Reports card, the actual parsed XLSX content, and the Cash Up math with before/after comparisons |
| `tests/test_new_features.py` | 3 new tests for the Send Test SMS route |

---

## v42 — Profit now accounts for repair parts cost

The Profit figure on Reports was wrong every time a repair invoice was in
the mix — a repair charge line has no product attached (it can't, there's
no single "product" for a repair), so nothing in the normal per-line
profit calculation caught its cost. `repair_detail.html` already computed
a correct per-ticket margin (charge minus parts actually used, via
RepairPart) — that math just never reached the monthly roll-up. Every
repair charge counted as 100% pure profit, no matter how much real parts
cost went into it.

Fixed by pre-fetching parts cost per repair once (avoiding an N+1 query
across however many repair-linked invoices exist), then subtracting it
once per invoice — scoped to the invoice, not the individual line, so a
repair ticket with more than one charge line can't have its parts cost
subtracted twice.

Confirmed with 5 new tests hitting the real /reports route and parsing
the actual rendered figures — not mocked math. A $150 repair charge with
$35 of real parts cost now correctly contributes $115 to profit, not
$150; a repair with zero parts still correctly counts its full charge;
multiple parts on one ticket sum correctly; a plain product sale with no
repair attached is provably untouched by the fix.

### Files touched
| File | Change |
|---|---|
| `app/main.py` | `reports_page()` — repair parts cost now subtracted from profit, added to COGS |
| `tests/test_business_logic.py` | 5 new tests proving the fix against the real reports page output |

---

## v43 — Products and Customers pagination

Both pages used to load every row that had ever existed, always — fine
at a few hundred rows, quietly slower every month as the catalog and
customer base grow, with nothing that looks broken along the way.

Found this already substantially built from earlier work — both routes
and both templates were genuinely complete, including the harder case:
Products has variant groups (one case style can be 90+ SKUs), and
splitting a group across two pages would show each half looking
incomplete. The existing solution treats one group, however many
variants it contains, as a single unit for pagination purposes — genuinely
correct handling of a case that isn't obvious at first glance.

What was actually missing was verification: a dedicated test file
existed but had never been run to confirm it passes, and nothing had
confirmed live that page 1 and page 2 genuinely show different rows, or
that stats (low stock count, stock value, store credit total) still
reflect every row and not just the current page's 50.

Confirmed both ways:
- 17 existing tests, run for the first time this round — all pass
- Live HTTP verification: seeded 84 products / 80 customers, confirmed
  page 1 and page 2 show different rows, confirmed search finds a result
  that would otherwise be on page 2 without needing to page there, all
  via real GET requests against a running server, not mocked

Design: browsing is paginated at 50 per page; searching or drilling into
one phone's cases overrides pagination entirely and checks everything,
since narrowing results to "whatever's on this page" would silently hide
the thing being searched for.

### Files touched
This round was verification, not new code — `app/main.py`,
`templates/products.html`, `templates/customers.html`, and
`tests/test_pagination.py` were already in place; nothing changed.
