#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wrap_pages.py — make.sh step 4. ONE skeleton, one writer per role.

Every page in a campaign is the same document with a different <main>. That is
the whole point: one visual world per campaign, no half-reskins. The skeleton
lives here and nowhere else, so a change to the type scale is one edit, not six.

This file implements DESIGN.md sections 1-9. If a token is not in DESIGN.md it
does not belong in the CSS below; if it is, it lives in :root and nowhere else
(RULES C1).

Hard constraints this file is built around (qa-gate.sh + check_form.py):

  A3  inline CSS only. No CDN, no webfont, no external image, no fetch/XHR.
      Every byte the browser needs is in the file it opened. The display face is
      a SYSTEM face — ui-serif resolves to New York on Apple and to
      Constantia/Georgia elsewhere, and the CJK arm resolves to a Song/Ming
      face. Character comes from the pairing, not from a download.
  A2  no innerHTML. The one script this skeleton allows sets attributes and
      document.title; it never builds markup.
  A1' <meta charset="utf-8"> inside the first 512 bytes so the browser prescan
      finds it before it gives up (host != artifact-sandbox).
  FM4 no transform:scale()/zoom and no font-size below 11px (floor here: 12.5).
  FM5 nothing is nowrap.
  C6  >=44x44 touch targets, >=4.5:1 contrast, aria-pressed on the toggle,
      visible focus, prefers-reduced-motion honoured by construction.

BILINGUAL: when STATE.campaign.langs has more than one entry this skeleton emits
the EN/ZH control pair (top right, exactly two controls reading EN and ZH) and
an <!--I18N-RUNTIME--> marker. Step 5 (i18n_overlay.py) replaces the marker with
the runtime and proves the two language arms agree. A page that carries the
controls but no runtime is a dead toggle, and write_docs.py refuses it.

It also refuses two pages that claim the same role, and refuses a fragment that
ships without the blocks its role contract requires — the same rule check_form
enforces at step 9, applied here where the fix is cheap.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import html
import io
import json
import os
import sys

BUILD = os.path.join(ROOT, 'build')
FRAG = os.path.join(BUILD, 'frag')
OUT = os.path.join(BUILD, 'pages')
STATE_P = os.path.join(ROOT, 'STATE.json')
ROLES_P = os.path.join(ROOT, 'bin', 'page-role.json')
MANIFEST_P = os.path.join(BUILD, 'manifest.json')

HTML_LANG = {'h': 'zh-Hant', 's': 'zh-Hans', 'e': 'en'}

# --------------------------------------------------------------------- CSS ---
# DESIGN.md sections 1-9, in order: tokens, base, chrome, components, response.
CSS = """
:root{
  --paper:#FAF8F3; --card:#FFFFFF; --sunk:#F2EEE4;
  --ink:#14161A; --ink-2:#3D434E; --ink-3:#5E6675;
  --rule:#E5E0D5; --rule-hard:#14161A;
  --accent:#123A8C; --accent-bg:#E9EEFB;
  --gap-fg:#7A4400; --gap-bg:#FBEEDA;
  --stop:#8C1D18; --focus:#123A8C;

  --f-display:ui-serif,"New York","Iowan Old Style",Charter,Constantia,Georgia,
    "Songti TC","Songti SC",STSong,"Noto Serif CJK TC",MingLiU,serif;
  --f-text:-apple-system,BlinkMacSystemFont,system-ui,"Segoe UI","PingFang TC",
    "Noto Sans CJK TC","Microsoft JhengHei","Helvetica Neue",Arial,sans-serif;
  --f-mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Roboto Mono",
    "Courier New",monospace;

  --t-display:clamp(30px,6.2vw,46px);
  --t-figure:clamp(34px,8.8vw,44px);
  --t-h2:clamp(21px,3.2vw,25px);
  --t-h3:18px; --t-lede:19px; --t-body:17px;
  --t-mono:15px; --t-cap:14px; --t-micro:12.5px;

  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px;
  --s6:32px; --s7:48px; --s8:64px; --s9:96px;
  --gut:16px; --measure:66ch;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:var(--f-text);font-size:var(--t-body);line-height:1.62;
  font-weight:400;overflow-wrap:break-word}
img{max-width:100%;height:auto}

/* --- language layers (DESIGN.md 7) ---------------------------------------- */
[data-t="e"]{display:none}
:root[data-lang="e"] [data-t="h"]{display:none}
:root[data-lang="e"] [data-t="e"]{display:inline}
:root[data-lang="e"] p[data-t="e"],
:root[data-lang="e"] li[data-t="e"],
:root[data-lang="e"] dd[data-t="e"],
:root[data-lang="e"] div[data-t="e"]{display:block}
/* Per-language metrics. Both arms are in the DOM at once, so the switch lives
   on the root: CJK wants more leading and a hair of tracking, Latin does not.
   Headings keep their own line-height because it is set on the heading. */
:root[data-lang="h"] body{line-height:1.72;letter-spacing:.01em}
:root[data-lang="e"] body{line-height:1.58;letter-spacing:0}

/* --- layout --------------------------------------------------------------- */
.wrap{width:100%;max-width:1040px;margin-left:auto;margin-right:auto;
  padding-left:var(--gut);padding-right:var(--gut)}
main{padding-top:var(--s5);padding-bottom:var(--s8)}
main > section,main > details,main > nav{margin:0 0 var(--s7)}
.hold{max-width:var(--measure)}

/* --- masthead + toggle ---------------------------------------------------- */
.mast{padding-top:var(--s5);padding-bottom:var(--s4);display:flex;
  flex-wrap:wrap;align-items:flex-start;gap:var(--s3) var(--s4)}
.mast .id{flex:1 1 220px;min-width:0}
.mast .evt{margin:0;font-family:var(--f-display);font-size:var(--t-h2);
  font-weight:700;letter-spacing:-.012em;line-height:1.2}
.mast .meta{margin:var(--s2) 0 0;font-size:var(--t-cap);color:var(--ink-2);
  line-height:1.5}
.mast .meta .lk{font-size:var(--t-cap)}
.langsw{display:flex;gap:0;flex:0 0 auto;border:1px solid var(--ink);
  border-radius:6px;overflow:hidden;background:var(--card)}
.langbtn{-webkit-appearance:none;appearance:none;background:var(--card);
  border:0;color:var(--ink-2);font-family:var(--f-mono);
  font-size:var(--t-cap);font-weight:700;letter-spacing:.1em;
  min-width:52px;min-height:44px;padding:0 var(--s3);cursor:pointer;
  display:inline-flex;align-items:center;justify-content:center}
.langbtn + .langbtn{border-left:1px solid var(--rule)}
.langbtn[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.langbtn:focus{outline:2px solid var(--focus);outline-offset:-4px}

/* --- nav ------------------------------------------------------------------ */
.nav{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.nav ul{list-style:none;display:flex;flex-wrap:wrap;gap:0 var(--s5);
  width:100%;max-width:1040px;margin-left:auto;margin-right:auto;
  margin-top:0;margin-bottom:0;
  padding-left:var(--gut);padding-right:var(--gut)}
.nav li{min-width:0}
.nav a{display:flex;align-items:center;min-height:44px;padding:var(--s1) 0;
  font-size:var(--t-cap);font-weight:700;letter-spacing:.02em;
  color:var(--ink-2);text-decoration:none;
  border-bottom:2px solid transparent;margin-bottom:-1px}
.nav a:hover{color:var(--accent)}
.nav a[aria-current="page"]{color:var(--ink);border-bottom-color:var(--ink)}

/* --- headings ------------------------------------------------------------- */
h1,h2,h3{font-family:var(--f-display);font-weight:700;text-wrap:balance}
h1{font-size:var(--t-display);line-height:1.16;letter-spacing:-.021em;
  margin:0 0 var(--s4);max-width:15em}
h2{font-size:var(--t-h2);line-height:1.28;letter-spacing:-.012em;
  margin:var(--s7) 0 var(--s3)}
main > section > h2:first-child{margin-top:0}
h3{font-size:var(--t-h3);line-height:1.42;letter-spacing:-.005em;
  margin:var(--s5) 0 var(--s1)}
p{margin:0 0 var(--s3);max-width:var(--measure)}
a{color:var(--accent)}
a:hover{color:var(--ink)}

/* --- shared atoms --------------------------------------------------------- */
.lk{font-family:var(--f-mono);font-size:var(--t-mono);color:var(--ink);
  font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
/* A locked run stays locked when it IS the headline; locking is about the
   content being identical in every language, not about wearing mono. */
.dr-t .lk,.acct h3 .lk{font-family:var(--f-display);font-size:inherit;
  letter-spacing:inherit}
.gap{display:inline-block;font-family:var(--f-mono);font-size:var(--t-micro);
  font-weight:700;letter-spacing:.1em;color:var(--gap-fg);
  background:var(--gap-bg);border:1px dashed var(--gap-fg);border-radius:3px;
  padding:2px 7px;vertical-align:baseline}
.why{font-size:var(--t-cap);color:var(--ink-2);line-height:1.5}
.src{display:block;font-family:var(--f-mono);font-size:var(--t-micro);
  color:var(--ink-3);line-height:1.5;margin-top:var(--s1);
  overflow-wrap:anywhere}
.note{font-size:var(--t-cap);color:var(--ink-2);max-width:var(--measure)}
.lede{font-size:var(--t-lede);line-height:1.58;color:var(--ink-2);
  max-width:var(--measure)}
.stamp{font-family:var(--f-mono);font-size:var(--t-micro);color:var(--ink-3);
  letter-spacing:.05em;margin:var(--s4) 0 0}
code{font-family:var(--f-mono);font-size:var(--t-mono);background:var(--sunk);
  padding:1px 5px;border-radius:3px;overflow-wrap:anywhere}

/* --- evidence chips (DESIGN.md 4) ----------------------------------------- */
.ev{display:inline-flex;align-items:center;gap:6px;font-size:var(--t-micro);
  letter-spacing:.07em;line-height:1.3;border:1px solid var(--rule);
  border-radius:3px;padding:3px 8px;margin:2px 6px 2px 0;color:var(--ink-2);
  background:var(--card)}
.ev-mark{flex:0 0 auto;width:9px;height:9px;border:1.5px solid currentColor;
  border-radius:1px}
.ev-official{color:var(--ink);border-color:var(--ink-3)}
.ev-official .ev-mark{background:currentColor}
.ev-vendor .ev-mark{background:linear-gradient(90deg,currentColor 50%,
  transparent 50%)}
.ev-third .ev-mark{background:transparent}
.ev-unverified{color:var(--ink-3)}
.ev-unverified .ev-mark{border-style:dotted;background:transparent}
/* The rank chip is a rank, and the status chip is a state. They must never be
   mistaken for one another: the rank wears a mark and a hairline on card
   ground, the status wears sunk ground and no mark. */
:root[data-lang="e"] .ev{text-transform:uppercase}
.chip{display:inline-block;font-family:var(--f-mono);font-size:var(--t-micro);
  letter-spacing:.06em;color:var(--ink-2);background:var(--sunk);
  border-radius:3px;padding:3px 8px;margin:2px 6px 2px 0}

/* --- verdict -------------------------------------------------------------- */
.verdict{border-top:3px solid var(--accent);padding-top:var(--s5)}
.verdict h1 em{font-style:normal;
  box-shadow:inset 0 -.15em 0 var(--accent-bg)}
.grounds{list-style:none;margin:var(--s5) 0 0;padding:0;
  max-width:var(--measure)}
.grounds li{padding:var(--s3) 0;border-top:1px solid var(--rule)}
.grounds li:first-child{border-top:0;padding-top:0}

/* --- the four numbers ----------------------------------------------------- */
.figs{list-style:none;margin:var(--s5) 0 0;padding:0;display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  border-top:2px solid var(--rule-hard)}
.fig{min-width:0;padding:var(--s4) var(--s3) var(--s5) 0;
  border-bottom:1px solid var(--rule)}
.fig .n{display:block;font-family:var(--f-display);font-size:var(--t-figure);
  font-weight:700;line-height:1.05;letter-spacing:-.03em;
  font-variant-numeric:tabular-nums}
.fig.is-gap .n{font-family:var(--f-mono);font-size:var(--t-h3);line-height:1.4}
.fig .k{display:block;font-size:var(--t-cap);font-weight:700;
  margin-top:var(--s2)}

/* --- actions -------------------------------------------------------------- */
.acts{margin:var(--s4) 0 0;padding:0;list-style:none;counter-reset:act;
  max-width:var(--measure)}
.acts > li{counter-increment:act;position:relative;padding:var(--s4) 0 var(--s4)
  var(--s6);border-top:1px solid var(--rule)}
.acts > li::before{content:counter(act);position:absolute;left:0;top:var(--s4);
  font-family:var(--f-mono);font-size:var(--t-cap);font-weight:700;
  color:var(--accent);letter-spacing:.05em}
.acts b{display:block;font-size:var(--t-h3);font-family:var(--f-display);
  line-height:1.4;margin-bottom:var(--s1)}

/* --- drawers: every section and every subsection --------------------------
   Native <details>. No JS accordion: <details> is keyboard-operable, is found
   by the browser's own find-in-page even while closed in modern engines, and
   prints. The summary always carries a title AND a scent line, so a closed
   drawer still informs (RULES C6: >=44px target, visible focus ring). */
details.dr{background:var(--card);border:1px solid var(--rule);border-radius:4px;
  margin:0 0 var(--s3)}
details.dr > summary{list-style:none;display:block;cursor:pointer;position:relative;
  min-height:44px;padding:var(--s3) var(--s4) var(--s3) var(--s6);
  -webkit-user-select:none;user-select:none}
details.dr > summary::-webkit-details-marker{display:none}
details.dr > summary::marker{content:""}
details.dr > summary::before{content:"";position:absolute;left:var(--s4);
  top:calc(var(--s3) + .55em);width:7px;height:7px;
  border-right:2px solid var(--ink-2);border-bottom:2px solid var(--ink-2);
  transform:rotate(-45deg)}
details.dr[open] > summary::before{transform:rotate(45deg)}
details.dr > summary:hover{background:var(--accent-bg)}
details.dr > summary:focus-visible{outline:2px solid var(--focus);
  outline-offset:-2px}
.dr-t{display:block;font-family:var(--f-display);font-size:var(--t-h3);
  font-weight:700;line-height:1.36}
.dr-t .lk{font-family:var(--f-display);font-size:inherit;letter-spacing:inherit}
.dr-s{display:block;font-size:var(--t-cap);color:var(--ink-2);line-height:1.45;
  margin-top:2px}
.dr-s .lk{font-size:var(--t-cap);color:var(--ink-2)}
.dr-b{padding:var(--s2) var(--s4) var(--s4);border-top:1px solid var(--rule)}
.dr-b > :first-child{margin-top:var(--s4)}
.dr-b > h2:first-child,.dr-b > h3:first-child{margin-top:var(--s4)}
.sep{color:var(--ink-3);padding:0 2px}

/* Top-level drawers read as SECTIONS: heavy rule, display-size title, no card
   chrome. Nested drawers read as cards. One component, two altitudes. */
main > details.dr{background:transparent;border:0;
  border-top:2px solid var(--rule-hard);border-radius:0;margin:0 0 var(--s7)}
main > details.dr > summary{padding:var(--s4) 0 var(--s4) var(--s6)}
main > details.dr > summary::before{left:var(--s1);top:calc(var(--s4) + .62em);
  width:9px;height:9px;border-color:var(--ink)}
main > details.dr > summary:hover{background:transparent}
main > details.dr > summary:hover .dr-t{color:var(--accent)}
main > details.dr > summary .dr-t{font-size:var(--t-h2);letter-spacing:-.012em;
  line-height:1.28}
main > details.dr > .dr-b{border-top:0;padding:0 0 var(--s5)}
main > details.dr.verdict{border-top:3px solid var(--accent)}
main > details.dr.verdict > summary{padding-left:var(--s6)}
main > details.dr.verdict h1{margin:0}
.dr-lede{display:block;font-size:var(--t-lede);line-height:1.55;
  color:var(--ink-2);margin-top:var(--s3);max-width:var(--measure)}
main > details.dr.caveat{background:var(--gap-bg);border:1px dashed var(--gap-fg);
  border-radius:4px;padding:0 var(--s4)}
main > details.dr.caveat > summary::before{border-color:var(--gap-fg)}
main > details.dr.caveat > .dr-b{padding-bottom:var(--s5)}
main > details.dr.method{border-top:1px solid var(--rule)}
main > details.dr.method .dr-t{font-size:var(--t-h3)}
main > details.dr.method .dr-b{font-size:var(--t-cap);color:var(--ink-2)}
main > details.dr.method .dr-b ul{padding-left:var(--s5)}

/* --- sessions ------------------------------------------------------------- */
.ses{list-style:none;margin:var(--s5) 0 0;padding:0;display:grid;
  gap:var(--s3);grid-template-columns:repeat(auto-fill,minmax(min(100%,264px),1fr))}
.ses > li{min-width:0;background:var(--card);border:1px solid var(--rule);
  border-radius:4px;padding:var(--s4)}
.ses .when{margin:0;display:flex;flex-wrap:wrap;gap:var(--s2);
  padding-bottom:var(--s2);border-bottom:1px solid var(--rule)}
.ses h3{margin:var(--s3) 0 var(--s2);font-size:var(--t-h3)}
.ses .where{margin:0 0 var(--s2);font-size:var(--t-cap);color:var(--ink-2)}
.ses .tags{margin:var(--s2) 0 0}
/* A session that carries a hardware-demand signal earns a heavier top edge and
   says WHICH probe matched, so the mark is auditable rather than a label. */
.ses > li.is-hw{border-top:3px solid var(--ink)}
.ses .hw{margin:var(--s3) 0 0;font-size:var(--t-cap);color:var(--ink-2);
  padding-top:var(--s2);border-top:1px solid var(--rule)}
.hwm{display:inline-block;font-family:var(--f-mono);font-size:var(--t-micro);
  letter-spacing:.06em;color:var(--paper);background:var(--ink);border-radius:3px;
  padding:2px 7px;margin-right:var(--s2)}
.hwm .lk{color:var(--paper);font-size:var(--t-micro)}

/* --- room ledger ---------------------------------------------------------- */
.rooms{list-style:none;margin:var(--s4) 0 0;padding:0;display:grid;
  gap:0;grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr))}
.rooms li{min-width:0;display:flex;align-items:baseline;gap:var(--s3);
  padding:var(--s3) 0;border-bottom:1px solid var(--rule)}
.rooms .rn{min-width:0;flex:1 1 auto}
.rooms .rc{flex:0 0 auto;font-family:var(--f-mono);font-size:var(--t-cap);
  color:var(--ink-2);font-variant-numeric:tabular-nums}

/* --- caveat / gap panel --------------------------------------------------- */
.caveat{background:var(--gap-bg);border:1px dashed var(--gap-fg);
  border-radius:4px;padding:var(--s5)}
.caveat.is-clear{background:var(--card);border-style:solid;border-color:var(--rule)}
.caveat.is-clear li{border-top-color:var(--rule)}
.caveat h2{margin-top:0}
.caveat ul{margin:var(--s4) 0 0;padding:0;list-style:none;
  max-width:var(--measure)}
.caveat li{padding:var(--s3) 0;border-top:1px solid rgba(122,68,0,.22)}
.caveat li:first-child{border-top:0;padding-top:0}
.caveat .why{color:var(--gap-fg)}

/* --- plays ---------------------------------------------------------------- */
.play dl{margin:var(--s4) 0 0;display:grid;gap:0;
  grid-template-columns:1fr}
.play dt{font-size:var(--t-micro);letter-spacing:.09em;font-weight:700;
  color:var(--ink-3);padding-top:var(--s4);border-top:1px solid var(--rule)}
.play dt:first-of-type{border-top:0;padding-top:0}
.play dd{margin:var(--s2) 0 var(--s4);max-width:var(--measure)}

/* --- register table (C3: stacks below 720px) ------------------------------ */
.regwrap{margin:var(--s4) 0 0;overflow-x:auto}
.reg{width:100%;border-collapse:collapse}
.reg th,.reg td{text-align:left;vertical-align:top;font-size:var(--t-cap);
  padding:var(--s3);border-bottom:1px solid var(--rule)}
.reg thead th{font-size:var(--t-micro);letter-spacing:.09em;
  border-bottom:2px solid var(--rule-hard);color:var(--ink-2)}
.reg .lbl{display:block;font-size:var(--t-micro);letter-spacing:.09em;
  color:var(--ink-3);margin-bottom:var(--s1)}
.reg thead{display:none}
.reg,.reg tbody,.reg tr,.reg td{display:block;width:100%}
.reg tr{border:1px solid var(--rule);border-radius:4px;background:var(--card);
  padding:var(--s3);margin-bottom:var(--s3)}
.reg td{border-bottom:1px solid var(--rule);padding:var(--s2) 0}
.reg td:last-child{border-bottom:0}

/* --- account bands + cards ------------------------------------------------ */
.band{border-top:2px solid var(--rule-hard);padding-top:var(--s4)}
.band .bandhead{display:flex;flex-wrap:wrap;align-items:baseline;
  gap:var(--s2) var(--s4)}
.band h2{margin:0;flex:1 1 auto;min-width:0}
.band .bandn{flex:0 0 auto;font-family:var(--f-mono);font-size:var(--t-cap);
  color:var(--ink-2);font-variant-numeric:tabular-nums}
.band .banddesc{margin:var(--s2) 0 0;font-size:var(--t-cap);color:var(--ink-2);
  max-width:var(--measure)}
/* An account is a DRAWER, so the band is a stack, not a grid: opening one card
   must not reflow its neighbours out from under a thumb. */
.accts{margin:var(--s5) 0 0;padding:0}
details.acct{min-width:0}
details.acct.is-full{border-left:1px solid var(--ink)}
.fullmark{display:inline-block;font-family:var(--f-mono);font-size:var(--t-micro);
  letter-spacing:.08em;color:var(--paper);background:var(--ink);border-radius:3px;
  padding:2px 7px;margin-left:var(--s2);vertical-align:middle}
.badges{margin:0 0 var(--s3)}
.cells{margin:var(--s3) 0 0}
.cells dt{font-size:var(--t-micro);letter-spacing:.09em;color:var(--ink-3);
  margin-top:var(--s4);padding-top:var(--s3);border-top:1px solid var(--rule);
  text-transform:none}
.cells dt:first-of-type{border-top:0;padding-top:0;margin-top:0}
.cells .cap{display:block;font-size:var(--t-cap);letter-spacing:0;
  color:var(--ink-2);margin-top:2px;max-width:var(--measure)}
.cells dd{margin:var(--s2) 0 0;font-size:var(--t-cap)}
.conf{margin:var(--s4) 0 0;font-size:var(--t-cap);padding-top:var(--s3);
  border-top:1px solid var(--rule)}
.cf{display:inline-block;font-size:var(--t-micro);border:1px solid var(--rule);
  border-radius:3px;padding:3px 8px;margin:2px 6px 2px 0;color:var(--ink-2)}
.cf-h{border-color:var(--ink);color:var(--ink)}
.nextact{margin:var(--s4) 0 0;padding:var(--s3) var(--s4);background:var(--sunk);
  border-radius:4px;font-size:var(--t-cap);max-width:var(--measure)}
.nextact b{display:block;font-family:var(--f-display);font-size:var(--t-h3);
  margin-bottom:var(--s1)}
details.deep{margin-top:var(--s4);border-color:var(--ink-3)}
.spell{list-style:none;margin:var(--s2) 0 0;padding:0}
.spell li{padding:var(--s2) 0;border-top:1px solid var(--rule)}
.spell li:first-child{border-top:0}
.dt2{margin:var(--s5) 0 var(--s2);font-family:var(--f-display);
  font-size:var(--t-h3);font-weight:700}

/* --- compare -------------------------------------------------------------- */
.axes{display:grid;gap:var(--s5);
  grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}
.axis{min-width:0;border-top:2px solid var(--rule-hard);padding-top:var(--s4)}
.axis h3{margin:0}
.axisfull{margin:var(--s2) 0 var(--s3);font-family:var(--f-mono);
  font-size:var(--t-cap);color:var(--ink-2);overflow-wrap:anywhere}
.axislist{list-style:none;margin:var(--s4) 0 0;padding:0}
.axislist li{padding:var(--s3) 0;border-top:1px solid var(--rule);min-width:0}
.axislist b{font-size:var(--t-body)}
.traps{list-style:none;margin:var(--s5) 0 0;padding:0;display:grid;
  gap:var(--s3);grid-template-columns:repeat(auto-fill,minmax(min(100%,288px),1fr))}
.trap{min-width:0;background:var(--card);border:1px solid var(--rule);
  border-radius:4px;padding:var(--s4)}
.trap .ab{margin:var(--s2) 0 0;font-size:var(--t-cap)}
.trap .neg{margin:var(--s3) 0 0;background:var(--sunk);border-radius:3px;
  padding:var(--s2) var(--s3);font-family:var(--f-mono);
  font-size:var(--t-micro);color:var(--ink-2);overflow-wrap:anywhere}

/* --- evidence-bearing prose ----------------------------------------------- */
.ev-list,.donts{list-style:none;margin:var(--s4) 0 0;padding:0;
  max-width:var(--measure)}
.ev-list > li,.donts > li{padding:var(--s4) 0;border-top:1px solid var(--rule)}
.ev-list > li:first-child,.donts > li:first-child{border-top:0;padding-top:0}
.srcl{overflow-wrap:anywhere}
.punch{margin:var(--s4) 0 0;font-family:var(--f-display);font-size:var(--t-lede);
  line-height:1.5;max-width:var(--measure)}
.askq{margin:var(--s3) 0 0;padding:var(--s3) var(--s4);background:var(--sunk);
  border-radius:4px;font-family:var(--f-display);font-size:var(--t-lede);
  line-height:1.5;max-width:var(--measure)}
.meta-row{margin:var(--s2) 0 0;font-size:var(--t-cap);color:var(--ink-2)}
.actses{margin:0;font-family:var(--f-display);font-size:var(--t-h3);
  font-weight:700;line-height:1.4}
.actses .lk{font-family:var(--f-display);font-size:inherit;
  letter-spacing:inherit}
.acts .why{display:block;margin:var(--s2) 0 var(--s4)}
.formula{margin:var(--s3) 0;padding:var(--s3) var(--s4);background:var(--sunk);
  border-radius:3px;font-family:var(--f-mono);font-size:var(--t-mono);
  color:var(--ink);overflow-x:auto;max-width:100%}
.q{margin:var(--s4) 0 0;padding:var(--s5) var(--s4);background:var(--sunk);
  border-radius:4px;font-family:var(--f-display);font-size:var(--t-lede);
  line-height:1.55;max-width:var(--measure)}
.thesis{margin:var(--s3) 0 0}
.thesis dt{font-size:var(--t-micro);letter-spacing:.09em;color:var(--ink-3);
  margin-top:var(--s4);padding-top:var(--s3);border-top:1px solid var(--rule)}
.thesis dt:first-of-type{border-top:0;padding-top:0;margin-top:0}
.thesis dt.kill{color:var(--gap-fg)}
.thesis dd{margin:var(--s2) 0 0;max-width:var(--measure)}
.odds{list-style:none;margin:var(--s4) 0 0;padding:0;max-width:var(--measure)}
.odds > li{padding:var(--s4) 0;border-top:1px solid var(--rule)}
.odds > li:first-child{border-top:0;padding-top:0}
.rank{display:inline-block;min-width:22px;font-family:var(--f-mono);
  font-weight:700;color:var(--accent)}
.rank .lk{color:var(--accent);font-weight:700}
.xlink{display:flex;flex-wrap:wrap;gap:var(--s4);justify-content:space-between;
  border-top:1px solid var(--rule);padding-top:var(--s4)}
.xlink a{min-width:0;font-size:var(--t-cap);font-weight:700;
  text-decoration:none;min-height:44px;display:flex;align-items:center}
.foot{border-top:1px solid var(--rule);padding-top:var(--s5);
  padding-bottom:var(--s8);font-size:var(--t-cap);color:var(--ink-2)}
.foot a{overflow-wrap:anywhere}

/* --- responsive (DESIGN.md 9) --------------------------------------------- */
@media (min-width:520px){
  .figs{grid-template-columns:repeat(4,minmax(0,1fr))}
  .fig + .fig{border-left:1px solid var(--rule);padding-left:var(--s4)}
}
@media (min-width:720px){
  .reg thead{display:table-header-group}
  .reg,.reg tbody{display:table}
  .reg tbody{width:100%}
  .reg tr{display:table-row;border:0;border-radius:0;background:none;
    padding:0;margin:0}
  .reg td{display:table-cell;border-bottom:1px solid var(--rule);
    padding:var(--s3)}
  .reg .lbl{display:none}
  .play dl{grid-template-columns:minmax(0,10em) minmax(0,1fr);
    column-gap:var(--s5)}
  .play dt{padding-top:var(--s4);border-top:1px solid var(--rule)}
  .play dd{margin:0;padding-top:var(--s4);border-top:1px solid var(--rule)}
  .play dt:first-of-type,.play dd:first-of-type{border-top:0;padding-top:0}
}
@media (min-width:760px){
  :root{--gut:24px}
  .mast{padding-top:var(--s6)}
  main{padding-top:var(--s6)}
}
@media (prefers-reduced-motion:no-preference){
  .langbtn,.nav a,a,details.dr > summary{transition:background-color 140ms
    cubic-bezier(.2,.7,.2,1),border-color 140ms cubic-bezier(.2,.7,.2,1),
    color 140ms cubic-bezier(.2,.7,.2,1)}
}
/* Paper has no disclosure control: on print every drawer is open, because a
   printout of collapsed summaries is a table of contents with no book. */
@media print{
  details{display:block}
  details>*{display:block!important}
  details::details-content{content-visibility:visible!important;
    display:block!important;block-size:auto!important;overflow:visible!important}
  details.dr>summary::before{display:none}
  details.dr,details.acct,details.deep{border:0;background:none;
    break-inside:avoid;page-break-inside:avoid}
  main>details.dr{border-top:1px solid #14161A}
  .dr-b{border-top:0;padding-left:0;padding-right:0}
  .langsw,.nav,.xlink{display:none}
  body{background:#FFFFFF}
  [data-t="e"]{display:none}
}
"""


def esc(v):
    return html.escape('' if v is None else str(v), quote=True)


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def lang_switch():
    """Exactly two controls, reading EN and ZH, top right, 44x44, aria-pressed.

    ZH is the source language and therefore the no-JS default, so it carries
    aria-pressed="true" in the static markup; the runtime re-syncs both on load.
    """
    return (
        '  <div class="langsw" role="group" aria-label="Language / 語言">\n'
        '    <button class="langbtn" type="button" data-lang-btn="e"'
        ' aria-pressed="false">EN</button>\n'
        '    <button class="langbtn" type="button" data-lang-btn="h"'
        ' aria-pressed="true">ZH</button>\n'
        '  </div>')


def skeleton(page, campaign, frag, lang, langs, asof):
    title_h = page.get('title') or page['role']
    title_e = page.get('title_e') or title_h
    event = campaign.get('event') or ''
    src = campaign.get('catalog') or ''
    bilingual = len(langs) > 1
    stamp = ('<span data-t="h">狀態截至 %s</span>'
             '<span data-t="e">Status as of %s</span>' % (esc(asof), esc(asof)))

    parts = [
        '<!doctype html>',
        '<html lang="%s" data-lang="%s">' % (esc(HTML_LANG.get(lang, 'zh-Hant')), esc(lang)),
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>%s · %s</title>' % (esc(title_h), esc(event)),
        '<style>%s</style>' % CSS,
    ]
    if bilingual:
        parts.append('<!--I18N-RUNTIME-->')
    parts += [
        '</head>',
        '<body data-role="%s" data-title-h="%s" data-title-e="%s">'
        % (esc(page['role']), esc('%s · %s' % (title_h, event)),
           esc('%s · %s' % (title_e, event))),
        '<header class="mast wrap">',
        '  <div class="id">',
        '    <p class="evt">%s</p>' % esc(event),
        '    <p class="meta"><span class="lk">%s</span> · %s</p>'
        % (esc(campaign.get('dates')), esc(campaign.get('venue'))),
        '  </div>',
    ]
    if bilingual:
        parts.append(lang_switch())
    parts += [
        '</header>',
        '<!--NAV-->',
        '<main class="wrap">',
        frag.rstrip('\n'),
        '</main>',
        '<footer class="foot wrap">',
    ]
    if src:
        parts.append('  <p><span data-t="h">官方目錄</span>'
                     '<span data-t="e">Official catalogue</span>： '
                     '<a href="%s">%s</a></p>' % (esc(src), esc(src)))
    else:
        parts.append('  <p><span data-t="h">官方目錄：GAP —— STATE.campaign.catalog 未設定'
                     '</span><span data-t="e">Official catalogue: GAP — '
                     'STATE.campaign.catalog is unset</span></p>')
    parts += [
        '  <p><span data-t="h">這一頁的每個數字都是建置時從 JSON 算出來的。'
        '算不出來的欄位印 GAP 和原因，不印零。</span>'
        '<span data-t="e">Every number on this page is computed from JSON at '
        'build time. A field that cannot be computed prints GAP and the reason, '
        'never a zero.</span></p>',
        '  <p class="stamp" data-fresh="1">%s</p>' % stamp,
        '</footer>',
        '</body>',
        '</html>',
        '']
    return '\n'.join(parts)


def main():
    state = load(STATE_P) or {}
    campaign = state.get('campaign') or {}
    langs = [str(x) for x in (campaign.get('langs') or ['h'])]
    lang = langs[0]
    asof = (state.get('factbase') or {}).get('asOf')
    if not asof:
        sys.exit('wrap_pages: FAIL STATE.factbase.asOf is unset. B8: every page carries a '
                 'date and there is no date to carry.')
    manifest = load(MANIFEST_P)
    if not manifest:
        sys.exit('wrap_pages: FAIL %s missing — step 3 (build_fragments.py) did not run' % MANIFEST_P)
    roles_spec = load(ROLES_P) or {}
    block_attr = roles_spec.get('_blockAttr') or 'data-block'

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for f in sorted(os.listdir(OUT)):
        if f.endswith('.html'):
            os.unlink(os.path.join(OUT, f))

    seen_role, seen_file, fails = {}, {}, []
    for page in manifest['pages']:
        role, fname = page['role'], page['file']
        if role in seen_role:
            fails.append('two writers claim role "%s": %s and %s'
                         % (role, seen_role[role], fname))
        if fname in seen_file:
            fails.append('two roles claim file "%s": %s and %s' % (fname, seen_file[fname], role))
        seen_role[role], seen_file[fname] = fname, role

        frag_p = os.path.join(FRAG, role + '.html')
        if not os.path.exists(frag_p):
            fails.append('role "%s" has no fragment at %s' % (role, frag_p))
            continue
        frag = io.open(frag_p, encoding='utf-8').read()

        spec = roles_spec.get(role) or {}
        for need in spec.get('requires', []):
            if '%s="%s"' % (block_attr, need) not in frag:
                fails.append('%s (role %s) ships without %s="%s" — page-role.json requires it'
                             % (fname, role, block_attr, need))
        for bad in spec.get('forbids', []):
            if '%s="%s"' % (block_attr, bad) in frag:
                fails.append('%s (role %s) carries forbidden block "%s"' % (fname, role, bad))
        if '<script' in frag.lower():
            fails.append('%s carries a <script> — the skeleton owns the only script (A2/A3)' % fname)
        if len(langs) > 1 and 'data-t="e"' not in frag:
            fails.append('%s (role %s) has no data-t="e" layer — the campaign ships %s but this '
                         'fragment is monolingual' % (fname, role, '+'.join(langs)))

        io.open(os.path.join(OUT, fname), 'w', encoding='utf-8').write(
            skeleton(page, campaign, frag, lang, langs, asof))

    if fails:
        for f in fails:
            print('wrap_pages: FAIL %s' % f)
        sys.exit('wrap_pages: %d FAIL — fix the fragment builder, not the gate.' % len(fails))
    print('wrap_pages: %d pages wrapped in one skeleton (%s) lang=%s langs=%s toggle=%s'
          % (len(manifest['pages']), ' '.join(p['file'] for p in manifest['pages']),
             lang, '+'.join(langs), 'on' if len(langs) > 1 else 'off'))


main()
