#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_layout.py — the pixels pre-screen. Runs after any layout change (§2 P4).

375 is the width the gate is named after: iPhone SE / mini, the narrowest phone
anyone actually reads a war-room page on. Content box = 375 - 2x16 padding = 343.

This is a STATIC estimator, not a browser. It catches the cheap, common
overflows — a nowrap cell, a fixed px width, an unbreakable token, a table with
too many columns — before anyone spends a matrix run on them. The authoritative
check is still the matrix gate (5 widths x theme x lang); this one exists so the
matrix gate is not where you discover a 480px table.

usage: measure_layout.py [file.html ...]      (default: every docs/*.html)
exit 1 when any run is predicted to overflow.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import os
import re
import sys

VIEWPORT = 375
PADDING = 16
CONTENT = VIEWPORT - 2 * PADDING          # 343
DEFAULT_FONT = 16.0

DOCS = os.path.join(ROOT, 'docs')

CJK = re.compile(r'[⺀-〿㐀-䶿一-鿿豈-﫿＀-￯]')
STYLE_BLK = re.compile(r'<style\b[^>]*>(.*?)</style>', re.S | re.I)
SCRIPT_BLK = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)
RULE = re.compile(r'([^{}]+)\{([^{}]*)\}', re.S)
FONT_PX = re.compile(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', re.I)
FONT_REM = re.compile(r'font-size\s*:\s*(\d+(?:\.\d+)?)rem', re.I)
NOWRAP = re.compile(r'white-space\s*:\s*nowrap', re.I)
WIDTH_PX = re.compile(r'\b(?:min-)?width\s*:\s*(\d+(?:\.\d+)?)px', re.I)
CELL = re.compile(r'<(t[dh]|pre|code|h1|h2|h3|span|div|li|a)\b([^>]*)>(.*?)</\1>', re.S | re.I)
CLASSES = re.compile(r'class\s*=\s*["\']([^"\']*)["\']', re.I)
INLINE = re.compile(r'style\s*=\s*["\']([^"\']*)["\']', re.I)
LONGTOK = re.compile(r'\S{24,}')


def text_width(s, font_px):
    """em-width model: CJK is full-width, capitals and digits are wide-ish,
    everything else is narrow. Good to roughly +/-8% for the shapes that matter."""
    em = 0.0
    for ch in s:
        if CJK.match(ch):
            em += 1.0
        elif ch in ' \t':
            em += 0.28
        elif ch.isupper() or ch.isdigit():
            em += 0.62
        elif ch in 'ilj.,;:\'"|!':
            em += 0.30
        else:
            em += 0.52
    return em * font_px


def sheet_fonts(src):
    """Very small selector model: tag / .class / #id -> font-size px."""
    out = {}
    for css in STYLE_BLK.findall(src):
        for sel, body in RULE.findall(css):
            px = None
            m = FONT_PX.search(body)
            if m:
                px = float(m.group(1))
            else:
                m = FONT_REM.search(body)
                if m:
                    px = float(m.group(1)) * DEFAULT_FONT
            if px is None:
                continue
            for one in sel.split(','):
                one = one.strip().split()[-1] if one.strip() else ''
                if re.match(r'^[.#]?[\w-]+$', one):
                    out[one.lower()] = px
    return out


def font_for(tag, attrs, fonts):
    m = INLINE.search(attrs)
    if m:
        f = FONT_PX.search(m.group(1))
        if f:
            return float(f.group(1))
        f = FONT_REM.search(m.group(1))
        if f:
            return float(f.group(1)) * DEFAULT_FONT
    for c in (CLASSES.search(attrs).group(1).split() if CLASSES.search(attrs) else []):
        if '.' + c.lower() in fonts:
            return fonts['.' + c.lower()]
    return fonts.get(tag.lower(), DEFAULT_FONT)


def measure(path):
    src = io.open(path, encoding='utf-8', errors='replace').read()
    body = SCRIPT_BLK.sub(' ', src)
    fonts = sheet_fonts(src)
    hits = []

    for css in STYLE_BLK.findall(src):
        for sel, rule in RULE.findall(css):
            for w in WIDTH_PX.findall(rule):
                if float(w) > CONTENT:
                    hits.append((float(w), 'css %s' % sel.strip()[:44], 'fixed width %spx' % w))

    for m in CELL.finditer(body):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', inner)).strip()
        if not txt:
            continue
        fp = font_for(tag, attrs, fonts)
        nowrap = bool(NOWRAP.search(attrs)) or tag.lower() in ('pre', 'code')
        wpx = WIDTH_PX.search(attrs)
        if wpx and float(wpx.group(1)) > CONTENT:
            hits.append((float(wpx.group(1)), '<%s>' % tag, 'fixed width %spx: %s' % (wpx.group(1), txt[:40])))
        if nowrap:
            w = text_width(txt, fp)
            if w > CONTENT:
                hits.append((w, '<%s nowrap>' % tag, '%s' % txt[:56]))
        for tok in LONGTOK.findall(txt):
            w = text_width(tok, fp)
            if w > CONTENT:
                hits.append((w, '<%s> unbreakable' % tag, tok[:56]))

    # a table's minimum width is the sum of its widest cells; 4+ dense columns
    # is the classic 375 failure
    for tm in re.finditer(r'<table\b.*?</table>', body, re.S | re.I):
        t = tm.group(0)
        rows = re.findall(r'<tr\b.*?</tr>', t, re.S | re.I)
        if not rows:
            continue
        widths = []
        for r in rows:
            cells = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip()
                     for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', r, re.S | re.I)]
            for i, c in enumerate(cells):
                w = text_width(max(c.split(' '), key=len, default=''), fonts.get('td', DEFAULT_FONT)) + 16
                while len(widths) <= i:
                    widths.append(0.0)
                widths[i] = max(widths[i], w)
        total = sum(widths)
        if total > CONTENT:
            hits.append((total, '<table> %d cols' % len(widths),
                         'min width ~%dpx (cols: %s)' % (total, ' '.join('%d' % w for w in widths))))
    return hits


def main(argv):
    files = argv or (sorted(os.path.join(DOCS, f) for f in os.listdir(DOCS) if f.endswith('.html'))
                     if os.path.isdir(DOCS) else [])
    if not files:
        print('measure_layout: no html to measure (%s)' % DOCS)
        return 0
    bad = 0
    for p in files:
        hits = measure(p)
        name = os.path.basename(p)
        if not hits:
            print('PASS %-28s <= %dpx' % (name, CONTENT))
            continue
        bad += 1
        print('FAIL %-28s %d predicted overflow(s) at %dpx viewport' % (name, len(hits), VIEWPORT))
        for w, what, detail in sorted(hits, reverse=True)[:10]:
            print('  ~%4dpx  %-22s %s' % (int(w), what, detail))
    print('measure_layout: %d/%d files clean at %dpx content box'
          % (len(files) - bad, len(files), CONTENT))
    if bad:
        print('  fix: wrap it, shorten it, or reflow the table. Do NOT reach for transform:scale() '
              '— check_form.py fails that (FM4).')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
