// Wash Works - Cloudflare Worker.
//
// Pages and assets are plain files that Cloudflare serves itself (free, unlimited,
// no code runs). This script only runs for the paths listed under "run_worker_first"
// in wrangler.jsonc, because they need something files cannot do:
//
//   POST /contact/submit   the contact form (this replaces Flask's contact_submit)
//   /static/video/*        byte-range support. Cloudflare's static hosting answers a
//                          Range request with the whole file and no Accept-Ranges
//                          header, and Safari/iOS will not play a <video> that way.

import site from "../content/site.json" with { type: "json" };

const MIN_FILL_SECONDS = 3;                        // T-6: bots submit instantly
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$/;
const FIELD_LIMITS = { name: 200, business: 200, email: 200, phone: 60, subject: 200, message: 5000 };
const PHONE = site.company.phone_display;

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);

    if (pathname === "/contact/submit") {
      if (request.method !== "POST") {
        return json({ status: "error", message: "Please use the contact form." }, 405, { Allow: "POST" });
      }
      return contactSubmit(request, env);
    }
    if (pathname.startsWith("/static/video/")) return serveWithRanges(request, env);

    return env.ASSETS.fetch(request);
  },
};

// ---------------------------------------------------------------------------
// contact form
// ---------------------------------------------------------------------------

async function contactSubmit(request, env) {
  let form;
  try {
    form = await request.formData();
  } catch {
    return json({ status: "error", message: "We could not read that. Please try again." }, 400);
  }
  const text = (key) => String(form.get(key) ?? "").trim();

  // T-6: honeypot plus a fill-time floor. Both answer "success" so a bot learns nothing.
  // A visitor whose clock runs ahead gives a negative elapsed time; that must pass, not
  // be mistaken for a bot and silently lose a real lead.
  const thanks = { status: "success", message: "Thank you. We will be in touch." };
  if (text("company_website")) return json(thanks);
  const elapsed = Date.now() / 1000 - parseFloat(text("rendered_at"));
  if (elapsed >= 0 && elapsed < MIN_FILL_SECONDS) return json(thanks);

  const fields = {};
  for (const [key, max] of Object.entries(FIELD_LIMITS)) fields[key] = text(key).slice(0, max);
  fields.subject = fields.subject.replace(/[\r\n]+/g, " ");

  const missing = ["name", "email", "message"].filter((key) => !fields[key]);
  if (missing.length) {
    return json({ status: "error", message: `Please fill in your ${missing.join(", ")}.`, fields: missing }, 400);
  }
  if (!EMAIL_RE.test(fields.email)) {
    return json({
      status: "error",
      message: "That email address does not look right. Please check it.",
      fields: ["email"],
    }, 400);
  }

  const record = {
    id: crypto.randomUUID().replaceAll("-", "").slice(0, 12),
    received_at: new Date().toISOString(),
    ip: request.headers.get("CF-Connecting-IP"),
    fields,
  };

  // T-5: save first. The email is only a notification, so a mail outage never loses a lead.
  let saved = false;
  if (env.SUBMISSIONS) {
    try {
      await env.SUBMISSIONS.put(`submission:${record.received_at}:${record.id}`, JSON.stringify(record));
      saved = true;
    } catch (err) {
      console.error(`could not save submission ${record.id}:`, String(err));
    }
  }

  const emailed = await sendEmail(record, env);

  if (!saved && !emailed) {
    // Nothing kept this lead. Do not claim success; leave the whole record in the logs.
    console.error("submission NOT saved or emailed:", JSON.stringify(record));
    return json({ status: "error", message: `Something went wrong on our end. Please call ${PHONE} instead.` }, 500);
  }
  if (!emailed) console.warn(`submission ${record.id} saved but not emailed`);
  return json({ status: "success", message: "Thank you. We have your message and will be in touch." });
}

async function sendEmail(record, env) {
  const to = env.CONTACT_TO || site.company.email;
  const from = env.MAIL_DEFAULT_SENDER;
  if (!env.RESEND_API_KEY || !to || !from) {
    console.warn("email skipped - set RESEND_API_KEY, MAIL_DEFAULT_SENDER and CONTACT_TO " +
                 "(Worker > Settings > Variables and Secrets)");
    return false;
  }

  const f = record.fields;
  const lines = Object.entries(f).filter(([, value]) => value)
    .map(([key, value]) => `${key.replace(/\b\w/g, (c) => c.toUpperCase())}: ${value}`);
  const body = `${lines.join("\n")}\n\nReference: ${record.id}\nReceived: ${record.received_at}`;

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
        // Resend sits behind Cloudflare's bot checks, which reject a missing/library User-Agent (error 1010).
        "User-Agent": "WashWorksWebsite/1.0 (+https://washworkscws.com)",
      },
      body: JSON.stringify({
        from,
        to: [to],
        reply_to: f.email,                         // T-4: replies go straight to the visitor
        subject: `Website enquiry - ${f.subject || "General"}`,
        text: body,
      }),
    });
    if (!res.ok) {
      console.error(`email failed - Resend HTTP ${res.status}, reference ${record.id}:`, (await res.text()).slice(0, 300));
      return false;
    }
    return true;
  } catch (err) {
    console.error(`email failed - transport error, reference ${record.id}:`, String(err));
    return false;
  }
}

// ---------------------------------------------------------------------------
// video byte ranges
// ---------------------------------------------------------------------------

async function serveWithRanges(request, env) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  // The asset store ignores Range, so ask it for the whole file and slice it here.
  const asset = await env.ASSETS.fetch(new Request(request.url, { method: "GET" }));
  if (!asset.ok) return asset;                     // missing file: the normal 404 page

  const bytes = await asset.arrayBuffer();
  const size = bytes.byteLength;
  const headers = new Headers({
    "Content-Type": asset.headers.get("Content-Type") || "video/mp4",
    "Accept-Ranges": "bytes",
    "Cache-Control": "public, max-age=604800",
    "X-Content-Type-Options": "nosniff",
  });
  const etag = asset.headers.get("ETag");
  if (etag) headers.set("ETag", etag);
  const headOnly = request.method === "HEAD";

  const range = parseRange(request.headers.get("Range"), size);
  if (range === "invalid") {
    headers.set("Content-Range", `bytes */${size}`);
    return new Response(null, { status: 416, headers });
  }
  if (!range) {                                    // no usable Range header: the whole file
    headers.set("Content-Length", String(size));
    return new Response(headOnly ? null : bytes, { status: 200, headers });
  }
  const { start, end } = range;
  headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
  headers.set("Content-Length", String(end - start + 1));
  return new Response(headOnly ? null : bytes.slice(start, end + 1), { status: 206, headers });
}

// "bytes=0-1", "bytes=500-", "bytes=-100"  ->  {start, end} | null (ignore it) | "invalid" (416)
function parseRange(header, size) {
  const m = /^bytes=(\d*)-(\d*)$/.exec((header || "").trim());
  if (!m || (m[1] === "" && m[2] === "")) return null;
  let start;
  let end;
  if (m[1] === "") {                               // suffix: the last N bytes
    const n = parseInt(m[2], 10);
    if (n === 0) return "invalid";
    start = Math.max(0, size - n);
    end = size - 1;
  } else {
    start = parseInt(m[1], 10);
    end = m[2] === "" ? size - 1 : Math.min(parseInt(m[2], 10), size - 1);
  }
  return start >= size || start > end ? "invalid" : { start, end };
}

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...extra,
    },
  });
}
