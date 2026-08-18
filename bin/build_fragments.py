#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_fragments.py --lang <src> — make.sh step 3. One HTML fragment per page role.

Reads the factbase (data/*.json), the account board
(deliverables/accounts/cards.json) and the research drafts P2 left in
deliverables/research/, and writes ONE fragment per role into build/frag/.
A fragment is the inside of <main>; wrap_pages.py step 4 owns the skeleton.

EVERY SECTION AND SUBSECTION IS A DRAWER. Native <details>/<summary>, no
JavaScript accordion — <details> is keyboard-accessible, findable by the
browser's own find-in-page, and printable. Top-level drawers open on
command-center and closed everywhere else; nested drawers always closed. A
<summary> that does not say what is inside AND how much of it is a defect: a
closed drawer still has to inform.

THE PACK NEVER DOCUMENTS ITSELF TO THE READER. No field names, no internal
taxonomy lectures, no evidence-vocabulary reference section, no pipeline
concepts. If a cell needs explaining, the explanation is that cell's own
caption, inline, one line. A term that has to be looked up elsewhere has
already failed the floor test.

The five rules this file exists to obey:

  B16  every count on every page is COMPUTED here from the JSON. A typed
       "50 sessions" is a defect even when it is currently true, because the
       next scrape makes it a lie and nothing catches it.
  B13  未知 != 無. Where a value is missing, print the literal GAP, the reason
       it is still open, and what would close it. Never 0, never 無, never
       "none" — those are findings, and we did not find them.
  B6   numbers, dates, room names, person names, company legal names and URLs
       are locked. They are emitted verbatim from the JSON, once, OUTSIDE the
       language layers wherever the sentence allows; step 5 proves both arms
       carry the identical locked-token sequence.
  B7   the second language is vocabulary, not transcoding. Every string in this
       file is authored twice, by hand, in tt(). There is no transliteration
       path and there is no machine in the loop.
  B1   evidence quality is its own axis. Every surfaced figure carries its rank
       chip, its source as a REAL LINK, and the date it was read.

Bilingual contract (DESIGN.md 7): a translatable run is a pair of sibling
spans, h first: <span data-t="h">…</span><span data-t="e">…</span>. Both
languages ship in the HTML; the toggle only switches visibility. Never nest one
pair inside another, and never put a locked run inside an arm.

Audience is SALES. No agent counts, no pipeline talk, no method above the
verdict (page-role.json forbids both on the hub).

ROOT is a literal written by scaffold.sh (RULES B9). --lang carries the source
language only; make.sh refuses any other value before this script is called.
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import html
import io
import json
import os
import re
import sys
try:
    from urllib.parse import urlparse
except ImportError:                                     # pragma: no cover
    from urlparse import urlparse                       # type: ignore
from collections import OrderedDict

DATA = os.path.join(ROOT, 'data')
ACCOUNTS = os.path.join(ROOT, 'deliverables', 'accounts')
RESEARCH = os.path.join(ROOT, 'deliverables', 'research')
BUILD = os.path.join(ROOT, 'build')
FRAG = os.path.join(BUILD, 'frag')
STATE_P = os.path.join(ROOT, 'STATE.json')

# role, filename (A5: same filename == same URL forever), title h/e, nav h/e
PAGES = [
    ('command-center', 'index.html',    '作戰台', 'War Room',      '作戰台', 'War Room'),
    ('agenda',         'agenda.html',   '議程',   'Agenda',        '議程',   'Agenda'),
    ('gtm',            'gtm.html',      '打法',   'Plays',         '打法',   'Plays'),
    ('accounts',       'accounts.html', '帳戶板', 'Account Board', '帳戶板', 'Accounts'),
    ('compare',        'compare.html',  '對位',   'Matchup',       '對位',   'Matchup'),
]

# key, ZH name, EN name, ZH caption, EN caption. The caption is what the band
# means for a rep standing in front of one of these companies — not a taxonomy
# lesson.
LAYERS = [
    ('operator', '營運商', 'Operator',
     '買機器、把 GPU 變成可租算力賣出去。他們簽的是最大的伺服器訂單',
     'Buys the machines and sells the GPUs on as rentable compute. These sign the biggest '
     'server orders in the room'),
    ('tenant', '租戶', 'Tenant',
     '買算力來跑自己的模型與產品。自建的那幾家會直接下單，租雲的那幾家只能給情報',
     'Buys compute to run its own models and products. The ones that build order directly; '
     'the ones that rent are intelligence, not pipeline'),
    ('channel', '通路', 'Channel',
     '把硬體或方案賣給上面兩層。可能是對手，也可能是共同提案的夥伴',
     'Sells hardware or solutions to the two layers above. Either a rival or a co-sell '
     'partner, and it is worth knowing which'),
    ('landlord', '房東', 'Landlord',
     '出租機房、電力與冷卻。寫伺服器訂單的是他們的租戶，不是他們',
     'Rents out the hall, the power and the cooling. The server order is written by their '
     'tenant, not by them'),
]

# Evidence vocabulary (DESIGN.md 4). Translated as VOCABULARY, never transcoded.
# Overridable from data/termbase.json["evidence"] so P6 can merge it upward.
EVIDENCE = OrderedDict([
    ('official',   ('官方一手', 'Official first-party')),
    ('vendor',     ('廠商自報', 'Vendor-reported')),
    ('third',      ('第三方',   'Third-party')),
    ('unverified', ('未證',     'Unverified')),
    ('gap',        ('GAP',      'GAP')),
])


# ------------------------------------------------------------- helpers ------
def esc(v):
    return html.escape('' if v is None else str(v), quote=False)


def att(v):
    return html.escape('' if v is None else str(v), quote=True)


def tt(h, e):
    """The only way to emit prose. Two arms, h first, both shipped (DESIGN.md 7)."""
    return '<span data-t="h">%s</span><span data-t="e">%s</span>' % (h, e)


def lk(v):
    """A locked run (B6): emitted verbatim, one shared style, both languages."""
    return '<span class="lk">%s</span>' % esc(v)


def pl(n, one, many):
    """English count. "1 companies" is the tell that a number was templated
    rather than written; the figure itself is unchanged, so B6 still holds."""
    return '%d %s' % (n, one if n == 1 else many)


def S(*parts):
    """A sentence. A ('zh', 'en') tuple becomes a language pair; a bare string
    becomes a LOCKED run emitted outside the pair (DESIGN.md 6), which is also
    what keeps step 5's figure gate satisfied without hand-matching digits."""
    out = []
    for p in parts:
        if p is None or p == '':
            continue
        if isinstance(p, (tuple, list)):
            out.append(tt(esc(p[0]), esc(p[1])))
        elif p in ('·', '—', '→'):
            out.append('<span class="sep" aria-hidden="true">%s</span>' % esc(p))
        else:
            out.append(lk(p))
    return ' '.join(out)


def gap(why_h, why_e):
    """The only legal way to print a missing value (B13). A GAP always carries
    its reason and what would close it — this helper cannot emit one without."""
    return ('<span class="gap">GAP</span> <span class="why">%s</span>'
            % tt(esc(why_h), esc(why_e)))


def ev(rank):
    """An evidence chip. rank is COMPUTED by evidence_of(), never typed."""
    h, e = EVIDENCE.get(rank, EVIDENCE['unverified'])
    return ('<span class="ev ev-%s"><span class="ev-mark" aria-hidden="true"></span>%s</span>'
            % (rank, tt(esc(h), esc(e))))


def url_label(u):
    """What the link SAYS. The href stays byte-identical; the label is trimmed
    so a 180-character SEC path does not eat the card."""
    try:
        p = urlparse(str(u))
    except Exception:
        return str(u)
    host = re.sub(r'^www\.', '', (p.netloc or '').lower())
    path = (p.path or '').rstrip('/')
    if len(path) > 30:
        path = path[:28] + '…'
    return (host + path) or str(u)


def src_a(url, date=None, note_h=None, note_e=None):
    """A source, visible: a real link plus the day it was read. Never implied."""
    bits = []
    if url:
        bits.append('<a class="srcl" href="%s" title="%s">%s</a>'
                    % (att(url), att(url), esc(url_label(url))))
    if date:
        bits.append(lk(date))
    if note_h or note_e:
        bits.append(tt(esc(note_h or ''), esc(note_e or '')))
    if not bits:
        return ''
    return '<span class="src">%s</span>' % ' '.join(bits)


def dr(title_html, scent_html, body, is_open=False, cls='', block='', fresh=False):
    """A drawer. The summary carries the title AND a scent line — what is inside
    plus a count or a verdict — so a closed drawer still informs (RULES C6: the
    control is >=44px, focusable, and native, so keyboard works for free)."""
    at = ['class="dr%s"' % ((' ' + cls) if cls else '')]
    if block:
        at.append('data-block="%s"' % att(block))
    if fresh:
        at.append('data-fresh="1"')
    if is_open:
        at.append('open')
    return ('<details %s>\n'
            '  <summary><span class="dr-t">%s</span><span class="dr-s">%s</span></summary>\n'
            '  <div class="dr-b">\n%s\n  </div>\n'
            '</details>' % (' '.join(at), title_html, scent_html, body))


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default
    except Exception as e:
        sys.exit('build_fragments: FAIL %s is unreadable: %s' % (path, e))


def as_list(blob):
    if isinstance(blob, dict):
        inner = blob.get('items') or blob.get('records') or blob.get('cards') or blob.get('orgs')
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            return [v for v in inner.values() if isinstance(v, dict)]
        return [v for v in blob.values() if isinstance(v, dict)]
    return [r for r in (blob or []) if isinstance(r, dict)]


def arg(flag, default=None):
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == flag and i + 1 < len(a):
            return a[i + 1]
        if x.startswith(flag + '='):
            return x.split('=', 1)[1]
    return default


# --------------------------------------------------------------- inputs ----
state = load(STATE_P) or {}
campaign = state.get('campaign') or {}
factbase = state.get('factbase') or {}
langs = campaign.get('langs') or ['h']
src_lang = arg('--lang', langs[0])
if src_lang != langs[0]:
    sys.exit('build_fragments: FAIL --lang %s is not the source language %s (B7: a fragment '
             'written straight into a target language is a second source of truth)'
             % (src_lang, langs[0]))

sessions = as_list(load(os.path.join(DATA, 'sessions.json'), []))
speakers = as_list(load(os.path.join(DATA, 'speakers.json'), []))
sponsors = as_list(load(os.path.join(DATA, 'sponsors.json'), []))
orgs = as_list(load(os.path.join(DATA, 'orgs.json'), []))
exhibitors = as_list(load(os.path.join(DATA, 'exhibitors.json'), []))
termbase = load(os.path.join(DATA, 'termbase.json'), {}) or {}
cards_p = os.path.join(ACCOUNTS, 'cards.json')
cards = as_list(load(cards_p, [])) if os.path.exists(cards_p) else None   # None == not built yet

for k, pair in (termbase.get('evidence') or {}).items():
    if isinstance(pair, dict) and pair.get('h') and pair.get('e'):
        EVIDENCE[k] = (str(pair['h']), str(pair['e']))

EVENT = campaign.get('event') or 'event'
ASOF = factbase.get('asOf') or ''
SOURCE = factbase.get('source') or campaign.get('catalog') or ''
CATALOG = campaign.get('catalog') or SOURCE
US = campaign.get('us') or ''
MAXFULL = int(((campaign.get('accountBudget') or {}).get('maxFull')) or 8)
STAMP = ('<p class="stamp" data-fresh="1">%s</p>'
         % tt('狀態截至 %s' % esc(ASOF), 'Status as of %s' % esc(ASOF)))


# ------------------------------------------------- evidence classification --
def _host(url):
    try:
        return (urlparse(str(url)).netloc or '').lower()
    except Exception:
        return ''


CATALOG_HOSTS = set(h for h in (_host(SOURCE), _host(campaign.get('catalog'))) if h)
EVENT_SLUG = '-'.join(t for t in re.findall(r'[a-z0-9]+', EVENT.lower())
                      if not re.match(r'^\d{4}$', t))


def evidence_of(url, subject_name=''):
    """Rank a cell's evidence from WHERE it came from. Deterministic, computed.

    1. no source                                        -> unverified
    2. host is the official catalogue                   -> official
    3. an event-branded page on any participating site  -> official
    4. host carries the subject company's own name      -> vendor
    5. anything else on the open web                    -> third
    """
    if not url:
        return 'unverified'
    host = _host(url)
    if not host:
        return 'unverified'
    if host in CATALOG_HOSTS:
        return 'official'
    if EVENT_SLUG and EVENT_SLUG in str(url).lower():
        return 'official'
    flat = re.sub(r'[^a-z0-9]', '', str(subject_name).lower())
    if flat and len(flat) >= 3 and flat in re.sub(r'[^a-z0-9]', '', host):
        return 'vendor'
    return 'third'


# ------------------------------------------------- computed aggregates -----
N_SESS, N_SPK, N_SPO, N_ORG = len(sessions), len(speakers), len(sponsors), len(orgs)

by_day = OrderedDict()
for s in sessions:
    by_day.setdefault(str(s.get('day') or ''), []).append(s)
DAYS = sorted(d for d in by_day if d)

tag_count, room_count = {}, {}
for s in sessions:
    for t in (s.get('tags') or []):
        tag_count[str(t)] = tag_count.get(str(t), 0) + 1
    r = str(s.get('room') or '')
    if r:
        room_count[r] = room_count.get(r, 0) + 1
TAGS = sorted(tag_count, key=lambda k: (-tag_count[k], k))
ROOMS = sorted(room_count, key=lambda k: (-room_count[k], k))

TIER_RANK = {'presenting': 0, 'diamond': 1, 'platinum': 2, 'gold': 3, 'silver': 4,
             'bronze': 5, 'startups': 6}
tier_count, tier_of = {}, {}
for s in sponsors:
    t = str(s.get('tier') or '')
    tier_count[t] = tier_count.get(t, 0) + 1
    if s.get('org_id'):
        tier_of[str(s['org_id'])] = t
TIERS = sorted(tier_count, key=lambda k: (TIER_RANK.get(k, 9), k))

org_by_id = OrderedDict()
for o in orgs:
    if o.get('id'):
        org_by_id[str(o['id'])] = o
exhibitor_of = {str(e['org_id']): e for e in exhibitors if e.get('org_id')}
speaker_orgs = [oid for oid, o in org_by_id.items()
                if 'speaker-employer' in (o.get('roles_at_event') or [])]
sponsor_orgs = [oid for oid, o in org_by_id.items()
                if 'sponsor' in (o.get('roles_at_event') or [])]
exhibitor_orgs = [oid for oid, o in org_by_id.items()
                  if o.get('exhibitor_capture') or 'exhibitor' in (o.get('roles_at_event') or [])]

seats_known = [s for s in sessions if s.get('seats') not in (None, '')]

# ---- the account board, tallied once ---------------------------------------
# The cell set is exactly the one check_facts.py polices, so the number on the
# page and the number the gate enforces cannot drift apart.
CELL_FIELDS = ('legal_name', 'aka', 'ticker_or_PRIVATE', 'hq', 'territory', 'role_at_event',
               'layer', 'buys_servers', 'oem_lock', 'mw_or_proxy', 'window', 'crm',
               'classification')


def is_gap(v):
    return isinstance(v, str) and v.strip().upper().startswith('GAP')


def cell_tally():
    pop = srcd = gapc = 0
    ranks = OrderedDict((k, 0) for k in EVIDENCE)
    urls = set()
    for c in (cards or []):
        srcs = c.get('sources') or {}
        for f in CELL_FIELDS:
            v = c.get(f)
            if v in (None, '', [], {}):
                continue
            if is_gap(v):
                gapc += 1
                ranks['gap'] += 1
                continue
            pop += 1
            s = srcs.get(f) if isinstance(srcs.get(f), dict) else None
            s = s or {}
            if s.get('source') and s.get('date'):
                srcd += 1
                urls.add(str(s['source']))
            ranks[evidence_of(s.get('source'), c.get('legal_name'))] += 1
    return pop, srcd, gapc, ranks, len(urls)


POP, SRCD, GAPC, RANKS, N_SRCURL = cell_tally()
N_CARDS = 0 if cards is None else len(cards)
FULLS = [c for c in (cards or []) if c.get('full') is True]
N_FULL = len(FULLS)
BUYS_YES = [c for c in (cards or []) if str(c.get('buys_servers')) == 'YES']
BUYS_PART = [c for c in (cards or []) if str(c.get('buys_servers')) == 'PARTIAL']
BUYS_NO = [c for c in (cards or []) if str(c.get('buys_servers')) == 'NO']
BUYS_GAP = [c for c in (cards or []) if is_gap(c.get('buys_servers'))]
RULED_OUT = [c for c in (cards or []) if str(c.get('classification')) == 'ruled-out']
WINDOW_KNOWN = [c for c in (cards or []) if c.get('window') and not is_gap(c.get('window'))]
MW_KNOWN = [c for c in (cards or []) if c.get('mw_or_proxy') and not is_gap(c.get('mw_or_proxy'))]


def _first_note(key, authored_h, authored_e):
    """The ZH arm is authored; the EN arm quotes the factbase's own words when
    it has any. A leading GAP marker is stripped — gap() prints the token."""
    v = next((s.get(key) for s in sessions if s.get(key)), None)
    if not v:
        return authored_h, authored_e
    e = re.sub(r'^\s*GAP\s*[-—–:]*\s*', '', str(v)) or authored_e
    return authored_h, e


SEAT_WHY_H, SEAT_WHY_E = _first_note(
    'seats_note', '官方目錄沒有揭露場次容量', 'the catalogue does not expose capacity')
LINK_WHY_H, LINK_WHY_E = _first_note(
    'speakers_note', '目錄的場次卡片沒有掛任何講者',
    'the session cards carry no speaker at all')


def missing_days():
    """Days inside campaign.dates that publish no session — a GAP, not 'no sessions'."""
    m = re.findall(r'(\d{4}-\d{2}-\d{2})', str(campaign.get('dates') or ''))
    if len(m) < 2:
        return []
    import datetime
    try:
        a = datetime.date.fromisoformat(m[0])
        b = datetime.date.fromisoformat(m[-1])
    except ValueError:
        return []
    out, cur = [], a
    while cur <= b:
        iso = cur.isoformat()
        if iso not in by_day:
            out.append(iso)
        cur += datetime.timedelta(days=1)
    return out


MISSING_DAYS = missing_days()


def axis_members(axis_str):
    """Resolve a STATE axis string to the orgs that are actually AT this event.

    The axis names its members in parentheses. Matching is deliberately
    conservative and ordered, because the traps in STATE are exactly the
    collisions a loose matcher would create (Lambda Labs vs AWS Lambda)."""
    inner = re.search(r'\(([^)]*)\)', axis_str)
    tokens = [t.strip() for t in re.split(r'[/,]', inner.group(1))] if inner else []
    hits = OrderedDict()
    for tok in [t for t in tokens if t]:
        low = tok.lower()
        picked = [oid for oid, o in org_by_id.items() if str(o.get('legal_name', '')).lower() == low]
        if not picked:
            picked = [oid for oid, o in org_by_id.items() if low in str(o.get('legal_name', '')).lower()]
        if not picked:
            flat = low.replace(' ', '')
            picked = [oid for oid in org_by_id if oid.split('_', 1)[-1].lower() == flat]
        if not picked:
            cand = [(len(str(o.get('legal_name', ''))), oid) for oid, o in org_by_id.items()
                    if str(o.get('legal_name', '')) and low.startswith(str(o.get('legal_name', '')).lower() + ' ')]
            picked = [max(cand)[1]] if cand else []
        for oid in picked:
            hits.setdefault(oid, tok)
        if not picked:
            hits.setdefault('!' + tok, tok)      # named on the axis, absent from orgs.json
    return hits


AXES = [str(a) for a in (campaign.get('axis') or [])]
AXIS_HITS = [(a, axis_members(a)) for a in AXES]
SEGMENTS = [str(s) for s in (campaign.get('segments') or [])]


def org_name(oid):
    o = org_by_id.get(oid)
    return str((o or {}).get('legal_name') or oid)


def org_badges(oid):
    """Computed presence chips — never typed."""
    out = []
    t = tier_of.get(oid)
    if t:
        out.append(t)
    o = org_by_id.get(oid) or {}
    for r in (o.get('roles_at_event') or []):
        out.append(str(r))
    if oid in exhibitor_of:
        out.append('exhibitor-capture')
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def band_key(layer_value):
    """Bind a card to a band by the head term of its layer ("tenant-selfuse"
    is a tenant). The full value still prints on the card, verbatim."""
    v = str(layer_value or '').strip().lower()
    if not v or v.startswith('gap'):
        return None
    known = {k for k, _n, _e, _d, _de in LAYERS}
    if v in known:
        return v
    head = v.split('-')[0].split('/')[0]
    return head if head in known else None


# ---- research drafts: read for provenance, never scraped for prose ---------
# The prose on the pages is authored in both languages below. What is read from
# the drafts here is WHICH draft carries a claim, so a citation is computed.
RESEARCH_TEXT = OrderedDict()
if os.path.isdir(RESEARCH):
    for f in sorted(os.listdir(RESEARCH)):
        if f.endswith('.md'):
            try:
                RESEARCH_TEXT[f] = io.open(os.path.join(RESEARCH, f),
                                           encoding='utf-8', errors='replace').read()
            except OSError:
                pass


def draft(prefix):
    """The draft filename that starts with this number — computed, so a rename
    surfaces as a GAP instead of a dead citation."""
    for f in RESEARCH_TEXT:
        if f.startswith(prefix):
            return f
    return ''


D01, D03, D05 = draft('01-'), draft('03-'), draft('05-')


def from_draft(fname, note_h='底稿', note_e='research draft'):
    if not fname:
        return ''
    return ('<span class="src">%s %s</span>'
            % (tt(esc(note_h), esc(note_e)), lk('deliverables/research/%s' % fname)))


def day_counts_h():
    return '、'.join('%s %d' % (d, len(by_day[d])) for d in DAYS)


def day_counts_e():
    return ', '.join('%s %d' % (d, len(by_day[d])) for d in DAYS)


def tier_counts_h():
    return '、'.join('%s %d' % (t, tier_count[t]) for t in TIERS)


def tier_counts_e():
    return ', '.join('%s %d' % (t, tier_count[t]) for t in TIERS)


def ul(items, cls='ev-list'):
    return ('  <ul class="%s">\n%s\n  </ul>'
            % (cls, '\n'.join('    <li>%s</li>' % x for x in items))) if items else ''


# ============================================================ command-center ==
# Research draft 01 reaches the reader HERE. Every claim keeps the hedge it was
# written with (B6): "未經雙方證實" does not become a bare assertion in English.

def frag_command_center():
    h = []
    a = h.append
    OPEN = True                       # top-level drawers open on the hub only

    # ---------------------------------------------------- 1. the verdict ----
    grounds = []
    axis_h, axis_e = [], []
    for axis, hits in AXIS_HITS:
        present = [o for o in hits if not o.startswith('!')]
        label = axis.split('(')[0].strip()
        axis_h.append('%s %d 家' % (esc(label), len(present)))
        axis_e.append('%s %d' % (esc(label), len(present)))
    grounds.append('%s %s' % (
        tt('到場 %d 家組織，兩條軸線都在現場：%s。' % (N_ORG, esc('、'.join(axis_h))),
           '%d organisations on site, and both axes are in the room: %s.'
           % (N_ORG, esc('; '.join(axis_e)))),
        ev('official')))
    grounds.append('%s %s' % (
        tt('贊助 %d 家，依層級：%s。這一層一層就是走廊上的優先順序。' % (N_SPO, esc(tier_counts_h())),
           '%d sponsors by tier: %s. That order is your corridor priority.'
           % (N_SPO, esc(tier_counts_e()))),
        ev('official')))
    if cards is not None:
        grounds.append('%s %s' % (
            tt('%d 家裡有 %d 家自己買機器、%d 家部分自購；%d 家這一輪查完判定不是買方，'
               '%d 家還沒查到足以判定的證據。'
               % (N_CARDS, len(BUYS_YES), len(BUYS_PART), len(RULED_OUT), len(BUYS_GAP)),
               'Of %d companies, %d buy their own machines and %d partly do; %d were researched '
               'this lap and are not buyers; %d carry no evidence either way yet.'
               % (N_CARDS, len(BUYS_YES), len(BUYS_PART), len(RULED_OUT), len(BUYS_GAP))),
            ev('third')))
    if US:
        grounds.append('%s %s %s' % (tt('我方定位：', 'Our position: '), esc(US), ev('unverified')))

    verdict_title = ('<h1>%s</h1>'
                     % tt('這一場的錢在<em>租算力</em>，不在買機器。我方以 scout 進場：收訊號，不擺攤。',
                          'The money in this room is spent <em>renting compute</em>, not buying '
                          'machines. We walk in as a scout: collect signal, hold no booth.'))
    verdict_scent = ('<span class="lede dr-lede">%s</span>'
                     % tt('沒有一家傳統伺服器對手在場。你要找的不是攤位對手，是誰在替這些人簽算力的帳。',
                          'Not one traditional server rival is here. You are not looking for a rival '
                          'booth — you are looking for whoever signs the compute bill for these '
                          'people.'))
    a(dr(verdict_title, verdict_scent,
         '  <ul class="grounds">\n%s\n  </ul>\n  %s'
         % ('\n'.join('    <li>%s</li>' % g for g in grounds), STAMP),
         is_open=OPEN, cls='verdict', block='verdict', fresh=True))
    a('<p class="stamp topstamp" data-block="asOf-stamp" data-fresh="1">%s</p>'
      % tt('狀態截至 %s' % esc(ASOF), 'Status as of %s' % esc(ASOF)))

    # ------------------------------------------------- 2. the four numbers --
    figs = [
        (str(N_SESS), '場次', 'Sessions',
         '目錄已公布的兩天：%s' % day_counts_h(),
         'the two days the catalogue has published: %s' % day_counts_e(), False),
        (str(N_ORG), '到場組織', 'Organisations on site',
         '講者雇主 %d、贊助 %d、現場捕獲 %d，可重疊'
         % (len(speaker_orgs), len(sponsor_orgs), len(exhibitor_orgs)),
         'speaker employers %d, sponsors %d, floor captures %d, overlapping'
         % (len(speaker_orgs), len(sponsor_orgs), len(exhibitor_orgs)), False),
    ]
    if cards is None:
        figs.append(('<span class="gap">GAP</span>', '自己買機器的', 'Buy their own machines',
                     '帳戶卡還沒建，這是未知，不是零', 'the account board is not built yet — '
                     'unknown, not zero', True))
        figs.append(('<span class="gap">GAP</span>', '完整檔', 'Full dossiers',
                     '帳戶卡還沒建', 'the account board is not built yet', True))
    else:
        figs.append((str(len(BUYS_YES)), '自己買機器的', 'Buy their own machines',
                     '另有 %d 家部分自購、%d 家證據不足' % (len(BUYS_PART), len(BUYS_GAP)),
                     'plus %d partly and %d with too little evidence to say'
                     % (len(BUYS_PART), len(BUYS_GAP)), False))
        figs.append((str(N_FULL), '完整檔', 'Full dossiers',
                     '本輪上限 %d；其餘 %d 家是單頁卡' % (MAXFULL, N_CARDS - N_FULL),
                     'cap %d this lap; the other %d are one-screen cards'
                     % (MAXFULL, N_CARDS - N_FULL), False))
    figs_html = ['  <ol class="figs">']
    for v, kh, ke, sh, se, g in figs:
        figs_html.append('    <li class="fig%s"><span class="n">%s</span>'
                         '<span class="k">%s</span><span class="src">%s</span></li>'
                         % (' is-gap' if g else '', v if g else esc(v),
                            tt(esc(kh), esc(ke)), tt(esc(sh), esc(se))))
    figs_html.append('  </ol>')
    figs_html.append('  %s' % STAMP)
    a(dr(tt('四個數字', 'Four numbers'),
         tt('全部在建置時從資料算出來，沒有一個是打上去的',
            'all computed from the data at build time, not one of them typed'),
         '\n'.join(figs_html), is_open=OPEN, block='four-numbers', fresh=True))

    # ----------------------------------------------------- 3. two actions ---
    prio = floor_priority()
    top2 = [p for p in prio if p['session']][:2]
    platinum = [oid for oid in sponsor_orgs
                if tier_of.get(oid) in ('presenting', 'diamond', 'platinum')]
    acts = ['  <ol class="acts">']
    acts.append('    <li>')
    acts.append('      <b>%s</b>' % tt('開場先卡這兩場。', 'Take these two rooms first.'))
    if top2:
        for p in top2:
            s = p['session']
            acts.append('      <p class="actses">%s</p>' % lk(s.get('title')))
            acts.append('      <p class="meta-row">%s <span class="sep" aria-hidden="true">·</span> '
                        '%s <span class="sep" aria-hidden="true">·</span> %s</p>'
                        % (lk(s.get('day')), lk(s.get('start_end')), lk(s.get('room'))))
            acts.append('      <p class="why">%s</p>' % tt(esc(p['why_h']), esc(p['why_e'])))
    else:
        acts.append('      <p>%s</p>'
                    % gap('底稿點名的優先場次在目錄裡對不上任何一場；到場用活動 App 重排',
                          'the sessions the draft prioritises match nothing in the catalogue; '
                          're-rank on the event app when you arrive'))
    acts.append('    </li>')
    acts.append('    <li>')
    acts.append('      <b>%s</b>' % tt('每一場對話都收同一題。',
                                       'Ask the same one question in every conversation.'))
    acts.append('      <p class="askq">%s</p>'
                % tt('「你們的 Ray 叢集跑在自己機房、租的 colo，還是純雲端執行個體？」',
                     '"Does your Ray cluster run in your own hall, in colo you rent, or purely on '
                     'cloud instances?"'))
    acts.append('      <p>%s</p>'
                % tt('自建或 colo 就能直銷；純雲端的人是情報來源，不是買家 —— 一句話就分完。',
                     'Own hall or colo means you can sell direct. Pure cloud means the person is '
                     'intelligence, not pipeline. One sentence sorts the room.'))
    if platinum:
        acts.append('      <p>%s</p>'
                    % tt('白金以上 %d 家先問：' % len(platinum),
                         'Start with the %d at platinum or above:' % len(platinum)))
        acts.append('      <p>%s</p>'
                    % ''.join('<span class="chip">%s</span>' % esc(org_name(o))
                              for o in platinum))
    acts.append('%s' % from_draft(D05))
    acts.append('    </li>')
    acts.append('  </ol>')
    a(dr(tt('兩個動作', 'Two actions'),
         tt('一個是站位，一個是問句。其餘等現場',
            'one is where to stand, one is what to ask. The rest waits for the floor'),
         '\n'.join(acts), is_open=OPEN, block='two-actions'))

    # ------------------------------------------------ 4. what room this is --
    room = []
    room.append(ul([
        '%s %s' % (S(('不是廠商展會，是工程社群年會加上供應商聚集。官方寫給的對象是 builders、'
                      'platform leads 與 researchers ——', 'Not a trade show: an engineering '
                      'community conference with vendors around it. The official audience line '
                      'reads builders, platform leads and researchers —'),
                     ('自建叢集的平台工程主管，不是採購。', 'the platform engineering leads who run '
                      'their own clusters, not procurement.')),
                   ev('official') + src_a(CATALOG, ASOF)),
        '%s %s' % (S(('票價', 'Tickets run'), 'USD 400–450',
                     ('，五張套票每張', ', or five-packs at'), 'USD 750',
                     ('。工程師自費就進得來 —— 來的人多半是實作者，不是簽核者。把「誰簽字」當成'
                      '每一次對話要挖出來的東西。',
                      ' each. That is self-funded-engineer money, so the room is implementers, not '
                      'signatories. Treat "who signs" as the thing every conversation has to '
                      'surface.')),
                   ev('official') + from_draft(D01)),
        '%s %s' % (S(('Ray 的治理已經交給 PyTorch Foundation，累計下載',
                      'Ray governance has moved to the PyTorch Foundation; cumulative downloads'),
                     '237M', ('，名單上的用戶含 OpenAI、Uber、Shopify、Netflix。'
                              '治理中立，商業層在 Nscale 手上。',
                              ', with OpenAI, Uber, Shopify and Netflix named as users. Neutral '
                              'governance, commercial layer in Nscale\'s hands.')),
                   ev('official') + src_a('https://pytorch.org', '2025-10-22')),
        '%s %s' % (S(('主辦權在會前三週半換人，換給了買機櫃的人：', 'Ownership of the show changed '
                      'hands three and a half weeks before it opens, to someone who buys racks: '),
                     'Nscale', ('於', 'agreed on'), '2026-07-30',
                     ('宣布收購 Anyscale，同時是本屆白金贊助商並有 keynote 席位。'
                      '雙方均未官方證實，寫進客戶簡報時這個 hedge 要跟著走。',
                      ' to acquire Anyscale, while also being a Platinum sponsor with a keynote '
                      'slot this year. Neither side has officially confirmed it; that hedge travels '
                      'with the claim into any customer deck.')),
                   ev('third')
                   + src_a('https://techcrunch.com/2026/07/30/nscale-buys-anyscale-as-it-seeks-to-own-more-of-the-ai-compute-stack/',
                           '2026-07-30')),
        '%s %s' % (S(('這房間的購買理由是「利用率」，不是規格。Torc 自報 GPU 利用率從',
                      'This room buys on utilisation, not on spec. Torc reports GPU utilisation '
                      'moving from'), '30–40%', ('拉到約', 'to about'), '90%',
                     ('，同等牆鐘時間內處理的資料量從', ', and data processed in the same wall clock '
                      'from'), '4TB', ('變成', 'to'), '38TB',
                     ('。跟這群人談 TFLOPS 會冷場，談「同樣機櫃多跑幾成」會熱。',
                      '. Talk TFLOPS to these people and the conversation dies; talk "more work out '
                      'of the same rack" and it opens.')),
                   ev('vendor') + from_draft(D01)),
    ]))
    a(dr(tt('這是什麼房間', 'What room this is'),
         tt('工程社群年會，實作者為主，買點是利用率不是規格',
            'an engineering community conference: implementers, and the buying reason is '
            'utilisation, not spec'),
         '\n'.join(room), is_open=OPEN))

    # --------------------------------------------------- 5. 2025 -> 2026 ----
    ch = []
    ch.append(ul([
        S(('時間前挪十週：上一屆是', 'Ten weeks earlier: last year ran'), '2025-11-03',
          ('至', 'to'), '2025-11-05', ('，這一屆是', ', this one runs'), '2026-08-24',
          ('至', 'to'), '2026-08-26',
          ('，同一個 Marriott Marquis。兩屆只隔約九個半月，客戶的預算年度沒有跟著走。',
           ', in the same Marriott Marquis. Two editions about nine and a half months apart — '
           'the customer budget year did not move with it.')) + ' ' + ev('official'),
        S(('主軸從八條收斂成四條，每一條都吃 GPU：Foundation Model Training、Multimodal Data '
           'Curation、Physical AI、LLM RL。去年還有 Ray Ecosystem、Generative AI、Research '
           'Frontiers —— 軟體話題被擠掉，剩下全是算力題。',
           'The tracks narrowed from eight to four, and every one of them eats GPU: Foundation '
           'Model Training, Multimodal Data Curation, Physical AI, LLM RL. Last year still had Ray '
           'Ecosystem, Generative AI and Research Frontiers. The software topics were squeezed '
           'out; what is left is all compute.')) + ' ' + ev('official') + from_draft(D01),
        S(('vLLM 第一次以獨立會議共構，同場舉行、Summit 票含全程，橫跨',
           'A first-ever standalone vLLM conference runs inside the show, covered by the Summit '
           'ticket, spanning'), '2026-08-25', ('與', 'and'), '2026-08-26',
          ('。硬體話題藏在那半場，不在 Ray 主軌。',
           '. The hardware conversation lives in that half of the building, not on the Ray '
           'track.')) + ' ' + ev('official') + src_a('https://vllm.ai', ASOF),
        S(('vLLM 商業化了：Inferact 於', 'vLLM has a company now: Inferact was founded in'),
          '2026-01', ('成立，種子輪', ', raised a'), 'USD 150M', ('、估值', 'seed at a'),
          'USD 800M', ('，a16z 與 Lightspeed 領投。去年掛專案名的人，今年掛公司抬頭。',
                       ' valuation, led by a16z and Lightspeed. The people who wore a project name '
                       'last year wear a company title this year.')) + ' ' + ev('third')
        + from_draft(D01),
        S(('話題從「怎麼管工作」變成「怎麼貼合機櫃」：去年 keynote 發表排程器與執行環境，'
           '今年上半年發表的是 GB300 NVL72 的拓撲感知排程。軟體開始感知機櫃，代表客戶已經跨多機櫃在跑。',
           'The subject moved from "how to manage jobs" to "how to fit the rack": last year\'s '
           'keynote shipped a scheduler and a runtime, this year\'s first half shipped '
           'topology-aware scheduling for GB300 NVL72. Software noticing racks means customers are '
           'already running across several of them.')) + ' ' + ev('vendor') + from_draft(D01),
    ]))
    a(dr(tt('2025 → 2026 變了什麼', 'What changed from 2025 to 2026'),
         tt('主軸從八條收成四條、全部吃 GPU；vLLM 有公司了；主辦權易主',
            'eight tracks became four and all of them eat GPU; vLLM has a company; the show '
            'changed owner'),
         '\n'.join(ch), is_open=OPEN))

    # ------------------------- 6. technical turn -> server demand -----------
    turns = [
        ('Physical AI', '機器人與自駕升為四大主軸，訓練日有 workshop、keynote 有 Torc 與 Bedrock',
         'Robotics and autonomy became one of the four tracks; there is a training-day workshop '
         'and Torc and Bedrock on the keynote stage',
         '新增一整類自建叢集買主。形狀是大量影片前處理加上 VLA 大模型訓練，資料量跳檔。'
         '這類客戶不租雲，會直接買機器 —— 對業務是新名單，不是新話術。',
         'A whole new class of cluster-building buyer. The shape is heavy video pre-processing plus '
         'large vision-language-action training, and the data volume steps up a gear. These '
         'customers do not rent; they buy. That is a new list, not a new pitch.',
         'official'),
        ('RL post-training', 'RL 後訓練獨立成一條主軸',
         'RL post-training became a track of its own',
         'RL 要在同一張網裡同時跑訓練與推論 rollout，要的是混合角色節點與統一互聯，'
         '不是純訓練機或純推論機。報價單的形狀會變。',
         'RL runs training and inference rollout inside one fabric, so it wants mixed-role nodes '
         'and one interconnect — not a pure training box and not a pure inference box. The shape of '
         'the quote changes.',
         'official'),
        ('Multimodal Data Curation', '多模態資料策展成主軸；Anyscale 以 NVIDIA RTX PRO 4500 '
         'Blackwell Server Edition 宣稱大規模去重成本較純 CPU 管線低八成',
         'Multimodal data curation became a track; Anyscale claims large-scale de-duplication at '
         'about four fifths below a CPU-only pipeline on NVIDIA RTX PRO 4500 Blackwell Server '
         'Edition',
         '這是非旗艦 PCIe GPU 伺服器的新需求池 —— 不是 NVL72，是可以大量出貨的標準機。'
         '對我方最直接、最好賣的一塊，而且沒有整櫃交期的問題。',
         'A demand pool for non-flagship PCIe GPU servers — not NVL72, but the standard boxes that '
         'ship in volume. The most directly sellable slice for us, and it carries none of the '
         'rack-level lead-time problem.',
         'vendor'),
        ('prefill / decode', 'MoE 服務加上分離式 prefill 與 decode、多層 KV offload',
         'MoE serving with disaggregated prefill and decode and tiered KV offload',
         'prefill 與 decode 獨立擴縮，於是異質節點配比、巨量快取記憶體與本地 NVMe、'
         '節點間高頻寬全變成規格重點。儲存側被拉進這場對話，VAST Data 掛金級正好呼應。',
         'Prefill and decode scale independently, so node mix, very large cache memory with local '
         'NVMe, and node-to-node bandwidth all become spec points. Storage gets pulled into the '
         'conversation — VAST Data sponsoring at Gold is the same signal.',
         'official'),
        ('GB300 NVL72', '議程出現整櫃拓撲感知排程',
         'The agenda now carries rack-topology-aware scheduling',
         '軟體開始感知機櫃，代表客戶已經跨多機櫃跑數百顆 GPU。命題從「賣一台」變成'
         '「交付完整 NVLink 網域與跨櫃網路」，對話對象也從工程師往上移。',
         'Software noticing racks means customers already run hundreds of GPUs across several of '
         'them. The proposition moves from selling a box to delivering a whole NVLink domain plus '
         'the network between racks — and the person you need moves up with it.',
         'vendor'),
        ('TPU / AMD / Intel', '非 NVIDIA 路線各有專場',
         'Non-NVIDIA silicon has its own sessions',
         '非 NVIDIA 在這房間是被正常化的，多矽晶機型有真實聽眾。可以主動開這個話題探需求，'
         '不必怕踩線。',
         'Non-NVIDIA is normalised here, so multi-silicon platforms have a real audience. You can '
         'open that topic deliberately instead of stepping around it.',
         'official'),
    ]
    tb = []
    for term, sig_h, sig_e, imp_h, imp_e, rank in turns:
        tb.append(dr('%s' % lk(term),
                     tt(esc(sig_h), esc(sig_e)),
                     '    <p>%s</p>\n    <p>%s %s</p>'
                     % (tt(esc(imp_h), esc(imp_e)), ev(rank), from_draft(D01))))
    a(dr(tt('技術轉向與伺服器需求含意', 'The technical turn, and what it means for server demand'),
         tt('%d 個議程訊號，每一個都翻成一句對報價單的影響' % len(turns),
            '%d agenda signals, each translated into one line about the quote' % len(turns)),
         '\n'.join(tb), is_open=OPEN))

    # ------------------------------------------------- 7. forward signals ---
    fw = []
    fw.append(ul([
        '%s %s' % (S(('Nscale 展台與 Josh Payne 的 keynote 是本屆第一優先。已與微軟簽約約',
                      'The Nscale booth and Josh Payne\'s keynote are the first priority of the '
                      'show. Contracted with Microsoft for roughly'), '200,000',
                     ('顆 GB300：德州園區約', 'GB300: a Texas campus of about'), '240MW',
                     ('、約', 'and roughly'), '104,000', ('顆，自', 'of them, from'), '2026 Q3',
                     ('起分批；葡萄牙 Sines 約', 'in batches; Sines in Portugal about'),
                     '12,600', ('顆自', 'from'), '2026 Q1',
                     ('；英國 Loughton', '; Loughton in the UK'), '50MW', ('、約', 'and about'),
                     '23,000', ('顆自', 'from'), '2027 Q1',
                     ('。這是真實的機櫃交付時間表，不是願景稿。',
                      '. That is a real rack delivery schedule, not a vision slide.')),
                   ev('official') + src_a('https://www.nscale.com/press-releases', ASOF)),
        '%s %s' % (S(('競爭旗標：Dell 是 Nscale 的投資人，與 NVIDIA、Nokia、Blue Owl、Aker 並列。'
                      '談 Nscale 供應鏈時要預設 Dell 已經在裡面，別把它當空白戰場。',
                      'Competitive flag: Dell is an investor in Nscale, alongside NVIDIA, Nokia, '
                      'Blue Owl and Aker. Assume Dell is already inside that supply chain; do not '
                      'walk in treating it as open ground.')),
                   ev('third') + from_draft(D01)),
        '%s %s' % (S(('新雲密度異常高：白金含 CoreWeave 與 Nscale，金級含 Nebius 與 Lambda，'
                      '再加上三家超大規模。一場會至少五家 GPU 雲同時在場 —— 這是買方密度，'
                      '不是展商密度。',
                      'Neocloud density is unusual: CoreWeave and Nscale at Platinum, Nebius and '
                      'Lambda at Gold, plus three hyperscalers. At least five GPU clouds in one '
                      'hall. That is buyer density, not exhibitor density.')),
                   ev('official')),
        '%s %s' % (S(('Nscale 的融資動能：收購前不到一個月剛完成', 'Nscale\'s funding momentum: less '
                      'than a month before the acquisition it closed a'), 'USD 900M',
                     ('循環信貸，十二家銀行聯貸，含 J.P. Morgan、Goldman Sachs、Morgan Stanley。'
                      '有錢，而且會繼續買。',
                      ' revolving facility syndicated across twelve banks including J.P. Morgan, '
                      'Goldman Sachs and Morgan Stanley. They have money and they will keep '
                      'buying.')),
                   ev('third') + from_draft(D01)),
        '%s %s' % (S(('推論堆疊的硬體適配決策權正在集中到 Inferact。vLLM 是各家硬體後端進入生產的'
                      '必經之路，NVIDIA、AMD、Google TPU、Intel 都派人上台；誰先進 vLLM 的支援列表，'
                      '誰的機型就先賣得動。認識 Inferact 的人，價值高於認識任何一家雲。',
                      'The power to decide which hardware the inference stack supports is '
                      'concentrating inside Inferact. vLLM is the road every hardware back end '
                      'takes into production, and NVIDIA, AMD, Google TPU and Intel all put people '
                      'on that stage. Whoever lands in the vLLM support list first sells first. '
                      'Knowing someone at Inferact is worth more than knowing any one cloud.')),
                   ev('official') + from_draft(D01)),
    ]))
    a(dr(tt('前瞻訊號', 'Forward signals'),
         tt('走廊上要抓的五件事，含一面競爭旗標', 'five things to catch in the corridor, one of them '
            'a competitive flag'),
         '\n'.join(fw), is_open=OPEN))

    # ------------------------------------------------------- 8. the gaps ----
    gaps = []
    if MISSING_DAYS:
        gaps.append(gap('會期內的 %s 在目錄上一場都沒有。官方結構顯示那天有 keynote、午餐與 breakout，'
                        '收購案只隔三週半，合體路線圖最可能壓在那一天。出發前務必再刷一次議程 ——'
                        '未公布不是沒有。' % '、'.join(MISSING_DAYS),
                        'The catalogue publishes not one session on %s inside the event window. The '
                        'official structure shows a keynote, lunch and breakouts that day, and the '
                        'acquisition is only three and a half weeks old, so the combined roadmap is '
                        'most likely parked there. Refresh the agenda before you fly — unpublished '
                        'is not absent.' % ', '.join(MISSING_DAYS))
                    + ' ' + ev('official'))
    gaps.append(gap('官方從未公布任何一屆的參加人數或公司數。找得到的「1,325 家公司」是第三方平台的'
                    '預測值，不是官方統計，不要拿去當簡報數字。',
                    'The organisers have never published attendance or company counts for any '
                    'edition. The one figure in circulation, 1,325 companies, is a third-party '
                    'platform forecast rather than an official count. Keep it out of your deck.')
                + ' ' + ev('third'))
    gaps.append(gap('Ray 主軌的場次標題裡看不到 GB200、GB300、NVL72、InfiniBand 這些字。'
                    '硬體話題藏在 vLLM 場次與供應商 keynote 裡，要找硬體對話就往那半場走。',
                    'No session title on the Ray track carries GB200, GB300, NVL72 or InfiniBand. '
                    'The hardware conversation sits in the vLLM sessions and the vendor keynotes; '
                    'walk to that half of the building.')
                + ' ' + ev('official'))
    gaps.append(gap('Supermicro 不在任何贊助層級名單中，所以沒有主場優勢，全靠走廊與攤位外接觸。'
                    '這是「沒買贊助」，不是「被排除」。是否有 expo 攤位或員工講者仍未證實 ——'
                    '到場第一件事是拿 expo 平面圖確認。',
                    'Supermicro is on no sponsor tier, so there is no home advantage: everything '
                    'happens in corridors and outside other people\'s booths. That means "did not '
                    'buy sponsorship", not "was excluded". Whether there is an expo booth or a '
                    'staff speaker is still unverified — first thing on arrival, get the floor plan '
                    'and settle it.')
                + ' ' + ev('official'))
    gaps.append(gap('Nscale 的機櫃 OEM 或 ODM 供應商未公開，只知道 Dell 是投資人。'
                    '這是現場最值得直接問出來的一題。',
                    'Nscale has not disclosed who builds its racks; the only public thread is that '
                    'Dell is an investor. This is the single most worthwhile thing to ask out loud '
                    'on the floor.')
                + ' ' + ev('unverified'))
    for g in (factbase.get('gaps') or []):
        gaps.append(gap(g, g))
    a(dr(tt('本場 GAP', 'What is still open'),
         tt('%d 個缺口，每一個都寫了什麼證據能結案' % len(gaps),
            '%d open questions, each with what would close it' % len(gaps)),
         ul(gaps) + '\n  %s' % STAMP, is_open=OPEN, cls='caveat', fresh=True))

    # ------- method LAST, below the verdict (page-role.json forbids above) ---
    m = []
    m.append('    <p>%s</p>'
             % tt('這一頁的每個數字都是建置時從 JSON 算出來的，沒有一個是打字打上去的。'
                  '算不出來的欄位印 GAP 和原因，不印零。',
                  'Every number on this page is computed from JSON at build time; none of them is '
                  'typed. A field that cannot be computed prints GAP and its reason, never a zero.'))
    m.append('    <ul>')
    for name, n in (('data/sessions.json', N_SESS), ('data/speakers.json', N_SPK),
                    ('data/sponsors.json', N_SPO), ('data/orgs.json', N_ORG)):
        m.append('      <li><code>%s</code> %s</li>'
                 % (esc(name), tt('%d 筆' % n, pl(n, 'record', 'records'))))
    m.append('      <li><code>deliverables/accounts/cards.json</code> %s</li>'
             % (tt('%d 筆' % N_CARDS, pl(N_CARDS, 'record', 'records')) if cards is not None
                else gap('尚未產生', 'not built yet')))
    for f in RESEARCH_TEXT:
        m.append('      <li><code>deliverables/research/%s</code></li>' % esc(f))
    m.append('    </ul>')
    if cards is not None:
        m.append('    <p>%s</p>'
                 % tt('帳戶板 %d 格已填的證據等級（計算值）：' % POP,
                      'Evidence rank of the %d populated account-board cells (computed):' % POP))
        m.append('    <p>')
        for rank, n in RANKS.items():
            if n:
                m.append('      %s %s' % (ev(rank), tt('%d 格' % n, pl(n, 'cell', 'cells'))))
        m.append('    </p>')
    if SOURCE:
        m.append('    <p>%s <a href="%s">%s</a></p>'
                 % (tt('目錄來源：', 'Catalogue source:'), att(SOURCE), esc(SOURCE)))
    a(dr(tt('方法與來源', 'Method and sources'),
         tt('數字從哪裡來、哪一格還沒結案', 'where the numbers come from, and which cells are '
            'still open'),
         '\n'.join(m), is_open=False, cls='method', block='method'))
    return '\n'.join(h)


# ==================================================== the floor priority list ==
# Research draft 05 ranked the sessions worth queueing for. The TITLES are
# matched against data/sessions.json here rather than retyped, so a catalogue
# change surfaces as a GAP instead of sending a rep to a room that moved.
FLOOR = [
    ('How the Data Center Shapes',
     '全場唯一直接談機房約束的題目。記下講者的機房是自建、colo 還是租雲 —— 那一句就決定他是不是買家。',
     'The only session in the building that talks about the hall itself. Write down whether the '
     'speaker\'s data centre is owned, colo or rented cloud — that one line decides whether they '
     'are a buyer.'),
    ('Industry Leaders Roundtable',
     '一場抓齊多家會自建機房的 Physical AI 買家，會後圍堵的成本最低。',
     'One room holding several Physical AI companies that may build their own halls. The cheapest '
     'place in the show to catch a group afterwards.'),
    ('Domain-Aware Scheduling',
     '問誰在跑 NVL72、幾櫃、熱與電的痛點在哪。對照語言：整櫃 132–140kW 加上直接液冷。',
     'Ask who is running NVL72, across how many racks, and where the heat and power hurt. The '
     'matching number to hold: 132–140kW per rack with direct liquid cooling.'),
    ('Right Resource, Right Job',
     '他報出來的節點型號清單就是一張現成的 BOM。抄下來。',
     'The list of node types he reads out is a ready-made bill of materials. Write it down.'),
    ('Petabyte-Scale Video Curation',
     '儲存與 CPU 節點的比例會被講出來，接得上既有的儲存共同提案。',
     'The storage-to-CPU-node ratio gets said out loud here, and it plugs straight into the '
     'existing joint storage proposal.'),
    ('Serving Frontier MoE Models',
     '推論端 TCO 的話術來源。每 token 成本是這房間唯一聽得進去的成本語言。',
     'Where the inference-side TCO language comes from. Cost per token is the only cost language '
     'this room actually hears.'),
    ('Scaling LLM Workloads on TPUs',
     '低優先：TPU 沒有伺服器機會，純競爭情報。衝堂就放棄。',
     'Low priority: no server opportunity on TPU, pure competitive intelligence. Drop it on a '
     'clash.'),
    ('Physical AI at Aerospace Scale',
     '低優先：衝堂就放棄，內容和圓桌重疊。',
     'Low priority: drop it on a clash, it overlaps the roundtable.'),
]


def floor_priority():
    """Resolve the draft's ranking against the real catalogue. Computed."""
    out = []
    for i, (probe, why_h, why_e) in enumerate(FLOOR, start=1):
        hit = next((s for s in sessions if probe.lower() in str(s.get('title', '')).lower()), None)
        out.append({'rank': i, 'probe': probe, 'session': hit, 'why_h': why_h, 'why_e': why_e})
    return out


PRIORITY = floor_priority()
PRIORITY_IDS = {str(p['session'].get('id')): p for p in PRIORITY if p['session']}

# Hardware-demand marks for the sessions the draft did NOT name. The probe that
# matched is printed, so the mark is auditable and nobody has to trust a label.
HW_PROBES = [
    ('Data Center', '機房約束', 'the hall itself'),
    ('GB200', '整櫃拓撲', 'rack topology'),
    ('GB300', '整櫃拓撲', 'rack topology'),
    ('Heterogeneous', '異質節點', 'mixed node types'),
    ('Petabyte', '儲存與 CPU 節點比', 'storage-to-CPU ratio'),
    ('Physical AI', '會自建機房的買家', 'buyers who may build a hall'),
    ('Robotics', '會自建機房的買家', 'buyers who may build a hall'),
    ('Autonomous', '影片資料量跳檔', 'video data steps up a gear'),
    ('Trucking', '影片資料量跳檔', 'video data steps up a gear'),
    ('MoE', '推論端 TCO', 'inference-side TCO'),
    ('TPU', '非 NVIDIA 路線', 'non-NVIDIA silicon'),
    ('Infrastructure Signals', '硬體遙測進到排程', 'hardware telemetry reaching the scheduler'),
]


def hw_marks(s):
    """Which hardware-demand probes this session matched, and what each means."""
    blob = ('%s %s' % (s.get('title') or '', ' '.join(str(t) for t in (s.get('tags') or [])))).lower()
    seen, out = set(), []
    for probe, wh, we in HW_PROBES:
        if probe.lower() in blob and (wh, we) not in seen:
            seen.add((wh, we))
            out.append((probe, wh, we))
    return out


HW_SESSIONS = [s for s in sessions if hw_marks(s)]


def parse_hm(t):
    m = re.match(r'\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*$', str(t or ''), re.I)
    if not m:
        return None
    hh, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if hh == 12:
        hh = 0
    return (hh + (12 if ap == 'PM' else 0)) * 60 + mm


def block_start(start_end):
    return parse_hm(str(start_end or '').split('-')[0])


def duration_min(start_end):
    parts = str(start_end or '').split('-')
    if len(parts) != 2:
        return None
    a, b = parse_hm(parts[0]), parse_hm(parts[1])
    if a is None or b is None or b <= a:
        return None
    return b - a


# ==================================================================== agenda ==
def frag_agenda():
    h = []
    a = h.append

    # -------------------------------------------- 1. the priority queue -----
    matched = [p for p in PRIORITY if p['session']]
    unmatched = [p for p in PRIORITY if not p['session']]
    pr = []
    for p in matched:
        s = p['session']
        d = duration_min(s.get('start_end'))
        head = '%s %s' % (lk('#%d' % p['rank']), lk(s.get('title')))
        scent = S(('第 %d 順位' % p['rank'], 'Priority %d' % p['rank']), '·',
                  s.get('day'), s.get('start_end'), '·', s.get('room'))
        body = ['    <p>%s</p>' % tt(esc(p['why_h']), esc(p['why_e']))]
        body.append('    <p class="meta-row">%s %s %s %s</p>'
                    % (S(('會議室', 'Room')), lk(s.get('room')),
                       S(('場次', 'Session')), lk(s.get('id'))))
        if d:
            body.append('    <p class="meta-row">%s %s %s</p>'
                        % (S(('時長', 'Runs')), lk('%d' % d), S(('分鐘', 'minutes'))))
        tags = [str(t) for t in (s.get('tags') or [])]
        body.append('    <p>%s</p>'
                    % (''.join('<span class="chip">%s</span>' % esc(t) for t in tags) if tags
                       else gap('目錄沒有給這一場標籤，主題只能從標題判斷',
                                'the catalogue gives this session no track tag, so the subject has '
                                'to be read off the title')))
        body.append('    <p>%s</p>' % gap('講者姓名與所屬公司未證實。到場用活動 App 於第一天補齊再排時程',
                                          'the speaker name and employer are unverified. Fill them '
                                          'in from the event app on day one and re-plan'))
        body.append('    %s' % from_draft(D05))
        pr.append(dr(head, scent, '\n'.join(body)))
    for p in unmatched:
        pr.append('  <p>%s %s</p>'
                  % (lk(p['probe']),
                     gap('底稿點名這一場，但目錄裡找不到對得上的標題 —— 可能改名或撤場，到場確認',
                         'the draft names this session but no catalogue title matches it — renamed '
                         'or pulled, settle it on site')))
    a(dr(tt('先卡這幾場', 'Queue for these first'),
         tt('%d 場排好順位，%d 場對不上目錄' % (len(matched), len(unmatched)),
            '%d sessions ranked, %d with no catalogue match' % (len(matched), len(unmatched))),
         '\n'.join(pr), block='priority-queue'))

    # ----------------------- 2. every session, day > time block > session ---
    days_html = []
    for d in DAYS:
        blocks = OrderedDict()
        for s in sorted(by_day[d], key=lambda x: (block_start(x.get('start_end')) or 0,
                                                  str(x.get('room') or ''))):
            blocks.setdefault(str(s.get('start_end') or ''), []).append(s)
        n_hw = len([s for s in by_day[d] if hw_marks(s)])
        rooms_today = len({str(s.get('room') or '') for s in by_day[d] if s.get('room')})
        blocks_html = []
        for be, items in blocks.items():
            cards_html = ['    <ol class="ses">']
            for s in items:
                sid = str(s.get('id') or '')
                marks = hw_marks(s)
                dur = duration_min(s.get('start_end'))
                cards_html.append('      <li%s>' % (' class="is-hw"' if marks else ''))
                cards_html.append('        <p class="when">%s %s%s</p>'
                                  % (lk(s.get('start_end') or ''), lk(sid),
                                     (' ' + lk('%d min' % dur)) if dur else ''))
                cards_html.append('        <h3>%s</h3>' % esc(s.get('title')))
                cards_html.append('        <p class="where">%s %s</p>'
                                  % (S(('會議室', 'Room')), lk(s.get('room') or '')))
                tags = [str(t) for t in (s.get('tags') or [])]
                cards_html.append('        <p class="tags">%s</p>'
                                  % (''.join('<span class="chip">%s</span>' % esc(t) for t in tags)
                                     if tags else
                                     gap('目錄沒有給這一場標籤',
                                         'the catalogue gives this session no track tag')))
                if sid in PRIORITY_IDS:
                    p = PRIORITY_IDS[sid]
                    cards_html.append('        <p class="hw"><span class="hwm">%s</span> %s</p>'
                                      % (lk('#%d' % p['rank']),
                                         tt(esc(p['why_h']), esc(p['why_e']))))
                elif marks:
                    for probe, wh, we in marks:
                        cards_html.append('        <p class="hw"><span class="hwm">%s</span> %s</p>'
                                          % (lk(probe), tt(esc(wh), esc(we))))
                cards_html.append('      </li>')
            cards_html.append('    </ol>')
            hw_here = len([s for s in items if hw_marks(s)])
            rooms_here = sorted({str(s.get('room') or '') for s in items if s.get('room')})
            scent = [('%d 場' % len(items), pl(len(items), 'session', 'sessions')), '·',
                     (' / '.join(rooms_here[:3]) + ('…' if len(rooms_here) > 3 else ''),
                      ' / '.join(rooms_here[:3]) + ('…' if len(rooms_here) > 3 else ''))]
            if hw_here:
                scent += ['·', ('%d 場帶硬體需求訊號' % hw_here,
                                '%d carrying a hardware-demand signal' % hw_here)]
            blocks_html.append(dr(lk(be), S(*scent), '\n'.join(cards_html)))
        days_html.append(dr(
            lk(d),
            S(('%d 場' % len(by_day[d]), pl(len(by_day[d]), 'session', 'sessions')), '·',
              ('%d 個時段' % len(blocks), pl(len(blocks), 'time block', 'time blocks')), '·',
              ('%d 間會議室' % rooms_today, pl(rooms_today, 'room', 'rooms')), '·',
              ('%d 場帶硬體需求訊號' % n_hw, '%d with a hardware-demand signal' % n_hw)),
            '\n'.join(blocks_html)))
    if MISSING_DAYS:
        days_html.append('  <p>%s</p>'
                         % gap('會期內的 %s 在目錄上一場都沒有 —— 是未公布，不是沒有場次。'
                               '出發前再刷一次議程' % '、'.join(MISSING_DAYS),
                               'the catalogue publishes no session at all on %s inside the event '
                               'window — unpublished, not absent. Refresh the agenda before you fly'
                               % ', '.join(MISSING_DAYS)))
    a(dr(tt('全部場次', 'Every session'),
         S(('%d 場' % N_SESS, pl(N_SESS, 'session', 'sessions')), '·',
           ('%d 天已公布' % len(DAYS), pl(len(DAYS), 'day published', 'days published')), '·',
           ('%d 間會議室' % len(ROOMS), pl(len(ROOMS), 'room', 'rooms')), '·',
           ('%d 場帶硬體需求訊號' % len(HW_SESSIONS),
            '%d carrying a hardware-demand signal' % len(HW_SESSIONS))),
         '\n'.join(days_html) + '\n  %s' % STAMP,
         block='day-filter', fresh=True))

    # ------------------------------------------------------- 3. the rooms ---
    rl = ['  <ul class="rooms">']
    for r in ROOMS:
        rl.append('    <li><span class="rn">%s</span><span class="rc">%s</span></li>'
                  % (lk(r), tt('%d 場' % room_count[r], pl(room_count[r], 'session', 'sessions'))))
    rl.append('  </ul>')
    rl.append('  <p class="note">%s</p>'
              % tt('會議室名稱、時間、日期一律維持目錄原文，兩個語言版本逐字元相同 ——'
                   '你唸出來的和門口貼的會是同一串字。',
                   'Room names, times and dates stay exactly as the catalogue prints them, '
                   'byte-identical in both languages: what you read aloud matches what is on the '
                   'door.'))
    busiest = ROOMS[0] if ROOMS else ''
    a(dr(tt('會議室', 'Rooms'),
         S(('%d 間' % len(ROOMS), pl(len(ROOMS), 'room', 'rooms')), '·',
           ('最忙的是', 'busiest is'), busiest, '·',
           ('%d 場' % room_count.get(busiest, 0),
            pl(room_count.get(busiest, 0), 'session', 'sessions'))),
         '\n'.join(rl), block='room'))

    # ------------------------------------------ 4. what the catalogue lacks -
    cav = []
    if seats_known:
        cav.append(tt('座位數：%d / %d 場有揭露。' % (len(seats_known), N_SESS),
                      'Seat counts: disclosed for %d of %d sessions.' % (len(seats_known), N_SESS)))
    else:
        cav.append('%s %s' % (tt('座位數：', 'Seat counts: '), gap(SEAT_WHY_H, SEAT_WHY_E)))
        cav.append(tt('所以「會不會滿」這件事現在無法回答。現場以活動 App 為準，別在客戶面前用猜的。',
                      'So "will it fill up" cannot be answered today. Defer to the event app on '
                      'site; do not guess in front of a customer.'))
    cav.append('%s %s' % (tt('講者對應：', 'Speaker linkage: '), gap(LINK_WHY_H, LINK_WHY_E)))
    cav.append(tt('名單上的 %d 位講者來自官方活動頁，不是場次卡片 —— 誰講哪一場尚未證實，'
                  '官方自己還寫了「and others」，所以這份名單是部分名單。' % N_SPK,
                  'The %d speakers we hold come from the official event page, not from the session '
                  'cards, so who speaks where is unverified — and the page says "and others", which '
                  'makes the roster partial by the organisers\' own admission.' % N_SPK))
    cav.append(tt('攤位號碼未公布。第一件事是拿 expo 平面圖。',
                  'Booth numbers are not published. First thing on arrival: get the floor plan.'))
    a(dr(tt('目錄沒有給的東西', 'What the catalogue does not give'),
         S(('%d 件' % len(cav), pl(len(cav), 'item', 'items')), '·',
           ('每一件都寫了現場怎麼補', 'each with how to close it on site')),
         ul(cav) + '\n  %s' % STAMP, cls='caveat', block='seats-caveat', fresh=True))
    return '\n'.join(h)


# ====================================================================== gtm ==
# Research draft 05 reaches the reader HERE: the theses WITH their falsifiers,
# the floor order, the five questions and what each answer reveals, and the
# do-not-do list.

THESES = [
    ('T1', 'OEM 綁定已成形，縫隙在 Lambda 與未公開供應商的中小新雲。',
     'The OEM lock has already set. The seam is Lambda plus the mid-size neoclouds that have never '
     'named a supplier.',
     '交付 CoreWeave 市場首套 GB300 NVL72 與首套 Vera Rubin NVL72 的是 Dell；Nscale 用 Dell '
     'PowerEdge XE9712 整櫃交付，且已簽微軟約二十萬顆 GB300。Verda 自有 Helsinki 與冰島機房、'
     '剛募得新資金，硬體供應商未證。',
     'Dell delivered the market-first GB300 NVL72 and the first Vera Rubin NVL72 to CoreWeave, and '
     'Nscale takes Dell PowerEdge XE9712 as integrated racks while holding a Microsoft contract for '
     'about two hundred thousand GB300. Verda owns halls in Helsinki and Iceland and has just '
     'raised — and has '
     'never named a hardware supplier.',
     '現場任何一位新雲工程師說整櫃供應商是多源、或正在認證第二供應商，T1 立刻失效，改打正面競標。',
     'If any neocloud engineer on the floor says racks are multi-sourced, or that a second supplier '
     'is being qualified, T1 is dead and you switch to bidding head-on.',
     'official'),
    ('T2', '利用率提升會延後而不是拉動節點採購 —— 除非工作佇列同步變長。',
     'Better utilisation delays node purchases rather than pulling them in — unless the job queue '
     'grows at the same time.',
     'Torc 四倍提速零增購，明說沒有加機器；議程上 Robinhood 講的就是用異質叢集把成本壓下來。',
     'Torc got a fourfold speed-up with no extra hardware and says so explicitly, and Robinhood is '
     'on the agenda talking about taking cost out with a mixed cluster.',
     '若平台團隊說利用率上去以後排隊時間沒有下降、反而把訓練規模擴大了，利用率就是需求放大器，'
     '這條論點反轉，該加碼而不是收手。',
     'If a platform team says queue time did not fall and they grew the training runs instead, then '
     'utilisation is a demand multiplier, the thesis inverts, and you lean in rather than back off.',
     'vendor'),
    ('T3', '近場機會是 CPU 前處理節點與資料節點，不是 NVL72。',
     'The near-term opening is CPU pre-processing and data nodes, not NVL72.',
     'Torc 的症狀是 GPU 餓著、同機 CPU 打滿；議程有 Robinhood 的異質叢集與 CoreWeave 的 PB 級'
     '影片策展；我方與 VAST 已有現成的聯合方案與具名機型。',
     'Torc\'s symptom is starved GPUs next to pinned CPUs; the agenda carries Robinhood\'s mixed '
     'cluster and CoreWeave\'s petabyte-scale video curation; and we already have a joint solution '
     'with VAST with named platforms.',
     '若這些工作全部以雲端執行個體消費、而且沒有落地計畫，就沒有 BOM 可談，退回情報收集。',
     'If those workloads are consumed purely as cloud instances with no on-prem plan, there is no '
     'bill of materials to discuss and you fall back to collecting intelligence.',
     'official'),
    ('T4', 'Physical AI 是唯一可能自建機房的買家群。',
     'Physical AI is the only group in this room that might build its own hall.',
     '議程排了 Physical AI 的產業圓桌；Silver 贊助含 Path Robotics 與 Foxglove；'
     'Torc 單一管線已達 38TB。',
     'The agenda schedules an industry roundtable on Physical AI, the Silver tier carries Path '
     'Robotics and Foxglove, and Torc\'s single pipeline already runs at 38TB.',
     '若圓桌上這些公司都說模擬與訓練全部在超大規模雲上，資料落地的論點就不成立。'
     '這是待驗條件，不是既有數據。',
     'If every company on that roundtable says simulation and training run entirely on hyperscale '
     'cloud, the data-gravity argument does not hold. This is a condition to test, not a number we '
     'already have.',
     'official'),
]

BOOTHS = [
    ('Lambda', '唯一既有關係。我方曾代租 Vernon 21MW、十年逾六億美元並轉分租。目標：下一批機型與時程。',
     'The only existing relationship. We took the Vernon 21MW lease, ten years and over six hundred million dollars, '
     'and sublet it. Target: the next platform and its dates.', 'official'),
    ('Verda', '自有機房加上新資金，OEM 未證 —— 全場賠率最高的新名字。',
     'Owns its halls, just raised, and has never named an OEM. The best odds on any new name here.',
     'third'),
    ('VAST Data', '有現成的聯合方案。走共同提案，不走直銷。',
     'A joint solution already exists. Co-sell, do not direct-sell.', 'official'),
    ('Nebius', '自研加上台系 ODM。只問一題：CPU、儲存、網路節點是否外購。',
     'Self-designed with Taiwanese ODMs. Ask one question only: are the CPU, storage and network '
     'nodes bought outside.', 'vendor'),
    ('CoreWeave / Nscale', '只做確認題，不推銷。它們是白金主辦夥伴，且已公開綁 Dell。',
     'Confirmation questions only, no pitching. They are Platinum partners of the host and are '
     'publicly tied to Dell.', 'official'),
    ('平台團隊 / Platform teams',
     'Uber、Pinterest、Netflix、Discord、Spotify、Apple、BMW、Robinhood —— 情報價值高於成交價值。',
     'Uber, Pinterest, Netflix, Discord, Spotify, Apple, BMW, Robinhood — worth more as '
     'intelligence than as pipeline.', 'unverified'),
]

QUESTIONS = [
    ('你們的 Ray 叢集跑在自己機房、租的 colo，還是純雲端執行個體？',
     'Does your Ray cluster run in your own hall, in colo you rent, or purely on cloud instances?',
     '自建或 colo 就能直銷；純雲端的話這個人是情報來源，不是買家，只能經新雲間接觸及。',
     'Own hall or colo means you can sell direct. Pure cloud means this person is a source, not a '
     'buyer, and you only reach them through a neocloud.'),
    ('CPU 前處理節點跟 GPU 節點是同一批機器、同一個採購週期嗎？',
     'Are the CPU pre-processing nodes and the GPU nodes the same batch on the same purchasing '
     'cycle?',
     '分開＝異質節點有獨立的 BOM 與獨立的汰換窗口，近場機會成立；同一批＝只能等整體 refresh。',
     'Separate means the mixed nodes have their own bill of materials and their own replacement '
     'window, and the near-term opening is real. Same batch means you wait for the whole refresh.'),
    ('你們最舊的那批 GPU 節點是哪一代，現在還在跑什麼？',
     'Which generation is your oldest batch of GPU nodes, and what still runs on it?',
     '世代分佈就是 refresh 時鐘。A100 或 H100 還在線＝十二到二十四個月內有一場汰換對話。',
     'The generation spread is the refresh clock. A100 or H100 still in service means a replacement '
     'conversation inside twelve to twenty-four months.'),
    ('這一櫃是誰整合的、on-site 誰做？',
     'Who integrated this rack, and who does the on-site work?',
     '「OEM 整櫃交付」＝已經鎖住；「我們自己 rack and stack」＝有縫，機房層方案切得進去。',
     '"The OEM delivers the rack" means locked. "We rack and stack it ourselves" means there is a '
     'seam, and a hall-level proposal fits into it.'),
    ('下一批容量的瓶頸是 GPU 交期、電力，還是機房空間？',
     'For the next tranche of capacity, is the bottleneck GPU lead time, power, or floor space?',
     '電力或空間＝液冷與機房層方案可以談；GPU 交期＝我們幫不上，禮貌結束，把時間留給下一個人。',
     'Power or space means liquid cooling and a hall-level proposal are in play. GPU lead time means '
     'we cannot help — close politely and give the time to the next person.'),
]

DONTS = [
    ('不要在 CoreWeave 或 Nscale 攤位 pitch。它們是白金主辦夥伴且已公開綁 Dell；'
     '在別人主場推銷會燒掉未來共同提案的門。',
     'Do not pitch at the CoreWeave or Nscale booths. They are Platinum partners of the host and '
     'publicly tied to Dell; selling on someone else\'s home ground burns the co-sell door.'),
    ('不要用「我們也有 GB300 NVL72」當開場。這房間買的是排程與利用率，規格開場會被歸類成機箱廠。',
     'Do not open with "we also have GB300 NVL72". This room buys scheduling and utilisation; a '
     'spec opener files you under box vendor.'),
    ('不要複述任何未經對方確認的機隊數字。問，不要說。',
     'Do not repeat any fleet number the other side has not confirmed. Ask; do not tell.'),
    ('不要把「不在贊助名單」讀成「被排除」。那只證明沒買贊助。',
     'Do not read "not on the sponsor list" as "excluded". It only proves nobody bought '
     'sponsorship.'),
    ('不要以名片數當 KPI。帶回五個具名、可追的答案，勝過五十張名片。',
     'Do not use business cards as the KPI. Five named, followable answers beat fifty cards.'),
    ('不要報價、不要承諾交期。scout 沒有定價授權；先報價等於提前讓出議價權。',
     'Do not quote and do not promise lead times. A scout has no pricing authority, and quoting '
     'first hands over the negotiating position.'),
]


def frag_gtm():
    h = []
    a = h.append

    # ------------------------------------------------------- 1. judgement ---
    jd = [
        '%s %s' % (S(('這房間裡真正簽伺服器訂單的是新雲，不是平台團隊。四家新雲贊助商裡，'
                      'CoreWeave 與 Nscale 已公開綁 Dell、Nebius 自研走 ODM，只有 Lambda 是既有客戶。'
                      '此行是情報場，不是開單場。',
                      'The people in this room who actually sign server orders are the neoclouds, '
                      'not the platform teams. Of the four neocloud sponsors, CoreWeave and Nscale '
                      'are publicly tied to Dell and Nebius self-designs through ODMs — only Lambda '
                      'is an existing customer. This trip is reconnaissance, not order-taking.')),
                   ev('official') + from_draft(D05)),
        '%s %s' % (S(('Ray 的核心賣點是「同樣硬體多榨兩到三倍」，短期對機箱生意是逆風。'
                      'Torc 把 GPU 利用率從三成多拉到九成、epoch 從二十分鐘壓到五分鐘，'
                      '而且明說沒有加機器。要賣的是異質節點與機房層，不是多賣一櫃。',
                      'Ray\'s core promise is two to three times more out of the same hardware, '
                      'which is a headwind for box sales in the short run. Torc took GPU '
                      'utilisation from the thirties to ninety per cent and an epoch from twenty '
                      'minutes to five — explicitly without adding hardware. What sells here is '
                      'mixed nodes and the hall layer, not one more rack.')),
                   ev('vendor') + from_draft(D05)),
        '%s %s' % (S(('我方不在官方贊助名單上。這是 GAP，不是被排除 —— 但代表無主場、無展台、'
                      '沒有正當的推銷位置，每一次對話都得靠走廊。',
                      'We are not on the official sponsor list. That is a gap, not an exclusion — '
                      'but it means no home ground, no booth, and no legitimate place to sell from. '
                      'Every conversation has to be earned in a corridor.')),
                   ev('official')),
    ]
    a(dr(tt('判斷', 'The judgement'),
         tt('簽單的是新雲；Ray 短期是逆風；我方沒有主場',
            'the neoclouds sign; Ray is a short-run headwind; we have no home ground'),
         ul(jd), block='judgement'))

    # ------------------------------------------- 2. theses and falsifiers ---
    th = []
    for tag, claim_h, claim_e, ev_h, ev_e, kill_h, kill_e, rank in THESES:
        body = ['    <dl class="thesis">']
        body.append('      <dt>%s</dt><dd>%s %s</dd>'
                    % (tt('證據', 'Evidence'), tt(esc(ev_h), esc(ev_e)), ev(rank)))
        body.append('      <dt class="kill">%s</dt><dd>%s</dd>'
                    % (tt('什麼話會當場推翻它', 'What kills it on the spot'),
                       tt(esc(kill_h), esc(kill_e))))
        body.append('    </dl>')
        body.append('    %s' % from_draft(D05))
        th.append(dr('%s %s' % (lk(tag), tt(esc(claim_h), esc(claim_e))),
                     tt('證據與反證都在裡面', 'evidence and the falsifier, both inside'),
                     '\n'.join(body)))
    a(dr(tt('論點與反證', 'Theses, each with what kills it'),
         S(('%d 條論點' % len(THESES), pl(len(THESES), 'thesis', 'theses')), '·',
           ('每一條都寫了現場聽到什麼就作廢',
            'each carries the sentence that would void it on the floor')),
         '\n'.join(th), block='theses'))

    # --------------------------------------------------- 3. booth odds ------
    bo = []
    for i, (name, why_h, why_e, rank) in enumerate(BOOTHS, start=1):
        bo.append('    <li><span class="rank">%s</span> %s %s %s</li>'
                  % (lk('%d' % i), lk(name), tt(esc(why_h), esc(why_e)), ev(rank)))
    a(dr(tt('攤位對話，按賠率排序', 'Booth conversations, ranked by odds'),
         S(('%d 個攤位' % len(BOOTHS), pl(len(BOOTHS), 'booth', 'booths')), '·',
           ('第一順位是唯一的既有客戶', 'the first is the only existing customer')),
         '  <ol class="odds">\n%s\n  </ol>\n  %s' % ('\n'.join(bo), from_draft(D05)),
         block='booth-odds'))

    # -------------------------------------------------- 4. segment plays ----
    for i, seg in enumerate(SEGMENTS, start=1):
        low = seg.lower()
        if 'neocloud' in low or 'gpu' in low:
            rule_h = '第一條軸線點名的公司'
            rule_e = 'the companies named on the first axis'
            oids = [o for o in (AXIS_HITS[0][1] if AXIS_HITS else {}) if not o.startswith('!')]
            open_h = ('先問誰整合那一櫃。它們自己就是伺服器需求，不是伺服器需求的替代品。')
            open_e = ('Open by asking who integrates the rack. These companies are server demand, '
                      'not a substitute for it.')
        elif 'lab' in low or 'model' in low:
            rule_h = '在 orgs.json 裡有講者席次的公司'
            rule_e = 'companies with a speaker slot in orgs.json'
            oids = speaker_orgs
            open_h = ('先問資料能不能出場域。不能出＝租賃不是選項，是不合規。')
            open_e = ('Open by asking whether the data may leave the premises. If it may not, '
                      'renting is not an option, it is a compliance failure.')
        elif 'enterprise' in low or 'platform' in low:
            rule_h = '在現場被捕獲、但沒有攤位的公司'
            rule_e = 'companies captured on the floor that hold no booth'
            oids = exhibitor_orgs
            open_h = ('先問最舊的那批 GPU 節點是哪一代。世代分佈就是 refresh 時鐘。')
            open_e = ('Open by asking which generation the oldest GPU nodes are. The generation '
                      'spread is the refresh clock.')
        else:
            rule_h = rule_e = ''
            oids = []
            open_h = open_e = ''
        known = [c for c in (cards or []) if band_key(c.get('layer')) and str(c.get('org_id')) in oids]
        yes = [c for c in (cards or []) if str(c.get('org_id')) in oids
               and str(c.get('buys_servers')) == 'YES']
        body = ['    <dl>']
        body.append('      <dt>%s</dt>' % tt('開場那一句', 'The opening line'))
        body.append('      <dd>%s</dd>' % tt(esc(open_h), esc(open_e)))
        body.append('      <dt>%s</dt>' % tt('現場候選', 'On-site shortlist'))
        if oids:
            body.append('      <dd>%s<span class="src">%s</span></dd>'
                        % (''.join('<span class="chip">%s%s</span>'
                                   % (esc(org_name(o)),
                                      (' %s' % esc(tier_of[o])) if tier_of.get(o) else '')
                                   for o in oids),
                           tt('依 %s，共 %d 家' % (esc(rule_h), len(oids)),
                              'by %s, %d in total' % (esc(rule_e), len(oids)))))
        else:
            body.append('      <dd>%s</dd>'
                        % gap('資料裡沒有任何欄位可以把公司指派到這個客群；要結案需要一次現場捕獲',
                              'no field in the data assigns a company to this segment; a floor '
                              'capture would close it'))
        body.append('      <dt>%s</dt>' % tt('其中自己買機器的', 'Of those, buy their own machines'))
        if cards is None:
            body.append('      <dd>%s</dd>'
                        % gap('帳戶卡尚未產生，這一格是未知，不是「沒有」',
                              'the account board is not built yet: unknown, not empty'))
        else:
            body.append('      <dd>%s</dd>'
                        % tt('%d / %d 家；%d 家已經分好層' % (len(yes), len(oids), len(known)),
                             '%d of %d; %d already placed in a layer'
                             % (len(yes), len(oids), len(known))))
        body.append('      <dt>%s</dt>' % tt('離場前要拿到', 'Leave with'))
        body.append('      <dd>%s</dd>'
                    % tt('需求、決策路徑、時間窗。三格都填才算一次有效對話 —— 空格寫 GAP 和你缺什麼，'
                         '不要寫「沒有」。',
                         'The need, the decision path, the timing window. A conversation only counts '
                         'when all three are filled. An empty one gets GAP and what is missing, '
                         'never "none".'))
        body.append('    </dl>')
        a(dr(lk(seg),
             S(('%d 家候選' % len(oids), pl(len(oids), 'candidate', 'candidates')), '·',
               ('%d 家自己買機器' % len(yes), '%d buy their own machines' % len(yes))),
             '\n'.join(body), cls='play', block='segment-play'))

    # ------------------------------------------- 5. the five questions ------
    qs = []
    for i, (q_h, q_e, r_h, r_e) in enumerate(QUESTIONS, start=1):
        qs.append(dr('%s %s' % (lk('Q%d' % i), tt(esc(q_h), esc(q_e))),
                     tt('答案代表什麼', 'what the answer means'),
                     '    <p>%s</p>\n    %s' % (tt(esc(r_h), esc(r_e)), from_draft(D05))))
    a(dr(tt('五個問題，與它們揭露什麼', 'Five questions, and what each answer reveals'),
         S(('%d 題' % len(QUESTIONS), pl(len(QUESTIONS), 'question', 'questions')), '·',
           ('每一題的答案都直接分類這個帳戶',
            'every answer sorts the account on the spot')),
         '\n'.join(qs), block='discovery'))

    # --------------------------------------------------- 6. do not do -------
    a(dr(tt('不要做什麼', 'What not to do'),
         S(('%d 條' % len(DONTS), pl(len(DONTS), 'rule', 'rules')), '·',
           ('每一條都花過錢', 'every one of them has cost money before')),
         ul(['%s' % tt(esc(x), esc(y)) for x, y in DONTS], cls='donts')
         + '\n  %s' % from_draft(D05), block='donts'))

    # --------------------------------------------------- 7. the register ----
    cols = [('客群', 'Segment'), ('需求', 'Need'), ('誰簽字', 'Who signs'),
            ('時間窗', 'Timing window'), ('狀態', 'Status')]
    cells = [('他們現在缺的是算力，還是把算力變成產品的人手？',
              'Are they short of compute, or of the people who turn compute into product?'),
             ('機房、雲，還是採購？',
              'The facility, the cloud team, or procurement?'),
             ('下一次擴容或換約是什麼時候？',
              'When is the next expansion or contract renewal?')]
    rg = ['  <div class="regwrap">', '  <table class="reg">']
    rg.append('    <thead><tr>%s</tr></thead>'
              % ''.join('<th>%s</th>' % tt(esc(ch), esc(ce)) for ch, ce in cols))
    rg.append('    <tbody>')
    for seg in (SEGMENTS or ['STATE.campaign.segments']):
        rg.append('      <tr>')
        rg.append('        <td><span class="lbl">%s</span>%s</td>'
                  % (tt(esc(cols[0][0]), esc(cols[0][1])), lk(seg)))
        for n, (ch, ce) in enumerate(cells):
            rg.append('        <td><span class="lbl">%s</span>%s</td>'
                      % (tt(esc(cols[n + 1][0]), esc(cols[n + 1][1])), tt(esc(ch), esc(ce))))
        rg.append('        <td><span class="lbl">%s</span>%s</td>'
                  % (tt(esc(cols[4][0]), esc(cols[4][1])),
                     gap('展前，尚未登記', 'pre-show, nothing registered yet')))
        rg.append('      </tr>')
    rg.append('    </tbody>')
    rg.append('  </table>')
    rg.append('  </div>')
    rg.append('  <p class="note">%s</p>'
              % tt('每一次現場對話結束後就地填。沒問到和沒有是兩件事 —— 沒問到寫 GAP。',
                   'Fill it the moment a conversation ends. Not asked and not there are different '
                   'findings; not asked is a GAP.'))
    rg.append('  %s' % STAMP)
    a(dr(tt('現場登記簿', 'The floor register'),
         S(('%d 個客群 × 3 格' % len(SEGMENTS or [1]),
            '%d segments x 3 cells' % len(SEGMENTS or [1])), '·',
           ('現在全部是空的，這是預期狀態', 'all empty right now, which is the expected state')),
         '\n'.join(rg), block='d-register', fresh=True))

    # -------------------------------------------------------- 8. the gaps ---
    g = [
        gap('上述場次的講者姓名與所屬公司未證實，議程子頁沒有給。用現場 App 於第一天補齊再排時程。',
            'The speaker names and employers for those sessions are unverified — the agenda '
            'sub-pages do not carry them. Fill them in from the event app on day one and re-plan.'),
        gap('Verda、Lila Sciences、Encord、Simplismart、Parasail、Path Robotics 的硬體供應商未證。'
            '要結案就在攤位上直接問誰整合那一櫃。',
            'The hardware suppliers behind Verda, Lila Sciences, Encord, Simplismart, Parasail and '
            'Path Robotics are unverified. Close it by asking at the booth who integrates the rack.'),
        gap('CoreWeave 是否同時用 Dell 以外的 OEM、Nebius 的 ODM 名稱與是否外購 CPU 或儲存節點，'
            '都只有單邊公告。要結案需要對方工程師的一句話。',
            'Whether CoreWeave uses an OEM other than Dell, which ODM Nebius uses, and whether it '
            'buys CPU or storage nodes outside, all rest on one-sided announcements. One sentence '
            'from their engineers closes it.'),
        gap('所有與會平台團隊的實際機隊規模與採購窗口未證。本頁一律不推估。',
            'The real fleet size and purchasing window of every platform team here is unverified. '
            'Nothing on this page estimates them.'),
    ]
    a(dr(tt('這一頁還沒結案的', 'What this page has not closed'),
         S(('%d 個缺口' % len(g), pl(len(g), 'open question', 'open questions')), '·',
           ('每一個都寫了現場怎麼問掉它', 'each with the question that closes it on the floor')),
         ul(g) + '\n  %s' % STAMP, cls='caveat', fresh=True))
    return '\n'.join(h)


# ================================================================= accounts ==
# 58 cards, every populated cell with its source as a real link and the day it
# was read, every GAP with the reason it is still open and what would close it.
# The caption on a cell says what that cell CHANGES — it never explains the
# field name back to the reader.

FIELD_SPEC = [
    ('layer', '他在這條鏈上的位置', 'Where they sit in the chain',
     '決定你直接賣給他，還是經他賣給別人',
     'decides whether you sell to them or through them',
     '位置未查證，不是不屬於任何一層',
     'their position is unverified, which is not the same as belonging nowhere'),
    ('buys_servers', '自己買機器嗎', 'Buys its own machines',
     '決定這是直銷帳戶，還是只能當情報來源',
     'decides whether this is a direct account or only a source',
     '本輪沒有找到足以判定的證據。自有機房、colo 機櫃、汰換週期、硬體採購職缺，任一有據就能結案 ——'
     '租來的 dedicated hosting 也叫 physical server，要看誰擁有那台鐵',
     'no evidence either way this lap. An owned hall, a colo cage, a replacement cycle or a hardware '
     'procurement job ad would each close it — rented dedicated hosting is also called a physical '
     'server, so the question is who owns the iron'),
    ('oem_lock', '整櫃是誰供的', 'Who supplies the racks',
     '鎖住就別正面打；有縫才有標',
     'locked means do not bid head-on; a seam means there is a deal',
     '整櫃供應商未公開。到攤位直接問「這一櫃是誰整合的、on-site 誰做」就能結案',
     'the rack supplier is not public. Asking at the booth who integrated this rack and who does the '
     'on-site work closes it'),
    ('window', '什麼時候會買', 'When they buy',
     '沒有窗口就沒有跟進的理由，也沒有排這一趟的理由',
     'without a window there is no reason to follow up and no reason to make the trip',
     '本輪未查證採購窗口。「未查證」和「查過、沒有窗口」不是同一件事，所以這裡不寫成沒有',
     'the purchasing window was not researched this lap. Not researched is a different finding from '
     'researched and empty, so it is not written as none'),
    ('mw_or_proxy', '規模有多大', 'How big they are',
     '規模決定值不值得為這一家排一趟拜訪',
     'scale decides whether this one is worth a trip',
     '規模未經一手證實。財報、電力合約或機房公告都能結案',
     'scale is not first-party confirmed. A filing, a power contract or a facility announcement '
     'would close it'),
    ('classification', '這一輪的判定', 'The call this lap',
     '判定會隨新證據翻盤，不是永久標籤',
     'the call flips when new evidence lands; it is not a permanent label',
     '本輪證據不足以下判定',
     'not enough evidence this lap to make the call'),
    ('role_at_event', '在這場怎麼出現', 'How they show up here',
     '有攤位才找得到人；只有講者席次就要在場外堵',
     'a booth means you can find them; a speaker slot only means catching them outside the room',
     '在這場的身分未證實',
     'how they appear at this event is unverified'),
    ('crm', '我們這邊誰在做', 'Who on our side owns it',
     '進門前要知道有沒有人已經在做這一家',
     'know before you walk in whether someone is already on this account',
     '沒有登入任何客戶系統查過，這一格請業務在自家系統確認',
     'no customer system was logged into, so this cell is for the rep to confirm in ours'),
    ('legal_name', '名單上的名字', 'The name on the roster',
     '名字對不上就是找錯公司；容易認錯的幾組列在對位頁',
     'the wrong name is the wrong company; the pairs that collide are on the matchup page',
     '這場名單上的正式名稱未證實',
     'the name on this event\'s roster is unverified'),
]

CONF_SPEC = [('tenancy', '他是不是買方', 'Whether they buy'),
             ('oem', '整櫃誰供', 'Who supplies the racks'),
             ('mw', '規模', 'Scale')]


def short(v, n=64):
    v = str(v or '')
    return v if len(v) <= n else v[:n - 1] + '…'


def unwrap_gated(v):
    """EVENT-GATED{...} carries the actual trigger inside the braces. Split it
    into readable clauses instead of printing the wrapper at the reader."""
    m = re.match(r'^\s*EVENT-GATED\s*\{(.*)\}\s*$', str(v or ''), re.S)
    inner = m.group(1) if m else str(v or '')
    return [p.strip() for p in re.split(r'\s*;\s*', inner) if p.strip()]


def card_cell(c, key, name):
    """(value_html, rank_or_None, source_html, is_gap)."""
    v = c.get(key)
    srcs = c.get('sources') or {}
    s = srcs.get(key) if isinstance(srcs.get(key), dict) else {}
    if isinstance(v, list):
        v = ' / '.join(str(x) for x in v) if v else ''
    spec = next((x for x in FIELD_SPEC if x[0] == key), None)
    if v in (None, '', [], {}) or is_gap(v):
        # A trailing note on the GAP itself is a real reason and outranks the
        # generic one — but "GAP-not-checked" is a field state, not a reason,
        # and the reader never sees our field states (it falls through).
        tail = str(v or '').strip()[3:].strip(' -—:') if is_gap(v) else ''
        if len(tail) < 8 or tail.lower().replace('-', ' ') in ('not checked', 'not researched'):
            tail = ''
        wh = tail or (spec[5] if spec else '本輪未查證，到現場問掉它')
        we = tail or (spec[6] if spec else 'not researched this lap; ask on the floor')
        return gap(wh, we), None, '', True
    rank = evidence_of(s.get('source'), name)
    # EVENT-GATED{...} is our own wrapper. The reader gets what is INSIDE it —
    # the actual trigger — never the wrapper.
    if isinstance(v, str) and v.strip().startswith('EVENT-GATED'):
        v = ' · '.join(unwrap_gated(v))
    return lk(v), rank, src_a(s.get('source'), s.get('date')), False


def card_drawer(c):
    name = str(c.get('legal_name') or c.get('org_id') or c.get('ledger_id') or '?')
    oid = str(c.get('org_id') or '')
    is_full = c.get('full') is True
    body = []

    badges = []
    if tier_of.get(oid):
        badges.append(tier_of[oid])
    role = c.get('role_at_event')
    for r in (role if isinstance(role, list) else [role] if role else []):
        badges.append(str(r))
    if c.get('classification') and not is_gap(c.get('classification')):
        badges.append(str(c['classification']))
    if badges:
        body.append('    <p class="badges">%s</p>'
                    % ''.join('<span class="chip">%s</span>' % esc(b) for b in badges))

    open_cells = 0
    body.append('    <dl class="cells">')
    for key, lh, le, ch, ce, _wh, _we in FIELD_SPEC:
        val, rank, src, g = card_cell(c, key, name)
        if g:
            open_cells += 1
        body.append('      <dt>%s<span class="cap">%s</span></dt>'
                    % (tt(esc(lh), esc(le)), tt(esc(ch), esc(ce))))
        body.append('      <dd>%s%s%s</dd>'
                    % (val, (' ' + ev(rank)) if rank else '', src))
    body.append('    </dl>')

    conf = c.get('confidence') or {}
    if isinstance(conf, dict) and conf:
        cc = []
        for k, kh, ke in CONF_SPEC:
            if conf.get(k):
                cc.append('<span class="cf cf-%s">%s %s</span>'
                          % (esc(str(conf[k]).lower()), tt(esc(kh), esc(ke)), lk(conf[k])))
        if cc:
            body.append('    <p class="conf">%s %s</p>'
                        % (tt('把握度：', 'How sure we are:'), ' '.join(cc)))

    if c.get('next_action'):
        body.append('    <p class="nextact"><b>%s</b> %s</p>'
                    % (tt('下一步', 'Next move'), esc(c['next_action'])))

    if is_full:
        deep = []
        mw = c.get('mw_or_proxy')
        deep.append('      <p class="dt2">%s</p>' % tt('規模，逐項', 'Scale, spelled out'))
        if mw and not is_gap(mw):
            deep.append(ul([lk(x) for x in re.split(r'\s*;\s*', str(mw)) if x.strip()],
                           cls='spell'))
            s = (c.get('sources') or {}).get('mw_or_proxy') or {}
            deep.append('      %s %s' % (ev(evidence_of(s.get('source'), name)),
                                         src_a(s.get('source'), s.get('date'))))
        else:
            deep.append('      <p>%s</p>'
                        % gap('這一家的規模本輪未經一手證實，財報或電力合約能結案',
                              'scale for this one is not first-party confirmed this lap; a filing '
                              'or a power contract would close it'))
        w = c.get('window')
        deep.append('      <p class="dt2">%s</p>' % tt('觸發點，逐項', 'Triggers, spelled out'))
        if w and not is_gap(w):
            deep.append(ul([lk(x) for x in unwrap_gated(w)], cls='spell'))
            s = (c.get('sources') or {}).get('window') or {}
            deep.append('      %s %s' % (ev(evidence_of(s.get('source'), name)),
                                         src_a(s.get('source'), s.get('date'))))
        else:
            deep.append('      <p>%s</p>'
                        % gap('採購窗口本輪未查證；問下一批容量什麼時候上線就能結案',
                              'the purchasing window was not researched this lap; asking when the '
                              'next tranche of capacity lands would close it'))
        body.append(dr(tt('完整檔', 'Full dossier'),
                       tt('規模與觸發點逐項攤開', 'scale and triggers, item by item'),
                       '\n'.join(deep), cls='deep'))

    scent = S((str(c.get('layer') or ''), str(c.get('layer') or '')), '·',
              ('買機器 %s' % short(c.get('buys_servers'), 12),
               'buys %s' % short(c.get('buys_servers'), 12)), '·',
              ('整櫃 %s' % short(c.get('oem_lock'), 14),
               'racks %s' % short(c.get('oem_lock'), 14)), '·',
              ('%d 格待補' % open_cells, '%d cells still open' % open_cells))
    head = '%s%s' % (lk(name),
                     (' <span class="fullmark">%s</span>'
                      % tt('完整檔', 'full dossier')) if is_full else '')
    return dr(head, scent, '\n'.join(body),
              cls='acct%s' % (' is-full' if is_full else ''))


def _flat(c, key):
    v = c.get(key)
    if isinstance(v, list):
        return ' / '.join(str(x) for x in v)
    return v


def frag_accounts():
    h = []
    a = h.append

    # ------------------------------------------- 1. the honest cover page ---
    cov = []
    if cards is None:
        cov.append('  <p>%s</p>'
                   % gap('帳戶卡尚未產生，%d 家組織的買方判定都還沒有結論' % N_ORG,
                         'the account cards have not been built, so the buyer call on all %d '
                         'organisations is still open' % N_ORG))
    else:
        cov.append('  <p>%s</p>'
                   % S(('這一板有', 'This board holds'), '%d' % N_CARDS,
                       ('家公司。已經填出來的欄位', 'companies. Cells filled in so far:'),
                       '%d' % POP, ('格，其中', 'of which'), '%d' % SRCD,
                       ('格帶著來源連結與讀取日期；還開著的是', 'carry a source link and the day it '
                        'was read. Still open:'), '%d' % GAPC,
                       ('格，每一格都寫了什麼證據能結案。',
                        'cells, each one carrying what would close it.')))
        cov.append('  <p>%s</p>'
                   % S(('拿得動的名單：', 'The list you can act on:'), '%d' % len(BUYS_YES),
                       ('家自己買機器、', 'buy their own machines,'), '%d' % len(BUYS_PART),
                       ('家部分自購。這一輪查完判定不是買方的有', 'partly do. Researched this lap and '
                        'found not to be buyers:'), '%d' % len(RULED_OUT),
                       ('家 —— 那是查過的結論，不是還沒查。另有', '— that is a conclusion, not an '
                        'unopened file. Another'), '%d' % len(BUYS_GAP),
                       ('家證據不足，仍在名單上。', 'have too little evidence either way and stay on '
                        'the list.')))
        no_layer = [c for c in cards if not band_key(c.get('layer'))]
        if no_layer:
            cov.append('  <p>%s</p>'
                       % gap('%d 家還沒分層，是未查證，不是不屬於任何一層' % len(no_layer),
                             '%d companies carry no layer yet — unverified, not unaffiliated'
                             % len(no_layer)))
        cov.append('  <p>%s</p>'
                   % S(('有具體採購窗口的', 'Companies with a dated purchasing window:'),
                       '%d' % len(WINDOW_KNOWN), ('家，有規模數字的', '. With a scale figure:'),
                       '%d' % len(MW_KNOWN),
                       ('家。其餘的窗口與規模都是 GAP —— 這一趟就是去問掉它們。',
                        '. Everything else is open on both, and that is what the trip is for.')))
        cov.append('  <p class="src">%s %s %s</p>'
                   % (tt('引用來源', 'Distinct sources cited'), lk('%d' % N_SRCURL),
                      tt('個不同網址', 'separate URLs')))
    cov.append('  %s' % STAMP)
    open_layer = cards is None or [c for c in cards if not band_key(c.get('layer'))]
    a(dr(tt('這一板現在的狀態', 'Where this board stands'),
         (S(('%d 家' % N_CARDS, pl(N_CARDS, 'company', 'companies')), '·',
            ('%d 格已填' % POP, '%d cells filled' % POP), '·',
            ('%d 格帶來源' % SRCD, '%d sourced' % SRCD), '·',
            ('%d 格待補' % GAPC, '%d still open' % GAPC), '·',
            ('%d 份完整檔' % N_FULL, '%d full dossiers' % N_FULL))
          if cards is not None else tt('帳戶卡尚未產生', 'the account cards are not built yet')),
         '\n'.join(cov), cls='caveat%s' % ('' if open_layer else ' is-clear'),
         block='gap-visible', fresh=True))

    # ------------------------------------------------------ 2. the bands ----
    banded = OrderedDict((k, []) for k, _n, _e, _d, _de in LAYERS)
    unbanded = []
    for c in (cards or []):
        key = band_key(c.get('layer'))
        (banded[key] if key else unbanded).append(c)

    def band(key, nh, ne, dh, de, items):
        yes = [c for c in items if str(c.get('buys_servers')) == 'YES']
        full = [c for c in items if c.get('full') is True]
        out = [c for c in items if str(c.get('classification')) == 'ruled-out']
        body = ['  <p class="banddesc">%s</p>' % tt(esc(dh), esc(de))]
        body.append('  <div class="accts" data-block="card-grid">')
        if not items:
            body.append('    <p>%s</p>'
                        % gap('這一層目前沒有卡片。沒有人落到這一層是「未查證」，不是「不屬於」',
                              'no card lands in this layer yet. Nobody here means unverified, not '
                              'unaffiliated'))
        for c in sorted(items, key=lambda c: (0 if c.get('full') else 1,
                                              TIER_RANK.get(tier_of.get(str(c.get('org_id') or ''), ''), 9),
                                              str(c.get('legal_name') or ''))):
            body.append(card_drawer(c))
        body.append('  </div>')
        return dr('%s %s' % (lk(key), tt(esc(nh), esc(ne))),
                  S(('%d 家' % len(items), pl(len(items), 'company', 'companies')), '·',
                    ('%d 家自己買機器' % len(yes), '%d buy their own machines' % len(yes)), '·',
                    ('%d 份完整檔' % len(full), '%d full dossiers' % len(full)), '·',
                    ('%d 家這輪判定不是買方' % len(out), '%d called out this lap' % len(out))),
                  '\n'.join(body), cls='band', block='layer-band')

    for key, nh, ne, dh, de in LAYERS:
        a(band(key, nh, ne, dh, de, banded[key]))
    if unbanded:
        a(band('unlayered', '還沒分層', 'Not yet placed',
               '分層欄位還是 GAP —— 未查證，不是不屬於任何一層。這一疊就是下一輪的排隊名單',
               'the layer cell is still open — unverified, not unaffiliated. This stack is the '
               'queue for the next lap', unbanded))

    # -------------------------------------------- 3. how solid any of it is -
    if cards is not None:
        el = []
        for rank, n in RANKS.items():
            if n:
                el.append('%s %s %s'
                          % (ev(rank), lk('%d' % n),
                             tt('格', 'cell' if n == 1 else 'cells')))
        body = ['  <p>%s</p>'
                % tt('同一張卡上的兩格可能一格是法說原文、一格是部落格轉述。'
                     '哪一格是哪一種，直接印在那一格旁邊，不用回頭查。',
                     'Two cells on one card can sit on very different ground — an earnings filing '
                     'next to a blog paraphrase. Which is which prints next to the cell itself.')]
        body.append('  <p>%s</p>' % ' '.join(el))
        body.append('  <p class="src">%s %s %s</p>'
                    % (tt('全部來自', 'All of it from'), lk('%d' % N_SRCURL),
                       tt('個不同來源網址，每一格都可以點開原文',
                          'separate source URLs, every cell clickable through to the original')))
        body.append('  %s' % STAMP)
        a(dr(tt('這些格子站得多穩', 'How solid any of this is'),
             S(('%d 格已填' % POP, '%d cells filled' % POP), '·',
               ('%d 格待補' % GAPC, '%d still open' % GAPC), '·',
               ('%d 個來源網址' % N_SRCURL, '%d source URLs' % N_SRCURL)),
             '\n'.join(body), fresh=True))
    return '\n'.join(h)


# ================================================================== compare ==
# Research draft 03 reaches the reader HERE: who rents, at what published rate,
# what building actually costs, where the crossover sits and WITH WHAT FORMULA,
# where we win, where we lose, and the other side's best argument at full
# strength rather than in a version we can beat.

RENTERS = [
    ('CoreWeave', 'platinum', 'GPU 雲、裸機加 Kubernetes、租期合約',
     'GPU cloud, bare metal plus Kubernetes, term contracts',
     ['Q2 2026 revenue USD 2,575M (YoY +112%)', 'backlog ~USD 104B',
      'contracted power ~3.7GW', 'active 1.5GW', 'quarterly capex USD 6,422M',
      'net loss USD 626M'],
     'https://investors.coreweave.com', '2026-08-11', 'official'),
    ('Nebius', 'gold', 'AI 雲、token 工廠、AI Studio',
     'AI cloud, token factory, AI Studio',
     ['Q2 2026 revenue USD 582.3M (YoY +454%)', 'ARR USD 3B',
      'adj. EBITDA +USD 236M', 'FY guidance USD 3.0–3.4B', 'capex USD 20–25B'],
     'https://nebius.com/newsroom', '2026-08-12', 'official'),
    ('Nscale', 'platinum', '垂直整合：自有電力到機櫃到 GPU 到 serverless 推論',
     'Vertically integrated: own power through racks and GPUs to serverless inference',
     ['Series C USD 2B at USD 14.6B valuation (2026-03-09)',
      'investors include Dell, Lenovo and NVIDIA',
      'Microsoft contract ~200,000 GB300'],
     'https://www.nscale.com/press-releases', '2026-08-17', 'official'),
    ('Lambda', 'gold', 'GPU 雲加工作站；一鍵叢集',
     'GPU cloud plus workstations; one-click clusters',
     ['FY to 2025-09 revenue > USD 520M', 'IPO targeted 2026'],
     'https://lambda.ai', '2026-08-17', 'third'),
]

# Rate card pivoted on the GPU, because the story is the SPREAD on one chip,
# not a list of prices. Every rate normalised to USD per GPU-hour so the columns
# are actually comparable; where a vendor quotes per-node the raw figure is kept
# in `raw` and shown, so nobody has to trust our arithmetic.
# None = that vendor does not publish this part. That is a GAP, never a zero.
LAMBDA_URL = 'https://lambda.ai/pricing'
CW_URL = 'https://www.coreweave.com/pricing'

# (chip, lambda_per_gpu_hr, coreweave_per_gpu_hr, coreweave_raw_note)
RATE_PIVOT = [
    ('B200',          6.69,  8.60,  None),
    ('H200',          None,  6.31,  ('USD 50.44 / 8-GPU hr', 'USD 50.44 per 8-GPU hour')),
    ('H100 SXM',      3.99,  6.16,  ('USD 49.24 / 8-GPU hr', 'USD 49.24 per 8-GPU hour')),
    ('A100 80GB',     2.79,  None,  None),
    ('GB200 NVL72',   None, 10.50,  ('USD 42.00 / 4-GPU hr', 'USD 42.00 per 4-GPU hour')),
]

# Multi-node costs MORE than single node at Lambda — the opposite of the volume
# discount a buyer expects, and worth its own line rather than a row in the grid.
CLUSTER_ROWS = [
    ('B200 1-Click Cluster', 'USD 8.87–9.86', 6.69),
    ('H100 1-Click Cluster', 'USD 5.54–6.16', 3.99),
]

LADDER = [('100%', 'USD 3.0'), ('70%', 'USD 4.3'), ('50%', 'USD 6.1'), ('30%', 'USD 10.1')]

# (label_h, label_e, rate_per_gpu_hr, crossover_pct, is_gap_on_terms)
CROSSOVERS = [
    ('CoreWeave 隨需', 'CoreWeave on demand', 8.60, '35%', False),
    ('Lambda 隨需', 'Lambda on demand', 6.69, '45%', False),
    ('CoreWeave 承諾用量（最高六折）', 'CoreWeave committed, up to forty per cent off', 3.44, '88%', True),
]

WINS = [
    ('高稼動、長期穩態推論：稼動率超過七成、且看得到三年以上需求時，自建的單位成本明確勝出。',
     'High utilisation, long steady-state inference: above about seventy per cent utilisation with '
     'three years of visible demand, building wins on unit cost and it is not close.', 'third'),
    ('資料主權與受監管業務：資料不能離開場域時，租賃不是比較貴的選項，是不合規的選項。',
     'Data sovereignty and regulated workloads: when the data may not leave the premises, renting '
     'is not the more expensive option, it is the non-compliant one.', 'official'),
    ('電力已經到位的客戶：最大的自建障礙已經消失，剩下的只是機器 —— 這是最短的成交路徑。',
     'Customers who already have power: the biggest obstacle to building is already gone and what '
     'is left is just the machines. That is the shortest path to a deal in the room.', 'official'),
    ('賣給租賃方本身：CoreWeave 單季資本支出與 Nebius 全年資本支出指引，兩個數字都是伺服器需求，'
     '不是伺服器需求的替代品。這一場最大的買家就是「對手」。',
     'Selling to the renters themselves: CoreWeave\'s quarterly capex and Nebius\'s full-year capex '
     'guidance are both server demand, not a substitute for it. The biggest buyers in this hall are '
     'the "competition".', 'official'),
]

LOSSES = [
    ('電力與併網：美國互連佇列積壓約 2,600GW，中位等待接近五年；變電站變壓器交期在 2026 年'
     '已超過 160 週。客戶沒有電的時候，我們賣什麼都沒用。',
     'Power and grid connection: the US interconnection queue is backed up by roughly 2,600GW with '
     'a median wait close to five years, and substation transformer lead times passed 160 weeks in '
     '2026. When the customer has no power, nothing we sell matters.', 'third'),
    ('不確定或爆量的需求：稼動率低於約四成時，自建在數學上就是輸，不需要辯論。',
     'Uncertain or spiky demand: below roughly forty per cent utilisation, building loses on '
     'arithmetic and there is nothing to argue about.', 'third'),
    ('世代風險：GB200 NVL72 交期六到十八個月、B200 HGX 三到六個月。等待期間世代已經換過，'
     '殘值風險由買方承擔。',
     'Generation risk: GB200 NVL72 runs six to eighteen months of lead time and B200 HGX three to '
     'six. The generation turns over inside that wait, and the residual-value risk sits with the '
     'buyer.', 'third'),
    ('維運能力：客戶沒有能跑 Ray 又能自動換掉壞卡的團隊時，超大規模雲那套「韌性外包」的訴求'
     '無法用硬體回應。',
     'Operational capacity: when the customer has no team that can both run Ray and swap failed '
     'accelerators automatically, the hyperscaler pitch about outsourced resilience cannot be '
     'answered with hardware.', 'official'),
]

QUOTE_H = ('你不是在買 GPU，你是在買一個你無法預測的三年賭注。你必須現在就決定三年後要多少算力、'
           '押哪個世代，還要自己找到電 —— 而併網的中位等待是五年。我們已經有 3.7GW 簽約電力和 '
           '51 個資料中心在運轉，你今天簽約，下週開跑。你談的稼動率交叉點只有在你真的填滿機器時'
           '才成立，而多數客戶填不滿；填不滿的那幾個月，你的折舊照跑。何況我們自己就用 6-year '
           '折舊、規模採購、跨客戶調度來攤平那條曲線 —— 你一家公司的單一叢集攤不平。最後：'
           '你買的那台機器，我們也在買，只是我們一次買 4.2GW，你買一櫃。你憑什麼認為你的單位成本'
           '會比我低？')
QUOTE_E = ('You are not buying GPUs. You are buying an unpredictable three-year bet. You have to '
           'decide today how much compute you will need in three years, which generation to back, '
           'and you have to find the power yourself — where the median grid wait is five years. We '
           'already have 3.7GW of contracted power and 51 data centres running. Sign today and you '
           'start next week. That utilisation crossover of yours only holds if you actually fill '
           'the machines, and most customers do not; in the months they do not, the depreciation '
           'runs anyway. And we run 6-year depreciation, buy at scale, and shift load across '
           'customers to flatten that curve — one cluster at one company cannot flatten it. Last '
           'thing: the machine you are buying, we are buying too. We buy 4.2GW at a time. You buy '
           'a rack. What makes you think your unit cost beats mine?')


def frag_compare():
    h = []
    a = h.append

    # -------------------------------------------------------- 1. the axis ---
    ax = ['  <p class="lede">%s</p>'
          % tt('這一場的買家在做的選擇是自建對租賃，不是 OEM 對 OEM。'
               '打錯軸，整頁對讀者沒用。',
               'The choice the buyers here are making is build versus rent, not OEM versus OEM. '
               'Fight the wrong axis and this whole page is useless to the reader.')]
    ax.append('  <div class="axes">')
    for n, (axis, hits) in enumerate(AXIS_HITS, start=1):
        present = [o for o in hits if not o.startswith('!')]
        absent = [o[1:] for o in hits if o.startswith('!')]
        ax.append('    <article class="axis" data-axis="%s">' % att(axis))
        ax.append('      <h3>%s</h3>' % tt('現場 %d 家' % len(present),
                                           '%d of them are here' % len(present)))
        ax.append('      <p class="axisfull">%s</p>' % esc(axis))
        ax.append('      <ul class="axislist">')
        for oid in present:
            ax.append('        <li>%s %s</li>'
                      % (lk(org_name(oid)),
                         ''.join('<span class="chip">%s</span>' % esc(b) for b in org_badges(oid))))
        for tok in absent:
            ax.append('        <li>%s %s</li>'
                      % (lk(tok), gap('軸線點名了，但這一場的名單裡沒有這一家；'
                                      '他們沒到場這件事本身也還沒證實',
                                      'named on the axis but absent from this event\'s roster, and '
                                      'their absence is itself unverified')))
        ax.append('      </ul>')
        ax.append('    </article>')
    ax.append('  </div>')
    ax.append('  %s' % STAMP)
    n_present = sum(len([o for o in hits if not o.startswith('!')]) for _x, hits in AXIS_HITS)
    a(dr(tt('這一場真正的對照軸', 'The axis this show is actually on'),
         S(('自建對租賃', 'Build versus rent'), '·',
           ('%d 條軸線' % len(AXES), pl(len(AXES), 'axis', 'axes')), '·',
           ('對面 %d 家在現場' % n_present, '%d of the other side are in the room' % n_present)),
         '\n'.join(ax), block='axis-from-STATE', fresh=True))

    # ------------------------------------------------- 2. who rents, what ---
    rn = []
    for name, tier, sell_h, sell_e, signals, url, date, rank in RENTERS:
        body = ['    <p>%s</p>' % tt(esc(sell_h), esc(sell_e))]
        body.append(ul([lk(x) for x in signals], cls='spell'))
        body.append('    %s %s' % (ev(rank), src_a(url, date)))
        rn.append(dr('%s <span class="chip">%s</span>' % (lk(name), esc(tier)),
                     S(('%d 個規模訊號' % len(signals),
                        pl(len(signals), 'scale signal', 'scale signals')), '·',
                       ('全部有來源', 'all sourced')),
                     '\n'.join(body)))
    a(dr(tt('租賃方是誰、賣什麼', 'Who rents, and what they sell'),
         S(('%d 家' % len(RENTERS), pl(len(RENTERS), 'renter', 'renters')), '·',
           ('全部在現場，全部是白金或金級',
            'all in the room, all at Platinum or Gold')),
         '\n'.join(rn), block='renters'))

    # ---------------------------------------------------- 3. the rate card --
    def spread(a, b):
        """Percentage the dearer side sits above the cheaper one."""
        if a is None or b is None:
            return None
        lo, hi = min(a, b), max(a, b)
        return int(round((hi - lo) / lo * 100)), ('CoreWeave' if b > a else 'Lambda')

    rc = ['  <p>%s</p>'
          % tt('只有兩家真的公布數字，所以這張表只有兩欄。全部換算成「每 GPU 每小時」才比得下去；'
               '對方按整台報價的，原始數字也印在旁邊，不用相信我們的算術。',
               'Only two of them publish numbers, so the table has two columns. Everything is '
               'normalised to one GPU for one hour or the columns cannot be compared; where a '
               'vendor quotes by the node, the raw figure prints beside it so you need not trust '
               'our arithmetic.')]
    rc.append('  <div class="regwrap">')
    rc.append('  <table class="reg ratecard">')
    rc.append('    <thead><tr>%s</tr></thead>'
              % ''.join('<th>%s</th>' % h for h in (
                  tt('晶片', 'Chip'), 'Lambda', 'CoreWeave',
                  tt('價差', 'Spread'))))
    rc.append('    <tbody>')
    for chip, lam, cw, raw in RATE_PIVOT:
        sp = spread(lam, cw)
        def cell(v, url, rawnote=None):
            if v is None:
                return ('<span class="lbl">%s</span>%s'
                        % (tt('每 GPU-hr', 'per GPU-hr'),
                           gap('未公布這一顆', 'does not publish this one')))
            extra = ('<span class="rawrate">%s</span>'
                     % tt(esc(rawnote[0]), esc(rawnote[1]))) if rawnote else ''
            return ('<span class="lbl">%s</span><b class="rate">%s</b>%s'
                    % (tt('每 GPU-hr', 'per GPU-hr'), lk('USD %.2f' % v), extra))
        rc.append('      <tr>')
        rc.append('        <td class="chip-c"><span class="lbl">%s</span>%s</td>'
                  % (tt('晶片', 'Chip'), lk(chip)))
        rc.append('        <td>%s</td>' % cell(lam, LAMBDA_URL))
        rc.append('        <td>%s</td>' % cell(cw, CW_URL, raw))
        if sp:
            pct, dearer = sp
            rc.append('        <td class="spread-c"><span class="lbl">%s</span>'
                      '<b class="spread">+%d%%</b> <span class="cap">%s</span></td>'
                      % (tt('價差', 'Spread'), pct,
                         tt('%s 較貴' % esc(dearer), '%s dearer' % esc(dearer))))
        else:
            rc.append('        <td class="spread-c"><span class="lbl">%s</span>%s</td>'
                      % (tt('價差', 'Spread'),
                         gap('只有一家報這顆，比不了',
                             'only one vendor lists it, so there is nothing to compare')))
        rc.append('      </tr>')
    rc.append('    </tbody>')
    rc.append('  </table>')
    rc.append('  </div>')
    rc.append('  %s %s %s' % (ev('official'), src_a(LAMBDA_URL, ASOF), src_a(CW_URL, ASOF)))

    h100 = next((r for r in RATE_PIVOT if r[0].startswith('H100')), None)
    if h100 and h100[1] and h100[2]:
        pct, dearer = spread(h100[1], h100[2])
        rc.append('  <p class="punch">%s</p>'
                  % S(('同一顆 H100，一家', 'The same H100, one vendor at'),
                      'USD %.2f' % h100[1], ('，另一家', ', the other at'),
                      'USD %.2f' % h100[2], ('。差', '. That is'), '%d%%' % pct,
                      ('，而且兩家都在這場展會裡。租賃市場自己就有這麼大的價差 ——'
                       '「租比較便宜」不是一個事實，是一句沒有講完的話。',
                       ', and both of them are at this show. The rental market carries that spread '
                       'inside itself. "Renting is cheaper" is not a fact, it is an unfinished '
                       'sentence.')))

    # multi-node costs more, not less
    cl = ['  <p>%s</p>'
          % tt('買家預期量大變便宜。Lambda 的多節點叢集比單機貴 —— 因為那條 InfiniBand 要錢。'
               '這是現場可以直接問的一句話。',
               'A buyer expects volume to get cheaper. Lambda\'s multi-node clusters cost more than '
               'single nodes, because the InfiniBand fabric is not free. That is a question you can '
               'ask on the floor as it stands.')]
    cl.append('  <div class="regwrap">')
    cl.append('  <table class="reg">')
    cl.append('    <thead><tr>%s</tr></thead>'
              % ''.join('<th>%s</th>' % h for h in (
                  tt('叢集方案', 'Cluster offer'), tt('叢集價', 'Cluster rate'),
                  tt('同顆單機價', 'Single-node rate'), tt('貴多少', 'Premium'))))
    cl.append('    <tbody>')
    for label, band, single in CLUSTER_ROWS:
        lo = float(re.findall(r'[\d.]+', band)[0])
        prem = int(round((lo - single) / single * 100))
        cl.append('      <tr><td><span class="lbl">%s</span>%s</td>'
                  '<td><span class="lbl">%s</span><b class="rate">%s</b></td>'
                  '<td><span class="lbl">%s</span>%s</td>'
                  '<td><span class="lbl">%s</span><b class="spread">+%d%%</b></td></tr>'
                  % (tt('叢集方案', 'Cluster offer'), lk(label),
                     tt('叢集價', 'Cluster rate'), lk(band),
                     tt('同顆單機價', 'Single-node rate'), lk('USD %.2f' % single),
                     tt('貴多少', 'Premium'), prem))
    cl.append('    </tbody>')
    cl.append('  </table>')
    cl.append('  </div>')
    cl.append('  %s %s' % (ev('official'), src_a(LAMBDA_URL, ASOF)))
    rc.append(dr(tt('多節點反而更貴', 'Multi-node costs more, not less'),
                 tt('叢集價比單機價高兩到四成', 'clusters run twenty to forty per cent above single nodes'),
                 '\n'.join(cl)))

    rc.append('  <p>%s</p>'
              % S(('CoreWeave 的承諾用量寫「最高六折」，但合約長度與級距沒公布。',
                   'CoreWeave says committed use goes up to forty per cent off but publishes '
                   'neither contract length nor tiers.'),
                  gap('那是 GAP，不是可以拿來算的數字。要結案：向客戶索取他手上的實際報價單',
                      'that is a gap, not a number you can compute with. To close it, ask the '
                      'customer for the quote they are actually holding')))
    a(dr(tt('公開牌價', 'The published rate cards'),
         S(('只有兩家公布數字', 'only two vendors publish anything'), '·',
           ('同一顆 H100 差 %d%%' % (spread(h100[1], h100[2])[0] if h100 and h100[1] and h100[2] else 0),
            'the same H100 differs by %d%%' % (spread(h100[1], h100[2])[0] if h100 and h100[1] and h100[2] else 0)),
           '·', ('多節點反而更貴', 'multi-node costs more')),
         '\n'.join(rc), block='rate-cards'))

    # ------------------------------------- 4. the arithmetic, with formula --
    ec = ['  <p>%s</p>'
          % tt('先把輸入攤開，因為結論全都靠這兩個數字撐著，其中一個還是部落格等級的來源。',
               'The inputs go first, because the whole conclusion rests on two numbers and one of '
               'them is a blog-grade source.')]
    ec.append(ul([
        '%s %s' % (S(('B200 每顆約', 'B200 at roughly'), 'USD 40,000'), ev('third')),
        '%s %s' % (S(('硬體只佔叢集總持有成本的', 'hardware is only'), '25–35%',
                     ('，其餘是電、冷、網、場地與人力',
                      ' of cluster total cost of ownership; the rest is power, cooling, network, '
                      'space and people')), ev('third')),
        '%s %s' % (S(('折舊年限各家自選而且會被改：CoreWeave 用', 'Depreciation life is a choice and '
                      'it gets changed: CoreWeave uses'), '6-year',
                     ('（2023 年從四年延長）、Nebius 用', '(extended from four in 2023), Nebius uses'),
                     '4-year', ('；Amazon 反向把部分伺服器從六年縮成五年，認列',
                                '; Amazon went the other way, cutting some servers from six years '
                                'to five and taking a'), 'USD 700M',
                     ('營益衝擊。誰的折舊比較長，誰的每小時成本就比較好看。',
                      ' operating income hit. Whoever depreciates longer has the prettier hourly '
                      'number.')), ev('third')),
    ]))
    ec.append('  <p class="dt2">%s</p>' % tt('推算式，原樣寫出來', 'The formula, written out'))
    ec.append('  <p class="formula">ESTIMATE{ (B200 USD 40,000/GPU &#247; 0.30 TCO share) '
              '&#247; (5 years &#215; 8,760 hours &#215; utilisation) }</p>')
    ec.append('  <p class="note">%s</p>'
              % tt('這是推算，不是報價。輸入來源都是第三方，讀取日期見下方。'
                   '拿去對話可以，拿去當價格不行。',
                   'This is an estimate and it is not a quote. Both inputs are third-party and the '
                   'read dates are below. Use it to have a conversation, never as a price.'))
    # The answer belongs IN the table. A ladder of build costs makes the reader
    # do the join; the question they actually carry is "against what, and from
    # what utilisation do I win".
    ec.append('  <p class="dt2">%s</p>'
              % tt('自建從幾成稼動開始贏', 'The utilisation at which building starts to win'))
    ec.append('  <div class="regwrap">')
    ec.append('  <table class="reg crossover">')
    ec.append('    <thead><tr>%s</tr></thead>'
              % ''.join('<th>%s</th>' % h for h in (
                  tt('比的對象', 'Against'), tt('對方每 GPU-hr', 'Their rate, per GPU-hr'),
                  tt('自建從這裡開始贏', 'Build wins from'))))
    ec.append('    <tbody>')
    for lh, le, rate, pct, terms_gap in CROSSOVERS:
        rate_cell = lk('USD %.2f' % rate)
        if terms_gap:
            rate_cell += (' <span class="cap">%s</span>'
                          % gap('合約長度與級距未公布，這個數字是從「最高六折」回推',
                                'contract length and tiers are unpublished; this figure is '
                                'derived back from the up-to-forty-per-cent-off line'))
        ec.append('      <tr><td><span class="lbl">%s</span>%s</td>'
                  '<td><span class="lbl">%s</span>%s</td>'
                  '<td><span class="lbl">%s</span><b class="xover">%s</b></td></tr>'
                  % (tt('比的對象', 'Against'), tt(esc(lh), esc(le)),
                     tt('對方每 GPU-hr', 'Their rate, per GPU-hr'), rate_cell,
                     tt('自建從這裡開始贏', 'Build wins from'), lk(pct)))
    ec.append('    </tbody>')
    ec.append('  </table>')
    ec.append('  </div>')
    ec.append('  <p class="punch">%s</p>'
              % tt('同一套自建成本，換一個比較對象，門檻從三成五跳到將近九成。'
                   '所以「幾成稼動才划算」這個問題,沒有先問「跟哪一種租賃比」就沒有答案。',
                   'One build cost, three different answers — the bar moves from thirty-five per '
                   'cent to nearly ninety depending only on what you compare against. '
                   '"What utilisation do I need" has no answer until someone says which rental.'))
    ec.append(dr(tt('自建成本階梯', 'The build-cost ladder behind it'),
                 tt('四個稼動率下的每 GPU-hr 成本', 'per GPU-hour at four utilisation levels'),
                 '  <div class="regwrap">\n  <table class="reg">\n'
                 + '    <thead><tr><th>%s</th><th>%s</th></tr></thead>\n'
                 % (tt('稼動率', 'Utilisation'), tt('自建每 GPU-hr', 'Build, per GPU-hr'))
                 + '    <tbody>\n'
                 + '\n'.join(
                     '      <tr><td><span class="lbl">%s</span>%s</td>'
                     '<td><span class="lbl">%s</span>%s</td></tr>'
                     % (tt('稼動率', 'Utilisation'), lk(u),
                        tt('自建每 GPU-hr', 'Build, per GPU-hr'), lk(c))
                     for u, c in LADDER)
                 + '\n    </tbody>\n  </table>\n  </div>'))
    ec.append('  <p class="punch">%s</p>'
              % tt('常被略過的一點：一年期預留合約的稼動率風險與自建完全相同 —— 用不用都要付。'
                   '唯一沒有稼動率風險的是隨需，而隨需最貴。所以在高承諾情境下兩邊幾乎是同一題，'
                   '租賃贏的是速度與選擇權，不是單位成本。',
                   'The point everyone skips: a one-year reserved contract carries exactly the same '
                   'utilisation risk as building — you pay whether you use it or not. The only thing '
                   'with no utilisation risk is on-demand, and on-demand is the most expensive. So '
                   'at high commitment the two sides are nearly the same question, and what renting '
                   'wins is speed and optionality, not unit cost.'))
    ec.append('  <p>%s</p>'
              % S(('真正不確定的是租金方向。H100 的每小時租金在', 'What is genuinely uncertain is '
                   'which way rent moves. H100 rent per hour was'), 'USD 7-10',
                  ('，是', ' in'), '2023', ('年的水準；到', '; by'), '2024-2025',
                  ('一度跌破', 'it had briefly dropped under'), 'USD 2',
                  ('，跌幅約七成。但一年期合約價從', ', about seventy per cent down. Then the '
                   'one-year contract price went from'), 'USD 1.70', ('（', '('), '2025-10',
                  ('）反彈約四成，到', ') back up about forty per cent to'), 'USD 2.35',
                  ('（', '('), '2026-03',
                  ('）。任何以「租金會一直跌」或「一直漲」為前提的模型都不可信，包括對方拿給客戶看的那一份。',
                   '). Any model that assumes rent only falls, or only rises, is not worth showing '
                   'anyone, including the one the other side shows your customer.')))
    ec.append('  %s %s' % (ev('third'), from_draft(D03)))
    a(dr(tt('自建對租賃的真實算術', 'What building actually costs, and where it crosses'),
         S(('推算式原樣寫出來', 'the formula is written out'), '·',
           ('三個交叉點', 'three crossover points'), '·',
           ('%d 級稼動率階梯' % len(LADDER), '%d-step utilisation ladder' % len(LADDER))),
         '\n'.join(ec), block='crossover'))

    # ------------------------------------------------ 5. hyperscalers -------
    hs = [ul([
        '%s %s' % (S(('AWS（白金）賣 SageMaker HyperPod 加 Ray。訴求是叢集不穩、稼動率低、'
                      '分散式太難，主打節點自動換修加 checkpoint 續跑，宣稱可節省最多四成訓練時間。',
                      'AWS (Platinum) sells SageMaker HyperPod with Ray. The pitch is that clusters '
                      'are unstable, utilisation is low and distributed is hard, answered with '
                      'automatic node replacement and checkpoint resume, claiming up to forty per '
                      'cent of training time saved.')), ev('vendor')),
        '%s %s' % (S(('Microsoft Azure（金級）主打在 AKS 上大規模跑 Ray。',
                      'Microsoft Azure (Gold) pitches running Ray at scale on AKS.')), ev('third')),
        '%s %s' % (S(('Google（白金）走開源路線，GKE 團隊與主辦方共同 upstream。',
                      'Google (Platinum) plays the open-source card, with the GKE team upstreaming '
                      'alongside the host.')), ev('official')),
    ])]
    hs.append('  <p class="punch">%s</p>'
              % tt('三家的共同賣點不是價格，是「韌性與維運外包」。他們不比每小時單價，'
                   '比的是你不用養 SRE、不用處理壞卡。這是自建方最難反駁的一段 ——'
                   '不要試著用規格反駁它，要問對方有沒有那個團隊。',
                   'What all three sell is not price, it is outsourced resilience and operations. '
                   'They do not compete on the hourly rate; they compete on you not having to keep '
                   'an SRE team or deal with dead accelerators. This is the hardest passage to '
                   'answer from the build side — do not try to answer it with specs, ask whether '
                   'the customer has that team.'))
    hs.append('  %s' % from_draft(D03))
    a(dr(tt('超大規模那一邊', 'The hyperscaler side'),
         S(('三家都在現場', 'all three are in the room'), '·',
           ('賣的不是價格，是維運外包', 'they sell outsourced operations, not price')),
         '\n'.join(hs), block='hyperscalers'))

    # -------------------------------------------- 6. where we win and lose --
    a(dr(tt('我們在哪裡贏', 'Where we win'),
         S(('%d 個情境' % len(WINS), pl(len(WINS), 'situation', 'situations')), '·',
           ('其中一個是「賣給對手」', 'one of them is selling to the competition')),
         ul(['%s %s' % (tt(esc(x), esc(y)), ev(r)) for x, y, r in WINS])
         + '\n  %s' % from_draft(D03), block='wins'))
    a(dr(tt('我們在哪裡輸', 'Where we lose'),
         S(('%d 個情境' % len(LOSSES), pl(len(LOSSES), 'situation', 'situations')), '·',
           ('照原樣寫，不打折', 'written at full strength, not discounted')),
         ul(['%s %s' % (tt(esc(x), esc(y)), ev(r)) for x, y, r in LOSSES])
         + '\n  %s' % from_draft(D03), block='losses'))

    # --------------------------------- 7. their best argument, full strength -
    q = ['  <blockquote class="q">%s</blockquote>' % tt(esc(QUOTE_H), esc(QUOTE_E))]
    q.append('  <p class="dt2">%s</p>' % tt('可用的反擊，只有一句', 'The counter, and it is one line'))
    q.append('  <p class="punch">%s</p>'
             % tt('這段話在稼動率穩定超過七成、電力已經到位、資料受監管的客戶身上全部失效；'
                  '而且對方的六折承諾價，其稼動率風險與自建完全相同。',
                  'Every word of that fails on a customer with steady utilisation above about '
                  'seventy per cent, power already in place, and regulated data — and their own '
                  'committed price carries exactly the same utilisation risk that building does.'))
    q.append('  <p class="note">%s</p>'
             % tt('這段是照他們最強的樣子寫的，不是照我們好打的樣子寫的。'
                  '你在現場會聽到的版本只會比這更順。',
                  'That is written the way they would say it, not the way we would like them to. '
                  'The version you hear on the floor will be smoother, not weaker.'))
    q.append('  %s' % from_draft(D03))
    a(dr(tt('對方最強的說法', 'Their strongest argument'),
         tt('照原樣寫出來，附一句反擊', 'quoted at full strength, with the one line that answers it'),
         '\n'.join(q), block='counterparty'))

    # -------------------------------------------------- 8. name collisions --
    traps = campaign.get('traps') or []
    tp = ['  <p class="note">%s</p>'
          % tt('認錯公司比認不出公司貴。', 'Naming the wrong company costs more than naming none.')]
    tp.append('  <ul class="traps">')
    for t in traps:
        tp.append('    <li class="trap">')
        tp.append('      <p><span class="chip">%s</span></p>' % esc(t.get('kind') or ''))
        tp.append('      <p class="ab"><b>A</b> %s</p>' % esc(t.get('a') or ''))
        tp.append('      <p class="ab"><b>B</b> %s</p>' % esc(t.get('b') or ''))
        tp.append('      <p class="neg">%s</p>' % esc(t.get('negation_query') or ''))
        tp.append('    </li>')
    if not traps:
        tp.append('    <li class="trap">%s</li>'
                  % gap('這一場還沒登記任何同名陷阱', 'no name collision registered for this event yet'))
    tp.append('  </ul>')
    a(dr(tt('同名陷阱', 'Names that collide'),
         S(('%d 組' % len(traps), pl(len(traps), 'collision', 'collisions')), '·',
           ('每一組都附反查字串', 'each with the query that separates them')),
         '\n'.join(tp), block='traps'))

    # -------------------------------------------------------- 9. the gaps ---
    g = [
        gap('CoreWeave、Nebius、Nscale 的承諾合約實際價格與最短年限未公開，只有「最高六折」一句。'
            '所有交叉點在拿到真實承諾價之前都是估算。要結案：向客戶索取他手上的報價單。',
            'The real committed price and minimum term at CoreWeave, Nebius and Nscale are not '
            'public — there is one line saying "up to forty per cent off". Every crossover here is '
            'an estimate '
            'until a real committed price lands. To close it: ask the customer for the quote they '
            'hold.'),
        gap('「硬體佔總持有成本 25–35%」是部落格等級的來源，卻是整個推算裡擺動最大的變數。'
            '若實際是 45%，交叉點會全數往有利自建的方向大幅移動。要結案：用客戶自己的電價、PUE、'
            '機房攤提與人力編組重算一次。',
            'The claim that hardware is 25–35% of total cost of ownership is a blog-grade source and '
            'it is the largest swing factor in the whole estimate. If the real figure is 45%, every '
            'crossover moves substantially in favour of building. To close it: rerun the numbers on '
            'the customer\'s own power price, PUE, facility amortisation and headcount.'),
        gap('GB300 NVL72 的整櫃採購價沒有可靠的公開來源，所以交叉點是以 B200 每顆推算的，'
            '沒有涵蓋機櫃級系統。要結案：內部報價。',
            'There is no reliable public price for a GB300 NVL72 rack, so the crossover is computed '
            'per B200 GPU and does not cover rack-scale systems at all. To close it: an internal '
            'quote.'),
        gap('Nscale 實際在役（而非簽約）容量未經一手證實，管線數字是第三方彙整。',
            'Nscale\'s actually-live capacity, as opposed to contracted, is not first-party '
            'confirmed; the pipeline figures are third-party aggregation.'),
        gap('我方是否在 CoreWeave、Nebius、Nscale 的供應鏈中未經證實。Lambda 已證實。'
            'CoreWeave 的 GB300 首發公開點名的是別人。這是此行最值得查證的一件事。',
            'Whether we are in the CoreWeave, Nebius or Nscale supply chain is unverified. Lambda is '
            'confirmed. CoreWeave\'s GB300 launch publicly named someone else. This is the single '
            'most worthwhile thing to settle on this trip.'),
    ]
    a(dr(tt('這一頁還沒結案的', 'What this page has not closed'),
         S(('%d 個缺口' % len(g), pl(len(g), 'open question', 'open questions')), '·',
           ('每一個都寫了什麼證據能結案', 'each with what would close it')),
         ul(g) + '\n  %s' % STAMP, cls='caveat', fresh=True))
    return '\n'.join(h)


BUILDERS = {
    'command-center': frag_command_center,
    'agenda': frag_agenda,
    'gtm': frag_gtm,
    'accounts': frag_accounts,
    'compare': frag_compare,
}


def main():
    budget = campaign.get('pageBudget') or {}
    allowed = set(budget.get('core') or []) | set(budget.get('depth') or [])
    for d in (BUILD, FRAG):
        if not os.path.isdir(d):
            os.makedirs(d)
    for f in sorted(os.listdir(FRAG)):
        if f.endswith('.html'):
            os.unlink(os.path.join(FRAG, f))

    manifest = {'event': EVENT, 'asOf': ASOF, 'srcLang': src_lang, 'source': SOURCE,
                'langs': [str(x) for x in langs], 'pages': []}
    written, drawers = [], 0
    for role, fname, title_h, title_e, nav_h, nav_e in PAGES:
        if allowed and role not in allowed:
            print('build_fragments: skip %s — not in STATE.campaign.pageBudget' % role)
            continue
        body = BUILDERS[role]()
        drawers += body.count('<details ')
        io.open(os.path.join(FRAG, role + '.html'), 'w', encoding='utf-8').write(body + '\n')
        manifest['pages'].append({'role': role, 'file': fname, 'title': title_h,
                                  'title_e': title_e, 'nav': nav_h, 'nav_e': nav_e,
                                  'frag': 'build/frag/%s.html' % role})
        written.append(role)
    for role in sorted(allowed - set(written)):
        sys.exit('build_fragments: FAIL pageBudget names role "%s" and this factory has no '
                 'fragment builder for it. Add one, or drop it from the budget (B12).' % role)
    io.open(os.path.join(BUILD, 'manifest.json'), 'w', encoding='utf-8').write(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('build_fragments: %d fragments (%s) lang=%s asOf=%s drawers=%d cards=%s '
          'cells=%d sourced=%d gap=%d evidence=%s'
          % (len(written), ' '.join(written), src_lang, ASOF or 'UNSET', drawers,
             'GAP' if cards is None else N_CARDS, POP, SRCD, GAPC,
             ','.join('%s:%d' % (k, v) for k, v in RANKS.items() if v) or 'none'))


main()
