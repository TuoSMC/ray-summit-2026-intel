#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i18n_overlay.py --src <lang> — make.sh step 5. Makes the language toggle real.

RULES B7: another language is VOCABULARY work. A character-conversion tool's
output is an error, not a draft. So this step does not translate anything — the
two language arms are authored by hand in build_fragments.py (step 3) and both
of them ship inside one HTML file. What this step does is make that shipped pair
into a working, provable toggle:

  1. RUNTIME     replaces the <!--I18N-RUNTIME--> marker the skeleton left in
                 <head> with the one inline script the pack is allowed. It sets
                 the root data-lang before first paint (no flash of the wrong
                 language), mirrors aria-pressed onto the two controls, swaps
                 document.title, and persists the choice in localStorage.
                 No network, no cookies (A3/A4). No innerHTML — the script sets
                 attributes and never builds markup (A2).

  2. PAIR GATE   every translatable run must be a pair: <span data-t="h"> then
                 <span data-t="e">, in that order, with nothing unmatched. A
                 half-translated page is worse than a monolingual one, so it
                 fails here rather than shipping.

  3. LOCKED GATE RULES B6. Numbers, dates, clock times, room names, person
                 names, company legal names and URLs must come out
                 BYTE-IDENTICAL in every language. They are what a rep reads
                 aloud in a corridor; a "translated" room name sends someone to
                 the wrong floor. Both arms of every pair are scanned for the
                 locked set and any divergence is a hard fail.

  4. VOCAB GATE  the evidence tags are vocabulary, not transcoding:
                 官方一手 = Official first-party, 廠商自報 = Vendor-reported,
                 第三方 = Third-party, 未證 = Unverified, and GAP stays GAP in
                 both languages because it is a status token, not a word.
                 An arm that carries one side without the other fails.

  5. TOGGLE GATE exactly two controls, reading EN and ZH, both with
                 aria-pressed, on every page.

ORDER FAILURE 1 (see make.sh): this step may only run on frozen source prose.
make.sh calls it after steps 3-4, never before. It refuses any --src that is not
STATE.campaign.langs[0].

When the campaign has one language it prints one line and exits 0. A skip is a
skip, not a silent success: it says which language it kept and why.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import re
import sys
from collections import Counter

DATA = os.path.join(ROOT, 'data')
PAGES = os.path.join(ROOT, 'build', 'pages')
STATE_P = os.path.join(ROOT, 'STATE.json')

MARKER = '<!--I18N-RUNTIME-->'

# Evidence vocabulary. Same table as build_fragments.py; data/termbase.json
# overrides it so P6 can merge the pairs upward without touching code.
EVIDENCE = {
    'official':   ('官方一手', 'Official first-party'),
    'vendor':     ('廠商自報', 'Vendor-reported'),
    'third':      ('第三方',   'Third-party'),
    'unverified': ('未證',     'Unverified'),
}

RUNTIME = """(function(){
  var KEY = '%(key)s', ROOTEL = document.documentElement, DEF = '%(def)s';
  var TAG = {h: 'zh-Hant', s: 'zh-Hans', e: 'en'};
  var cur = DEF;
  function paint(l){
    ROOTEL.setAttribute('data-lang', l);
    ROOTEL.setAttribute('lang', TAG[l] || TAG[DEF]);
    var body = document.body;
    if (body) {
      var t = body.getAttribute(l === 'e' ? 'data-title-e' : 'data-title-h');
      if (t) { document.title = t; }
    }
    var btns = document.querySelectorAll('[data-lang-btn]');
    for (var i = 0; i < btns.length; i++) {
      var on = btns[i].getAttribute('data-lang-btn') === l;
      btns[i].setAttribute('aria-pressed', on ? 'true' : 'false');
    }
  }
  function stored(){
    try {
      var v = window.localStorage.getItem(KEY);
      return (v === 'e' || v === 'h' || v === 's') ? v : DEF;
    } catch (err) { return DEF; }
  }
  cur = stored();
  paint(cur);
  document.addEventListener('DOMContentLoaded', function(){ paint(cur); });
  document.addEventListener('click', function(ev){
    var n = ev.target;
    while (n && n !== document) {
      if (n.getAttribute && n.getAttribute('data-lang-btn')) { break; }
      n = n.parentNode;
    }
    if (!n || n === document) { return; }
    cur = n.getAttribute('data-lang-btn');
    paint(cur);
    try { window.localStorage.setItem(KEY, cur); } catch (err) {}
  });
})();"""


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def arg(flag, default=None):
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == flag and i + 1 < len(a):
            return a[i + 1]
        if x.startswith(flag + '='):
            return x.split('=', 1)[1]
    return default


def as_list(blob):
    if isinstance(blob, dict):
        inner = blob.get('items') or blob.get('records') or blob.get('orgs')
        if isinstance(inner, list):
            return inner
        return [v for v in blob.values() if isinstance(v, dict)]
    return [r for r in (blob or []) if isinstance(r, dict)]


state = load(STATE_P) or {}
campaign = state.get('campaign') or {}
langs = [str(x) for x in (campaign.get('langs') or ['h'])]
src = arg('--src', langs[0])

if src != langs[0]:
    sys.exit('i18n_overlay: FAIL --src %s is not the source language %s. Build the source, '
             'freeze it, then overlay (B7).' % (src, langs[0]))
if len(langs) < 2:
    print('i18n_overlay: skip — STATE.campaign.langs is ["%s"] only. Nothing to pair, no toggle '
          'to wire; the source pages are the shipped pages.' % src)
    raise SystemExit(0)

termbase = load(os.path.join(DATA, 'termbase.json'), {}) or {}
for k, pair in (termbase.get('evidence') or {}).items():
    if isinstance(pair, dict) and pair.get('h') and pair.get('e') and k in EVIDENCE:
        EVIDENCE[k] = (str(pair['h']), str(pair['e']))

sessions = as_list(load(os.path.join(DATA, 'sessions.json'), []))
speakers = as_list(load(os.path.join(DATA, 'speakers.json'), []))
orgs = as_list(load(os.path.join(DATA, 'orgs.json'), []))

# ------------------------------------------------------------ locked set ----
# B6 is enforced in two ways, and the split matters.
#
# FIGURES — numbers, dates, clock times and URLs cannot be kept out of a
# sentence, so both arms are scanned and compared. A figure that appears in one
# arm and not the other is a new claim with no source.
#
# NAMES — room names, person names and company legal names are protected by
# PLACEMENT instead. build_fragments.py emits them through lk(), which always
# sits OUTSIDE the language pair, so no code path can translate them. That is
# proved below by refusing any lk() run found inside an arm — a structural
# check with no false positives, unlike matching name strings against prose
# (this event has a room called "Keynote" and companies called "Grab",
# "Notion", "Apple" and "Intel"; string-matching those against English prose
# invents divergences that do not exist).
NAMES = set()
for rec in sessions:
    if rec.get('room'):
        NAMES.add(str(rec['room']))
for rec in speakers:
    if rec.get('name'):
        NAMES.add(str(rec['name']))
for rec in orgs:
    if rec.get('legal_name'):
        NAMES.add(str(rec['legal_name']))

LOCKED = [
    r'https?://[^\s"\'<>]+',                       # URLs
    r'\d{4}-\d{2}-\d{2}',                          # ISO dates
    r'\d{1,2}:\d{2}\s?(?:AM|PM)',                  # clock times
]
LOCKED += [str(p) for p in ((termbase.get('locked') or {}).get('patterns') or [])]
# Bare figures last, and without swallowing the punctuation that follows them:
# "3." in English and "3。" in Chinese are the same locked figure.
LOCKED += [r'(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])']
LOCKED_RE = re.compile('|'.join('(?:%s)' % p for p in LOCKED))

TAGRE = re.compile(r'<[^>]+>')
OPEN_T = re.compile(r'<span\s+data-t="([hse])"\s*>')
SPAN_ANY = re.compile(r'<span\b|</span>', re.I)
LK_IN_ARM = re.compile(r'<span class="lk">(.*?)</span>', re.S)


def slug(text):
    parts = re.findall(r'[a-z0-9]+', str(text).lower())
    return '-'.join(parts) or 'campaign'


def visible(chunk):
    return TAGRE.sub(' ', chunk)


def layers(doc):
    """[(lang, inner_html, tag_start)] in document order, nesting-aware.

    A language layer may legitimately contain markup (<em>, a locked run), so
    the closing tag is found by counting <span>/</span> rather than by a lazy
    regex that would stop at the first close.
    """
    out = []
    for m in OPEN_T.finditer(doc):
        depth, pos, end = 1, m.end(), None
        for t in SPAN_ANY.finditer(doc, m.end()):
            depth += 1 if t.group(0).lower().startswith('<span') else -1
            if depth == 0:
                end = t.start()
                break
        if end is None:
            end = len(doc)
        out.append((m.group(1), doc[pos:end], m.start()))
    return out


def line_of(doc, pos):
    return doc.count('\n', 0, pos) + 1


def check_page(name, doc, fails):
    ls = layers(doc)
    if not ls:
        fails.append('%s carries no data-t language layer at all — step 3 built a monolingual '
                     'fragment' % name)
        return
    # ---- 2. pair gate -----------------------------------------------------
    pairs, i = [], 0
    while i < len(ls):
        if i + 1 < len(ls) and ls[i][0] == src and ls[i + 1][0] != src:
            pairs.append((ls[i], ls[i + 1]))
            i += 2
        else:
            fails.append('%s:%d unmatched data-t="%s" layer — every translatable run is a pair, '
                         '%s first (DESIGN.md 7)' % (name, line_of(doc, ls[i][2]), ls[i][0], src))
            i += 1
    # ---- 3. locked gate (B6) + 4. vocabulary gate -------------------------
    by_h = dict((h, e) for h, e in EVIDENCE.values())
    by_e = dict((e, h) for h, e in EVIDENCE.values())
    for (lang_a, a_html, a_pos), (lang_b, b_html, _b_pos) in pairs:
        va, vb = visible(a_html), visible(b_html)
        ca = Counter(m.group(0) for m in LOCKED_RE.finditer(va))
        cb = Counter(m.group(0) for m in LOCKED_RE.finditer(vb))
        if ca != cb:
            missing = sorted((ca - cb).elements())[:6]
            added = sorted((cb - ca).elements())[:6]
            fails.append('%s:%d figure drift %s->%s  missing=%s added=%s\n'
                         '     %s: "%s"\n     %s: "%s"'
                         % (name, line_of(doc, a_pos), lang_a, lang_b, missing, added,
                            lang_a, va.strip()[:90], lang_b, vb.strip()[:90]))
        for arm_html, arm_lang in ((a_html, lang_a), (b_html, lang_b)):
            for m in LK_IN_ARM.finditer(arm_html):
                fails.append('%s:%d a locked run "%s" sits INSIDE the %s arm — emit it with lk() '
                             'outside the pair so no language can rewrite it (B6, DESIGN.md 6)'
                             % (name, line_of(doc, a_pos), visible(m.group(1)).strip()[:40],
                                arm_lang))
        # The evidence tags are vocabulary. A chip's arms are the tag and
        # nothing else, so the comparison is exact — no substring guessing
        # ("未證" is a substring of "尚未證實", which is a different sentence).
        ta, tb2 = va.strip(), vb.strip()
        if ta in by_h and tb2.lower() != by_h[ta].lower():
            fails.append('%s:%d evidence tag "%s" is paired with "%s"; it must read "%s" — the '
                         'tags are vocabulary, not transcoding'
                         % (name, line_of(doc, a_pos), ta, tb2[:40], by_h[ta]))
        if tb2 in by_e and ta != by_e[tb2]:
            fails.append('%s:%d evidence tag "%s" is paired with "%s"; it must read "%s"'
                         % (name, line_of(doc, a_pos), tb2, ta[:40], by_e[tb2]))
    # ---- 5. toggle gate ---------------------------------------------------
    btns = re.findall(r'<button[^>]*data-lang-btn="([a-z])"[^>]*>([^<]*)</button>', doc)
    if len(btns) != 2:
        fails.append('%s carries %d language control(s); the contract is exactly two, reading '
                     'EN and ZH (DESIGN.md 7)' % (name, len(btns)))
    labels = sorted(lbl.strip() for _v, lbl in btns)
    if btns and labels != ['EN', 'ZH']:
        fails.append('%s language controls read %s; they must read EN and ZH' % (name, labels))
    for v, _lbl in btns:
        if not re.search(r'<button[^>]*data-lang-btn="%s"[^>]*aria-pressed=' % v, doc):
            fails.append('%s control "%s" has no aria-pressed (C6)' % (name, v))
    return


def main():
    if not os.path.isdir(PAGES):
        sys.exit('i18n_overlay: FAIL %s missing — step 4 (wrap_pages.py) did not run' % PAGES)
    files = sorted(f for f in os.listdir(PAGES) if f.endswith('.html'))
    if not files:
        sys.exit('i18n_overlay: FAIL no built page in %s' % PAGES)

    key = 'evt.%s.lang' % slug(campaign.get('event'))
    script = '<script>\n%s\n</script>' % (RUNTIME % {'key': key, 'def': src})

    fails, wired, paired = [], 0, 0
    for f in files:
        path = os.path.join(PAGES, f)
        doc = io.open(path, encoding='utf-8').read()
        check_page(f, doc, fails)
        paired += len(layers(doc)) // 2
        if MARKER in doc:
            doc = doc.replace(MARKER, script, 1)
            io.open(path, 'w', encoding='utf-8').write(doc)
            wired += 1
        elif '<script' not in doc.lower():
            fails.append('%s has neither the %s marker nor a runtime — the toggle would ship '
                         'dead' % (f, MARKER))

    if fails:
        for x in fails:
            print('i18n_overlay: FAIL %s' % x)
        sys.exit('i18n_overlay: %d FAIL — fix the fragment builder, never the locked set.'
                 % len(fails))
    print('i18n_overlay: %d page(s) wired (%s), %d translated pairs verified — locked set '
          'byte-identical, evidence tags translated as vocabulary, toggle key %s'
          % (wired, '+'.join(langs), paired, key))


main()
