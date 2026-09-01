# Wash Works Inc. — website

Custom-coded marketing site for [washworkscws.com](https://washworkscws.com).
Flask + Jinja templates, served by gunicorn, deployed to Render. No CMS, no
template builder — moved off GoDaddy's builder deliberately.

## Run locally

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # then fill in values
python app.py                 # http://localhost:5000
```

`app.py` reloads `content/site.json` on every request in debug mode, so copy
edits show up on refresh without a restart.

## How this project is organised

| Path | What it is |
|------|-----------|
| `app.py` | Routes, contact-form handling, schema, sitemap/robots |
| `content/site.json` | **All editable copy.** Change text here, not in templates |
| `templates/base.html` | The one layout every page inherits — head, nav, footer, schema |
| `templates/partials/` | Header, footer, and the pending-item marker |
| `static/css/style.css` | Design system. Every navy derives from `#003274` |
| `tools/build_assets.py` | Regenerates the logo + favicon set from the source PNG |
| `brand-source/` | The three client-supplied PNGs + the original handoff |
| `data/submissions.jsonl` | Contact-form submissions (gitignored, created at runtime) |

## Editing content

`content/site.json` drives the site. Two conventions:

- **Any value left `null` is an unanswered question.** The page shows a visible
  `PENDING` marker instead of inventing content. Search the rendered site (or
  the server log at startup) for these before launch.
- **Keys beginning `_` are notes to whoever edits the file** — the discovery
  item they trace to, and what is needed. They never render.

To feature a service (give it its own page), set `"featured": true` and write
its `"body"`. Until `body` is filled the page shows the summary and a quote CTA.

## Brand assets

Regenerate everything from the single usable source PNG:

```bash
python tools/build_assets.py
```

There is no vector source (discovery item **A-1**), so these are traced from
raster. A vector from the original designer would still be an upgrade — the
build tool prints that reminder every run.

## Before this goes live

The site is built, but it is **not launch-ready** until the blocking discovery
items are answered. `app.py` logs the outstanding ones at startup. The five that
genuinely gate launch:

1. **L-1** — CSLB contractor license number (legally required in all advertising)
2. **L-2** — UL508A file number + mark authorisation
3. **L-4** — privacy policy reviewed
4. **A-6** — licensed photography (no unlicensed stock)
5. **O-2** — a rehearsed DNS cutover that does not break email

See the discovery brief for the full list and who owns each item.

## Deploy (Render)

Push to GitHub, connect the repo in Render — `render.yaml` is picked up
automatically. Set the `sync: false` secrets in the dashboard. Use the paid
`starter` plan, not free (see **T-1** in the blueprint for why).
