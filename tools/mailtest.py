"""Standalone checker for the contact-form mail settings (Resend).

Reads .env exactly the way app.py does, then walks the Resend send one step at
a time, so you know precisely where it fails without going through the whole
Flask app.

    python tools/mailtest.py          # validate key + domain (no real email)
    python tools/mailtest.py --send    # also send one real test email to CONTACT_TO

Keep all print() output ASCII - this runs in the Windows console (cp1252).
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("! python-dotenv not installed in this interpreter - run with .venv")

SEND = "--send" in sys.argv


def mask(v):
    if not v:
        return "(EMPTY)"
    return f"{v[:3]}..{v[-2:]} (len {len(v)})"


api_key = os.getenv("RESEND_API_KEY")
sender = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("CONTACT_FROM")
to_address = os.getenv("CONTACT_TO")

print("=" * 60)
print("Resend contact-form mail check")
print("=" * 60)
print(f"  RESEND_API_KEY       {mask(api_key)}")
print(f"  MAIL_DEFAULT_SENDER  {sender or '(EMPTY)'}")
print(f"  CONTACT_TO           {to_address or '(EMPTY)'}")
print()

missing = [n for n, v in (("RESEND_API_KEY", api_key),
                          ("MAIL_DEFAULT_SENDER", sender)) if not v]
if missing:
    print(f"[ ] not configured - missing {', '.join(missing)} in .env (NOT .env.example)")
    sys.exit(1)

if not api_key.startswith("re_"):
    print("[!] RESEND_API_KEY does not start with 're_' - Resend keys normally do.")
    print("    Double-check you copied the API key, not a domain ID or something else.\n")

# Without --send, use Resend's always-accepted test address so we exercise auth
# and the from-domain check without putting a real message in anyone's inbox.
recipient = to_address if SEND else "delivered@resend.dev"
if SEND and not to_address:
    print("[x] --send needs CONTACT_TO set to a real inbox.")
    sys.exit(1)

payload = json.dumps({
    "from": sender,
    "to": [recipient],
    "subject": "Wash Works mail check",
    "text": "If you are reading this, the contact form's mail path works.",
}).encode()

req = urllib.request.Request("https://api.resend.com/emails", data=payload, method="POST")
req.add_header("Authorization", f"Bearer {api_key}")
req.add_header("Content-Type", "application/json")
# Match app.py: Cloudflare in front of api.resend.com 403s the default
# "Python-urllib" User-Agent (Cloudflare error 1010).
req.add_header("User-Agent", "WashWorksWebsite/1.0 (+https://washworkscws.com)")

print(f"-> POST https://api.resend.com/emails  (to: {recipient})")
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read(300).decode("utf-8", "replace")
    print(f"  [OK] {resp.status} - {body}")
except urllib.error.HTTPError as e:
    detail = e.read(600).decode("utf-8", "replace")
    if "1010" in detail:
        print(f"  [x] Cloudflare blocked the request ({e.code}, error 1010) - the")
        print("      User-Agent header is missing or being stripped. This should")
        print("      not happen with the header app.py/mailtest.py now set.")
    elif "domain" in detail.lower() and e.code in (403, 422):
        print(f"  [x] rejected ({e.code}) - the 'from' domain is not verified in Resend:")
        print(f"      {detail}")
        print("      Resend dashboard -> Domains -> add the DNS records, wait for green.")
    elif e.code in (401, 403):
        print(f"  [x] AUTH rejected ({e.code}). RESEND_API_KEY is wrong or revoked.")
        print("      Resend dashboard -> API Keys -> create a fresh one.")
    else:
        print(f"  [x] HTTP {e.code}: {detail}")
    sys.exit(1)
except Exception as e:
    print(f"  [x] transport error: {e}")
    sys.exit(1)

print()
if SEND:
    print(f"[OK] test email accepted for delivery to {to_address}.")
    print("     Check the inbox - and the spam folder - in a minute. If it lands")
    print("     in spam, the domain's DNS (SPF/DKIM) needs another look.")
else:
    print("[OK] key and from-domain accepted. Run again with --send to put a real")
    print("     message in the CONTACT_TO inbox and confirm end-to-end delivery.")
sys.exit(0)
