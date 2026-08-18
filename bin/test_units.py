#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_units.py — make.sh step 1. The data contract, asserted BEFORE anything builds.

A build that renders a broken factbase into six pretty pages costs a lap. This
step is cheap and it runs first:

  T1  the three catalogs parse, are lists of records, and carry unique ids
  T2  orgs.json is a JOIN — every org id resolves to a speaker employer, a
      sponsor row or an explicit exhibitor capture, and every reference from
      the catalogs resolves to an org (dangling both ways is a defect)
  T3  STATE.factbase counts agree with the catalogs (the assert exists so that
      two independent sources agree — never rewrite the count from len())
  T4  cards.json covers every org

T4 has one deliberate softness: when deliverables/accounts/cards.json does not
exist at all, P2a has not run and that is a declared GAP, not a contract breach
— the build continues and the accounts page prints GAP with its reason (B13).
A cards.json that EXISTS but misses orgs is a hard fail: a half-filled account
board is worse than a visibly empty one.

ROOT is a literal written by scaffold.sh (RULES B9): never argv, $PWD or env.
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import sys

DATA = os.path.join(ROOT, 'data')
ACCOUNTS = os.path.join(ROOT, 'deliverables', 'accounts')
STATE_P = os.path.join(ROOT, 'STATE.json')

FAILS = []
NOTES = []


def fail(code, msg, fix=''):
    FAILS.append('FAIL %-20s %s%s' % (code, msg, ('\n     fix: ' + fix) if fix else ''))


def note(msg):
    NOTES.append('     ' + msg)


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default
    except Exception as e:
        fail('T0 json-unreadable', '%s: %s' % (path, e))
        return default


def records(blob, id_keys):
    """Catalogs are lists of records, or a dict keyed by id. Both normalise."""
    out = []
    if isinstance(blob, dict):
        inner = blob.get('items') or blob.get('records') or blob.get('cards') or blob.get('orgs')
        blob = inner if inner is not None else blob
    if isinstance(blob, dict):
        return [(str(k), v) for k, v in blob.items() if isinstance(v, dict)]
    if isinstance(blob, list):
        for r in blob:
            if isinstance(r, dict):
                out.append((next((str(r[k]) for k in id_keys if r.get(k)), ''), r))
    return out


state = load(STATE_P)
if state is None:
    print('FAIL T0 no-state         %s missing. Nothing can be asserted.' % STATE_P)
    sys.exit(1)
factbase = state.get('factbase') or {}

# ------------------------------------------------- T1 three catalogs parse ---
CATALOGS = (
    ('sessions', ('id', 'session_id', 'code'), ('title', 'day', 'room')),
    ('speakers', ('id', 'speaker_id'), ('name',)),
    ('sponsors', ('org_id', 'id'), ('legal_name', 'tier')),
)
parsed = {}
for name, id_keys, need in CATALOGS:
    path = os.path.join(DATA, '%s.json' % name)
    if not os.path.exists(path):
        fail('T1 catalog-missing', '%s does not exist' % path,
             'the three catalogs are the factbase. P1 writes them before P3 builds')
        parsed[name] = []
        continue
    blob = load(path)
    if blob is None:
        parsed[name] = []
        continue
    recs = records(blob, id_keys)
    parsed[name] = recs
    if not recs:
        fail('T1 catalog-empty', '%s parsed to zero records' % name,
             'an empty catalog is a scrape failure, not a finding')
        continue
    seen = {}
    for rid, r in recs:
        if not rid:
            fail('T1 catalog-id', '%s has a record with no id: %s'
                 % (name, json.dumps(r, ensure_ascii=False)[:70]), 'every record needs a stable id')
        elif rid in seen:
            fail('T1 catalog-dup', '%s id "%s" appears twice' % (name, rid),
                 'de-duplicate at the scraper, not at the page builder')
        seen[rid] = 1
        for k in need:
            if r.get(k) in (None, ''):
                fail('T1 catalog-field', '%s %s is missing "%s"' % (name, rid or '?', k),
                     'a missing required field is a re-scrape, not a GAP note')
    note('%s: %d records' % (name, len(recs)))

sessions = parsed['sessions']
speakers = parsed['speakers']
sponsors = parsed['sponsors']
orgs = records(load(os.path.join(DATA, 'orgs.json'), []), ('id', 'org_id'))
exhibitors = records(load(os.path.join(DATA, 'exhibitors.json'), []), ('org_id', 'id'))

# ----------------------------------------------- T2 orgs.json ids resolve ----
org_ids = set()
for oid, o in orgs:
    if not oid:
        fail('T2 org-id', 'an orgs.json record has no id', 'every joined org needs a stable id')
    elif oid in org_ids:
        fail('T2 org-dup', 'orgs.json id "%s" appears twice' % oid, 'the join must be idempotent')
    org_ids.add(oid)

refs = {}          # org id -> the catalogs that reference it
def ref(oid, where):
    if oid:
        refs.setdefault(str(oid), set()).add(where)

for sid, s in speakers:
    ref(s.get('company_id') or s.get('org_id') or s.get('companyId'), 'speakers.json')
for sid, s in sponsors:
    ref(s.get('org_id') or s.get('id'), 'sponsors.json')
for eid, e in exhibitors:
    ref(e.get('org_id') or e.get('id'), 'exhibitors.json')

for oid, o in orgs:
    if not oid:
        continue
    if oid not in refs and not o.get('exhibitor_capture'):
        fail('T2 orgs-join', 'orgs.json id "%s" (%s) is referenced by no speaker, sponsor or '
             'explicit exhibitor capture' % (oid, o.get('legal_name') or '?'),
             'orgs.json is a JOIN, never a fourth scrape. Drop the row or mark it '
             'exhibitor_capture: true with a source (B10)')
for oid in sorted(refs):
    if oid not in org_ids:
        fail('T2 dangling-ref', '%s points at org id "%s" which is not in orgs.json'
             % (', '.join(sorted(refs[oid])), oid), 'rebuild the join: bin/join_orgs.py')

# ------------------------------------------------------ T3 STATE agreement ---
declared = factbase.get('sessionCount')
if declared is None:
    fail('T3 session-count', 'STATE.factbase.sessionCount is unset',
         'set it from the catalog header, not from len(sessions.json)')
elif int(declared) != len(sessions):
    fail('T3 session-count', 'STATE.factbase.sessionCount=%s but sessions.json has %d'
         % (declared, len(sessions)), 're-scrape, or correct it and log the delta in STATE.corrections[]')
declared_orgs = factbase.get('orgCount')
if declared_orgs is not None and int(declared_orgs) != len(orgs):
    fail('T3 org-count', 'STATE.factbase.orgCount=%s but orgs.json has %d'
         % (declared_orgs, len(orgs)), 'rebuild the join, do not retype the number')

# ------------------------------------------------- T4 cards cover the orgs ---
cards_p = os.path.join(ACCOUNTS, 'cards.json')
if not os.path.exists(cards_p):
    note('GAP — %s does not exist. P2a (account-intel) has not run this lap; the accounts page '
         'prints GAP with this reason and the facts gate will hold the build at F6 card-coverage.'
         % cards_p)
else:
    cards = records(load(cards_p, []), ('ledger_id', 'org_id', 'id'))
    covered = {str(c.get('org_id')) for cid, c in cards if c.get('org_id')}
    for oid, o in orgs:
        if oid and oid not in covered:
            fail('T4 card-coverage', 'org "%s" (%s) has no card in cards.json'
                 % (oid, o.get('legal_name') or '?'),
                 'a speaker-only employer still gets a card; a sponsor with no speaker still gets one')
    for cid, c in cards:
        if c.get('org_id') and str(c['org_id']) not in org_ids:
            fail('T4 card-orphan', 'card %s points at org_id "%s" which is not in orgs.json'
                 % (cid or '?', c['org_id']), 'a card without an org row is an account we invented')
    note('cards: %d for %d orgs' % (len(cards), len(orgs)))

for n in NOTES:
    print(n)
if FAILS:
    print('\n'.join(FAILS))
    print('test_units: %d FAIL — the data contract is broken. Nothing builds on top of it.' % len(FAILS))
    sys.exit(1)
print('test_units: PASS  sessions=%d speakers=%d sponsors=%d orgs=%d'
      % (len(sessions), len(speakers), len(sponsors), len(orgs)))
