#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""write_docs.py — make.sh step 7. The built pages land in docs/, with relative links.

docs/ is the shipped edition. Nothing is generated here: this step copies what
steps 3-6 built, after asserting that each page is actually shippable —

  * <meta charset="utf-8"> inside the first 512 bytes (qa-gate A1')
  * a nav, and a filled freshness stamp — an unfilled slot means step 6 was
    skipped and the page would ship undated (B8)
  * every internal href relative and bare (ORDER FAILURE 2: relink runs AFTER
    docs/ lands, never before, so the links written here must already be right)
  * at most ONE inline <script> and never a <script src=>, no innerHTML, no
    external resource (A2/A3). The one script a page may carry is the language
    runtime injected at step 5; a page that ships the EN/ZH controls without it
    would ship a dead toggle, so that combination fails here.

It also REGISTERS the pages in STATE.pages[] (file + role). That registration
has to happen before the step-9 gates, because check_form.py fails any
docs/*.html that STATE does not claim — on lap 1 STATE.pages[] is empty and the
gate would reject the whole edition. Step 10 (update_state.py) rewrites the
same list from the same manifest, so the two agree by construction; this is one
truth written twice in the same lap, not two truths.

Language variants (index.s.html) go to docs/<lang>/ so that one role still owns
exactly one file in docs/ (check_form FM2), and their in-directory links stay
bare and correct.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import datetime
import io
import json
import os
import re
import sys

BUILD = os.path.join(ROOT, 'build')
PAGES = os.path.join(BUILD, 'pages')
DOCS = os.path.join(ROOT, 'docs')
MANIFEST_P = os.path.join(BUILD, 'manifest.json')
STATE_P = os.path.join(ROOT, 'STATE.json')

CHARSET = re.compile(r'<meta[^>]+charset\s*=\s*["\']?\s*utf-?8', re.I)
EXT = re.compile(r'<(script|link|img|iframe)\b[^>]*\b(src|href)\s*=\s*"https?://', re.I)
EGRESS = re.compile(r'\b(fetch\s*\(|XMLHttpRequest|navigator\.sendBeacon|new\s+WebSocket)', re.I)
EMPTY_STAMP = re.compile(r'<p class="stamp"[^>]*>\s*</p>')
HREF = re.compile(r'href\s*=\s*"([^"]*)"')


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def check(name, doc):
    errs = []
    if not CHARSET.search(doc[:512]):
        errs.append('no <meta charset="utf-8"> in the first 512 bytes')
    if '<nav class="nav"' not in doc:
        errs.append('no nav — step 6 (structure_pass.py) did not run')
    if EMPTY_STAMP.search(doc):
        errs.append('an unfilled freshness stamp slot — step 6 did not run (B8)')
    if '狀態截至' not in doc:
        errs.append('no freshness stamp (B8)')
    scripts = re.findall(r'<script\b[^>]*>', doc, re.I)
    if len(scripts) > 1:
        errs.append('carries %d <script> blocks; the skeleton owns exactly one' % len(scripts))
    if any(re.search(r'\bsrc\s*=', s, re.I) for s in scripts):
        errs.append('external <script src=> (A3)')
    if 'data-lang-btn' in doc and not scripts:
        errs.append('ships the EN/ZH controls with no runtime — a dead toggle. '
                    'Step 5 (i18n_overlay.py) did not run')
    if '<!--I18N-RUNTIME-->' in doc:
        errs.append('still carries the I18N-RUNTIME marker — step 5 did not run')
    if '.innerHTML' in doc:
        errs.append('innerHTML (A2)')
    if EXT.search(doc):
        errs.append('external resource load (A3)')
    if EGRESS.search(doc):
        errs.append('network egress call (A3)')
    for h in HREF.findall(doc):
        h = h.strip()
        if h.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        if h.startswith('/') or h.startswith('..') or ':' in h.split('/')[0]:
            errs.append('non-relative internal link "%s"' % h)
    return ['%s: %s' % (name, e) for e in errs]


def main():
    manifest = load(MANIFEST_P)
    if not manifest:
        sys.exit('write_docs: FAIL %s missing — steps 3-6 did not run' % MANIFEST_P)
    state = load(STATE_P)
    if state is None:
        sys.exit('write_docs: FAIL STATE.json is unreadable')
    langs = [str(x) for x in ((state.get('campaign') or {}).get('langs') or ['h'])]
    if not os.path.isdir(DOCS):
        os.makedirs(DOCS)

    fails, shipped, variants = [], [], 0
    for page in manifest['pages']:
        src = os.path.join(PAGES, page['file'])
        if not os.path.exists(src):
            fails.append('%s: not built (step 4/6 missing)' % page['file'])
            continue
        doc = io.open(src, encoding='utf-8').read()
        errs = check(page['file'], doc)
        if errs:
            fails.extend(errs)
            continue
        io.open(os.path.join(DOCS, page['file']), 'w', encoding='utf-8').write(doc)
        shipped.append(page)

        stem = page['file'][:-5]
        for lang in langs[1:]:
            vsrc = os.path.join(PAGES, '%s.%s.html' % (stem, lang))
            if not os.path.exists(vsrc):
                continue
            vdoc = io.open(vsrc, encoding='utf-8').read()
            verrs = check('%s.%s.html' % (stem, lang), vdoc)
            if verrs:
                fails.extend(verrs)
                continue
            vdir = os.path.join(DOCS, lang)
            if not os.path.isdir(vdir):
                os.makedirs(vdir)
            io.open(os.path.join(vdir, page['file']), 'w', encoding='utf-8').write(vdoc)
            variants += 1

    if fails:
        for x in fails:
            print('write_docs: FAIL %s' % x)
        sys.exit('write_docs: %d FAIL — nothing half-shipped.' % len(fails))

    # ------------------------------------------------ register STATE.pages ---
    now = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    state['pages'] = [{'file': 'docs/%s' % p['file'], 'role': p['role'],
                       'title': p.get('title') or p['role'], 'lang': langs[0], 'builtAt': now}
                      for p in shipped]
    io.open(STATE_P, 'w', encoding='utf-8').write(
        json.dumps(state, ensure_ascii=False, indent=2) + '\n')

    known = {p['file'] for p in shipped}
    stale = [f for f in sorted(os.listdir(DOCS)) if f.endswith('.html') and f not in known]
    for f in stale:
        print('write_docs: WARN docs/%s is not built by any role this lap. A5: a filename is a '
              'URL forever — retire it deliberately, do not let a build delete it.' % f)
    print('write_docs: %d pages -> docs/ (%s)%s; STATE.pages[] registered'
          % (len(shipped), ' '.join(p['file'] for p in shipped),
             '; %d language variants -> docs/<lang>/' % variants if variants else ''))


main()
