#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relink_artifact.py — make.sh step 8. Only meaningful when host == artifact-sandbox.

ORDER FAILURE 2 (see make.sh): relink was once run BEFORE docs/ existed. It
rewrote hrefs to files that were not there yet, so the website edition shipped
with dead relative links while the sandbox copy looked fine. Hence two rules,
both enforced here rather than remembered:

  * this step reads docs/ — it never writes a page docs/ does not already have
  * every internal href must resolve to a file that exists in docs/ AFTER the
    rewrite. A dead link is a hard fail, not a warning.

In the sandbox every page is served flat from one bag, so an href with any
directory part ("./agenda.html", "pages/agenda.html") is normalised to its bare
filename. Everything else is left alone: make.sh runs bin/encode_regions.py
immediately after this step and that is where the ASCII pass belongs.

Any other host exits 0 with one line. A no-op that says so is not a skipped
step; a silent one would be.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import re
import sys

DOCS = os.path.join(ROOT, 'docs')
BUILD = os.path.join(ROOT, 'build')
STATE_P = os.path.join(ROOT, 'STATE.json')

HREF = re.compile(r'(href\s*=\s*")([^"]*)(")')
EXT = re.compile(r'<(script|link|img|iframe)\b[^>]*\b(src|href)\s*=\s*"https?://', re.I)


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def main():
    state = load(STATE_P) or {}
    host = (state.get('campaign') or {}).get('host') or ''
    if host != 'artifact-sandbox':
        print('relink_artifact: skip — host=%s, not artifact-sandbox. docs/ links are already '
              'relative and stay as they are.' % (host or 'UNSET'))
        raise SystemExit(0)

    if not os.path.isdir(DOCS):
        sys.exit('relink_artifact: FAIL docs/ does not exist. Step 7 writes docs/ BEFORE relink '
                 'touches it (ORDER FAILURE 2).')
    files = sorted(f for f in os.listdir(DOCS) if f.endswith('.html'))
    if not files:
        sys.exit('relink_artifact: FAIL docs/ has no pages to relink')

    fails, rewrites, mapping = [], 0, {}
    for f in files:
        path = os.path.join(DOCS, f)
        doc = io.open(path, encoding='utf-8').read()
        if EXT.search(doc):
            fails.append('%s loads an external resource; the sandbox blocks it (A3)' % f)
        out, n = [], 0
        pos = 0
        for m in HREF.finditer(doc):
            href = m.group(2).strip()
            new = href
            if not href.startswith(('http://', 'https://', 'mailto:', '#')) and href:
                new = os.path.basename(href.split('#')[0].split('?')[0])
                frag = href[len(href.split('#')[0]):]
                new = new + frag
                if new != href:
                    n += 1
                target = new.split('#')[0]
                if target and target not in files:
                    fails.append('%s links to "%s" which is not in docs/ — a dead link in the '
                                 'sandbox edition' % (f, href))
            out.append(doc[pos:m.start()] + m.group(1) + new + m.group(3))
            pos = m.end()
        out.append(doc[pos:])
        doc = ''.join(out)
        if n:
            io.open(path, 'w', encoding='utf-8').write(doc)
            rewrites += n
        mapping[f] = n

    if fails:
        for x in fails:
            print('relink_artifact: FAIL %s' % x)
        sys.exit('relink_artifact: %d FAIL' % len(fails))
    if not os.path.isdir(BUILD):
        os.makedirs(BUILD)
    io.open(os.path.join(BUILD, 'relink.json'), 'w', encoding='utf-8').write(
        json.dumps({'host': host, 'files': mapping}, ensure_ascii=False, indent=2) + '\n')
    print('relink_artifact: %d pages flattened for artifact-sandbox, %d hrefs rewritten, '
          'every internal link resolves' % (len(files), rewrites))


main()
