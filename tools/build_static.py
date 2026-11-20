"""Build the static copy of the site that Cloudflare serves (dist/).

    python tools/build_static.py             # production build (indexable)
    python tools/build_static.py --noindex   # staging copy: robots.txt blocks crawlers

The Flask app stays the single source of truth. This asks it, in-process, for every
page listed in sitemap.xml plus robots.txt, sitemap.xml and the 404 page, writes each
as <path>/index.html, and copies static/. What you preview with `python app.py` is
exactly what ships. The only dynamic piece, the contact form, lives in worker/index.js.

Run it with the project's Python (the one that has Flask), e.g. .venv\\Scripts\\python.exe
"""

import argparse
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_FILE_BYTES = 25 * 1024 * 1024    # Cloudflare rejects static files larger than this
MAX_FILES = 20000                    # ...and more files than this per deploy (free plan)

# Cloudflare reads this file (it is not served). Mirrors app.py's security_headers()
# and gives static files sensible cache lifetimes. /static/video/* is served by the
# Worker, which sets its own headers.
HEADERS = """\
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN

/static/img/*
  Cache-Control: public, max-age=2592000
/static/favicon/*
  Cache-Control: public, max-age=2592000
/static/fonts/*
  Cache-Control: public, max-age=31536000, immutable
/static/css/*
  Cache-Control: public, max-age=86400
/static/js/*
  Cache-Control: public, max-age=86400
"""


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Build the static site into dist/ for Cloudflare.")
    ap.add_argument("--noindex", action="store_true",
                    help="staging build: robots.txt disallows everything")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="output folder (default dist/)")
    args = ap.parse_args()

    # Decide indexing BEFORE importing the app: it reads NOINDEX at import and per request.
    os.environ["NOINDEX"] = "1" if args.noindex else "0"
    sys.path.insert(0, ROOT)
    import app as site

    base = f"https://{site.CANONICAL_HOST}"      # real canonical/og URLs, never localhost
    client = site.app.test_client()

    def fetch(path, expect=200):
        resp = client.get(path, base_url=base)
        if resp.status_code != expect:
            sys.exit(f"build failed: GET {path} returned {resp.status_code}, expected {expect}")
        return resp.get_data()

    out = os.path.abspath(args.out)
    if os.path.exists(out):
        # dist/ is generated and git-ignored. Refuse to wipe anything else.
        if os.path.basename(out) != "dist" and os.listdir(out):
            sys.exit(f"refusing to overwrite {out}: not named 'dist' and not empty")
        shutil.rmtree(out)

    sitemap = fetch("/sitemap.xml").decode("utf-8")
    paths = re.findall(r"<loc>https://[^/<]+(/[^<]*)</loc>", sitemap)
    if not paths:
        sys.exit("build failed: sitemap.xml listed no pages")

    pages = []
    for path in paths:
        html = fetch(path)
        if b"localhost" in html or b"127.0.0.1" in html:
            sys.exit(f"build failed: {path} contains a localhost URL")
        write(os.path.join(out, path.lstrip("/"), "index.html"), html)
        pages.append(path)

    write(os.path.join(out, "sitemap.xml"), sitemap)
    write(os.path.join(out, "robots.txt"), fetch("/robots.txt"))
    write(os.path.join(out, "404.html"), fetch("/this-page-does-not-exist/", expect=404))
    write(os.path.join(out, "_headers"), HEADERS)

    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(out, "static"),
                    ignore=shutil.ignore_patterns(".gitkeep"))
    favicon = os.path.join(ROOT, "static", "favicon", "favicon.ico")
    if os.path.isfile(favicon):                   # browsers ask for /favicon.ico regardless
        shutil.copy(favicon, os.path.join(out, "favicon.ico"))

    files = [os.path.join(d, f) for d, _, names in os.walk(out) for f in names]
    too_big = [f for f in files if os.path.getsize(f) > MAX_FILE_BYTES]
    if too_big:
        listing = "\n".join(f"  {os.path.relpath(f, out)}  {os.path.getsize(f) / 1048576:.1f} MB" for f in too_big)
        sys.exit(f"build failed: Cloudflare rejects static files over 25 MiB:\n{listing}\n"
                 "Shrink the hero video:  python tools/make_hero_video.py <your clip>")
    if len(files) > MAX_FILES:
        sys.exit(f"build failed: {len(files)} files; Cloudflare's free plan allows {MAX_FILES}")

    biggest = max(files, key=os.path.getsize)
    print(f"built {out}")
    print(f"  mode:     {'STAGING (robots.txt blocks crawlers)' if args.noindex else 'production (indexable)'}")
    print(f"  pages:    {len(pages)}  ->  " + ", ".join(pages[:4]) + (" ..." if len(pages) > 4 else ""))
    print(f"  files:    {len(files)}  ({sum(os.path.getsize(f) for f in files) / 1048576:.1f} MB total)")
    print(f"  largest:  {os.path.relpath(biggest, out)}  ({os.path.getsize(biggest) / 1048576:.2f} MB, limit 25)")
    print(f"  canonical host: {site.CANONICAL_HOST}")


if __name__ == "__main__":
    main()
