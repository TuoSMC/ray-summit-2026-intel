# DESIGN — ray-summit-2026

One visual world per campaign. No half-reskins (spine-plan-v2 §2 P3).
This file is the contract the generators implement. If a value is not here, no
generator may invent it; if a value is here, no generator may hand-paste around it.

**Owners.** `bin/wrap_pages.py` owns the skeleton (tokens, chrome, nav slot, lang
toggle, runtime marker). `bin/build_fragments.py` owns per-role markup and every
bilingual string. `bin/i18n_overlay.py` owns the runtime injection and the four
i18n gates. `bin/structure_pass.py` owns nav + cross-links only.

---

## 0. The scene the design is for

A Supermicro salesperson, standing in a bright convention hall, holding a phone,
between sessions, with about three seconds. Not an engineer. Hub mode is
**Operate**; the long research pages are **Read**.

Consequences, binding:

- Light world. Bright ambient light, glossy phone. High contrast, no dark theme.
- Hierarchy must survive a glance: exactly one thing per screen is loudest.
- Evidence quality is part of the content, not a footnote. It is ranked
  typographically, not colour-coded into a rainbow.
- `GAP` is the honest answer, so it is **visible, calm and legible** — never
  hidden, never dimmed to grey, never styled as an error.
- No external resource of any kind (RULES A3). System fonts only. No `innerHTML`
  (A2). Everything inline.

**Anti-reference:** the incumbent pack — Helvetica fallback stack at a flat 16px,
navy pill nav, ten near-identical white rounded cards per page. That look is
evidence of the problem, not a starting point.

---

## 1. Type

System faces only (A3). Character comes from the pairing and the rhythm, not from
a download.

```
--f-display: ui-serif, "New York", "Iowan Old Style", Charter, Constantia,
             Georgia, "Songti TC", "Songti SC", STSong, "Noto Serif CJK TC",
             MingLiU, serif
--f-text:    -apple-system, BlinkMacSystemFont, system-ui, "Segoe UI",
             "PingFang TC", "Noto Sans CJK TC", "Microsoft JhengHei",
             "Helvetica Neue", Arial, sans-serif
--f-mono:    ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
             "Roboto Mono", "Courier New", monospace
```

- **Display serif** carries the masthead, the verdict, and every `h2`. On Apple
  that resolves to New York; on Windows to Constantia/Georgia; the CJK arm
  resolves to a Song/Ming face. Serif display over sans body is the pairing.
- **Text sans** carries body, lists, tables, chrome.
- **Mono** carries *data only* — session ids, clock times, room names, dates,
  URLs, negation queries, source stamps. Mono is never decoration; if it is not a
  value a rep might read aloud or type, it is not mono.
- **Weights are 400 and 700 only** (RULES C2). No 500/600, no synthetic weight.

### Scale

Base 17px. Phone-first; the two fluid steps use `clamp()`, nothing else moves.

| token | size | line-height | tracking | use |
|---|---|---|---|---|
| `--t-display` | `clamp(30px, 6.2vw, 46px)` | 1.16 | -0.021em | verdict `h1`, one per page |
| `--t-figure`  | `clamp(34px, 8.8vw, 44px)` | 1.05 | -0.03em | the four numbers (tabular) |
| `--t-h2`      | `clamp(21px, 3.2vw, 25px)` | 1.28 | -0.012em | section heads |
| `--t-h3`      | `18px` | 1.42 | -0.005em | card / session titles |
| `--t-lede`    | `19px` | 1.58 | 0 | the one paragraph under a verdict |
| `--t-body`    | `17px` | 1.62 | 0 | prose, list items, `dd` |
| `--t-mono`    | `15px` | 1.5 | 0 | locked data |
| `--t-cap`     | `14px` | 1.5 | 0 | sources, notes, `dt` |
| `--t-micro`   | `12.5px` | 1.35 | +0.09em, uppercase | chips, labels, rank marks |

Nothing below 12.5px anywhere (gate floor is 11px; we keep headroom).
No `transform:scale()`, no `zoom` (FM4). Nothing is `nowrap` (FM5).

### Measure and CJK tuning

- `--measure: 66ch` on every prose block. At 17px that is ≈560px: 68–72 Latin
  characters, 32–36 CJK characters. Both sit inside the comfortable band.
- Per-language metrics switch on the **root**, not on the layers: CJK wants more
  leading and a hair of tracking, Latin does not.
  - `:root[data-lang="h"] body` — `line-height: 1.72`, `letter-spacing: .01em`
  - `:root[data-lang="e"] body` — `line-height: 1.58`, `letter-spacing: 0`
  Setting these on `[data-t]` instead leaks CJK leading into every heading that
  contains a language layer, which is how the first build shipped a 1.78 display
  line-height. Headings own their own line-height; the root owns the body.
- English counts pluralise (`pl()`): "1 companies" is the tell that a number was
  templated. The figure is untouched, so B6 still holds.
- `font-variant-numeric: tabular-nums` on every figure, time, count and table
  number so columns align and a changed number does not reflow the row.
- Headings use `text-wrap: balance` where supported; it degrades silently.

---

## 2. Space

4px base. Nine steps, no improvisation between them.

```
--s1 4   --s2 8   --s3 12   --s4 16   --s5 24
--s6 32  --s7 48  --s8 64   --s9 96
```

Rules the generators obey:

- **More space above a heading than below it.** `h2` margin is `--s7 / --s3`;
  `h3` is `--s5 / --s1`.
- Tight groups, generous separation: items inside one block are `--s2`/`--s3`
  apart; blocks are `--s7` apart; the masthead-to-content gap is `--s6`.
- Page gutter `--s4` on phones, `--s5` from 760px.
- Container: `width: min(100% - 2*gutter, 1040px)`. Prose inside it is clamped to
  `--measure` regardless of container width.

---

## 3. Colour

Ink on warm paper. One accent. One status hue. Nothing else.

```
--paper:      #FAF8F3    page ground (warm, not blue-white)
--card:       #FFFFFF    raised surface
--sunk:       #F2EEE4    inset surface: mono runs, query strings
--ink:        #14161A    primary text            17.1:1 on paper
--ink-2:      #3D434E    secondary text           9.4:1 on paper
--ink-3:      #5E6675    captions, sources        5.5:1 on paper
--rule:       #E5E0D5    hairlines
--rule-hard:  #14161A    the 2px section rule
--accent:     #123A8C    links, active nav, verdict rule    9.9:1 on paper
--accent-bg:  #E9EEFB    active/hover wash
--gap-fg:     #7A4400    GAP token text           7.5:1 on paper, 6.9:1 on gap-bg
--gap-bg:     #FBEEDA    GAP token ground
--stop:       #8C1D18    reserved: contradictions only, never GAP
--focus:      #123A8C    focus ring
```

Every interactive and text colour is ≥4.5:1 (C6). **No hardcoded hex outside the
`:root` block** (C1) — a new component that needs a colour needs a token first.

Accent budget: the navy appears on the active nav tab, inline links, the verdict
rule, and focus. That is the whole list. It is not a decoration colour.

---

## 4. Evidence chips — rank, not rainbow

Evidence quality is a *rank*. Rank is drawn as a mark (a CSS-drawn square, never
a glyph or emoji), not signalled by five competing colours. The label is
vocabulary in both languages.

| rank | mark | ZH | EN | when |
|---|---|---|---|---|
| `official` | filled square, `--ink` | 官方一手 | Official first-party | source host is the event catalogue or the host org |
| `vendor` | half-filled square, `--ink-2` | 廠商自報 | Vendor-reported | source host is the subject company's own domain |
| `third` | hollow square, `--ink-2` | 第三方 | Third-party | any other http(s) source |
| `unverified` | hollow dotted square, `--ink-3` | 未證 | Unverified | populated value with no source record |
| `gap` | the GAP token (below) | GAP | GAP | no value — untranslated, it is a status token |

Rank is **computed** from `sources[field].source`, never typed (B16). The chip is
`--t-micro`, uppercase for the Latin arm, with a 1px `--rule` border and no fill.

Markup contract:

```html
<span class="ev ev-official"><span class="ev-mark" aria-hidden="true"></span>
  <span data-t="h">官方一手</span><span data-t="e">Official first-party</span></span>
```

---

## 5. GAP treatment

`GAP` is the campaign's most important token. Nothing about it may read as
failure, and nothing may make it easy to skim past.

- The token itself: `--gap-fg` on `--gap-bg`, mono, `--t-micro`, uppercase, 3px
  radius, `2px 7px` padding, **1px dashed** border. Dashed = "open", not "wrong".
- It is always followed by its reason in `--t-cap`/`--ink-2` — a GAP without a
  reason is a bug, and the generator's `gap()` helper cannot emit one.
- A card whose value is GAP keeps the full card: `--card` ground, dashed `--rule`
  border. It is **not** dimmed, not collapsed, not moved to the bottom.
- `--stop` (red) is reserved for contradictions (B2). GAP never uses it.
- The GAP token is byte-identical in both languages; only the reason translates.

---

## 6. Locked data (B6)

Numbers, dates, clock times, room names, person names, company legal names, and
URLs are **byte-identical in every language**. They are emitted verbatim from
JSON and rendered in one shared style so a rep can find them instantly:

```html
<span class="lk">Golden Gate</span>
```

`.lk` = `--f-mono`, `--t-mono`, `--ink`, `tabular-nums`, `overflow-wrap:anywhere`.
Locked runs sit *outside* the `data-t` language layers wherever the sentence
allows, and where they must sit inside, `i18n_overlay.py` proves both arms carry
the identical locked-token sequence and fails the build if they do not.

---

## 7. Bilingual contract

Both languages ship in the HTML. The toggle switches visibility. No fetch, no
cookies (A3/A4).

- Every translatable run is a **pair of sibling elements**:
  `<span data-t="h">…</span><span data-t="e">…</span>`, h always first.
- Visibility is a root attribute: `<html data-lang="h">` / `data-lang="e"`.
  CSS: `:root[data-lang="h"] [data-t="e"]{display:none}` and the mirror.
  With JS off, ZH shows and EN is hidden — the source language always wins.
- The control: two `<button data-lang-btn>` in the masthead, top right, reading
  exactly `EN` and `ZH`. Minimum target 44×44 (C6). `aria-pressed` on the active
  one. Native buttons, so keyboard works without extra code.
- Choice persists in `localStorage["rs26.lang"]`. Nothing leaves the page.
- The runtime is **one** inline script in `<head>` — it sets the root attribute
  before first paint (no flash), syncs `aria-pressed` on DOMContentLoaded, and
  listens for clicks by delegation. It builds no DOM, so `innerHTML` never
  appears (A2).
- Structure is identical across the two arms: `i18n_overlay.py` fails the build
  on an unpaired layer, a locked-token divergence, a missing evidence-vocabulary
  translation, or a toggle without a runtime.

---

## 8. Component inventory

Each entry is a class the generators emit. No component outside this list.

| component | class | notes |
|---|---|---|
| masthead | `.mast` | event in display serif; dates·venue in mono micro; toggle right |
| lang toggle | `.langsw` / `.langbtn` | 2 controls, 44×44, `aria-pressed` |
| nav | `.nav` | 6 tabs, wrap (never scroll), active = ink underline + weight |
| verdict | `.verdict` | display `h1`, **no eyebrow**, 3px `--accent` rule above, grounds list |
| figures | `.figs` / `.fig` | the four numbers as a rule-separated ledger row, not stat cards |
| actions | `.acts` | ordered; numbering is earned (it is a sequence) |
| evidence chip | `.ev` | §4 |
| GAP token | `.gap` + `.why` | §5 |
| locked run | `.lk` | §6 |
| drawer | `details.dr` + `.dr-t` / `.dr-s` / `.dr-b` | §11. Every section and subsection |
| session card | `.ses` | time · title · room · tags; grid `minmax(min(100%,264px),1fr)` |
| hardware mark | `.is-hw` / `.hwm` | a session that carries a hardware-demand signal, naming the probe that matched |
| day filter | day drawers | a closed day IS the filter; the CSS radio is retired |
| room ledger | `.rooms` | name ↔ count rows, dotted leader |
| caveat | `.caveat` | what the catalogue does not give; GAP ground |
| play | `.play` | segment play, `dl` |
| register table | `.reg` | table ≥720px, stacked labelled rows below (C3) |
| band | `.band` | accounts layer band; heavy top rule + count |
| account card | `details.acct` | one drawer per company; `.cells` `dl` inside, one row per cell with its caption, rank chip, source link and date |
| full dossier | `details.deep` | only on a FULL account: `mw_or_proxy` and `window` spelled out item by item |
| axis panel | `.axis` | `data-axis` verbatim from STATE |
| trap | `.trap` | A/B pair + negation query in `--sunk` mono |
| method | `.method` | a drawer, always last, never above the verdict |
| footer | `.foot` | source link + freshness stamp |

Banned in this world: nested cards; a coloured `border-left` above 1px; eyebrow
or kicker text above any heading; gradient text; glass/blur; emoji or Unicode
glyphs as icons; a card grid used as the page's structure where a list is the
honest shape.

---

## 9. Motion, focus, responsive

- One authored moment only: state changes on nav tabs, the lang toggle and links
  — `background-color`/`border-color` over `140ms cubic-bezier(.2,.7,.2,1)`.
  Everything is wrapped in `@media (prefers-reduced-motion: no-preference)`, so
  the reduced-motion path is the default with nothing to switch off (C6).
- Focus: `outline: 2px solid var(--focus); outline-offset: 2px` on every
  focusable element. Never removed.
- Breakpoints: `520px` (figures go 4-up), `720px` (tables stop stacking),
  `760px` (gutter and display step up).
- No horizontal page scroll at 320px (C3). Every grid uses
  `minmax(min(100%, Npx), 1fr)`; every flex child carries `min-width:0`; every
  wide block owns its own `overflow-x:auto`; URLs and queries use
  `overflow-wrap:anywhere`.
- Item grids (`.ses`, `.rooms`, `.traps`) use **`auto-fill`**, not `auto-fit`. A
  band holding one item is a real state here, and `auto-fit` collapses the empty
  tracks and stretches that single card across the whole 1040px. Only `.axes`,
  which always splits a fixed pair across one row, uses `auto-fit`.
- `.accts` is the exception and is a **stack**, not a grid: its children are
  drawers, and opening one card inside a grid reflows its neighbours out from
  under the thumb that is still moving toward them.
- Any flex container holding sibling text runs declares an explicit `gap`: flex
  drops the whitespace between children, which is how a day label first shipped
  reading "2026-08-248 sessions".
- `.caveat` carries the GAP ground. When the gap it describes is closed, the
  generator adds `.is-clear` and it reverts to `--card` — an alarm panel with
  nothing to report teaches the reader to ignore alarm panels.

---

## 10. Non-negotiables the gates already enforce

- Counts are COMPUTED from JSON. A typed "50 sessions" is a defect (B16).
- 未知 ≠ 無. A missing value prints `GAP` + reason, never `0`, `無`, `N/A` (B13).
- `<meta charset="utf-8">` inside the first 512 bytes (D1, host=docs-local).
- Exactly one inline `<script>` per page, no `src`, no fetch/XHR/beacon/WS (A3).
- Method never above the verdict; no agent counts anywhere (page-role.json).
- The pack never documents itself to the reader. Field names, internal
  taxonomies, evidence-vocabulary reference tables and pipeline concepts stay
  off reader-facing surfaces. If a cell needs explaining, the explanation is
  that cell's own caption, inline, one line. A term the reader has to look up
  somewhere else has already failed the floor test — which is why the glossary
  page was deleted rather than rewritten.

---

## 11. Drawers

Every section and every subsection is a native `<details>` + `<summary>`. No
JavaScript accordion: `<details>` is focusable and operable from the keyboard
with no code, is reachable by the browser's own find-in-page, and prints.

```html
<details class="dr" data-block="…">
  <summary><span class="dr-t">TITLE</span><span class="dr-s">SCENT</span></summary>
  <div class="dr-b">…</div>
</details>
```

- **Open state.** Top-level drawers are `open` on `command-center` and closed on
  every other page. Nested drawers are always closed.
- **The scent line is mandatory.** `.dr-s` says what is inside plus a count or a
  verdict, so a closed drawer still informs:
  `帳戶板 · 58 家 · 362 格已填 · 140 格待補 · 8 份完整檔` beats `帳戶板`.
  `structure_pass.py` fails the build on a `<summary>` without one, and on a
  `<details>` that does not open with a `<summary>` — the browser would print
  the word "Details" and the section would go invisible.
- **The control.** `cursor:pointer`, `min-height:44px` (C6), a visible
  `:focus-visible` ring, and `user-select:none` so a tap on a phone never turns
  into a text selection instead of a toggle. The marker is a CSS-drawn chevron;
  the UA triangle is suppressed, and no glyph or emoji is used (§8).
- **Two altitudes, one component.** `main > details.dr` reads as a section:
  heavy `--rule-hard` top rule, `--t-h2` title, no card chrome. Nested drawers
  read as cards: `--card` ground, hairline border, `--t-h3` title.
- **The verdict drawer's handle IS the verdict.** Its `<summary>` carries the
  `h1` and the lede, so nothing sits above the headline. An eyebrow above a
  heading is still banned (§8); a disclosure control that IS the heading is not
  an eyebrow.
- **Print.** Paper has no disclosure control, so `@media print` forces every
  drawer open — `details{display:block}`, `details>*{display:block!important}`,
  and `details::details-content{content-visibility:visible!important}` for the
  engines that moved the closed state into a pseudo-element. A printout of
  collapsed summaries is a table of contents with no book.
