"""Wash Works Inc. - washworkscws.com

Content lives in content/site.json so copy changes do not require touching
templates (discovery item O-3). Anything still unanswered is null there, and the
templates hide it rather than inventing a value.
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone

from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, url_for)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional in production
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_PATH = os.path.join(BASE_DIR, "content", "site.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
SUBMISSIONS_PATH = os.path.join(DATA_DIR, "submissions.jsonl")

CANONICAL_HOST = os.getenv("CANONICAL_HOST", "washworkscws.com")
# S-2: if washworkscw.com is ever reclaimed, add it here and it gets 301'd.
LEGACY_HOSTS = {h.strip() for h in os.getenv("LEGACY_HOSTS", "").split(",") if h.strip()}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-not-for-production")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("washworks")


# ---------------------------------------------------------------------------
# content
# ---------------------------------------------------------------------------

def load_content():
    with open(CONTENT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


CONTENT = load_content()


@app.before_request
def reload_content_in_debug():
    """Pick up site.json edits without a restart while developing."""
    if app.debug:
        global CONTENT
        CONTENT = load_content()


def featured_services():
    return [s for s in CONTENT["services"] if s.get("featured")]


def service_by_slug(slug):
    return next((s for s in CONTENT["services"] if s["slug"] == slug), None)


def prune(value):
    """Drop empty values so unanswered fields are omitted from schema, not guessed."""
    if isinstance(value, dict):
        cleaned = {k: prune(v) for k, v in value.items() if not k.startswith("_")}
        return {k: v for k, v in cleaned.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [prune(v) for v in value if v not in (None, "", [], {})]
    return value


def local_business_schema():
    """S-4: LocalBusiness markup. Only asserts what the client has confirmed."""
    company = CONTENT["company"]
    address = company["address"]
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": company["name"],
        "url": f"https://{CANONICAL_HOST}/",
        "telephone": company["phone_display"],
        "email": company.get("email"),
        "foundingDate": company.get("founded"),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address["street"],
            "addressLocality": address["city"],
            "addressRegion": address["region"],
            "postalCode": address["postal_code"],
            "addressCountry": address["country"],
        },
        "areaServed": company.get("service_area"),
        "openingHoursSpecification": company.get("hours"),
    }
    return prune(schema)


@app.context_processor
def inject_content():
    company = CONTENT["company"]
    return {
        "site": CONTENT,
        "company": company,
        "featured_services": featured_services(),
        "canonical_url": request.base_url.replace("http://", "https://", 1),
        "business_schema": local_business_schema(),
        "current_year": datetime.now(timezone.utc).year,
    }


# ---------------------------------------------------------------------------
# host canonicalisation
# ---------------------------------------------------------------------------

@app.before_request
def redirect_legacy_hosts():
    host = request.host.split(":")[0]
    if host in LEGACY_HOSTS:
        return redirect(request.url.replace(host, CANONICAL_HOST, 1), code=301)
    return None


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", page_title=None,
                           meta_description="Car wash maintenance, installation, repair and "
                                            "UL508A motor control panels. Serving operators "
                                            "from Lodi, California.")


@app.route("/services/")
def services():
    return render_template("services.html", page_title="Services",
                           meta_description="Car wash maintenance, installation and repair - "
                                            "tunnel adjustments, conveyors, electrical, vacuums, "
                                            "reclaim and RO.")


@app.route("/services/<slug>/")
def service_detail(slug):
    service = service_by_slug(slug)
    if not service or not service.get("featured"):
        abort(404)
    return render_template("service_detail.html", service=service,
                           page_title=service["name"],
                           meta_description=service["summary"])


@app.route("/consulting/")
def consulting():
    return render_template("consulting.html", page_title="Consulting",
                           meta_description="Car wash consulting - proformas, traffic counts, "
                                            "site inspections, equipment recommendations and "
                                            "repair diagnostics.")


@app.route("/marketing/")
def marketing():
    return render_template("marketing.html", page_title="Marketing Services",
                           meta_description="Social media management and website design for "
                                            "car wash operators.")


@app.route("/motor-control-centers/")
def motor_control_centers():
    return render_template("mcc.html", page_title="Motor Control Centers",
                           meta_description="UL508A motor control panels for tunnel equipment, "
                                            "dryers, central vacuums and lighting control.")


@app.route("/about/")
def about():
    return render_template("about.html", page_title="About",
                           meta_description="Wash Works Inc. - car wash service, equipment and "
                                            "control panels from Lodi, California.")


@app.route("/contact/")
def contact():
    return render_template("contact.html", page_title="Contact",
                           meta_description="Contact Wash Works Inc. in Lodi, California. "
                                            "Call (209) 263-7086.")


@app.route("/privacy/")
def privacy():
    # L-4: CalOPPA requires this to exist and be conspicuously linked.
    return render_template("privacy.html", page_title="Privacy Policy",
                           meta_description="How Wash Works Inc. handles information submitted "
                                            "through this website.")


# ---------------------------------------------------------------------------
# contact form
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
MIN_FILL_SECONDS = 3


def persist(record):
    """Append the submission to disk before anything else can fail.

    T-5: the email is a notification, not the record. The precedent build
    reported success from its exception handler, so an expired API key silently
    dropped every lead. Writing first means a delivery failure costs a
    notification, never the enquiry itself.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SUBMISSIONS_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def notify(record):
    """Send the enquiry on. Returns True if it was delivered.

    T-4: send from an address on washworkscws.com once C-7 confirms which one,
    and add the provider to the existing SPF record rather than creating a
    second one. Reply-To is the submitter so replies work from the inbox.
    """
    api_key = os.getenv("MAILJET_API_KEY")
    secret = os.getenv("MAILJET_SECRET_KEY")
    to_address = os.getenv("CONTACT_TO") or CONTENT["company"].get("email")
    from_address = os.getenv("CONTACT_FROM")

    if not all([api_key, secret, to_address, from_address]):
        log.warning("notify skipped - mail not configured (blocked on C-7/T-4)")
        return False

    try:
        from mailjet_rest import Client
    except ImportError:
        log.error("notify failed - mailjet_rest not installed")
        return False

    lines = "".join(
        f"<p style='margin:4px 0'><strong>{k.replace('_', ' ').title()}:</strong> {v}</p>"
        for k, v in record["fields"].items() if v
    )
    payload = {"Messages": [{
        "From": {"Email": from_address, "Name": "Wash Works Website"},
        "To": [{"Email": to_address}],
        "ReplyTo": {"Email": record["fields"]["email"]},
        "Subject": f"Website enquiry - {record['fields'].get('subject') or 'General'}",
        "HTMLPart": f"<div style='font-family:sans-serif'>{lines}"
                    f"<p style='color:#666;font-size:12px'>Reference {record['id']}</p></div>",
    }]}

    try:
        result = Client(auth=(api_key, secret), version="v3.1").send.create(data=payload)
    except Exception:
        log.exception("notify failed - transport error, reference %s", record["id"])
        return False

    if result.status_code != 200:
        log.error("notify failed - mailjet returned %s, reference %s",
                  result.status_code, record["id"])
        return False
    return True


@app.route("/contact/submit", methods=["POST"])
def contact_submit():
    form = request.form

    # T-6: honeypot plus a fill-time floor. Both are invisible to real users.
    if form.get("company_website"):
        log.info("spam rejected - honeypot filled")
        return jsonify({"status": "success", "message": "Thank you. We will be in touch."})
    try:
        if time.time() - float(form.get("rendered_at", 0)) < MIN_FILL_SECONDS:
            log.info("spam rejected - submitted too fast")
            return jsonify({"status": "success", "message": "Thank you. We will be in touch."})
    except (TypeError, ValueError):
        pass

    fields = {k: form.get(k, "").strip() for k in
              ("name", "business", "email", "phone", "subject", "message")}

    missing = [k for k in ("name", "email", "message") if not fields[k]]
    if missing:
        return jsonify({"status": "error",
                        "message": f"Please fill in your {', '.join(missing)}.",
                        "fields": missing}), 400

    if not EMAIL_RE.match(fields["email"]):
        return jsonify({"status": "error",
                        "message": "That email address does not look right. Please check it.",
                        "fields": ["email"]}), 400

    record = {
        "id": uuid.uuid4().hex[:12],
        "received_at": datetime.now(timezone.utc).isoformat(),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "fields": fields,
    }

    try:
        persist(record)
    except OSError:
        log.exception("could not persist submission - refusing to claim success")
        return jsonify({"status": "error",
                        "message": "Something went wrong on our end. Please call "
                                   f"{CONTENT['company']['phone_display']} instead."}), 500

    delivered = notify(record)
    if not delivered:
        log.warning("submission %s saved but not emailed", record["id"])

    return jsonify({"status": "success",
                    "message": "Thank you. We have your message and will be in touch."})


# ---------------------------------------------------------------------------
# crawler files
# ---------------------------------------------------------------------------

@app.route("/robots.txt")
def robots():
    # O-1: the staging host must never be indexed alongside the live domain.
    if os.getenv("NOINDEX") == "1":
        body = "User-agent: *\nDisallow: /\n"
    else:
        body = ("User-agent: *\n"
                "Allow: /\n"
                "Disallow: /contact/submit\n\n"
                f"Sitemap: https://{CANONICAL_HOST}/sitemap.xml\n")
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    endpoints = ["index", "services", "consulting", "marketing",
                 "motor_control_centers", "about", "contact", "privacy"]
    urls = [url_for(e) for e in endpoints]
    urls += [url_for("service_detail", slug=s["slug"]) for s in featured_services()]

    entries = "".join(
        f"  <url><loc>https://{CANONICAL_HOST}{u}</loc>"
        f"<changefreq>monthly</changefreq></url>\n" for u in urls
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{entries}</urlset>\n")
    return Response(xml, mimetype="application/xml")


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html", page_title="Page not found"), 404


# ---------------------------------------------------------------------------

@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


def report_blockers():
    """Print what is still unanswered, so nobody ships past a blocker by accident.

    Interim copy (About, service bodies) counts as filled here - it is presentable
    for a client demo. These checks track the *client's own facts* still missing.
    """
    c = CONTENT["company"]
    checks = [
        ("C-7", "contact email on washworkscws.com", c.get("email")),
        ("C-1", "emergency response details", c.get("emergency", {}).get("available")),
        ("C-2", "service area", c.get("service_area")),
        ("C-8", "hours of operation", c.get("hours")),
        ("C-6", "testimonials", CONTENT.get("testimonials")),
        ("L-1", "CSLB licence NUMBER (licence itself confirmed)", c.get("license_number")),
    ]
    outstanding = [f"{ref} {label}" for ref, label, value in checks if not value]
    if outstanding:
        log.warning("still awaiting client input (%d): %s",
                    len(outstanding), "; ".join(outstanding))

    # Hard compliance guard: on the PUBLIC (indexed) instance, advertising the
    # licence without its number violates CA B&P 7030.5. Staging is NOINDEX=1.
    is_public = os.getenv("NOINDEX") != "1"
    if is_public and c.get("licensed") and not c.get("license_number"):
        log.warning("COMPLIANCE: public instance is advertising 'Licensed' with no "
                    "CSLB number (B&P 7030.5). Add company.license_number before "
                    "the indexed launch, or run staging with NOINDEX=1.")


report_blockers()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
