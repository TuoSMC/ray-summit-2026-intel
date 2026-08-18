#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_facts.py — the facts gate. Runs at EVERY build (spine-plan-v2 §2 P4).

Blocks: count drift, 未知 != 無 (B13), unsourced figures, JSON<->view drift
(D2: the JSON catalogs are the factbase, a markdown list is a generated view
and loses every argument), card coverage, the FULL cap, ledger_id resolution
and first_seen rewrites (§7.1, §14.1).

ROOT is a literal written by scaffold.sh. RULES B9: never resolved from argv,
$PWD or an env var.
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import re
import sys

STATE_P = os.path.join(ROOT, 'STATE.json')
DATA = os.path.join(ROOT, 'data')
ACCOUNTS = os.path.join(ROOT, 'deliverables', 'accounts')
RESEARCH = os.path.join(ROOT, 'deliverables', 'research')
DOCS = os.path.join(ROOT, 'docs')
CARD_SCHEMA = os.path.expanduser('~/.claude/skills/account-intel/templates/card.schema.json')

FAILS = []
NOTES = []


def fail(code, msg, fix=''):
    FAILS.append('FAIL %-22s %s%s' % (code, msg, ('\n     fix: ' + fix) if fix else ''))


def note(msg):
    NOTES.append('     ' + msg)


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default
    except Exception as e:
        fail('F0 json-unreadable', '%s: %s' % (path, e))
        return default


def as_records(blob, id_keys=('id', 'org_id', 'ledger_id', 'slug')):
    """Catalogs may be a list of records or a dict keyed by id. Both normalise
    to [(id, record)] so no builder has to care which shape a scraper left."""
    out = []
    if isinstance(blob, dict):
        inner = (blob.get('items') or blob.get('records') or blob.get('cards')
                 or blob.get('orgs'))   # ledger/index.json wraps its records in "orgs"
        if isinstance(inner, dict):
            blob = inner
            return [(k, v) for k, v in blob.items() if isinstance(v, dict)]
        if isinstance(inner, list):
            blob = inner
        else:
            for k, v in blob.items():
                if isinstance(v, dict):
                    out.append((str(k), v))
            return out
    if isinstance(blob, list):
        for r in blob:
            if not isinstance(r, dict):
                continue
            rid = next((str(r[k]) for k in id_keys if r.get(k)), '')
            out.append((rid, r))
    return out


# ---------------------------------------------------------------- inputs ---
state = load(STATE_P)
if state is None:
    print('FAIL F0 no-state           %s missing. Nothing can be checked.' % STATE_P)
    sys.exit(1)

campaign = state.get('campaign') or {}
factbase = state.get('factbase') or {}
acct_state = state.get('accounts') or {}
max_full = int(((campaign.get('accountBudget') or {}).get('maxFull')) or 8)

sessions = as_records(load(os.path.join(DATA, 'sessions.json'), []))
speakers = as_records(load(os.path.join(DATA, 'speakers.json'), []))
sponsors = as_records(load(os.path.join(DATA, 'sponsors.json'), []))
orgs = as_records(load(os.path.join(DATA, 'orgs.json'), []))
cards = as_records(load(os.path.join(ACCOUNTS, 'cards.json'), []), id_keys=('ledger_id', 'org_id', 'id'))

# =============================================================== F1 counts ==
declared = factbase.get('sessionCount')
if declared is None:
    fail('F1 session-count', 'STATE.factbase.sessionCount is unset',
         'set it from the official catalog header, not from len(sessions.json) — '
         'the point of the assert is that two independent sources agree')
elif int(declared) != len(sessions):
    fail('F1 session-count', 'STATE.factbase.sessionCount=%s but len(sessions.json)=%d'
         % (declared, len(sessions)),
         're-scrape, or correct sessionCount and log the delta in STATE.corrections[]')

declared_orgs = factbase.get('orgCount')
if declared_orgs is not None and int(declared_orgs) != len(orgs):
    fail('F1 org-count', 'STATE.factbase.orgCount=%s but len(orgs.json)=%d'
         % (declared_orgs, len(orgs)), 'orgs.json is a JOIN, never a fourth scrape — rebuild the join')

# orgs.json must be a join, not an independent capture (B10 / identity assert)
ref_ids = set()
for _, s in speakers:
    for k in ('company_id', 'org_id', 'companyId', 'orgId'):
        if s.get(k):
            ref_ids.add(str(s[k]))
for _, s in sponsors:
    for k in ('org_id', 'id', 'orgId'):
        if s.get(k):
            ref_ids.add(str(s[k]))
for oid, o in orgs:
    if not oid:
        fail('F1 org-id', 'an orgs.json record has no id', 'every joined org needs a stable id')
    elif ref_ids and oid not in ref_ids and not o.get('exhibitor_capture'):
        fail('F1 orgs-join', 'orgs.json id "%s" is referenced by no speaker, sponsor or explicit '
             'exhibitor capture' % oid,
             'orgs.json is a JOIN. Drop the row or mark it exhibitor_capture: true with a source')

# ====================================================== F3 未知 != 無 (B13) ==
ABSENCE = {'無', '没有', '沒有', '無資料', '无', 'N/A', 'n/a', 'NA', 'na', 'None', 'none',
           'null', 'NULL', '-', '—', '–', '不明', '沒有資料', '没有资料', 'nil', 'n.a.'}
GAP_FIELDS = ('buys_servers', 'oem_lock', 'mw_or_proxy', 'window', 'crm', 'layer',
              'classification', 'hq', 'ticker_or_PRIVATE')

for cid, c in cards:
    for f in GAP_FIELDS:
        v = c.get(f)
        if isinstance(v, str) and v.strip() in ABSENCE:
            fail('F3 未知≠無', 'card %s field %s = "%s"' % (cid or '?', f, v.strip()),
                 'unverified is GAP, never 無/NO/N/A. An empty cell is a gap, not a finding (B13)')
    if isinstance(c.get('crm'), str) and 'never registered' in c['crm'].lower():
        fail('F3 未知≠無', 'card %s crm claims "never registered"' % (cid or '?'),
             'the agent never registers and never checked; crm default is GAP-not-checked (B21)')


def md_tables(path):
    """Yield (header_cells, [row_cells]) for every pipe table in a markdown file."""
    lines = io.open(path, encoding='utf-8', errors='replace').read().split('\n')
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith('|') and i + 1 < len(lines) \
                and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            hdr = [c.strip() for c in lines[i].strip().strip('|').split('|')]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith('|'):
                rows.append([c.strip() for c in lines[j].strip().strip('|').split('|')])
                j += 1
            yield hdr, rows
            i = j
        else:
            i += 1


def md_files():
    for d in (ACCOUNTS, RESEARCH, DOCS):
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith('.md'):
                    yield os.path.join(d, f)


for p in md_files():
    for hdr, rows in md_tables(p):
        for r in rows:
            for cell in r:
                if cell in ABSENCE:
                    fail('F3 未知≠無', '%s table cell = "%s"' % (os.path.basename(p), cell),
                         'write GAP (and what would close it), not 無/N/A/—')

# ================================================== F4 unsourced figures ====
SOURCED_FIELDS = ('legal_name', 'aka', 'ticker_or_PRIVATE', 'hq', 'territory', 'role_at_event',
                  'layer', 'buys_servers', 'oem_lock', 'mw_or_proxy', 'window', 'crm',
                  'classification')
for cid, c in cards:
    srcs = c.get('sources') or {}
    for f in SOURCED_FIELDS:
        v = c.get(f)
        if v in (None, '', [], {}):
            continue
        if isinstance(v, str) and v.strip().upper() in ('GAP', 'GAP-NOT-CHECKED', 'NONE'):
            continue
        if f not in srcs:
            fail('F4 unsourced-cell', 'card %s cell "%s" is populated with no sources["%s"]'
                 % (cid or '?', f, f), 'source + date on every populated cell, or clear it to GAP')
        else:
            s = srcs[f] if isinstance(srcs[f], dict) else {}
            if not s.get('source') or not s.get('date'):
                fail('F4 unsourced-cell', 'card %s sources["%s"] lacks source or date' % (cid or '?', f),
                     'both keys are required; a contact aggregator is a routing hint, not a source')

FIG = re.compile(r'(?<![\w.])\d[\d,.]*\s?(MW|kW|GW|kw|mw|racks?|U\b|%|億|亿|萬|万|座|台|人|席)')
BIGNUM = re.compile(r'(?<![\w.,-])\d{4,}(?![\w.,%-])')
SRCMARK = re.compile(r'(https?://|〔|BASIS:|ESTIMATE\{|\bas ?Of\b|來源|来源|source:|\(\s*\d{4}-\d{2}-\d{2}\s*\)|\d{4}-\d{2}-\d{2})', re.I)
for p in md_files():
    lines = io.open(p, encoding='utf-8', errors='replace').read().split('\n')
    for n, ln in enumerate(lines):
        if ln.lstrip().startswith(('#', '>', '```')):
            continue
        if not (FIG.search(ln) or BIGNUM.search(ln)):
            continue
        window = '\n'.join(lines[max(0, n - 1):n + 2])
        if not SRCMARK.search(window):
            fail('F4 unsourced-figure', '%s:%d %s' % (os.path.basename(p), n + 1, ln.strip()[:90]),
                 'attach a source+date, mark it ESTIMATE{formula}, or delete the figure')

# ================================================= F5 JSON <-> view drift ===
SESSION_KEYS = {'id': ('id', 'session_id', 'code'), 'title': ('title', 'name'),
                'room': ('room', 'location', 'hall'), 'day': ('day', 'date'),
                'start': ('start', 'start_time', 'from'), 'end': ('end', 'end_time', 'to'),
                'seats': ('seats', 'capacity')}
sess_by_id = {}
for sid, s in sessions:
    if sid:
        sess_by_id[sid] = s


def field(rec, logical):
    for k in SESSION_KEYS[logical]:
        if rec.get(k) not in (None, ''):
            return str(rec[k])
    return None


for p in md_files():
    base = os.path.basename(p)
    if 'session' not in base and 'agenda' not in base and '議程' not in base:
        continue
    seen_rows = 0
    for hdr, rows in md_tables(p):
        cols = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            for logical, alts in SESSION_KEYS.items():
                if hl in alts or hl == logical or (logical == 'room' and h in ('會議室', '房間', '地點')) \
                        or (logical == 'title' and h in ('議題', '標題', '題目')):
                    cols.setdefault(logical, i)
        if 'id' not in cols:
            continue
        for r in rows:
            seen_rows += 1
            rid = r[cols['id']].strip('`* ')
            if rid not in sess_by_id:
                fail('F5 view-drift', '%s row id "%s" is not in sessions.json' % (base, rid),
                     'D2: JSON wins. Rebuild the view with make.sh views — never hand-edit it')
                continue
            for logical, i in cols.items():
                if logical == 'id' or i >= len(r):
                    continue
                want = field(sess_by_id[rid], logical)
                got = re.sub(r'[`*]', '', r[i]).strip()
                if want is not None and got and got != want.strip():
                    fail('F5 view-drift', '%s %s.%s view="%s" json="%s"'
                         % (base, rid, logical, got, want),
                         'D2: JSON wins. make.sh views')
    if seen_rows and sessions and seen_rows != len(sessions):
        fail('F5 view-count', '%s lists %d sessions, sessions.json has %d'
             % (base, seen_rows, len(sessions)), 'D2: JSON wins. make.sh views')

# ================================================ F6 card coverage (§7.1) ===
card_by_org = {}
for cid, c in cards:
    if c.get('org_id'):
        card_by_org[str(c['org_id'])] = c
for oid, o in orgs:
    if oid and oid not in card_by_org:
        fail('F6 card-coverage', 'orgs.json id "%s" has no card in deliverables/accounts/cards.json' % oid,
             'a speaker-only employer still gets a card; a sponsor with no speaker still gets a card')

# ==================================== F7 FULL cap — WRITTEN this lap (T4) ===
# §14.1: a FULL earned on an earlier lap is reused with a delta and does NOT
# consume a slot again. Only ledger_status == "new" is a FULL written this lap.
full_written = [cid for cid, c in cards if c.get('full') is True and c.get('ledger_status') == 'new']
full_reused = [cid for cid, c in cards if c.get('full') is True and c.get('ledger_status') in ('reused', 'stale')]
if len(full_written) > max_full:
    fail('F7 full-cap', 'FULLs written this lap = %d > accountBudget.maxFull = %d  (%s)'
         % (len(full_written), max_full, ', '.join(full_written[:12])),
         'cut to the cap or raise maxFull in STATE and say why in STATE.decisions[]')
if acct_state.get('fullWritten') is not None and int(acct_state['fullWritten']) != len(full_written):
    fail('F7 full-count', 'STATE.accounts.fullWritten=%s but cards say %d'
         % (acct_state['fullWritten'], len(full_written)), 'make.sh step 10 rewrites this; do not hand-edit')
note('FULL: %d written this lap, %d reused from the ledger (cap %d)'
     % (len(full_written), len(full_reused), max_full))

if os.path.isdir(ACCOUNTS):
    full_slugs = {c.get('org_id') or cid for cid, c in cards if c.get('full') is True}
    full_names = {str(x).lower() for x in full_slugs if x}
    full_names |= {str(cid).lower() for cid, c in cards if c.get('full') is True}
    for f in sorted(os.listdir(ACCOUNTS)):
        if not f.endswith('.md'):
            continue
        if f[:-3].lower() not in full_names:
            fail('F7 orphan-dossier', 'deliverables/accounts/%s has no card row with full: true' % f,
                 'either set full: true on its card (and pay a maxFull slot) or move the file out')

# ============================== F8/F9 ledger resolution + first_seen (§14.1) =
ledger_index_p = os.path.expanduser(acct_state.get('ledgerIndex')
                                    or '~/.claude/skills/account-intel/ledger/index.json')
ledger = load(ledger_index_p)
if ledger is None:
    if cards:
        fail('F8 ledger-missing', 'ledger index %s not found but %d cards exist'
             % (ledger_index_p, len(cards)),
             'lap 1: create it (an empty [] is legal) — the ledger is the thing that must not die')
    else:
        note('ledger index absent and no cards yet — lap 1, nothing to resolve')
else:
    lmap = {}
    for lid, rec in as_records(ledger, id_keys=('ledger_id', 'id', 'slug')):
        if lid:
            lmap[lid] = rec
    for cid, c in cards:
        lid = c.get('ledger_id')
        if not lid:
            fail('F8 ledger-id', 'card %s has no ledger_id' % (cid or '?'),
                 'the ledger_id is the loop key; without it this lap re-researches a filed company')
            continue
        if lid not in lmap:
            fail('F8 ledger-id', 'ledger_id "%s" does not resolve in %s' % (lid, ledger_index_p),
                 'register it in the ledger, or fix the slug. When in doubt, new — a wrong merge '
                 'poisons two accounts (§14.1)')
            continue
        master = lmap[lid]
        m_first = master.get('first_seen')
        c_first = c.get('first_seen')
        if m_first and c_first and m_first != c_first:
            fail('F9 first_seen-rewritten', 'ledger_id "%s" ledger=%s card=%s'
                 % (lid, json.dumps(m_first, ensure_ascii=False), json.dumps(c_first, ensure_ascii=False)),
                 'first_seen is WRITE-ONCE. Restore the ledger value; append to seen_at[] instead')
        if c.get('ledger_status') == 'reused' and c_first and not m_first:
            fail('F9 first_seen-invented', 'card %s is "reused" but the ledger master carries no first_seen'
                 % lid, 'a reused card cannot be the lap that created it — recheck the ledger match')

# ========================================= card schema (account-intel §7.1) ==
schema = load(CARD_SCHEMA)
if schema is None:
    note('card.schema.json not found at %s — schema validation skipped' % CARD_SCHEMA)
elif cards:
    try:
        import jsonschema  # type: ignore
        validator = jsonschema.Draft202012Validator(schema)
        for cid, c in cards:
            for err in sorted(validator.iter_errors(c), key=lambda e: list(e.path)):
                fail('F2 card-schema', 'card %s %s: %s'
                     % (cid or '?', '/'.join(str(x) for x in err.path) or '(root)', err.message),
                     'enums are enums; free text in an enum field is a schema failure, not a nuance (Y4)')
    except ImportError:
        note('jsonschema not installed — running the built-in subset validator')
        props = schema.get('properties', {})
        for cid, c in cards:
            for k in schema.get('required', []):
                if c.get(k) in (None, ''):
                    fail('F2 card-schema', 'card %s missing required "%s"' % (cid or '?', k), '')
            for k, v in c.items():
                spec = props.get(k)
                if spec is None:
                    fail('F2 card-schema', 'card %s has unknown field "%s"' % (cid or '?', k),
                         'additionalProperties is false — do not grow the card informally')
                    continue
                if 'enum' in spec and v not in spec['enum']:
                    fail('F2 card-schema', 'card %s %s="%s" is not in %s'
                         % (cid or '?', k, v, '|'.join(map(str, spec['enum']))), 'Y4: enums are enums')
                if isinstance(v, str) and spec.get('pattern') and not re.search(spec['pattern'], v):
                    fail('F2 card-schema', 'card %s %s="%s" fails pattern' % (cid or '?', k, v[:60]),
                         'hedges and free text fail here by design (Y4)')

# ------------------------------------------------------------- report ------
for n in NOTES:
    print(n)
if FAILS:
    print('\n'.join(FAILS))
    print('check_facts: %d FAIL — HARD STOP 4. Craft never outranks a red mechanical gate.' % len(FAILS))
    sys.exit(1)
print('check_facts: PASS  sessions=%d orgs=%d cards=%d fullWritten=%d/%d'
      % (len(sessions), len(orgs), len(cards), len(full_written), max_full))
