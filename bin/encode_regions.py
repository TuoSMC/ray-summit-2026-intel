#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""encode_regions.py — region-aware pure-ASCII codec. Ported from event-warroom.

Why: the artifact wrapper's <meta charset> sits beyond the browser's 1024-byte
prescan window, so raw UTF-8 ships as mojibake. In an artifact-sandbox build
every HTML file must contain zero bytes >127. HTML entities are NOT decoded
inside <script>, so the two regions need different escapes (RULES A1):

    HTML region   : U+8868  ->  &#x8868;
    <script> body : U+8868  ->  \\u8868   (surrogate pairs above U+FFFF)
    <style> body  : keep ASCII-only; do not put CJK in CSS content

RULES D1 / A1' — this transform belongs to ONE host. Running it on a docs-local
or private-acl build is the defect, not the fix: those hosts ship real UTF-8 and
qa-gate.sh fails an entity-encoded file. This script therefore reads
STATE.campaign.host and refuses unless host == artifact-sandbox (--force
overrides, for the one case where you are hand-preparing a sandbox copy).

Usage:
    encode_regions.py                       # encode every docs/*.html in place
    encode_regions.py file.html [...]       # encode those files in place
    encode_regions.py --check file.html     # exit 1 if any byte >127
As a library: encode(text) -> ascii str;  decode(text) -> unicode str.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import re
import sys

DOCS = os.path.join(ROOT, 'docs')
STATE_P = os.path.join(ROOT, 'STATE.json')

PART = re.compile(r'(<script\b[^>]*>)(.*?)(</script>)', re.S | re.I)


def enc_html(s):
    return ''.join(c if ord(c) < 128 else '&#x%X;' % ord(c) for c in s)


def enc_js(s):
    out = []
    for c in s:
        v = ord(c)
        if v < 128:
            out.append(c)
        elif v > 0xFFFF:
            u = v - 0x10000
            out.append('\\u%04X\\u%04X' % (0xD800 + (u >> 10), 0xDC00 + (u & 0x3FF)))
        else:
            out.append('\\u%04X' % v)
    return ''.join(out)


def encode(d):
    """Unicode HTML text -> pure-ASCII, region-aware."""
    out, pos = [], 0
    for m in PART.finditer(d):
        out.append(enc_html(d[pos:m.start()]))
        out.append(m.group(1) + enc_js(m.group(2)) + m.group(3))
        pos = m.end()
    out.append(enc_html(d[pos:]))
    r = ''.join(out)
    assert all(ord(c) < 128 for c in r), 'encode failed to reach pure ASCII'
    return r


def decode(s):
    """Escaped source -> unicode (for grep/analysis). Only decodes non-ASCII
    codepoints, so markup entities like &amp; &lt; survive untouched."""
    s = re.sub(r'&#x([0-9A-Fa-f]{2,6});',
               lambda m: chr(int(m.group(1), 16)) if int(m.group(1), 16) > 127 else m.group(0), s)
    return re.sub(r'\\u([0-9A-Fa-f]{4})',
                  lambda m: chr(int(m.group(1), 16)) if int(m.group(1), 16) > 127 else m.group(0), s)


def host():
    try:
        return (json.load(io.open(STATE_P, encoding='utf-8')).get('campaign') or {}).get('host') or ''
    except Exception:
        return ''


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv[1:]

    if args and args[0] == '--check':
        bad = 0
        for f in args[1:]:
            raw = open(f, 'rb').read()
            i = next((i for i, c in enumerate(raw) if c > 127), -1)
            if i >= 0:
                print('FAIL %s byte>127 at offset %d' % (f, i)); bad = 1
            else:
                print('PASS %s' % f)
        sys.exit(bad)

    h = host()
    if h != 'artifact-sandbox' and not force:
        sys.exit('encode_regions: REFUSED host=%s. Entity encoding is an artifact-sandbox transform '
                 'only (RULES D1); on %s it is the defect qa-gate.sh fails. Use --force only when '
                 'hand-preparing a sandbox copy.' % (h or 'UNSET', h or 'this host'))

    files = args or (sorted(os.path.join(DOCS, f) for f in os.listdir(DOCS) if f.endswith('.html'))
                     if os.path.isdir(DOCS) else [])
    if not files:
        sys.exit('encode_regions: nothing to encode in %s' % DOCS)
    for f in files:
        d = io.open(f, encoding='utf-8').read()
        io.open(f, 'w', encoding='utf-8').write(encode(d))
        print('encoded %s' % os.path.basename(f))
