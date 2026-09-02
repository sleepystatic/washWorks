"""Standalone SMTP checker for the contact-form mail settings.

Reads .env exactly the way app.py does, then walks the SMTP handshake one step
at a time and tells you precisely where it fails - connect, STARTTLS, login, or
send - so you are not debugging mail through the whole Flask app.

    python tools/mailtest.py            # check connect + login only
    python tools/mailtest.py --send     # also send one real test email to CONTACT_TO
"""

import os
import smtplib
import socket
import sys

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

server = os.getenv("MAIL_SERVER")
port = int(os.getenv("MAIL_PORT", "587"))
username = os.getenv("MAIL_USERNAME")
password = os.getenv("MAIL_PASSWORD")
sender = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("CONTACT_FROM")
to_address = os.getenv("CONTACT_TO")
use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes", "on")
use_tls = os.getenv("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes", "on")

print("=" * 60)
print("Loaded mail settings")
print("=" * 60)
print(f"  MAIL_SERVER          {server or '(EMPTY)'}")
print(f"  MAIL_PORT            {port}")
print(f"  MAIL_USE_TLS/SSL     tls={use_tls}  ssl={use_ssl}")
print(f"  MAIL_USERNAME        {username or '(EMPTY)'}")
print(f"  MAIL_PASSWORD        {mask(password)}")
print(f"  MAIL_DEFAULT_SENDER  {sender or '(EMPTY)'}")
print(f"  CONTACT_TO           {to_address or '(EMPTY)'}")
print()

missing = [n for n, v in (("MAIL_SERVER", server), ("MAIL_USERNAME", username),
                          ("MAIL_PASSWORD", password), ("MAIL_DEFAULT_SENDER", sender))
           if not v]
if missing:
    print(f"[x] STOP: these are empty in .env -> {', '.join(missing)}")
    print("  Fill them in .env (NOT .env.example) and re-run.")
    if password and password.strip().startswith("key-"):
        pass
    sys.exit(1)

import re
_pw = password.strip()
# Old-format API key: "key-" + 32 hex. New-format: 32 hex - 8 hex - 8 hex.
_looks_like_api_key = (
    _pw.lower().startswith("key-")
    or _pw.lower().startswith("mailgun")
    or re.fullmatch(r"[0-9a-f]{32}-[0-9a-f]{8}-[0-9a-f]{8}", _pw.lower())
)
if _looks_like_api_key:
    print("[!] NOTE: MAIL_PASSWORD is shaped like a Mailgun API key. Some Mailgun")
    print("  accounts DO accept this as the SMTP password too - the login check")
    print("  below is the real test, not this shape check. If login fails, this")
    print("  is the first thing to double back on: Mailgun -> Send -> Domain")
    print("  settings -> SMTP -> 'SMTP credentials'.\n")

# 1) DNS / TCP
try:
    print(f"-> resolving and connecting to {server}:{port} ...")
    if use_ssl:
        smtp = smtplib.SMTP_SSL(server, port, timeout=15)
    else:
        smtp = smtplib.SMTP(server, port, timeout=15)
except socket.gaierror:
    sys.exit(f"[x] DNS: cannot resolve '{server}'. Check MAIL_SERVER "
             f"(US=smtp.mailgun.org, EU=smtp.eu.mailgun.org).")
except (socket.timeout, ConnectionRefusedError, OSError) as e:
    sys.exit(f"[x] CONNECT failed: {e}. Port {port} may be blocked on this network.")
print("  [OK] connected")

# 2) STARTTLS
try:
    with smtp:
        smtp.ehlo()
        if use_tls and not use_ssl:
            smtp.starttls()
            smtp.ehlo()
            print("  [OK] STARTTLS ok")

        # 3) LOGIN
        try:
            smtp.login(username, password)
        except smtplib.SMTPAuthenticationError as e:
            code = e.smtp_code
            sys.exit(f"[x] LOGIN rejected ({code}). Almost always one of:\n"
                     f"    - MAIL_PASSWORD is the API key, not the SMTP password\n"
                     f"    - MAIL_USERNAME wrong (need the full login, e.g. "
                     f"postmaster@mg.washworkscws.com)\n"
                     f"    - domain is in the other region (EU vs US host)")
        print("  [OK] login accepted - credentials are correct")

        # 4) optional send
        if "--send" in sys.argv:
            if not to_address:
                sys.exit("[x] --send needs CONTACT_TO set to a real inbox.")
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["Subject"] = "Wash Works SMTP test"
            msg["From"] = sender
            msg["To"] = to_address
            msg.set_content("If you're reading this, the contact form's mail path works.")
            try:
                smtp.send_message(msg)
            except smtplib.SMTPRecipientsRefused:
                sys.exit(f"[x] SEND refused for {to_address}. On a Mailgun SANDBOX "
                         f"domain the recipient must be an Authorized Recipient.")
            print(f"  [OK] test email accepted for delivery to {to_address}")
            print("    (check the inbox - and the spam folder - in a minute)")
except smtplib.SMTPException as e:
    sys.exit(f"[x] SMTP error: {e}")

print("\n[OK] ALL GOOD. The contact form will send with these settings.")
