---
name: Squeegee Guy
description: Tucson window cleaning & pressure washing — trusted-local-pro marketing site
colors:
  tucson-blue: "#0e63b8"
  tucson-blue-deep: "#0a4a8a"
  ink-navy: "#0b2540"
  sky-tint: "#e8f3fc"
  desert-amber: "#f59e0b"
  desert-amber-deep: "#d97706"
  body-ink: "#16222e"
  muted-slate: "#5b6b7a"
  hairline: "#dde6ee"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "clamp(2.1rem, 4.6vw, 3.4rem)"
    fontWeight: 850
    lineHeight: 1.12
    letterSpacing: "normal"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "clamp(1.7rem, 3.4vw, 2.5rem)"
    fontWeight: 800
    lineHeight: 1.2
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 800
    letterSpacing: "0.12em"
    fontFeature: "uppercase"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: "8px"
  md: "11px"
  lg: "14px"
  pill: "999px"
spacing:
  sm: "0.8rem"
  md: "1.4rem"
  lg: "2.5rem"
  xl: "4.5rem"
components:
  button-primary:
    backgroundColor: "{colors.desert-amber}"
    textColor: "{colors.ink-navy}"
    rounded: "{rounded.md}"
    padding: ".95rem 1.9rem"
  button-primary-hover:
    backgroundColor: "#ffb424"
    textColor: "{colors.ink-navy}"
  button-secondary:
    backgroundColor: "{colors.tucson-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: ".95rem 1.9rem"
  button-secondary-hover:
    backgroundColor: "{colors.tucson-blue-deep}"
    textColor: "#ffffff"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.tucson-blue}"
    rounded: "{rounded.md}"
    padding: ".95rem 1.9rem"
---

# Design System: Squeegee Guy

## 1. Overview

**Creative North Star: "The Neighbor With a Truck and a Squeegee"**

Squeegee Guy is a local, one-operator-feeling home service business, not a franchise or a SaaS product. The visual system exists to answer three fast questions for a Tucson homeowner scanning on a phone in bright sun: does this person serve my area, can I trust them, and how fast can I get on their schedule. The current implementation (`site/index.html`) already commits to a blue/navy/amber identity — Tucson-sky blue for trust and links, deep navy for authority sections (hero, quote, footer), and desert amber as the one loud "act now" color reserved almost entirely for CTAs. That committed-but-narrow palette is worth preserving.

What this system explicitly rejects, per `PRODUCT.md` and the `2026-07-05` design critique already run against this page: generic national-franchise polish, fake urgency, exaggerated luxury styling, cheesy clip-art service graphics, and a contractor page overloaded with badges and unsupported claims. The critique also flagged that the current build under-delivers on that rejection — repeated uppercase kickers, identical tier/why-us card grids, emoji standing in for real iconography and imagery, and generic proof numbers all read as templated rather than as a specific local operator. The palette and structure are sound; the surface treatment needs to earn the trust it's asking for.

**Key Characteristics:**
- One committed CTA color (amber) against a blue/navy trust palette — Restrained-to-Committed strategy, not Full palette.
- Deep navy "authority" bands (hero, quote, footer) alternate with light neutral sections — a layered rhythm, not a flat single-tone page.
- Single system-font family carries the whole page; hierarchy comes from weight and size, not a second typeface.
- Floating white cards (hero stat card, quote form) hover above the navy gradient bands via a heavy, warm-black shadow — the system's one elevation move.
- Sticky mobile call bar is a first-class component: this is a phone-first local-service site.

## 2. Colors

Blue carries trust and navigation; navy carries authority and grounds the two "decision" bands (hero, quote); amber is reserved almost exclusively for the primary action. The palette is Committed-adjacent: two saturated hues do real work, amber is rare and therefore legible as "the button."

### Primary
- **Tucson Blue** (`#0e63b8` / `{colors.tucson-blue}`): links, section labels, tier "popular" border, form focus ring, secondary buttons. The everyday brand color.
- **Tucson Blue Deep** (`#0a4a8a` / `{colors.tucson-blue-deep}`): hover state for blue buttons and stat numbers.

### Secondary
- **Desert Amber** (`#f59e0b` / `{colors.desert-amber}`): the single conversion color — nav CTA, hero primary button, form submit, mobile sticky call bar. **The One Loud Color Rule.** Amber never appears as decoration; if it's on screen, it's asking for a tap.
- **Desert Amber Deep** (`#d97706` / `{colors.desert-amber-deep}`): amber hover/pressed state.

### Tertiary
- **Ink Navy** (`#0b2540` / `{colors.ink-navy}`): topbar, hero and quote section backgrounds (as a gradient base), footer, headline text color on light sections.

### Neutral
- **Body Ink** (`#16222e` / `{colors.body-ink}`): default text color on light backgrounds.
- **Muted Slate** (`#5b6b7a` / `{colors.muted-slate}`): secondary/supporting copy, captions, sub-labels.
- **Sky Tint** (`#e8f3fc` / `{colors.sky-tint}`): light-blue section backgrounds (stat tiles, chips, "why" section wash).
- **Hairline** (`#dde6ee` / `{colors.hairline}`): card and input borders, nav divider.

### Named Rules
**The One Loud Color Rule.** Amber is reserved for the primary action only. It never fills a background, an icon, or a decorative accent — if it appears, it is a button or a phone-tap target.

## 3. Typography

**Body Font:** -apple-system / Segoe UI / Roboto / Helvetica / Arial (system sans stack)
**Display Font:** same stack, distinguished by weight (800–850) and size only — no second typeface is loaded.

**Character:** A single, neutral system sans carrying the entire page. Hierarchy is built from weight (400 body → 800 headline → 850 display) and a fluid `clamp()` scale, not from a display/body font pairing. This reads as fast and native rather than "designed," which fits a phone-first local-service brief, but it also means the system currently has no distinctive typographic voice of its own.

### Hierarchy
- **Display** (850, `clamp(2.1rem, 4.6vw, 3.4rem)`, 1.12 line-height): hero `<h1>` only.
- **Headline** (800, `clamp(1.7rem, 3.4vw, 2.5rem)`, 1.2 line-height): section titles (`.section-title`).
- **Title** (800, ~1.2–1.3rem): card headings (tier names, why-us card titles, form heading).
- **Body** (400, 1rem, 1.6 line-height): paragraph copy; capped informally around 640px max-width on section subheads (`.section-sub`).
- **Label** (800, 0.78rem, 0.12em tracking, uppercase): `.section-label` kicker above every section heading.

### Named Rules
**The Repeated Kicker Problem.** `.section-label` appears above every section as identical uppercase-tracked scaffolding. Flagged by the 2026-07-05 critique as an AI-template tell — treat as a Don't (see §6), not as an established brand system, since it was never a deliberate named device.

## 4. Elevation

Mostly flat. The system uses one deliberate elevation move — a heavy, warm-tinted shadow that lifts white cards off the navy gradient bands — plus a light hover-lift on interactive tier cards. There is no ambient elevation scale (no Material-style tonal layers); shadows are structural, marking "this card floats above the hero/quote background."

### Shadow Vocabulary
- **Card-float** (`box-shadow: 0 24px 60px rgba(4,20,40,.35)`): the hero stat card and quote form, floating over the navy gradient sections.
- **Hover-lift** (`box-shadow: 0 14px 40px rgba(10,60,110,.12); transform: translateY(-3px)`): pricing tier cards on hover.
- **Sticky-call** (`box-shadow: 0 10px 30px rgba(0,0,0,.3)`): the fixed mobile call bar, kept visible above page content.

### Named Rules
**The Float-on-Navy Rule.** Shadows only appear where a white surface sits directly on a navy/gradient background. On light sections, cards use a 1px hairline border instead of a shadow.

## 5. Components

### Buttons
- **Shape:** rounded rectangle, 11px radius (`--radius`-derived, `.btn`).
- **Primary (amber):** `background: #f59e0b; color: #0b2540`, `.95rem 1.9rem` padding, 800 weight. Hover → `#ffb424` + `translateY(-1px)`.
- **Secondary (blue):** `background: #0e63b8; color: #fff`. Hover → `#0a4a8a`.
- **Outline:** `2px solid #0e63b8`, transparent fill, blue text. Hover → `background: #e8f3fc`.
- **Ghost (on navy):** `2px solid rgba(255,255,255,.55)`, white text, for the hero secondary CTA. Hover → `background: rgba(255,255,255,.12)`.

### Chips / Pills
- **Style:** `background: #e8f3fc; color: #0a4a8a`, 999px radius, 700 weight — used for service-area tags.
- **Tier flag:** same pill shape, `background: #0e63b8` (or slate `#64748b` / amber for "gold" tier), white/navy text, positioned as a badge overlapping the card's top edge.

### Cards / Containers
- **Corner Style:** 14px radius (`--radius`) for tier cards, why-cards, reviews, hero stat card, quote form.
- **Background:** white on light sections; `#e8f3fc` for stat tiles and additional-service cards.
- **Shadow Strategy:** see Elevation — hairline border by default, `Card-float` shadow only when floating over a navy band.
- **Border:** `1px solid #dde6ee` default; `.popular` tier upgrades to `2px solid #0e63b8`.
- **Internal Padding:** ~1.7–2rem.

### Inputs / Fields
- **Style:** `1.5px solid #c9d6e2`, 8px radius, white background.
- **Focus:** border shifts to `#0e63b8` with a `0 0 0 3px rgba(14,99,184,.14)` glow ring.
- **Error / Disabled:** not currently defined — native `required` validation only, no custom error styling.

### Navigation
- **Style:** sticky, translucent white with `blur(8px)` backdrop, 66px height, hairline bottom border. Links are 600-weight ink; the final nav link is always the amber CTA pill. Below 760px, all links collapse except the CTA.

### Sticky Mobile Call Bar (signature component)
- Fixed full-width amber bar at the viewport bottom on mobile (≤640px), navy text, `Sticky-call` shadow. This is the primary mobile conversion path when the quote form is scrolled out of view — treat it as a first-class component, not a decorative afterthought.

## 6. Do's and Don'ts

### Do:
- **Do** keep amber (`#f59e0b`) reserved for the single primary action per view — nav CTA, hero button, form submit, sticky call bar. Diluting it into decoration kills the "this is the button" signal.
- **Do** use the navy gradient bands (`--navy` → `--blue`) as the "decision" sections (hero, quote) and keep everything else on light neutral backgrounds — this alternating rhythm is the page's structural spine.
- **Do** reserve the `Card-float` shadow (`0 24px 60px rgba(4,20,40,.35)`) for surfaces floating on navy; use hairline borders everywhere else.
- **Do** make the sticky mobile call bar and quote form the two fastest paths to conversion; any redesign should shorten, not lengthen, the distance to either.
- **Do** ground proof in Tucson-specific, concrete detail (service areas, hard-water/monsoon specifics) rather than generic superlatives — this is the one differentiator PRODUCT.md calls out by name.

### Don't:
- **Don't** repeat the uppercase tracked `.section-label` kicker as unexamined scaffolding above every section — the 2026-07-05 critique named this an AI-template tell; treat it as an ex-post problem to fix, not a shipping brand system.
- **Don't** rebuild the tier/why-us layout as more identical card grids (three pricing tiers + six why-cards + four service cards is already flagged as comparison overload); avoid adding a fourth uniform grid.
- **Don't** use emoji as substitute iconography (🧽 🌵 💧 ⚡) or substitute proof photography — PRODUCT.md explicitly bans "cheesy clip-art service graphics" and the critique flagged emoji-heavy identity as a credibility cost. Real photography, real SVG icons, or nothing.
- **Don't** introduce generic national-franchise polish, fake urgency, exaggerated luxury styling, or badge-overload — direct anti-references from PRODUCT.md.
- **Don't** let hero/lead body text sit below WCAG AA contrast against the navy gradient (the critique flagged the light-blue lead text and amber-on-navy glow as under-contrast); darken or re-weight before shipping any hero variant.
- **Don't** introduce a second display typeface casually — the single-family system is intentional for this brief's fast, native feel; a second family needs a real reason, not decoration.
