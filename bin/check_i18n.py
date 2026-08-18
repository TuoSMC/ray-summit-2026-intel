#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_i18n.py — the i18n gate. Runs at EVERY translation (§2 P4).

Blocks: residue, locked terms, tag-stream drift, non-verbatim numbers.

B7 — i18n is VOCABULARY, not transcoding. A character-conversion tool's output
is an error, not a draft.
B6 — numbers, dates, rooms, people and URLs are byte-identical across languages.
A translated figure is a new claim with no source.

File convention (set by the factory, read by make.sh step 5):
    page.html      source language  (STATE.campaign.langs[0])
    page.s.html    zh-Hans overlay
    page.e.html    English overlay

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import re
import sys
from collections import Counter

STATE_P = os.path.join(ROOT, 'STATE.json')
TERMBASE_P = os.path.join(ROOT, 'data', 'termbase.json')
DOCS = os.path.join(ROOT, 'docs')

FAILS = []
NOTES = []


def fail(code, msg, fix=''):
    FAILS.append('FAIL %-22s %s%s' % (code, msg, ('\n     fix: ' + fix) if fix else ''))


def load(p, default=None):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except FileNotFoundError:
        return default


state = load(STATE_P) or {}
termbase = load(TERMBASE_P) or {}
langs = ((state.get('campaign') or {}).get('langs')) or ['h']
SRC = langs[0]
terms = termbase.get('terms') or []
locked = ((termbase.get('locked') or {}).get('patterns')) or []

if len(langs) < 2:
    print('check_i18n: SKIP  single language (%s)' % SRC)
    sys.exit(0)
if not os.path.isdir(DOCS):
    print('check_i18n: SKIP  no docs/ yet')
    sys.exit(0)

TAG = re.compile(r'<\s*(/?)([a-zA-Z][a-zA-Z0-9-]*)')
SCRIPT_STYLE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.S | re.I)
NUM = re.compile(r'(?<![\w-])\d[\d,.:]*\d|(?<![\w-])\d(?![\w])')
URL = re.compile(r'https?://[^\s"\'<>)]+')
DATE = re.compile(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}')
LOCKED = [re.compile(p) for p in locked]

VARIANT = re.compile(r'^(?P<stem>.+?)[.-](?P<lang>[se])\.html$')

pairs = []
for f in sorted(os.listdir(DOCS)):
    m = VARIANT.match(f)
    if not m:
        continue
    for sep in ('.', '-'):
        cand = m.group('stem') + '.html'
        if os.path.exists(os.path.join(DOCS, cand)):
            pairs.append((cand, f, m.group('lang')))
            break
    else:
        fail('I0 orphan-variant', '%s has no source page' % f,
             'the overlay is applied to a frozen source; there is no free-standing translation')

if not pairs:
    print('check_i18n: SKIP  no <page>.<lang>.html overlays found (langs=%s)' % ','.join(langs))
    sys.exit(0)


def read(f):
    return io.open(os.path.join(DOCS, f), encoding='utf-8', errors='replace').read()


def visible(s):
    s = SCRIPT_STYLE.sub(' ', s)
    return re.sub(r'<[^>]+>', ' ', s)


for src_f, var_f, lang in pairs:
    a, b = read(src_f), read(var_f)
    va, vb = visible(a), visible(b)

    # ------------------------------------------------------- I1 residue ----
    # A term left in the source language inside the overlay. The h/s/e columns
    # of the termbase are exactly the vocabulary the overlay is supposed to swap.
    residue = []
    for t in terms:
        src_term, tgt_term = t.get(SRC), t.get(lang)
        if not src_term or not tgt_term or src_term == tgt_term:
            continue
        if src_term in vb:
            residue.append('%s (should be %s)' % (src_term, tgt_term))
    if residue:
        fail('I1 residue', '%s still carries %d source terms: %s'
             % (var_f, len(residue), '; '.join(residue[:8])),
             'B7: finish the vocabulary pass. Half a translation is worse than none')

    # -------------------------------------------------- I2 locked terms ----
    for pat in LOCKED:
        ca, cb = Counter(pat.findall(va)), Counter(pat.findall(vb))
        if ca != cb:
            missing = sorted((ca - cb).elements())
            added = sorted((cb - ca).elements())
            fail('I2 locked-term', '%s locked pattern /%s/ drifted  missing=%s added=%s'
                 % (var_f, pat.pattern, missing[:6], added[:6]),
                 'product names, room numbers, person names and times are NOT translated (B6)')

    # --------------------------------------------------- I3 tag stream -----
    ta = [m.group(1) + m.group(2).lower() for m in TAG.finditer(a)]
    tb = [m.group(1) + m.group(2).lower() for m in TAG.finditer(b)]
    if ta != tb:
        i = next((k for k in range(min(len(ta), len(tb))) if ta[k] != tb[k]), min(len(ta), len(tb)))
        fail('I3 tag-stream', '%s structure diverges from %s at tag #%d (src=%s var=%s, %d vs %d tags)'
             % (var_f, src_f, i, ta[i] if i < len(ta) else '-', tb[i] if i < len(tb) else '-',
                len(ta), len(tb)),
             'the overlay replaces text nodes only. If the structure had to change, the source '
             'was not frozen — go back to step 3')

    # ---------------------------------------------- I4 verbatim numbers ----
    for name, rx in (('number', NUM), ('date', DATE), ('url', URL)):
        ca, cb = Counter(rx.findall(va)), Counter(rx.findall(vb))
        if ca != cb:
            missing = sorted((ca - cb).elements())
            added = sorted((cb - ca).elements())
            fail('I4 verbatim-%s' % name, '%s %s drift  missing=%s added=%s'
                 % (var_f, name, missing[:8], added[:8]),
                 'B6: numbers, dates, rooms, people and URLs are byte-identical across languages. '
                 'A translated figure is a new claim with no source')

for n in NOTES:
    print(n)
if FAILS:
    print('\n'.join(FAILS))
    print('check_i18n: %d FAIL — HARD STOP 4.' % len(FAILS))
    sys.exit(1)
print('check_i18n: PASS  src=%s pairs=%d terms=%d locked=%d'
      % (SRC, len(pairs), len(terms), len(locked)))
