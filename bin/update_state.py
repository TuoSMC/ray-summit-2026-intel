#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update_state.py — make.sh step 10. STATE.pages[], factbase.asOf, STATE.cost[].

The last thing a build does is tell STATE what it built:

  pages[]        one entry per role: {file, role, title, lang}. check_form.py
                 fails any docs/*.html STATE does not claim, and any role
                 claimed twice — so this list is rewritten from the manifest,
                 never appended to.
  factbase.asOf  COMPUTED from the catalogs' own asOf fields, not from today's
                 date. The factbase is as fresh as the last scrape, and a build
                 that "refreshes" a date it did not re-scrape is how a stale
                 pack starts looking current. staleAfter moves with it, keeping
                 the cadence gap the freshness owner set.
  accounts       fullWritten / fullReused recomputed from cards.json — §14.1: a
                 FULL earned on an earlier lap is reused and does not consume a
                 slot again, so only ledger_status == "new" counts.
  cost[]         append one row for this build. make.sh appends its own row for
                 the whole phase right after; both are wall time, no estimates.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import datetime
import io
import json
import os
import sys

DATA = os.path.join(ROOT, 'data')
DOCS = os.path.join(ROOT, 'docs')
BUILD = os.path.join(ROOT, 'build')
ACCOUNTS = os.path.join(ROOT, 'deliverables', 'accounts')
MANIFEST_P = os.path.join(BUILD, 'manifest.json')
STATE_P = os.path.join(ROOT, 'STATE.json')


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def as_list(blob):
    if isinstance(blob, dict):
        inner = blob.get('items') or blob.get('records') or blob.get('cards') or blob.get('orgs')
        if isinstance(inner, list):
            return inner
        return [v for v in blob.values() if isinstance(v, dict)]
    return [r for r in (blob or []) if isinstance(r, dict)]


def main():
    state = load(STATE_P)
    if state is None:
        sys.exit('update_state: FAIL STATE.json is unreadable')
    manifest = load(MANIFEST_P)
    if not manifest:
        sys.exit('update_state: FAIL %s missing — this build did not run steps 3-7' % MANIFEST_P)
    langs = [str(x) for x in ((state.get('campaign') or {}).get('langs') or ['h'])]

    # ------------------------------------------------------------ pages ----
    pages, missing = [], []
    for p in manifest['pages']:
        if not os.path.exists(os.path.join(DOCS, p['file'])):
            missing.append(p['file'])
            continue
        pages.append({'file': 'docs/%s' % p['file'], 'role': p['role'],
                      'title': p.get('title') or p['role'], 'lang': langs[0]})
    if missing:
        sys.exit('update_state: FAIL these roles never reached docs/: %s. Do not register a page '
                 'that does not exist.' % ', '.join(missing))
    seen = {}
    for p in pages:
        if p['role'] in seen:
            sys.exit('update_state: FAIL role "%s" is claimed by %s and %s — one writer per role'
                     % (p['role'], seen[p['role']], p['file']))
        seen[p['role']] = p['file']
    state['pages'] = pages

    # ------------------------------------------- factbase.asOf (computed) ---
    factbase = state.setdefault('factbase', {})
    old_asof, old_stale = factbase.get('asOf'), factbase.get('staleAfter')
    seen_asof = set()
    for name in ('sessions', 'speakers', 'sponsors', 'orgs', 'exhibitors'):
        for r in as_list(load(os.path.join(DATA, '%s.json' % name), [])):
            if r.get('asOf'):
                seen_asof.add(str(r['asOf']))
    new_asof = max(seen_asof) if seen_asof else old_asof
    if new_asof and new_asof != old_asof:
        factbase['asOf'] = new_asof
        if old_asof and old_stale:
            try:
                gap = (datetime.date.fromisoformat(old_stale)
                       - datetime.date.fromisoformat(old_asof)).days
                factbase['staleAfter'] = (datetime.date.fromisoformat(new_asof)
                                          + datetime.timedelta(days=gap)).isoformat()
            except ValueError:
                pass
    asof_note = ('asOf %s -> %s' % (old_asof, factbase.get('asOf'))) if new_asof != old_asof \
        else ('asOf %s (catalogs unchanged)' % factbase.get('asOf'))

    # ------------------------------------------------ accounts (§14.1) ------
    cards = as_list(load(os.path.join(ACCOUNTS, 'cards.json'), []))
    acct = state.setdefault('accounts', {})
    acct['fullWritten'] = len([c for c in cards if c.get('full') is True
                               and c.get('ledger_status') == 'new'])
    acct['fullReused'] = len([c for c in cards if c.get('full') is True
                              and c.get('ledger_status') in ('reused', 'stale')])

    # ------------------------------------------------------------ cost -----
    try:
        wall = int(datetime.datetime.now().timestamp() - os.path.getmtime(MANIFEST_P))
    except OSError:
        wall = 0
    state.setdefault('cost', []).append({
        'phase': 'P3-pages',
        'agents': 0,
        'outputTokens': 0,
        'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'wallSeconds': max(0, wall),
        'note': '%d pages built from %s' % (len(pages), ', '.join(sorted(seen)))})

    io.open(STATE_P, 'w', encoding='utf-8').write(
        json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    print('update_state: pages=%d (%s) · %s · fullWritten=%d fullReused=%d · cost[] += P3-pages'
          % (len(pages), ' '.join(sorted(seen)), asof_note,
             acct['fullWritten'], acct['fullReused']))


main()
