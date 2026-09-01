# Wash Works Inc. — Website Build Handoff

## Project Summary
Build a fully custom-coded website for Wash Works Inc. from scratch — no CMS, no template builder (explicitly moving off GoDaddy's Website Builder due to its template limitations). Stack: HTML, CSS, JavaScript, and Python (Flask if a backend is needed). Target hosting: Render or Vercel (final choice still open). Domain will remain registered with GoDaddy; DNS will be pointed at whichever host is chosen once the site is ready to go live.

## Company Background
- **Wash Works Inc.** — car wash maintenance, installation, repair, equipment sales, consulting, and marketing services.
- Sister company to New Wave Innovations Inc. (a car wash parts manufacturer), sharing the same physical address, though a separate brand/site.
- Address: 502 North School Street, Lodi, CA 95240
- Phone: (209) 263-7086
- **Domain: washworkscws.com** (currently registered/managed via GoDaddy — the original washworkscw.com domain was lost and is no longer in use)
- ⚠️ Contact emails on the reference flyer (bill@washworkscw.com, mike@washworkscw.com) use the OLD domain. Custom employee email addresses are already set up on the current domain, washworkscws.com — confirm the exact current addresses before publishing anything on the site. Do not reuse the old-domain emails.

## Brand Identity

**Color palette:** Navy blue + white as the primary site palette (confirmed direction — matches the logo files, not the orange/black scheme used on an older print flyer, which should NOT carry over to the site).

**Logo assets (3 files, already provided by the client):**
1. `washworks_logo.png` — wide "MOTOR CONTROL CENTERS BY WASH WORKS" lockup, white artwork on a navy background. Use for the Motor Control Centers sub-brand section.
2. `washworks_logo_png.png` — the main "WASH WORKS / CAR WASH SERVICES" logo, black artwork on a transparent background. Use as the primary site logo (works on any background).
3. `washworks_logo_square.png` — square version of the navy "Motor Control Centers by Wash Works" lockup. Suited for favicon, social profile image, or small icon use.

**Typography direction:** A tall, high-contrast serif display face for the "WASH WORKS" wordmark (elegant, editorial feel), paired with a bold geometric sans-serif for supporting text like "CAR WASH SERVICES."

**Icon/motif:** A minimalist car viewed head-on, positioned between two vertical brush/tire-tread wash rollers, with small sparkle accents above the car and a suds/bubble base beneath it. This icon is baked into the provided logo files — reuse it consistently as a recurring graphic motif (section dividers, favicon, etc.) rather than introducing new iconography.

## Sub-Brand Structure
"Motor Control Centers by Wash Works" is a distinct product line (UL508A-certified control panels) that needs its own clearly separated section on the site — own visual treatment using the navy lockup logo — while remaining part of the same overall site and navigation (not a separate domain or subdomain).

## Sitemap
- Home
- Services
- Consulting
- Marketing Services
- Motor Control Centers by Wash Works (sub-brand section, distinct visual treatment)
- About
- Contact

## Page Content Reference

### Home
Hero section introducing Wash Works, with clear navigation into Services, Consulting, and Motor Control Centers. Contact CTA (phone number + contact form).
⚠️ The reference flyer advertised a "$99 service rate" promo valid through May 1st. **Do not use this without confirming current validity** — it's very likely expired and needs updated pricing/promo info from the client before publishing.

### Services — Car Wash Maintenance, Installation & Repair
- Monthly Maintenance Plan
- Tunnel Adjustments
- Conveyor Installation & Repairs
- Compressor Maintenance
- Electrical Installation & Repairs
- Security Video Systems
- Vacuum Installation & Repairs
- Equipment Sales
- Parts
- Custom Ladder Rack
- Chemical Service
- Custom Manufacturing
- Reclaim Service
- RO Repair
(Flyer notes "AND MORE!" — confirm with client whether additional services exist beyond this list.)

### Consulting
- Financial Information
- Equipment Recommendations
- Repair Diagnostics
- Wash Packages
- Traffic Counts
- Proforma
- Site Inspections
- Signs / Marketing
- Land for Sale

### Marketing Services
Positioned as: "No spare time? Let us manage your social media accounts, websites & promotions." Wash Works offers this as a service to ITS OWN clients (not something the visitor is being sold on for Wash Works itself):
- Social media account management — Facebook, Instagram, TikTok, LinkedIn, X (Twitter)
- Website design

### Motor Control Centers by Wash Works (sub-brand section)
**UL508A Certified Panels.** UL508A-rated motor control panels for tunnel equipment, dryers, central vacuums, and lighting control — built for maximum efficiency, suited for all car wash applications, with an emphasis on quality and safety.

**Advantages to highlight:**
- Competitive Pricing
- Maximum Reliability
- Specifically Built for Carwash Equipment
- Custom Lighting Panels
- Quality Components

CTA: "Call Today for a Quote" — (209) 263-7086

### About
Not yet written — needs company background copy from the client (founding story, team, service area, years in business, etc.).

### Contact
- Phone: (209) 263-7086
- Email(s): confirm current addresses on washworkscws.com (see warning above — do not use the old-domain emails from the flyer)
- Address: 502 North School Street, Lodi, CA 95240
- Recommend a working contact form (this is likely where Flask would actually be needed, if used at all — see Open Items)

## Technical Requirements
- Fully custom-coded — HTML/CSS/JS front end
- Python/Flask backend ONLY if a genuinely dynamic feature is needed (e.g., contact form handling/email routing); if the site is otherwise static, evaluate whether a simpler static-form solution (e.g., a form service compatible with Render/Vercel static hosting) avoids the need for a backend at all
- Fully responsive/mobile-friendly
- HTTPS/SSL required (typically automatic on Render/Vercel)
- Deploy target: Render or Vercel — final decision still open
- DNS: washworkscws.com stays registered with GoDaddy; A/CNAME records will need to be updated to point to the chosen host once ready. Email (MX records) is separate and must NOT be affected by this change — verify before and after any DNS update.

## Open Items / Decisions Still Needed
- [ ] Final hosting choice: Render vs. Vercel
- [ ] Confirm the current, correct contact email addresses on washworkscws.com
- [ ] Confirm whether the "$99 service rate" promo is still active, or needs replacing/removing
- [ ] Write About page company background copy
- [ ] Source real photography — the reference flyer used what appears to be stock/example imagery (a car mid-wash, a generic electrical panel). Confirm these are licensed for use, or replace with Wash Works' own photos, before publishing
- [ ] Confirm whether Flask/a backend is actually required, or if the site can ship fully static
- [ ] Additional services beyond the flyer's list ("AND MORE!") — confirm with client

## Related Context (background only, not part of this build)
Sister company New Wave Innovations Inc. (Lodi, CA) is a separate, ongoing project — a car wash parts manufacturer at the same physical address. Not part of this site, but may be useful context for brand tone/consistency if the two companies want to look related.
