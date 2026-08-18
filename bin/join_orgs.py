#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1b — build data/orgs.json as a JOIN, then diff it against the account ledger.

This is the loop's spine. Every other saving in the family is downstream of one
question: have we filed this company before? Prose in a phase file cannot answer
it reproducibly, so it is answered here, mechanically, and check_facts.py
validates the answer afterwards.

  orgs.json = speaker employers  U  sponsors  U  explicit exhibitor captures
              (RULES B10 — a JOIN, never a fourth scrape)

  ledger_status per org (spine-plan-v2 s14.1):
    new     no ledger match          -> full P2a research
    reused  match, asOf still fresh  -> one seen_at append, ZERO research
    stale   match, asOf rotted       -> delta refresh of the rotting fields only

Freshness: 180 days, tightened to 90 when the ledger says buys_servers == YES.
Matching: legal_name + aka[] + ticker, case/punctuation folded. Ambiguity resolves
to `new` (RULES B25 — a duplicate card is recoverable, a wrong merge poisons two
accounts). Every ambiguous near-miss is reported so a human can merge on purpose.

ROOT is a literal written by scaffold.sh. RULES B9: never resolved from argv,
never from the working directory.

Usage: join_orgs.py [--write] [--asof YYYY-MM-DD]
       without --write it prints the plan and touches nothing.
"""

import io
import json
import os
import re
import sys
import datetime

ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'
DATA = os.path.join(ROOT, 'data')
STATE_P = os.path.join(ROOT, 'STATE.json')

FRESH_DAYS_DEFAULT = 180
FRESH_DAYS_BUYER = 90

problems = []
notes = []


def fail(code, what, fix):
    problems.append('  FAIL  [%s] %s\n        fix: %s' % (code, what, fix))


def note(msg):
    notes.append('  note  ' + msg)


def load(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except ValueError as exc:
        fail('J0 parse', '%s is not valid JSON (%s)' % (path, exc),
             'fix the file; a half-written catalog is a gap, not an empty event')
        return default


def records(blob):
    """Accept a list of dicts or a dict-of-dicts. Return [(id, dict)]."""
    if isinstance(blob, list):
        out = []
        for r in blob:
            if isinstance(r, dict):
                rid = r.get('id') or r.get('org_id') or r.get('ledger_id') or r.get('slug')
                out.append((rid, r))
        return out
    if isinstance(blob, dict):
        inner = blob.get('orgs') if isinstance(blob.get('orgs'), (list, dict)) else blob
        if isinstance(inner, list):
            return records(inner)
        return [(k, v) for k, v in inner.items() if isinstance(v, dict)]
    return []


def fold(name):
    """Fold a company name for matching. Keeps CJK, drops case/punctuation/suffixes."""
    if not name:
        return ''
    s = name.lower()
    s = re.sub(r'[\.,\'"()\[\]/\\&+-]', ' ', s)
    s = re.sub(r'\b(inc|corp|corporation|co|ltd|limited|llc|plc|gmbh|ag|sa|nv|bv|pte|pty|holdings|group|technologies|technology|systems|solutions|services)\b', ' ', s)
    s = re.sub(r'(股份有限公司|有限公司|公司|集團)', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def parse_date(v):
    if not v:
        return None
    try:
        return datetime.date(*[int(x) for x in str(v)[:10].split('-')])
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------- inputs --
asof = None
write = False
argv = sys.argv[1:]
for i, a in enumerate(argv):
    if a == '--write':
        write = True
    elif a == '--asof' and i + 1 < len(argv):
        asof = parse_date(argv[i + 1])
if asof is None:
    state_pre = load(STATE_P, {}) or {}
    asof = parse_date((state_pre.get('factbase') or {}).get('asOf'))
if asof is None:
    fail('J0 asof', 'no as-of date: STATE.factbase.asOf is unset and --asof was not given',
         'set STATE.factbase.asOf after the scrape, or pass --asof YYYY-MM-DD')
    asof = datetime.date(1970, 1, 1)

speakers = records(load(os.path.join(DATA, 'speakers.json'), []))
sponsors = records(load(os.path.join(DATA, 'sponsors.json'), []))
exhibitors = records(load(os.path.join(DATA, 'exhibitors.json'), []))

state = load(STATE_P, {}) or {}
this_event = (state.get('campaign') or {}).get('event')
acct = state.get('accounts') or {}
ledger_p = os.path.expanduser(acct.get('ledgerIndex')
                              or '~/.claude/skills/account-intel/ledger/index.json')
ledger = load(ledger_p)

# ------------------------------------------------------------------ join ---
# B10: three catalogs in, one derived file out. Nothing is scraped here.
joined = {}


def touch(oid, role, extra=None):
    if not oid:
        fail('J1 org-id', 'a catalog row names no org id (role %s)' % role,
             'give every speaker a company_id and every sponsor an org_id before the join')
        return
    rec = joined.setdefault(oid, {
        'id': oid, 'legal_name': None, 'aka': [], 'ticker': None,
        'roles_at_event': [], 'layer': None, 'buys_servers': 'GAP',
        'ledger_id': None, 'ledger_status': None,
    })
    if role not in rec['roles_at_event']:
        rec['roles_at_event'].append(role)
    for k, v in (extra or {}).items():
        if v and not rec.get(k):
            rec[k] = v


for _, s in speakers:
    touch(s.get('company_id') or s.get('org_id'), 'speaker-employer',
          {'legal_name': s.get('company') or s.get('company_name')})
for oid, s in sponsors:
    touch(oid, 'sponsor', {'legal_name': s.get('legal_name') or s.get('name')})
for oid, s in exhibitors:
    touch(oid, 'exhibitor', {'legal_name': s.get('legal_name') or s.get('name')})
    joined[oid]['exhibitor_capture'] = True

for oid, rec in joined.items():
    if not rec['legal_name']:
        rec['legal_name'] = oid
    rec['roles_at_event'].sort()

# --------------------------------------------------------- ledger diff -----
index = {}
if ledger is not None:
    for lid, r in records(ledger):
        if not lid:
            continue
        names = [r.get('legal_name')] + list(r.get('aka') or [])
        index[lid] = {
            'rec': r,
            'keys': set(f for f in (fold(n) for n in names if n) if f),
            'ticker': (r.get('ticker') or '').upper() or None,
            'last_asOf': parse_date(r.get('last_asOf')),
            'buys_servers': r.get('buys_servers'),
        }
else:
    note('no ledger index at %s — lap 1, every org is new' % ledger_p)

counts = {'new': 0, 'reused': 0, 'stale': 0}
ambiguous = []

for oid, rec in sorted(joined.items()):
    keys = set(f for f in [fold(rec['legal_name'])] + [fold(a) for a in rec['aka']] if f)
    tick = (rec.get('ticker') or '').upper() or None
    hits = [lid for lid, L in index.items()
            if (keys & L['keys']) or (tick and tick == L['ticker'])]

    if len(hits) > 1:
        # B25: never guess a merge.
        ambiguous.append((oid, hits))
        rec['ledger_status'] = 'new'
        rec['ledger_id'] = oid.lower().replace('org_', '').replace('_', '-')
        counts['new'] += 1
        continue

    if not hits:
        rec['ledger_status'] = 'new'
        rec['ledger_id'] = oid.lower().replace('org_', '').replace('_', '-')
        counts['new'] += 1
        continue

    lid = hits[0]
    L = index[lid]
    rec['ledger_id'] = lid
    # Same-lap guard: if the ledger master was first seen at THIS event, the org is
    # new this lap even though a mid-lap ledger write already registered it. Without
    # this, re-running the join inside one lap marks a lap's own new orgs "reused",
    # and T4 then counts zero FULLs written. 〔Ray-Summit-2026: 4 FULLs counted as 0〕
    _fs = (L['rec'].get('first_seen') or {}).get('event')
    if _fs and this_event and _fs == this_event:
        rec['ledger_status'] = 'new'
        counts['new'] += 1
        for k in ('layer', 'buys_servers'):
            if L['rec'].get(k):
                rec[k] = L['rec'][k]
        continue
    window = FRESH_DAYS_BUYER if L['buys_servers'] == 'YES' else FRESH_DAYS_DEFAULT
    last = L['last_asOf']
    if last is None:
        rec['ledger_status'] = 'stale'
    else:
        rec['ledger_status'] = 'reused' if (asof - last).days <= window else 'stale'
    counts[rec['ledger_status']] += 1
    for k in ('layer', 'buys_servers'):
        if L['rec'].get(k):
            rec[k] = L['rec'][k]

for oid, hits in ambiguous:
    fail('J2 ambiguous', 'org "%s" matches %d ledger entries: %s'
         % (oid, len(hits), ', '.join(hits)),
         'B25 — filed as NEW rather than guessing. Merge on purpose in the ledger, '
         'record it in STATE.corrections[], then re-run the join')

# ------------------------------------------------------------------ out ----
orgs = [joined[k] for k in sorted(joined)]
print('join_orgs — %s' % ROOT)
print('  catalogs: speakers %d, sponsors %d, exhibitors %d'
      % (len(speakers), len(sponsors), len(exhibitors)))
print('  orgs joined: %d   new %d / reused %d / stale %d'
      % (len(orgs), counts['new'], counts['reused'], counts['stale']))
if counts['reused']:
    print('  reused orgs cost a seen_at append and ZERO research this lap (s14.1)')
for n in notes:
    print(n)

if problems:
    print('\n'.join(problems))
    print('\njoin_orgs: RED — %d problem(s). orgs.json not written.' % len(problems))
    sys.exit(1)

if write:
    json.dump(orgs, io.open(os.path.join(DATA, 'orgs.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    state.setdefault('factbase', {})['orgCount'] = len(orgs)
    state.setdefault('lap', {})
    state['lap']['ledgerReused'] = counts['reused'] + counts['stale']
    state['lap']['ledgerNew'] = counts['new']
    json.dump(state, io.open(STATE_P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('  wrote data/orgs.json and STATE.lap')
else:
    print('  (dry run — pass --write to commit orgs.json and STATE.lap)')

sys.exit(0)
