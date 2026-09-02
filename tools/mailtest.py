"""Standalone checker for the contact-form mail settings.

Reads .env exactly the way app.py does, then walks whichever transport is
configured - Mailgun's HTTP API, SMTP, or both - one step at a time, so you
know precisely where it fails without going through the whole Flask app.

Mirrors notify()'s own order: API first (works on any host/plan - see the
.env.example note on why SMTP alone doesn't work on Render's free tier),
falling back to SMTP.

    python tools/mailtest.py            # check whichever is configured
    python tools/mailtest.py --send     # also send one real test email
    python tools/mailtest.py --api      # force-test only the API path
    python tools/mailtest.py --smtp     # force-test only the SMTP path
"""

import base64
import os
import re
import smtplib
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("! python-dotenv not installed in this interpreter - run with .venv")


def mask(v):
    if not v:
        return "(EMPTY)"
    return f"{v[:2]}..{v[-2:]} (len {len(v)})"


SEND = "--send" in sys.argv
FORCE_API = "--api" in sys.argv
FORCE_SMTP = "--smtp" in sys.argv

sender = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("CONTACT_FROM")
to_address = os.getenv("CONTACT_TO")

print("=" * 60)
print("Shared settings")
print("=" * 60)
print(f"  MAIL_DEFAULT_SENDER  {sender or '(EMPTY)'}")
print(f"  CONTACT_TO           {to_address or '(EMPTY)'}")


def test_api():
    api_key = os.getenv("MAILGUN_API_KEY")
    domain = os.getenv("MAILGUN_DOMAIN")
    base_url = os.getenv("MAILGUN_API_BASE", "https://api.mailgun.net/v3")

    print("\n" + "=" * 60)
    print("Mailgun HTTP API")
    print("=" * 60)
    print(f"  MAILGUN_API_KEY      {mask(api_key)}")
    print(f"  MAILGUN_DOMAIN       {domain or '(EMPTY)'}")
    print(f"  MAILGUN_API_BASE     {base_url}")

    missing = [n for n, v in (("MAILGUN_API_KEY", api_key), ("MAILGUN_DOMAIN", domain),
                              ("MAIL_DEFAULT_SENDER", sender))
               if not v]
    if missing:
        print(f"  [ ] not configured - missing {', '.join(missing)}")
        return None

    url = f"{base_url}/{domain}/messages"
    data = {"from": sender, "to": to_address or "test@example.com",
           "subject": "Wash Works API test", "text": "API path connectivity check."}
    req = urllib.request.Request(url, data=urllib.parse.urlencode(
        data if SEND else {**data, "o:testmode": "yes"}).encode(), method="POST")
    req.add_header("Authorization",
                   "Basic " + base64.b64encode(f"api:{api_key}".encode()).decode())

    if not SEND and not to_address:
        # Mailgun's test-mode still needs a syntactically valid recipient.
        data["to"] = "mailtest@example.com"

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read(500).decode("utf-8", "replace")
        if e.code == 401:
            print("  [x] AUTH rejected (401). MAILGUN_API_KEY is wrong - get the")
            print("      'Private API key' from Mailgun -> Settings -> API Keys.")
        elif e.code == 404:
            print(f"  [x] domain not found (404). Is '{domain}' exactly what shows")
            print("      as Verified under Mailgun -> Sending -> Domains?")
        else:
            print(f"  [x] HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        print(f"  [x] transport error: {e}")
        return False

    if SEND:
        if not to_address:
            print("  [x] --send needs CONTACT_TO set to a real inbox.")
            return False
        print(f"  [OK] test email accepted for delivery to {to_address}")
        print("       (check the inbox - and the spam folder - in a minute)")
    else:
        print("  [OK] API reachable, key and domain accepted (sent in test mode -")
        print("       Mailgun validated the request but did not actually send it)")
    return True


def test_smtp():
    server = os.getenv("MAIL_SERVER")
    port = int(os.getenv("MAIL_PORT", "587"))
    username = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes", "on")
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes", "on")

    print("\n" + "=" * 60)
    print("SMTP")
    print("=" * 60)
    print(f"  MAIL_SERVER          {server or '(EMPTY)'}")
    print(f"  MAIL_PORT            {port}   tls={use_tls}  ssl={use_ssl}")
    print(f"  MAIL_USERNAME        {username or '(EMPTY)'}")
    print(f"  MAIL_PASSWORD        {mask(password)}")

    missing = [n for n, v in (("MAIL_SERVER", server), ("MAIL_USERNAME", username),
                              ("MAIL_PASSWORD", password), ("MAIL_DEFAULT_SENDER", sender))
               if not v]
    if missing:
        print(f"  [ ] not configured - missing {', '.join(missing)}")
        return None

    pw = password.strip()
    if pw.lower().startswith("key-") or re.fullmatch(r"[0-9a-f]{32}-[0-9a-f]{8}-[0-9a-f]{8}", pw.lower()):
        print("  [!] MAIL_PASSWORD is shaped like a Mailgun API key. Some Mailgun")
        print("      accounts DO accept this as the SMTP password too - the login")
        print("      check below is the real test, not this shape check.")

    print(f"  -> connecting to {server}:{port} ...")
    try:
        smtp = smtplib.SMTP_SSL(server, port, timeout=15) if use_ssl else smtplib.SMTP(server, port, timeout=15)
    except socket.gaierror:
        print(f"  [x] DNS: cannot resolve '{server}' (US=smtp.mailgun.org, EU=smtp.eu.mailgun.org)")
        return False
    except (socket.timeout, TimeoutError, ConnectionRefusedError, OSError) as e:
        print(f"  [x] CONNECT timed out/failed: {e}")
        print(f"      If this is a Render FREE web service, this is expected - Render")
        print(f"      blocks outbound SMTP (25/465/587) on Free entirely. Either use")
        print(f"      the Mailgun API above, or move this service to a paid plan.")
        return False
    print("  [OK] connected")

    try:
        with smtp:
            smtp.ehlo()
            if use_tls and not use_ssl:
                smtp.starttls()
                smtp.ehlo()
                print("  [OK] STARTTLS ok")
            try:
                smtp.login(username, password)
            except smtplib.SMTPAuthenticationError as e:
                print(f"  [x] LOGIN rejected ({e.smtp_code}). Check MAIL_USERNAME/MAIL_PASSWORD,")
                print(f"      or that the domain is in the right region (EU vs US host).")
                return False
            print("  [OK] login accepted - credentials are correct")

            if SEND:
                if not to_address:
                    print("  [x] --send needs CONTACT_TO set to a real inbox.")
                    return False
                msg = EmailMessage()
                msg["Subject"] = "Wash Works SMTP test"
                msg["From"] = sender
                msg["To"] = to_address
                msg.set_content("SMTP path connectivity check.")
                try:
                    smtp.send_message(msg)
                except smtplib.SMTPRecipientsRefused:
                    print(f"  [x] SEND refused for {to_address}. On a Mailgun SANDBOX domain")
                    print(f"      the recipient must be an Authorized Recipient.")
                    return False
                print(f"  [OK] test email accepted for delivery to {to_address}")
    except smtplib.SMTPException as e:
        print(f"  [x] SMTP error: {e}")
        return False
    return True


results = {}
if FORCE_API:
    results["api"] = test_api()
elif FORCE_SMTP:
    results["smtp"] = test_smtp()
else:
    results["api"] = test_api()
    results["smtp"] = test_smtp()

print("\n" + "=" * 60)
if any(v is True for v in results.values()):
    working = [k for k, v in results.items() if v is True]
    print(f"[OK] working: {', '.join(working)}. notify() tries API first, then SMTP,")
    print("     so the contact form will send as long as one of these is green.")
    sys.exit(0)
elif any(v is False for v in results.values()):
    print("[x] configured but failing - see the [x] lines above for why.")
    sys.exit(1)
else:
    print("[ ] nothing is configured yet. Fill in .env (NOT .env.example), the API")
    print("    block is the one to prioritize - see the comment there for why.")
    sys.exit(1)
