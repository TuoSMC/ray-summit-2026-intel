#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""structure_pass.py — make.sh step 6. Nav, cross-links, and the freshness stamp.

Three jobs, all of them structural, none of them prose:

  1. NAV — the same six-item nav on every page, built from build/manifest.json,
     with the current page marked. One nav, one order, one place to change it.
  2. CROSS-LINKS — every internal href is RELATIVE and bare (agenda.html, not
     /docs/agenda.html and not an absolute URL). A pack gets copied into a
     sandbox, a share drive and someone's laptop; an absolute link survives
     exactly one of those. Anything absolute is a hard fail here.
  3. FRESHNESS (B8) — every time-sensitive block carries "狀態截至 YYYY-MM-DD".
     A block marked data-fresh="1" that has no stamp slot is a fail: an intel
     page without a date is a rumour, and the reader cannot tell which.
  4. DRAWERS — every <details> opens with a <summary>, and every <summary>
     carries a scent line. A drawer whose handle says only "Accounts" forces
     the reader to open all of them to find anything, which is worse than no
     drawer at all; the contract is title PLUS a count or a verdict. A
     <details> with no <summary> is worse still — the browser invents the word
     "Details" and the section becomes invisible.

Idempotent: it consumes the <!--NAV--> marker, and re-running replaces the nav
it already wrote and leaves filled stamps alone.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import html
import io
import json
import os
import re
import sys

BUILD = os.path.join(ROOT, 'build')
PAGES = os.path.join(BUILD, 'pages')
MANIFEST_P = os.path.join(BUILD, 'manifest.json')
STATE_P = os.path.join(ROOT, 'STATE.json')

STAMP_SLOT = re.compile(r'(<p class="stamp"[^>]*data-fresh="1"[^>]*>)\s*(</p>)')
FRESH_TAG = re.compile(r'<(\w+)\b[^>]*\bdata-fresh="1"[^>]*>')
NAV_BLOCK = re.compile(r'<nav class="nav".*?</nav>', re.S)
DETAILS_OPEN = re.compile(r'<details\b[^>]*>')
SUMMARY = re.compile(r'<summary\b[^>]*>(.*?)</summary>', re.S)
TAGS_RE = re.compile(r'<[^>]+>')
INERT = re.compile(r'<(style|script)\b[^>]*>.*?</\1>', re.S | re.I)
XLINK_BLOCK = re.compile(r'<nav class="xlink".*?</nav>', re.S)
HREF = re.compile(r'href\s*=\s*"([^"]*)"')


def esc(v):
    return html.escape('' if v is None else str(v), quote=True)


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def base_stem(fname):
    """index.s.html -> index.html. A language variant links to its own edition."""
    parts = fname.split('.')
    return '%s.html' % parts[0] if len(parts) > 2 else fname


def matching_close(doc, open_start, tag):
    """End offset of the element that opens at open_start, counting nesting."""
    depth = 0
    pat = re.compile(r'<(/?)%s\b' % re.escape(tag), re.I)
    for m in pat.finditer(doc, open_start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.end()
    return len(doc)


def label(p):
    """Nav chrome is bilingual too. build_fragments.py writes nav / nav_e into
    the manifest; when a campaign ships one language the pair collapses to the
    source arm and the markup is unchanged (DESIGN.md 7)."""
    h = p.get('nav') or p.get('title') or p['role']
    e = p.get('nav_e') or p.get('title_e')
    if not e:
        return esc(h)
    return '<span data-t="h">%s</span><span data-t="e">%s</span>' % (esc(h), esc(e))


def pair(h, e, bilingual):
    if not bilingual:
        return esc(h)
    return '<span data-t="h">%s</span><span data-t="e">%s</span>' % (esc(h), esc(e))


def build_nav(pages, current_file, bilingual):
    li = []
    for p in pages:
        cur = ' aria-current="page"' if p['file'] == current_file else ''
        li.append('    <li><a href="%s"%s>%s</a></li>'
                  % (esc(p['file']), cur, label(p) if bilingual else
                     esc(p.get('nav') or p.get('title') or p['role'])))
    return ('<nav class="nav" data-block="nav" aria-label="Pages / 頁面">\n'
            '  <ul>\n%s\n  </ul>\n</nav>' % '\n'.join(li))


def build_xlink(pages, idx, bilingual):
    prev_p = pages[idx - 1] if idx > 0 else None
    next_p = pages[idx + 1] if idx + 1 < len(pages) else None
    bits = []
    if prev_p:
        bits.append('  <a class="prev" href="%s">%s %s</a>'
                    % (esc(prev_p['file']), pair('上一頁', 'Previous', bilingual),
                       label(prev_p) if bilingual else esc(prev_p.get('nav') or prev_p['role'])))
    if next_p:
        bits.append('  <a class="next" href="%s">%s %s</a>'
                    % (esc(next_p['file']), pair('下一頁', 'Next', bilingual),
                       label(next_p) if bilingual else esc(next_p.get('nav') or next_p['role'])))
    if not bits:
        return ''
    return ('<nav class="xlink" aria-label="Previous and next / 前後頁">\n%s\n</nav>'
            % '\n'.join(bits))


def main():
    manifest = load(MANIFEST_P)
    if not manifest:
        sys.exit('structure_pass: FAIL %s missing — step 3 did not run' % MANIFEST_P)
    state = load(STATE_P) or {}
    asof = (state.get('factbase') or {}).get('asOf')
    if not asof:
        sys.exit('structure_pass: FAIL STATE.factbase.asOf is unset. B8: every time-sensitive '
                 'block carries a date, and there is no date to carry.')
    stamp_text = '狀態截至 %s' % asof
    pages = manifest['pages']
    langs = [str(x) for x in ((state.get('campaign') or {}).get('langs') or ['h'])]
    bilingual = len(langs) > 1
    by_base = {p['file']: i for i, p in enumerate(pages)}

    fails, touched, stamps, drawers = [], 0, 0, {}
    for f in sorted(os.listdir(PAGES)):
        if not f.endswith('.html'):
            continue
        base = base_stem(f)
        if base not in by_base:
            fails.append('%s is in build/pages but no manifest role owns it' % f)
            continue
        path = os.path.join(PAGES, f)
        doc = io.open(path, encoding='utf-8').read()

        # ---- 1. nav -------------------------------------------------------
        nav = build_nav(pages, base, bilingual)
        if '<!--NAV-->' in doc:
            doc = doc.replace('<!--NAV-->', nav, 1)
        elif NAV_BLOCK.search(doc):
            doc = NAV_BLOCK.sub(lambda m: nav, doc, count=1)
        else:
            fails.append('%s has no <!--NAV--> marker and no nav to replace' % f)
            continue

        # ---- 2. cross-links ----------------------------------------------
        xlink = build_xlink(pages, by_base[base], bilingual)
        if xlink:
            if XLINK_BLOCK.search(doc):
                doc = XLINK_BLOCK.sub(lambda m: xlink, doc, count=1)
            else:
                doc = doc.replace('</main>', '%s\n</main>' % xlink, 1)
        for href in HREF.findall(doc):
            h = href.strip()
            if h.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            if h.startswith('/') or h.startswith('..') or ':' in h.split('/')[0]:
                fails.append('%s links to "%s" — internal links are relative and bare' % (f, h))

        # ---- 3. freshness stamp (B8) -------------------------------------
        doc, n = STAMP_SLOT.subn(lambda m: m.group(1) + stamp_text + m.group(2), doc)
        stamps += n
        for m in FRESH_TAG.finditer(doc):
            tag, start = m.group(1), m.start()
            if tag.lower() == 'p' and 'class="stamp"' in m.group(0):
                continue
            end = matching_close(doc, start, tag)
            if stamp_text not in doc[start:end]:
                fails.append('%s has a data-fresh block <%s> with no "%s" stamp inside it (B8)'
                             % (f, tag, stamp_text))
        if stamp_text not in doc:
            fails.append('%s carries no freshness stamp at all (B8)' % f)

        # ---- 4. drawer integrity -----------------------------------------
        # <style> and <script> are inert here: the stylesheet legitimately
        # NAMES the element it styles, and a CSS comment is not a drawer.
        body_doc = INERT.sub(lambda m: ' ' * len(m.group(0)), doc)
        n_det = len(DETAILS_OPEN.findall(body_doc))
        n_sum = 0
        for m in DETAILS_OPEN.finditer(body_doc):
            rest = body_doc[m.end():]
            if not rest.lstrip().startswith('<summary'):
                fails.append('%s has a <details> that does not open with a <summary> — the browser '
                             'would invent the word "Details" and the section would go invisible'
                             % f)
                continue
            n_sum += 1
            s0 = m.end() + rest.index('<summary')
            s1 = body_doc.find('</summary>', s0)
            inner = body_doc[s0:s1] if s1 > 0 else ''
            if 'class="dr-s"' not in inner:
                fails.append('%s has a <summary> with no scent line: "%s". A closed drawer still '
                             'has to say what is inside and how much of it'
                             % (f, TAGS_RE.sub('', inner).strip()[:50]))
            elif len(TAGS_RE.sub(' ', inner).split()) < 2:
                fails.append('%s has an empty <summary>' % f)
        drawers[f] = (n_det, n_sum)

        io.open(path, 'w', encoding='utf-8').write(doc)
        touched += 1

    if fails:
        for x in fails:
            print('structure_pass: FAIL %s' % x)
        sys.exit('structure_pass: %d FAIL' % len(fails))
    print('structure_pass: %d pages — nav + cross-links + %d freshness stamps (%s) — '
          'drawers %d, every one with a summary and a scent line'
          % (touched, stamps, stamp_text, sum(d for d, _s in drawers.values())))


main()
