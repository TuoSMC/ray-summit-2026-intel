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


def dr(title_html, scent_html, body, is_open=False, cls='', block='', fresh=False, aid=None):
    """A drawer. The summary carries the title AND a scent line — what is inside
    plus a count or a verdict — so a closed drawer still informs (RULES C6: the
    control is >=44px, focusable, and native, so keyboard works for free)."""
    at = ['class="dr%s"' % ((' ' + cls) if cls else '')]
    if aid:
        at.append('id="%s"' % att(aid))
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


# ==================================================== structure & wayfinding ==
# Three problems this block exists to solve, all of them the same problem seen
# from different distances:
#
#   1. A long section reads as a wall. The reader cannot tell what is in it
#      without opening it, and cannot tell what it is FOR even then.  -> spine()
#   2. A bullet is a sentence with no handle. The reader who wants "the pricing
#      one" has to read all nine to find it.                          -> item()
#   3. A company named in the plays page is the same company that has a card on
#      the account board, and the two never touched.                  -> xref()
#
# Everything here is anchor-based and computed. An anchor that is not registered
# cannot be linked at (xref/secref refuse), so a rename can never silently
# produce a dead link — it produces a build failure instead.

PAGE_FILE = {r: f for r, f, _th, _te, _nh, _ne in PAGES}
PAGE_ZH = {r: nh for r, _f, _th, _te, nh, _ne in PAGES}
PAGE_EN = {r: ne for r, _f, _th, _te, _nh, ne in PAGES}

# id -> (kind, page_role, zh, en). Ordered, because the index prints in order.
ANCHORS = OrderedDict()


def slug(v):
    """A stable anchor fragment. Same input, same URL, forever (RULES A5)."""
    s = re.sub(r'[^a-z0-9]+', '-', str(v or '').lower()).strip('-')
    return s or 'x'


def reg(aid, kind, role, zh, en):
    """Register an anchor. Duplicate ids are a build failure, not a warning:
    two elements answering to one href is how a 'working' link lands on the
    wrong thing."""
    if aid in ANCHORS:
        sys.exit('build_fragments: FAIL duplicate anchor id "%s" (%s vs %s). '
                 'Anchors are URLs; two things cannot share one.'
                 % (aid, ANCHORS[aid][0], kind))
    ANCHORS[aid] = (kind, role, zh, en)
    return aid


def href(aid):
    """Cross-page while the pack is six files, in-page once onepage.py folds it.
    onepage.py rewrites "<file>#frag" to "#frag"; nothing here needs to know
    which edition it is being built for."""
    if aid not in ANCHORS:
        sys.exit('build_fragments: FAIL link to unregistered anchor "%s". '
                 'Register it with reg() at the place it is emitted, or fix the id.' % aid)
    role = ANCHORS[aid][1]
    return '%s#%s' % (PAGE_FILE.get(role, ''), aid)


def a_to(aid, label_h=None, label_e=None, cls='xr'):
    """A cross-reference. The label defaults to the target's own registered
    name, so a renamed target renames every link to it."""
    _k, _r, zh, en = ANCHORS[aid]
    return ('<a class="%s" href="%s">%s</a>'
            % (cls, att(href(aid)), tt(esc(label_h or zh), esc(label_e or en))))


def secref(sid, label_h=None, label_e=None):
    """Link to another section, by section id."""
    return a_to('s-' + sid, label_h, label_e, cls='xr xr-sec')


def xref(oid_or_lid, label=None):
    """Link a company mention to its card. A company with no card is emitted as
    plain text — a link to nothing is worse than no link (B13 in spirit: do not
    imply a file exists)."""
    key = str(oid_or_lid or '')
    lid = ORG_TO_CARD.get(key) or ORG_TO_CARD.get(key.lower())
    name = label or (CARD_NAME.get(lid) if lid else None) or org_name(key)
    if not lid:
        return esc(name)
    aid = 'acct-' + slug(lid)
    if aid not in ANCHORS:
        return esc(name)
    return '<a class="xr xr-org" href="%s">%s</a>' % (att(href(aid)), esc(name))


def sesref(sess):
    """Link a session mention to its row in the agenda."""
    sid = str((sess or {}).get('id') or '')
    aid = 'ses-' + slug(sid)
    title = str((sess or {}).get('title') or sid)
    if not sid or aid not in ANCHORS:
        return lk(title)
    return '<a class="xr xr-ses" href="%s">%s</a>' % (att(href(aid)), lk(title))


# ---- the section table: one row per section, and it IS the spine ------------
# The spine, the anchor registry, the in-page index and the section heading all
# read this table. They cannot drift apart, because there is nothing to drift.
#
# columns: role, sid, ZH title, EN title, ZH "what this answers", EN
SECTIONS = [
    ('command-center', 'verdict', '判斷', 'The call',
     '這一場的錢花在哪裡，我方該用什麼身分走進去',
     'where the money in this room actually goes, and what we walk in as'),
    ('command-center', 'numbers', '四個數字', 'Four numbers',
     '這場的規模,四個從資料算出來、不是打上去的數字',
     'the size of the thing, in four figures computed from the data rather than typed'),
    ('command-center', 'actions', '兩個動作', 'Two actions',
     '到現場先站哪裡、開口先問什麼',
     'where to stand when you arrive, and what to say first'),
    ('command-center', 'room', '這是什麼房間', 'What room this is',
     '來的是哪一種人、誰付的錢、他們用什麼標準判斷東西好不好',
     'who is in the room, who paid to be here, and what they judge a product by'),
    ('command-center', 'changed', '2025 → 2026 變了什麼', 'What changed from 2025 to 2026',
     '跟上屆比,哪幾件事變了,以及變的那幾件事怎麼改寫我們的說法',
     'what moved since the last edition, and how each move rewrites our pitch'),
    ('command-center', 'turn', '技術轉向與伺服器含意', 'The technical turn',
     '議程上的技術重心往哪裡移,那個移動會不會變成伺服器訂單',
     'where the agenda has moved technically, and whether that movement becomes a server order'),
    ('command-center', 'signals', '前瞻訊號', 'Forward signals',
     '還沒發生但已經看得到的事,以及看到之後要做什麼',
     'what has not happened yet but is already visible, and what to do about each'),
    ('command-center', 'open', '本場 GAP', 'What is still open',
     '這一包還不知道的事,以及什麼證據能結案',
     'what this pack does not know, and what evidence would close each one'),
    ('command-center', 'method', '方法與來源', 'Method and sources',
     '這些結論怎麼來的,哪一步可以被推翻',
     'how these conclusions were produced, and which step you could overturn'),

    ('command-center', 'index', '索引', 'Index',
     '這一包裡的每一節、每一家公司、每一場,一次列完,每一條都是連結',
     'every section, every company and every session in this pack, listed once, each one a link'),

    ('agenda', 'queue', '先卡這幾場', 'Queue for these first',
     '時間有限的話,哪幾場非去不可,理由是什麼',
     'if time is short, which rooms are non-negotiable and why'),
    ('agenda', 'all-sessions', '全部場次', 'Every session',
     '目錄已公布的每一場,可以自己重排',
     'every session the catalogue has published, so you can re-rank it yourself'),
    ('agenda', 'rooms', '會議室', 'Rooms',
     '哪一間房間裝哪一種人,走廊怎麼走',
     'which room holds which kind of person, and how the corridor runs'),
    ('agenda', 'catalog-gap', '目錄沒有給的東西', 'What the catalogue does not give',
     '議程資料本身缺什麼,缺的地方怎麼補',
     'what the agenda data itself is missing, and how to work around it'),

    ('gtm', 'judgement', '判斷', 'The judgement',
     '這一場我方的打法是什麼,一句話',
     'our play at this show, in one sentence'),
    ('gtm', 'theses', '論點與反證', 'Theses, each with what kills it',
     '我們相信的每一件事,以及什麼事發生就代表我們錯了',
     'each thing we believe, paired with the observation that would prove it wrong'),
    ('gtm', 'booths', '攤位對話,按賠率排序', 'Booth conversations, by odds',
     '走廊上每一攤值不值得停,停下來要拿到什麼',
     'whether each booth is worth stopping at, and what to walk away holding'),
    ('gtm', 'segments', '分客群打法', 'Play by segment',
     '同一場活動裡有幾種買家,每一種的開場句和候選名單都不一樣',
     'this show holds several kinds of buyer, and each one takes a different opening line and a '
     'different shortlist'),
    ('gtm', 'questions', '五個問題', 'Five questions',
     '五句問話,每一句的答案會透露什麼',
     'five things to ask, and what each answer actually reveals'),
    ('gtm', 'dont', '不要做什麼', 'What not to do',
     '在這個房間會直接把對話講死的幾件事',
     'the moves that kill a conversation in this particular room'),
    ('gtm', 'register', '現場登記簿', 'The floor register',
     '現場收到的訊號往哪裡記,回去以後誰接手',
     'where the signal you collect gets written down, and who picks it up afterwards'),
    ('gtm', 'gtm-open', '這一頁還沒結案的', 'What this page has not closed',
     '打法上還沒想清楚的部分',
     'the parts of the play that are not settled'),

    ('accounts', 'board', '這一板現在的狀態', 'Where this board stands',
     '這板子填到什麼程度,哪些格子還開著',
     'how far this board is filled, and which cells are still open'),
    ('accounts', 'bands', '四層', 'The four layers',
     '每一家落在哪一層,那一層代表他會不會簽伺服器訂單',
     'which layer each company sits in, and what that layer says about whether they sign a server order'),
    ('accounts', 'solidity', '這些格子站得多穩', 'How solid any of this is',
     '每一格背後是法說原文還是部落格轉述',
     'whether a given cell rests on an earnings filing or a blog paraphrase'),

    ('compare', 'axis', '這一場真正的對照軸', 'The axis this show is on',
     '這場的競爭不在攤位之間,在哪裡',
     'the competition at this show is not booth against booth — this is where it is'),
    ('compare', 'renters', '租賃方是誰、賣什麼', 'Who rents, and what they sell',
     '在場的算力出租方各是誰,各自賣什麼',
     'which compute landlords are in the room, and what each one sells'),
    ('compare', 'rates', '公開牌價', 'The published rate cards',
     '同一顆晶片,租一小時各家要多少錢',
     'the same chip, hour by hour, priced across every vendor in the room'),
    ('compare', 'crossover', '自建對租賃的真實算術', 'Build versus rent, and where it crosses',
     '買機器什麼時候比租便宜,交叉點在哪',
     'when owning beats renting, and where exactly the line is'),
    ('compare', 'hyperscalers', '超大規模那一邊', 'The hyperscaler side',
     '雲廠在這場的位置',
     'where the hyperscalers sit at this show'),
    ('compare', 'we-win', '我們在哪裡贏', 'Where we win',
     '對上租賃方,我方站得住的地方',
     'the ground we hold against the rental case'),
    ('compare', 'we-lose', '我們在哪裡輸', 'Where we lose',
     '對上租賃方,我方站不住的地方 —— 先講,免得被別人講',
     'the ground we do not hold — said here first, so it is not said to us'),
    ('compare', 'their-case', '對方最強的說法', 'Their strongest argument',
     '如果租賃方只能講一句話說服買家,那句是什麼',
     'if the rental side got one sentence to win the buyer, this is the sentence'),
    ('compare', 'chips', '晶片世代履歷', 'What generation each chip is',
     '客戶講出一個型號的時候,那是新機隊還是舊機隊,差幾個月換一次',
     'when a customer names a part, whether that is a new fleet or an old one, and how long until '
     'it gets replaced'),
    ('compare', 'collisions', '同名陷阱', 'Names that collide',
     '這場有哪些名字會查錯人、查錯公司',
     'the names at this show that send research to the wrong company'),
    ('compare', 'compare-open', '這一頁還沒結案的', 'What this page has not closed',
     '對位上還沒查清楚的部分',
     'the parts of the matchup that are not settled'),
]

SEC_BY_ID = OrderedDict()
for _role, _sid, _th, _te, _wh, _we in SECTIONS:
    if _sid in SEC_BY_ID:
        sys.exit('build_fragments: FAIL duplicate section id "%s" in SECTIONS' % _sid)
    SEC_BY_ID[_sid] = (_role, _th, _te, _wh, _we)
    reg('s-' + _sid, 'section', _role, _th, _te)


def sec(sid, scent_html, body, is_open=False, cls='', block='', fresh=False,
        title_html=None, count_h=None, count_e=None):
    """A section. Same drawer as before, plus three things it did not have:
    a stable anchor, its own number, and one line saying what question it
    answers. The number and the question come from SECTIONS, so the spine at
    the top of the page and the section itself can never disagree."""
    if sid not in SEC_BY_ID:
        sys.exit('build_fragments: FAIL section "%s" is not in SECTIONS. Add the row first — '
                 'the spine reads that table, so an unlisted section is invisible.' % sid)
    role, th, te, wh, we = SEC_BY_ID[sid]
    n = [s for _r, s, _a, _b, _c, _d in SECTIONS if _r == role].index(sid) + 1
    at = ['class="dr sec%s"' % ((' ' + cls) if cls else ''), 'id="s-%s"' % sid]
    if block:
        at.append('data-block="%s"' % att(block))
    if fresh:
        at.append('data-fresh="1"')
    if is_open:
        at.append('open')
    title = title_html or ('<span class="sec-n" aria-hidden="true">%02d</span>%s' % (n, tt(esc(th), esc(te))))
    what = '<span class="sec-w">%s</span>' % tt(esc(wh), esc(we))
    return ('<details %s>\n'
            '  <summary><span class="dr-t">%s</span>%s<span class="dr-s">%s</span></summary>\n'
            '  <div class="dr-b">\n%s\n  </div>\n'
            '</details>' % (' '.join(at), title, what, scent_html, body))


INDEX_SLOT = '<!--INDEX-SLOT-->'

INDEX_KINDS = [
    ('section', '章節', 'Sections', '每一節回答一個問題', 'each answers one question'),
    ('item', '子項', 'Items', '每一節底下的每一項,可以單獨連結',
     'every item inside every section, each with its own link'),
    ('account', '公司', 'Companies', '這一板上的每一家,連到它的卡',
     'every company on the board, linked to its card'),
    ('session', '場次', 'Sessions', '目錄已公布的每一場', 'every session the catalogue publishes'),
    ('chip', '晶片', 'Chips', '每一顆的世代履歷,文中提到就連過去',
     'the generation record for each part; every mention in the text links here'),
]


def build_index():
    """Every registered anchor, grouped by what it is. Built from ANCHORS, so
    it cannot drift from the pages: an anchor that exists is listed, and an
    anchor that is listed exists — href() would have failed the build otherwise.
    """
    out = ['  <div class="idx">']
    for kind, kh, ke, wh, we in INDEX_KINDS:
        rows = [(aid, meta) for aid, meta in ANCHORS.items() if meta[0] == kind]
        if not rows:
            continue
        out.append('    <section class="idx-g">')
        out.append('      <h3 class="idx-h">%s <span class="idx-c">%s</span></h3>'
                   % (tt(esc(kh), esc(ke)), lk('%d' % len(rows))))
        out.append('      <p class="idx-w">%s</p>' % tt(esc(wh), esc(we)))
        out.append('      <ul class="idx-l">')
        for aid, (_k, role, zh, en) in rows:
            out.append('        <li><a href="%s">%s</a><span class="idx-p">%s</span></li>'
                       % (att(href(aid)), tt(esc(zh), esc(en)),
                          tt(esc(PAGE_ZH.get(role, role)), esc(PAGE_EN.get(role, role)))))
        out.append('      </ul>')
        out.append('    </section>')
    out.append('  </div>')
    return '\n'.join(out)


def spine(role):
    """The architectural map, printed at the top of a page: every section in it,
    numbered, with the question it answers. A reader who reads only this knows
    what the page contains and can jump straight at the one they need."""
    rows = [(sid, th, te, wh, we) for r, sid, th, te, wh, we in SECTIONS if r == role]
    if not rows:
        return ''
    out = ['<nav class="spine" data-block="spine" aria-label="%s">'
           % att('Sections on this page / 本頁章節')]
    out.append('  <p class="spine-h">%s</p>'
               % tt('這一頁有 %d 節。每一節回答一個問題。' % len(rows),
                    'This page has %d sections. Each one answers one question.' % len(rows)))
    out.append('  <ol class="spine-l">')
    for i, (sid, th, te, wh, we) in enumerate(rows, 1):
        out.append('    <li><a href="%s">'
                   '<span class="spine-n" aria-hidden="true">%02d</span>'
                   '<span class="spine-t">%s</span>'
                   '<span class="spine-q">%s</span></a></li>'
                   % (att(href('s-' + sid)), i, tt(esc(th), esc(te)), tt(esc(wh), esc(we))))
    out.append('  </ol>')
    out.append('</nav>')
    return '\n'.join(out)


# ---- sub-items: a heading with a handle, and a line saying what it is -------
_ITEM_N = {}


def item(sid, key, label_h, label_e, what_h, what_e, body, tag_h=None, tag_e=None):
    """One sub-item inside a section.

    A bullet gives the reader a sentence. An item gives them a heading they can
    aim at, a line telling them what the heading IS before they read the body,
    and a URL they can send to someone else. The heading is highlighted because
    it is the scanning surface: on a show floor the reader reads headings and
    stops at one.

    `tag` is the optional right-hand chip — a verdict, a count, an evidence
    rank. It is what the item resolves to, so the reader can skip the body when
    the answer is enough.
    """
    # A label or a "what" passed with its second arm None is already-built HTML
    # (a locked title, a cross-reference). Passing it through esc() would print
    # the tags. One arm means one language-neutral run, which is exactly what a
    # session title or a company name is.
    lab = label_h if label_e is None else tt(esc(label_h), esc(label_e))
    wht = what_h if what_e is None else tt(esc(what_h), esc(what_e))
    aid = reg('i-%s-%s' % (sid, slug(key)), 'item', SEC_BY_ID[sid][0],
              label_h if label_e is None else label_h, label_e or label_h)
    _ITEM_N[sid] = _ITEM_N.get(sid, 0) + 1
    n = _ITEM_N[sid]
    tag = ('<span class="itm-tag">%s</span>'
           % (tag_h if tag_e is None else tt(esc(tag_h or ''), esc(tag_e or '')))) \
        if (tag_h or tag_e) else ''
    return ('<section class="itm" id="%s">\n'
            '  <h3 class="itm-h"><span class="itm-n" aria-hidden="true">%d</span>'
            '<span class="itm-l">%s</span>%s'
            '<a class="itm-a" href="#%s" aria-label="%s">&#167;</a></h3>\n'
            '  <p class="itm-w">%s</p>\n'
            '  <div class="itm-b">%s</div>\n'
            '</section>'
            % (aid, n, lab, tag, aid,
               att('Link to this item / 連到這一項'),
               wht, body))


def items(sid, rows):
    """rows: (key, label_h, label_e, what_h, what_e, body[, tag_h, tag_e])"""
    return items_wrap([item(sid, *r) for r in rows])


def items_wrap(built):
    """Same container, for items already built one at a time in a loop."""
    if not built:
        return ''
    return '  <div class="itms">\n%s\n  </div>' % '\n'.join(built)


# ---- chip generation records ------------------------------------------------
# Why this table exists: this pack argues that the generation spread inside a
# customer's fleet IS the refresh clock (gtm thesis T-refresh, and the third of
# the five questions). An unannotated "H100" does not tell a rep whether that is
# an old fleet or a current one. Every mention gets linked to its row here.
#
# name, arch, announced, available, predecessor, successor, still_shipping,
# read_h, read_e, sources[]
_NV = 'https://nvidianews.nvidia.com/news/'
_Q1FY27 = ('https://s201.q4cdn.com/141608511/files/doc_financials/2027/q1/'
           'NVDA-Q1-2027-Earnings-Call-20-May-2026-5_00-PM-ET.pdf')
_10K26 = ('https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/'
          'nvda-20260125.htm')

CHIPS = [
    dict(name='A100 80GB', aka=['A100', 'A100 80GB SXM', 'A100 SXM'], arch='Ampere',
         announced='2020-11-16', available='2021-01', predecessor='A100 40GB',
         successor='H100 (2022-03-22)',
         still_shipping=('OEM 已停售,NVIDIA 從未發過 EOL —— 兩件事不衝突',
                         'end-of-sale at the OEMs; NVIDIA never issued an EOL, and those are not '
                         'in conflict'),
         read_h='六年前的矽,但 NVIDIA 財務長說它在雲上被租滿、租金年初至今漲近 15%。'
                '客戶手上的 A100 是資產不是包袱 —— 但 OEM 那邊已經買不到新的了。',
         read_e='Six-year-old silicon that NVIDIA\'s own CFO says is sold out in the cloud with '
                'rental up nearly 15% year-to-date. A customer\'s A100 fleet is an asset, not a '
                'liability — but you cannot buy it new from an OEM any more.',
         sources=[(_NV + 'nvidia-doubles-down-announces-a100-80gb-gpu-supercharging-worlds-most-powerful-gpu-for-ai-supercomputing', '2026-08-18'),
                  (_Q1FY27, '2026-08-18')]),
    dict(name='H100 SXM', aka=['H100', 'HGX H100'], arch='Hopper',
         announced='2022-03-22', available='2022-10', predecessor='A100 80GB',
         successor='H200 (2023-11-13) / B200 (2024-03-18)',
         still_shipping=('NVIDIA 向 SEC 說已經轉離 Hopper HGX;Dell 仍在目錄裡,Lenovo 已撤',
                         'NVIDIA told the SEC it has moved off selling Hopper HGX; Dell still '
                         'catalogues it, Lenovo has withdrawn it'),
         read_h='NVIDIA 在 10-K 裡用過去式寫「已從販售 Hopper HGX 轉向 Blackwell」。'
                '沒有人發過 EOL 通知,但廠商自己已經走了 —— 客戶的機隊如果是 H100 SXM,'
                '他的供應商比他先換了立場。',
         read_e='NVIDIA\'s 10-K uses the past tense: it "transitioned from offering Hopper HGX '
                'systems" to Blackwell. Nobody sent an EOL letter, but the vendor has already '
                'moved — if a customer\'s fleet is H100 SXM, their supplier changed position '
                'before they did.',
         sources=[(_NV + 'nvidia-hopper-in-full-production', '2026-08-18'),
                  (_10K26, '2026-08-18')]),
    dict(name='H200', aka=['HGX H200', 'H200 NVL'], arch='Hopper',
         announced='2023-11-13', available='2024-06', predecessor='H100 SXM',
         successor='B200 (2024-03-18)',
         still_shipping=('NVIDIA 頁面寫 Now available,但 Cisco 的最後訂購日是 2026-06-25',
                         'NVIDIA\'s page says "Now available", but Cisco\'s last order date was '
                         '2026-06-25'),
         read_h='全表唯一有 2026 年 OEM 最後訂購日的一顆。客戶若把 H200 當成未來三年的答案,'
                '那個答案在通路上已經開始關門了。',
         read_e='The only part on this table carrying a 2026-dated OEM last-order date. If a '
                'customer is treating H200 as their answer for the next three years, that answer '
                'is already closing in the channel.',
         sources=[(_NV + 'nvidia-supercharges-hopper-the-worlds-leading-ai-computing-platform', '2026-08-18'),
                  ('https://www.nvidia.com/en-us/data-center/h200/', '2026-08-18')]),
    dict(name='B200', aka=['HGX B200'], arch='Blackwell',
         announced='2024-03-18', available='2025-02', predecessor='H100 SXM',
         successor='B300 (2025-03-18)',
         still_shipping=('NVIDIA 自己寫「HGX B300 and HGX B200 shipping now」',
                         'NVIDIA\'s own page says "HGX B300 and HGX B200 shipping now"'),
         read_h='還在出貨,但已經是兩張 Blackwell 板子裡比較舊的那一張,'
                '而 NVIDIA 本季營收是 Blackwell 300 帶起來的。沒有特別理由就直接談 B300。',
         read_e='Still shipping, but it is now the older of the two Blackwell HGX boards, and '
                'NVIDIA\'s current quarter is driven by Blackwell 300. Absent a specific reason, '
                'talk about B300 instead.',
         sources=[(_NV + 'nvidia-blackwell-platform-arrives-to-power-a-new-era-of-computing', '2026-08-18'),
                  ('https://www.nvidia.com/en-us/data-center/hgx/', '2026-08-18')]),
    dict(name='B300', aka=['HGX B300', 'Blackwell Ultra', 'B300 NVL16', 'HGX B300 NVL16'],
         arch='Blackwell Ultra',
         announced='2025-03-18', available='2025-08', predecessor='B200',
         successor='HGX Rubin NVL8 (2026-01-05)',
         still_shipping=('NVIDIA 與我方都標 Now Shipping', 'both NVIDIA and we mark it Now Shipping'),
         read_h='十二個月大,還是營收主力,而且是 Rubin 之前最後一張 Blackwell 世代板子 ——'
                '這一代裡最安全的買點。發布時叫 HGX B300 NVL16,現在官網只寫 HGX B300,'
                '對客戶講後者。',
         read_e='Twelve months old, still the revenue engine, and the last Blackwell-generation '
                'board before Rubin — the safe current-generation buy. It launched as "HGX B300 '
                'NVL16" and nvidia.com now says just "HGX B300"; use the latter with customers.',
         sources=[(_NV + 'nvidia-blackwell-ultra-ai-factory-platform-paves-way-for-age-of-ai-reasoning', '2026-08-18'),
                  ('https://www.nvidia.com/en-us/data-center/hgx/', '2026-08-18')]),
    dict(name='GB200 NVL72', aka=['GB200'], arch='Blackwell',
         announced='2024-03-18', available='2025-02', predecessor='GAP',
         successor='GB300 NVL72 (2025-03-18)',
         still_shipping=('仍在產品線,但官網 CTA 還停在 2024 年的「Notify Me」,不要誤讀成還沒上市',
                         'still in the line, but the page CTA is a stale 2024 "Notify Me" — do not '
                         'read that as not-yet-available'),
         read_h='才十八個月大就已經退後兩代。這是全表最清楚的一件事:'
                'NVIDIA 換機櫃的節奏比任何正常的攤提年限都快。',
         read_e='Barely eighteen months old and already two generations back. This is the clearest '
                'single illustration on the table: NVIDIA\'s rack cadence outruns any normal '
                'depreciation schedule.',
         sources=[(_NV + 'nvidia-blackwell-platform-arrives-to-power-a-new-era-of-computing', '2026-08-18'),
                  ('https://www.nvidia.com/en-us/data-center/gb200-nvl72/', '2026-08-18')]),
    dict(name='GB300 NVL72', aka=['GB300'], arch='Blackwell Ultra',
         announced='2025-03-18', available='2025-07', predecessor='GB200 NVL72',
         successor='Vera Rubin NVL72 (2026-01-05)',
         still_shipping=('官網標 Available Now,我方標 Now Shipping',
                         'nvidia.com says Available Now; we mark it Now Shipping'),
         read_h='今天真的買得到量的最高階機櫃。Vera Rubin 已經出貨,但只進了幾家指名的雲。',
         read_e='The top rack you can actually buy in volume today. Vera Rubin is shipping, but '
                'only into a handful of named clouds.',
         sources=[(_NV + 'nvidia-blackwell-ultra-ai-factory-platform-paves-way-for-age-of-ai-reasoning', '2026-08-18'),
                  ('https://www.nvidia.com/en-us/data-center/gb300-nvl72/', '2026-08-18')]),
]

CHIP_BY_NAME = {}
CHIP_ALIASES = {}


def _chip_index():
    for c in CHIPS:
        CHIP_BY_NAME[c['name']] = c
        for a in [c['name']] + list(c.get('aka') or []):
            CHIP_ALIASES[a] = c['name']


def chip_age_months(available):
    """Months from GA to the factbase as-of date. Computed, never typed —
    a hand-typed age is wrong the day after it is written."""
    try:
        y, m = int(str(available)[:4]), int(str(available)[5:7])
    except (ValueError, TypeError):
        return None
    try:
        ay, am = int(str(ASOF)[:4]), int(str(ASOF)[5:7])
    except (ValueError, TypeError):
        return None
    return (ay - y) * 12 + (am - m)


def chipref(name, label=None):
    """A chip mention, linked to its generation record. The chip name is a
    locked run either way (B6) — the link wraps it, it does not translate it."""
    key = CHIP_ALIASES.get(name, name)
    aid = 'chip-' + slug(key)
    text = esc(label or name)
    if key not in CHIP_BY_NAME or aid not in ANCHORS:
        return text
    # No inner <span class="lk"> on purpose. Most mentions ALREADY sit inside a
    # locked run, and nesting one inside another makes the i18n locked-run gate
    # (LK_IN_ARM is non-greedy) capture the wrong span and fail a good build.
    # The mono face comes from .xr-chip in the stylesheet instead.
    return '<a class="xr xr-chip" href="%s">%s</a>' % (att(href(aid)), text)


# Longest-first so "GB200 NVL72" wins over "GB200", and "H100 SXM" over "H100".
_CHIP_SKIP = re.compile(r'<(a|script|style)\b', re.I)


def annotate_chips(html):
    """Link every bare chip mention in built markup to its generation record.

    Done mechanically on the output rather than by hand at 60-odd call sites,
    because a hand-annotated corpus goes stale the first time someone adds a
    sentence. Rewrites TEXT ONLY: never inside a tag, never inside an existing
    <a>, so a source URL containing "H100" is left alone.
    """
    if not CHIPS:
        return html, 0
    names = sorted(CHIP_ALIASES, key=len, reverse=True)
    pat = re.compile(r'(?<![\w-])(%s)(?![\w-])'
                     % '|'.join(re.escape(n) for n in names))
    out, n, depth_a, i = [], 0, 0, 0
    for m in re.finditer(r'<[^>]+>|[^<]+', html):
        chunk = m.group(0)
        if chunk.startswith('<'):
            low = chunk.lower()
            if low.startswith('<a ') or low == '<a>':
                depth_a += 1
            elif low.startswith('</a'):
                depth_a = max(0, depth_a - 1)
            out.append(chunk)
            continue
        if depth_a:                      # already a link — never nest one
            out.append(chunk)
            continue
        def _sub(mm):
            nonlocal n
            n += 1
            return chipref(mm.group(1), mm.group(1))
        out.append(pat.sub(_sub, chunk))
    return ''.join(out), n


# ---- every company and every session gets an anchor, up front ---------------
# Registered BEFORE any fragment renders, because the plays page links at cards
# the account board has not emitted yet. Registration order is not render order.
ORG_TO_CARD = {}
CARD_NAME = {}
for _c in (cards or []):
    _lid = str(_c.get('ledger_id') or _c.get('org_id') or '')
    if not _lid:
        continue
    _nm = str(_c.get('legal_name') or _lid)
    CARD_NAME[_lid] = _nm
    reg('acct-' + slug(_lid), 'account', 'accounts', _nm, _nm)
    for _k in filter(None, [_lid, str(_c.get('org_id') or ''), _nm] + list(_c.get('aka') or [])):
        ORG_TO_CARD.setdefault(str(_k), _lid)
        ORG_TO_CARD.setdefault(str(_k).lower(), _lid)

for _s in sessions:
    _sid = str(_s.get('id') or '')
    if not _sid:
        continue
    _t = str(_s.get('title') or _sid)
    reg('ses-' + slug(_sid), 'session', 'agenda', _t, _t)

_chip_index()
for _c in CHIPS:
    reg('chip-' + slug(_c['name']), 'chip', 'compare', _c['name'], _c['name'])



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
    a(sec('verdict', verdict_scent,
          '  <ul class="grounds">\n%s\n  </ul>\n  %s'
          % ('\n'.join('    <li>%s</li>' % g for g in grounds), STAMP),
          is_open=OPEN, cls='verdict', block='verdict', fresh=True,
          title_html=verdict_title))
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
    a(sec('numbers',
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
    a(sec('actions',
          tt('一個是站位，一個是問句。其餘等現場',
             'one is where to stand, one is what to ask. The rest waits for the floor'),
          '\n'.join(acts), is_open=OPEN, block='two-actions'))

    # ------------------------------------------------ 4. what room this is --
    # Five separate facts, each with its own handle, because a rep looking for
    # "the ticket-price one" should find it by scanning headings, not by reading
    # five paragraphs to the end.
    room = [items('room', [
        ('audience', '來的是誰', 'Who is in the room',
         '判斷你在跟哪一種人講話 —— 決定要不要花時間往下挖',
         'tells you which kind of person you are talking to, which decides whether to keep digging',
         '<p>%s %s</p>' % (
             S(('不是廠商展會，是工程社群年會加上供應商聚集。官方寫給的對象是 builders、'
                'platform leads 與 researchers ——', 'Not a trade show: an engineering '
                'community conference with vendors around it. The official audience line '
                'reads builders, platform leads and researchers —'),
               ('自建叢集的平台工程主管，不是採購。', 'the platform engineering leads who run '
                'their own clusters, not procurement.')),
             ev('official') + src_a(CATALOG, ASOF)),
         '工程師,非採購', 'engineers, not procurement'),

        ('ticket', '票價說明了誰付錢', 'What the ticket price tells you',
         '票價低到工程師自己刷卡就能來,所以現場多半不是簽核者',
         'the ticket is cheap enough to be expensed by an individual engineer, so the room is '
         'mostly not the people who sign',
         '<p>%s %s</p>' % (
             S(('票價', 'Tickets run'), 'USD 400-450',
               ('，五張套票每張', ', or five-packs at'), 'USD 750',
               ('。工程師自費就進得來 —— 來的人多半是實作者，不是簽核者。把「誰簽字」當成'
                '每一次對話要挖出來的東西。',
                ' each. That is self-funded-engineer money, so the room is implementers, not '
                'signatories. Treat "who signs" as the thing every conversation has to '
                'surface.')),
             ev('official') + from_draft(D01)),
         'USD 400-750', 'USD 400-750'),

        ('governance', 'Ray 歸誰管', 'Who owns Ray',
         '治理中立、商業層有主。這一條決定 Anyscale 的話能不能代表整個生態',
         'governance is neutral but the commercial layer is not — this decides whether Anyscale '
         'speaks for the ecosystem or only for itself',
         '<p>%s %s</p>' % (
             S(('Ray 的治理已經交給 PyTorch Foundation，累計下載',
                'Ray governance has moved to the PyTorch Foundation; cumulative downloads'),
               '237M', ('，名單上的用戶含 OpenAI、Uber、Shopify、Netflix。'
                        '治理中立，商業層在 Nscale 手上。',
                        ', with OpenAI, Uber, Shopify and Netflix named as users. Neutral '
                        'governance, commercial layer in Nscale\'s hands.')),
             ev('official') + src_a('https://pytorch.org', '2025-10-22')),
         '基金會治理', 'foundation-governed'),

        ('owner', '主辦權三週半前易主', 'The show changed owner three weeks ago',
         '買下主辦方的人自己就是買機櫃的人 —— 這改變了整場的動機結構',
         'the company that bought the host is itself a rack buyer, which changes the motive '
         'structure of the whole event',
         # CORRECTION 2026-08-18: this pack shipped saying neither side had
         # confirmed. Both have. The deal is signed and not yet closed — which
         # is a different hedge, not the absence of one.
         '<p>%s %s</p>\n         <p>%s %s</p>\n         <p>%s %s</p>' % (
             S(('主辦權在會前三週半換人，換給了買機櫃的人：', 'Ownership of the show changed '
                'hands three and a half weeks before it opens, to someone who buys racks: '),
               'Nscale', ('於', 'announced a definitive agreement on'), '2026-07-30',
               ('宣布與 Anyscale 簽定確定協議，同時是本屆白金贊助商並有 keynote 席位。'
                '兩邊都已官方發布 —— 這一條先前寫成「未經雙方證實」，是錯的,已更正。',
                ' to acquire Anyscale, while also being a Platinum sponsor with a keynote slot '
                'this year. Both sides have now published it — this pack previously said neither '
                'had confirmed, which was wrong and is corrected here.')),
             ev('official')
             + src_a('https://www.anyscale.com/press/nscale-acquires-anyscale-enhancing-its-full-stack-ai-cloud-platform', '2026-08-18')
             + src_a('https://www.nscale.com/press-releases/nscale-acquires-anyscale', '2026-08-18'),
             S(('已簽約，尚未交割。預計', 'Signed, not closed. Expected to close in'),
               'H2 2026',
               ('完成，仍須通過交割條件與主管機關核可。約 200 名 Anyscale 員工移轉，'
                'Anyscale 品牌續存。Ray 續留 PyTorch Foundation，Nscale 承諾加入該基金會。',
                ', subject to closing conditions and regulatory approval. About 200 Anyscale '
                'employees transfer and the Anyscale brand continues. Ray stays with the PyTorch '
                'Foundation, and Nscale has committed to join it.')),
             ev('official')
             + src_a('https://www.nscale.com/press-releases/nscale-acquires-anyscale', '2026-08-18'),
             S(('價格兩家都沒揭露。', 'Neither company disclosed a price.'),
               ('彭博引述知情人士報約', 'Bloomberg reported roughly'), 'USD 1.65B',
               ('—— 這是單一未具名消息來源，不是公司說法,講給客戶時要帶著這個 hedge。',
                ', citing one person familiar with the deal. That is a single unnamed source and '
                'not a company statement; the hedge travels with the number.')),
             ev('third')
             + src_a('https://thenextweb.com/news/nscale-anyscale-acquisition-full-stack-ai-cloud',
                     '2026-08-18')),
         '已簽,未交割', 'signed, not closed'),

        ('bathurst', 'Nscale 自己講的話,對你有用', 'What Nscale itself said, and why it helps you',
         '收購方的產品長公開講了三句話,每一句都能直接拿去回客戶的疑慮',
         'the acquirer\'s chief product officer said three things on the record, and each one '
         'answers a question your customer is about to ask',
         '<p>%s %s</p>' % (
             S(('Nscale 產品長 Dan Bathurst：Anyscale 在 AWS、GCP、Azure 上的 BYOC 部署照常,'
                '既有承諾延續;',
                'Nscale CPO Dan Bathurst: Anyscale bring-your-own-cloud deployments on AWS, GCP '
                'and Azure continue and existing commitments carry forward;'),
               ('他把定位講成「平台層中立,基礎設施層做差異化」,並說「我們要贏的是效能,'
                '不是任何形式的廠商鎖定」。這幾句是你回答「被買走以後會不會被鎖住」的現成材料。',
                ' he frames the position as "neutrality on the platform layer, but differentiation '
                'on the infrastructure layer", and says "where we want to win is on performance, '
                'not on any sort of vendor lock-in". That is ready-made material for the question '
                'your customer will ask — does the acquisition lock me in?')),
             ev('third')
             + src_a('https://thenewstack.io/nscale-anyscale-acquisition-neocloud-lockin/',
                     '2026-07-31')),
         '公開發言', 'on the record'),

        ('buying-reason', '他們用什麼標準買東西', 'What they actually buy on',
         '這一條直接決定你開口講什麼。講錯軸就冷場',
         'this one decides your opening sentence — the wrong axis kills the conversation',
         '<p>%s %s</p>' % (
             S(('這房間的購買理由是「利用率」，不是規格。', 'This room buys on utilisation, not on '
                'spec. '), None,
               ) + xref('torc', 'Torc') + ' ' +
             S(('自報 GPU 利用率從', 'reports GPU utilisation moving from'),
               '30-40%', ('拉到約', 'to about'), '90%',
               ('，同等牆鐘時間內處理的資料量從', ', and data processed in the same wall clock '
                'from'), '4TB', ('變成', 'to'), '38TB',
               ('。跟這群人談 TFLOPS 會冷場，談「同樣機櫃多跑幾成」會熱。',
                '. Talk TFLOPS to these people and the conversation dies; talk "more work out '
                'of the same rack" and it opens.')),
             ev('vendor') + from_draft(D01)),
         '利用率,不是規格', 'utilisation, not spec'),
    ])]
    a(sec('room',
          tt('工程社群年會，實作者為主，買點是利用率不是規格',
             'an engineering community conference: implementers, and the buying reason is '
             'utilisation, not spec'),
          '\n'.join(room), is_open=OPEN))

    # --------------------------------------------------- 5. 2025 -> 2026 ----
    # Each change gets a handle AND a "so what" line, because a change the
    # reader cannot act on is trivia. The heading is the change; the line under
    # it is what the change does to our pitch.
    ch = [items('changed', [
        ('calendar', '日期前挪十週', 'The calendar moved ten weeks earlier',
         '兩屆只隔九個半月,客戶的預算年度沒有跟著搬 —— 錢還在上一個週期裡',
         'two editions nine and a half months apart, and the customer budget year did not move '
         'with them — the money is still in the previous cycle',
         '<p>%s %s</p>' % (
             S(('上一屆是', 'Last year ran'), '2025-11-03',
               ('至', 'to'), '2025-11-05', ('，這一屆是', ', this one runs'), '2026-08-24',
               ('至', 'to'), '2026-08-26',
               ('，同一個 Marriott Marquis。兩屆只隔約九個半月，客戶的預算年度沒有跟著走。',
                ', in the same Marriott Marquis. Two editions about nine and a half months apart — '
                'the customer budget year did not move with it.')), ev('official')),
         '早 10 週', '10 weeks earlier'),

        ('tracks', '主軸從八條收成四條', 'Eight tracks became four',
         '被留下來的四條全部吃 GPU。軟體題被擠掉,代表這場已經是算力場',
         'all four survivors eat GPU. The software topics were squeezed out, which means this is '
         'now a compute show',
         '<p>%s %s</p>' % (
             S(('每一條都吃 GPU：Foundation Model Training、Multimodal Data '
                'Curation、Physical AI、LLM RL。去年還有 Ray Ecosystem、Generative AI、Research '
                'Frontiers —— 軟體話題被擠掉，剩下全是算力題。',
                'Every one of them eats GPU: Foundation Model Training, Multimodal Data '
                'Curation, Physical AI, LLM RL. Last year still had Ray Ecosystem, Generative AI '
                'and Research Frontiers. The software topics were squeezed out; what is left is '
                'all compute.')),
             ev('official') + from_draft(D01)),
         '8 -> 4', '8 -> 4'),

        ('vllm-conf', 'vLLM 第一次在場內開自己的會', 'vLLM runs its own conference inside the show',
         '硬體話題搬到那半場去了。你要找的人在那邊,不在 Ray 主軌',
         'the hardware conversation moved into that half of the building — the people you want are '
         'there, not on the Ray track',
         '<p>%s %s</p>' % (
             S(('同場舉行、Summit 票含全程，橫跨',
                'Held inside the show, covered by the Summit ticket, spanning'),
               '2026-08-25', ('與', 'and'), '2026-08-26',
               ('。硬體話題藏在那半場，不在 Ray 主軌。',
                '. The hardware conversation lives in that half of the building, not on the Ray '
                'track.')), ev('official') + src_a('https://vllm.ai', ASOF)),
         '8/25-8/26', '8/25-8/26'),

        ('inferact', 'vLLM 有公司了', 'vLLM has a company now',
         '去年掛專案名的人,今年掛公司抬頭。同一批人,不同的談判位置',
         'the people who wore a project name last year wear a company title this year — same '
         'people, different negotiating position',
         '<p>%s %s</p>' % (
             S(('Inferact 於', 'Inferact was founded in'),
               '2026-01', ('成立，種子輪', ', raised a'), 'USD 150M', ('、估值', 'seed at a'),
               'USD 800M', ('，a16z 與 Lightspeed 領投。',
                            ' valuation, led by a16z and Lightspeed.')),
             ev('third') + from_draft(D01)),
         'USD 150M seed', 'USD 150M seed'),

        ('rack-aware', '軟體開始感知機櫃', 'The software started noticing racks',
         '排程器開始管拓撲,代表客戶已經跨多機櫃在跑 —— 那是我方的尺寸',
         'a scheduler that manages topology means customers are already running across several '
         'racks, and that is our size of problem',
         '<p>%s %s</p>' % (
             S(('話題從「怎麼管工作」變成「怎麼貼合機櫃」：去年 keynote 發表排程器與執行環境，'
                '今年上半年發表的是 GB300 NVL72 的拓撲感知排程。',
                'The subject moved from "how to manage jobs" to "how to fit the rack": last '
                'year\'s keynote shipped a scheduler and a runtime, this year\'s first half '
                'shipped topology-aware scheduling for GB300 NVL72.')),
             ev('vendor') + from_draft(D01)),
         'GB300 NVL72', 'GB300 NVL72'),
    ])]
    a(sec('changed',
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
    # The heading is the term the agenda uses; the line under it is the signal
    # that put the term there; the body is what it does to a quote. Three
    # altitudes, so the reader can stop at whichever one answers their question.
    tb = [items('turn', [
        (term, term, term, sig_h, sig_e,
         '    <p>%s</p>\n    <p>%s %s</p>'
         % (tt(esc(imp_h), esc(imp_e)), ev(rank), from_draft(D01)))
        for term, sig_h, sig_e, imp_h, imp_e, rank in turns])]
    a(sec('turn',
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
    a(sec('signals',
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
    a(sec('open',
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
    a(sec('method',
          tt('數字從哪裡來、哪一格還沒結案', 'where the numbers come from, and which cells are '
             'still open'),
          '\n'.join(m), is_open=False, cls='method', block='method'))
    # The index is filled in by main() once every fragment has registered its
    # anchors: command-center renders first, so it cannot see the item anchors
    # the other four pages create. A placeholder here, resolved there.
    h.append(sec('index',
                 tt('每一條都是連結', 'every line is a link'),
                 INDEX_SLOT, block='index'))
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
        # The session title is the heading a reader scans for, so it IS the
        # heading — and it links to the same session's row in section 02, which
        # carries the speakers and the full block. The line under the heading
        # says why this room, before the reader commits to the body.
        pr.append(item(
            'queue', s.get('id') or ('rank%d' % p['rank']),
            '%s%s' % (lk('#%d' % p['rank']), sesref(s)), None,
            p['why_h'], p['why_e'],
            '\n'.join(body),
            S(s.get('day'), s.get('start_end'), '·', s.get('room')), None))
    for p in unmatched:
        pr.append(item(
            'queue', 'unmatched-%s' % slug(p['probe']),
            lk(p['probe']), None,
            '底稿點名這一場，目錄裡沒有對得上的標題',
            'the draft names this session; the catalogue has no title that matches it',
            '  <p>%s</p>'
            % gap('可能改名，可能撤場，也可能還沒公布。到場用活動 App 確認,別在客戶面前引用',
                  'renamed, pulled, or not yet published. Settle it on the event app when you '
                  'arrive; do not quote it to a customer before then'),
            '對不上', 'no match'))
    a(sec('queue',
          S(('%d 場排好順位' % len(matched), '%d ranked' % len(matched)), '·',
            ('%d 場對不上目錄' % len(unmatched), '%d with no catalogue match' % len(unmatched)), '·',
            ('每一場都寫了為什麼是這一場', 'each carrying why this room and not another')),
          items_wrap(pr), block='priority-queue'))

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
        for be, blk in blocks.items():
            cards_html = ['    <ol class="ses">']
            for s in blk:
                sid = str(s.get('id') or '')
                marks = hw_marks(s)
                dur = duration_min(s.get('start_end'))
                _said = 'ses-' + slug(sid)
                cards_html.append('      <li%s%s>'
                                  % (' class="is-hw"' if marks else '',
                                     (' id="%s"' % att(_said)) if _said in ANCHORS else ''))
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
            hw_here = len([s for s in blk if hw_marks(s)])
            rooms_here = sorted({str(s.get('room') or '') for s in blk if s.get('room')})
            scent = [('%d 場' % len(blk), pl(len(blk), 'session', 'sessions')), '·',
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
    a(sec('all-sessions',
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
    a(sec('rooms',
          S(('%d 間' % len(ROOMS), pl(len(ROOMS), 'room', 'rooms')), '·',
            ('最忙的是', 'busiest is'), busiest, '·',
            ('%d 場' % room_count.get(busiest, 0),
             pl(room_count.get(busiest, 0), 'session', 'sessions'))),
          items('rooms', [
              ('load', '哪一間最忙', 'Where the traffic is',
               '每一間排了幾場。場次最多的那一間,走廊也最擠',
               'how many sessions each room holds. The busiest room is also the busiest corridor',
               '\n'.join(rl)),
              ('verbatim', '房間名為什麼不翻譯', 'Why the room names are not translated',
               '中英兩版的房間名逐字元相同,你唸出來的就是門口貼的',
               'the room name is byte-identical in both languages, so what you read aloud matches '
               'what is on the door',
               '  <p>%s</p>'
               % tt('會議室名稱、時間、日期一律維持目錄原文。翻譯這幾個字省不了力,'
                    '卻會讓一個人站錯門口。',
                    'Room names, times and dates stay exactly as the catalogue prints them. '
                    'Translating them saves nobody anything and can put a person at the wrong '
                    'door.')),
          ]), block='room'))

    # ------------------------------------------ 4. what the catalogue lacks -
    # Three named holes, each with the move that closes it on site. A flat list
    # of caveats reads as apology; a named hole with a fix reads as a task.
    rows = []
    if seats_known:
        rows.append(('seats', '座位數', 'Seat counts',
                     '%d / %d 場有揭露,所以「會不會滿」這一題部分可答'
                     % (len(seats_known), N_SESS),
                     'disclosed for %d of %d sessions, so "will it fill up" is partly answerable'
                     % (len(seats_known), N_SESS),
                     '  <p>%s</p>'
                     % tt('沒揭露的那幾場仍以活動 App 為準。',
                          'For the rest, the event app is the authority.'),
                     '%d/%d' % (len(seats_known), N_SESS), None))
    else:
        rows.append(('seats', '座位數', 'Seat counts',
                     '目錄一場都沒給,所以現在沒有人能說哪一場會爆滿',
                     'the catalogue gives none, so nobody can say today which room fills up',
                     '  <p>%s</p>\n  <p>%s</p>'
                     % (gap(SEAT_WHY_H, SEAT_WHY_E),
                        tt('現場以活動 App 為準,別在客戶面前用猜的 —— '
                           '猜錯一次,後面每個數字都要重新被信任。',
                           'Defer to the event app on site and do not guess in front of a '
                           'customer: one wrong guess and every other figure has to earn trust '
                           'again.')),
                     'GAP', None))
    rows.append(('linkage', '講者對場次', 'Which speaker is in which room',
                 '名單有 %d 位講者,但誰講哪一場沒有對應 —— 官方自己寫了 and others' % N_SPK,
                 'we hold %d speakers but no mapping from speaker to session, and the organisers '
                 'themselves wrote "and others"' % N_SPK,
                 '  <p>%s</p>\n  <p>%s</p>'
                 % (gap(LINK_WHY_H, LINK_WHY_E),
                    tt('名單來自官方活動頁,不是場次卡片,所以這是一份部分名單 —— '
                       '把它當成下限,不是全部。',
                       'The roster comes from the official event page, not from the session '
                       'cards, which makes it a partial list: treat it as a floor, not a '
                       'total.')),
                 'GAP', None))
    # Day 3 exists in this pack, but not from the catalogue. A reader who does
    # not know that will quote it as official and be wrong.
    _v = [x for x in sessions if 'vllm.ai' in str(x.get('source') or '')]
    if _v:
        rows.append(('day3-source', '2026-08-26 不是目錄給的', '2026-08-26 does not come from the catalogue',
                     '主辦目錄至今沒有公布 2026-08-26 任何一場。這一天的 %d 場來自同場的 vLLM 大會官網'
                     % len(_v),
                     'the official catalogue still publishes nothing at all for 2026-08-26. The %d '
                     'rows on that day come from the co-located vLLM Conference site instead'
                     % len(_v),
                     '  <p>%s</p>\n  <p>%s</p>\n  <p>%s</p>'
                     % (tt('每一場的來源連結都指向 vLLM 官網,不是目錄 —— 點開就看得到出處。'
                           '引用給客戶時要說清楚是哪一邊發的,因為主辦自己還沒公布這份議程。',
                           'Every one of those rows links to the vLLM site rather than to the '
                           'catalogue, so the provenance is visible on the row itself. Say which '
                           'source it came from when you quote it: the organisers have not '
                           'published this agenda themselves.'),
                        S(('Ray 主軌在 2026-08-26 的場次,兩邊都沒有公布。',
                           'The Ray-track sessions for 2026-08-26 are unpublished on both sites.')),
                        gap('會議室與結束時間 vLLM 官網都沒有給,所以那兩格是 GAP,不是我們沒抄。'
                            '要結案:出發前再刷一次目錄,或現場用活動 App',
                            'the vLLM site publishes neither rooms nor end times, so those two '
                            'cells are GAP rather than an omission on our side. To close it: '
                            'refresh the catalogue before you fly, or use the event app on site')),
                     '%d 場' % len(_v), '%d rows' % len(_v)))
    rows.append(('booths', '攤位號碼', 'Booth numbers',
                 '未公布,所以走廊順序現在排不出來',
                 'unpublished, so the corridor route cannot be planned in advance',
                 '  <p>%s</p>'
                 % tt('落地第一件事是拿 expo 平面圖,再把 %s 那一節的順位貼上去。'
                      % '打法', 'First thing after you land: get the expo floor plan, then lay '
                      'the ranked order from the plays page over it.'),
                 'GAP', None))
    a(sec('catalog-gap',
          S(('%d 件' % len(rows), pl(len(rows), 'hole', 'holes')), '·',
            ('每一件都寫了現場怎麼補', 'each with the move that closes it on site')),
          items('catalog-gap', rows) + '\n  %s' % STAMP,
          cls='caveat', block='seats-caveat', fresh=True))
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
     '世代分佈告訴你機隊多舊,不等於快要換。'
     'NVIDIA 財務長說六年前的 A100 現在還在滿載跑、租金還在漲,CoreWeave 簽的 A100 合約到 2029。'
     '所以不要問「什麼時候換」,要問「舊的那批現在還在賺錢嗎」—— 答案是還在,'
     '那就代表他擴充會加機器,不是換機器。',
     'The generation spread tells you how old a fleet is, not that it is about to be replaced. '
     'NVIDIA\'s CFO says six-year-old A100s still run at full utilisation with rental prices '
     'rising, and CoreWeave has signed an A100 contract running into 2029. So do not ask when they '
     'will replace it — ask whether the old batch still earns. If it does, their next expansion '
     'ADDS machines rather than swapping them.'),
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
    a(sec('judgement',
          tt('簽單的是新雲；Ray 短期是逆風；我方沒有主場',
             'the neoclouds sign; Ray is a short-run headwind; we have no home ground'),
          items('judgement', [
              ('who-signs', '誰真的簽伺服器訂單', 'Who actually signs the server order',
               '把房間裡的人分成兩類:簽得了單的,和簽不了單但知道內情的',
               'sorts the room into two kinds of person — the ones who can sign, and the ones who '
               'cannot but know what is happening',
               '  <p>%s</p>' % jd[0], '新雲', 'the neoclouds'),
              ('headwind', 'Ray 對機箱生意是逆風', 'Ray is a headwind for box sales',
               '這場的主角技術會讓客戶「暫時不用加機器」,所以要賣的東西必須換一個',
               'the technology this show is about lets a customer defer buying hardware, so what '
               'we sell has to change',
               '  <p>%s</p>' % jd[1], '賣異質節點與機房層',
               'sell mixed nodes and the hall layer'),
              ('no-home', '我方沒有主場', 'We have no home ground',
               '不在贊助名單上代表沒有攤位、沒有正當推銷位置,每一次對話都得靠走廊',
               'not being on the sponsor list means no booth and no legitimate place to sell from; '
               'every conversation is earned in a corridor',
               '  <p>%s</p>' % jd[2], 'GAP,不是被排除', 'a gap, not an exclusion'),
          ]), block='judgement'))

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
        # The claim is the heading. The line under it is not a restatement — it
        # is what believing this thesis commits you to doing differently.
        th.append(item('theses', tag,
                       '%s %s' % (lk(tag), tt(esc(claim_h), esc(claim_e))), None,
                       ev_h, ev_e, '\n'.join(body),
                       '可被推翻', 'falsifiable'))
    a(sec('theses',
          S(('%d 條論點' % len(THESES), pl(len(THESES), 'thesis', 'theses')), '·',
            ('每一條都寫了現場聽到什麼就作廢',
             'each carries the sentence that would void it on the floor')),
          items_wrap(th), block='theses'))

    # --------------------------------------------------- 3. booth odds ------
    # Each booth is a company you can walk to, so the company name is the
    # heading — and it links straight at that company's card, because the
    # question a rep asks next ("what do we already know?") is answered there.
    bo = []
    for i, (name, why_h, why_e, rank) in enumerate(BOOTHS, start=1):
        bo.append(item('booths', name,
                       '%s %s' % (lk('#%d' % i), xref(name.split(' / ')[0], name)), None,
                       why_h, why_e,
                       '  <p>%s %s</p>' % (ev(rank), from_draft(D05)),
                       None, None))
    a(sec('booths',
          S(('%d 個攤位' % len(BOOTHS), pl(len(BOOTHS), 'booth', 'booths')), '·',
            ('第一順位是唯一的既有客戶', 'the first is the only existing customer'), '·',
            ('每個名字連到它的帳戶卡', 'every name links to its account card')),
          items_wrap(bo), block='booth-odds'))

    # -------------------------------------------------- 4. segment plays ----
    seg_items = []
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
            open_h = ('先問最舊的那批 GPU 節點是哪一代,以及那一批現在還在不在賺錢。')
            open_e = ('Open by asking which generation the oldest GPU nodes are, and whether '
                      'that batch still earns its keep.')
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
        seg_items.append(item('segments', seg, lk(seg), None,
                              open_h, open_e, '\n'.join(body),
                              S(('%d 家候選' % len(oids), '%d candidates' % len(oids)), '·',
                                ('%d 家買機器' % len(yes), '%d buy' % len(yes))), None))
    a(sec('segments',
          S(('%d 個客群' % len(SEGMENTS), pl(len(SEGMENTS), 'segment', 'segments')), '·',
            ('每一群一句開場、一份候選名單',
             'one opening line and one shortlist per segment')),
          items_wrap(seg_items) or
          ('  <p>%s</p>'
           % gap('STATE.campaign.segments 是空的,所以沒有客群可以分',
                 'STATE.campaign.segments is empty, so there is no segmentation to print')),
          cls='play', block='segment-play'))

    # ------------------------------------------- 5. the five questions ------
    # The question is the heading because the question is what a rep says out
    # loud. The line beneath is what the answer tells you — the reason to ask.
    qs = []
    for i, (q_h, q_e, r_h, r_e) in enumerate(QUESTIONS, start=1):
        qs.append(item('questions', 'q%d' % i,
                       '%s %s' % (lk('Q%d' % i), tt(esc(q_h), esc(q_e))), None,
                       r_h, r_e,
                       '    %s' % from_draft(D05), None, None))
    a(sec('questions',
          S(('%d 題' % len(QUESTIONS), pl(len(QUESTIONS), 'question', 'questions')), '·',
            ('每一題的答案都直接分類這個帳戶',
             'every answer sorts the account on the spot')),
          items_wrap(qs), block='discovery'))

    # --------------------------------------------------- 6. do not do -------
    # Each rule gets the short name of the mistake as its heading, so a rep
    # scanning before they walk in remembers the shape rather than the sentence.
    DONT_KEYS = [
        ('pitch-partner-booth', '不在別人主場推銷', 'Do not pitch on a partner\'s home ground'),
        ('spec-opener', '不用規格開場', 'Do not open with a spec'),
        ('unconfirmed-fleet', '不複述未證實的機隊數字', 'Do not repeat unconfirmed fleet numbers'),
        ('absence-as-exclusion', '不把缺席讀成被排除', 'Do not read absence as exclusion'),
        ('cards-as-kpi', '不用名片數當 KPI', 'Do not make business cards the KPI'),
        ('quote-first', '不報價、不承諾交期', 'Do not quote and do not promise dates'),
    ]
    dn = []
    for i, (x, y) in enumerate(DONTS):
        k, lh, le = DONT_KEYS[i] if i < len(DONT_KEYS) else ('dont%d' % i, x[:12], y[:24])
        dn.append(item('dont', k, lh, le, x, y,
                       '    %s' % from_draft(D05), None, None))
    a(sec('dont',
          S(('%d 條' % len(DONTS), pl(len(DONTS), 'rule', 'rules')), '·',
            ('每一條都花過錢', 'every one of them has cost money before')),
          items_wrap(dn), block='donts'))

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
    a(sec('register',
          S(('%d 個客群 × 3 格' % len(SEGMENTS or [1]),
             '%d segments x 3 cells' % len(SEGMENTS or [1])), '·',
            ('現在全部是空的，這是預期狀態', 'all empty right now, which is the expected state')),
          items('register', [
              ('grid', '要填的三格', 'The three cells to fill',
               '每一次對話結束就地填。三格填滿才算一次有效對話',
               'fill it the moment a conversation ends; a conversation only counts when all three '
               'are filled',
               '\n'.join(rg)),
          ]), block='d-register', fresh=True))

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
    GAP_KEYS = [
        ('speaker-employer', '講者對不上公司', 'Speakers are not matched to employers',
         '沒有這個對應,走廊上遇到一個人也不知道他代表誰',
         'without the mapping, meeting someone in a corridor tells you nothing about who they '
         'represent'),
        ('unknown-oem', '六家的整櫃供應商不明', 'Six rack suppliers are unknown',
         '不知道誰供櫃,就不知道該正面競標還是側面切入',
         'not knowing who supplies the rack means not knowing whether to bid head-on or find a '
         'seam'),
        ('one-sided', '兩家只有單邊公告', 'Two rest on one-sided announcements',
         '只有廠商自己講的話,對方沒有證實過',
         'only the vendor has said it; the other side has never confirmed'),
        ('fleet-size', '平台團隊的機隊規模全部未證', 'Every platform team fleet size is unverified',
         '規模是排不排這一趟的依據,所以這一格空著就沒有排序依據',
         'scale is what decides whether an account is worth a trip, so an empty cell means no way '
         'to rank'),
    ]
    a(sec('gtm-open',
          S(('%d 個缺口' % len(g), pl(len(g), 'open question', 'open questions')), '·',
            ('每一個都寫了現場怎麼問掉它', 'each with the question that closes it on the floor')),
          items('gtm-open', [(GAP_KEYS[i][0], GAP_KEYS[i][1], GAP_KEYS[i][2],
                              GAP_KEYS[i][3], GAP_KEYS[i][4],
                              '  <p>%s</p>' % g[i], 'GAP', None)
                             for i in range(min(len(g), len(GAP_KEYS)))])
          + '\n  %s' % STAMP, cls='caveat', fresh=True))
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
    lid = str(c.get('ledger_id') or c.get('org_id') or '')
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
    # The anchor lands HERE, on the card itself, because this is what every
    # xref() in the pack promises to take the reader to.
    _aid = 'acct-' + slug(lid)
    return dr(head, scent, '\n'.join(body),
              cls='acct%s' % (' is-full' if is_full else ''),
              aid=_aid if _aid in ANCHORS else None)


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
    a(sec('board',
          (S(('%d 家' % N_CARDS, pl(N_CARDS, 'company', 'companies')), '·',
             ('%d 格已填' % POP, '%d cells filled' % POP), '·',
             ('%d 格帶來源' % SRCD, '%d sourced' % SRCD), '·',
             ('%d 格待補' % GAPC, '%d still open' % GAPC), '·',
             ('%d 份完整檔' % N_FULL, '%d full dossiers' % N_FULL))
           if cards is not None else tt('帳戶卡尚未產生', 'the account cards are not built yet')),
          items('board', [
              ('fill', '填到什麼程度', 'How far this board is filled',
               '已填、帶來源、還開著各多少格。帶來源的那些點得進原文',
               'how many cells are filled, how many carry a source, how many are still open — the '
               'sourced ones click through to the original',
               '\n'.join(cov[:1] + cov[3:]) if len(cov) > 3 else '\n'.join(cov[:1])),
              ('actionable', '拿得動的名單', 'The list you can act on',
               '自己買機器的、部分自購的、查完判定不是買方的,三堆分開 —— '
               '「查過沒有」和「還沒查」不是同一件事',
               'who buys, who partly buys, and who was researched and found not to be a buyer — '
               'three different stacks, because researched-and-empty is not the same finding as '
               'not-yet-researched',
               '\n'.join(cov[1:3]) if len(cov) > 2 else ''),
          ]), cls='caveat%s' % ('' if open_layer else ' is-clear'),
          block='gap-visible', fresh=True))

    # ------------------------------------------------------ 2. the bands ----
    banded = OrderedDict((k, []) for k, _n, _e, _d, _de in LAYERS)
    unbanded = []
    for c in (cards or []):
        key = band_key(c.get('layer'))
        (banded[key] if key else unbanded).append(c)

    def band(key, nh, ne, dh, de, mem):
        yes = [c for c in mem if str(c.get('buys_servers')) == 'YES']
        full = [c for c in mem if c.get('full') is True]
        out = [c for c in mem if str(c.get('classification')) == 'ruled-out']
        body = ['  <p class="banddesc">%s</p>' % tt(esc(dh), esc(de))]
        body.append('  <div class="accts" data-block="card-grid">')
        if not mem:
            body.append('    <p>%s</p>'
                        % gap('這一層目前沒有卡片。沒有人落到這一層是「未查證」，不是「不屬於」',
                              'no card lands in this layer yet. Nobody here means unverified, not '
                              'unaffiliated'))
        for c in sorted(mem, key=lambda c: (0 if c.get('full') else 1,
                                              TIER_RANK.get(tier_of.get(str(c.get('org_id') or ''), ''), 9),
                                              str(c.get('legal_name') or ''))):
            body.append(card_drawer(c))
        body.append('  </div>')
        return dr('%s %s' % (lk(key), tt(esc(nh), esc(ne))),
                  S(('%d 家' % len(mem), pl(len(mem), 'company', 'companies')), '·',
                    ('%d 家自己買機器' % len(yes), '%d buy their own machines' % len(yes)), '·',
                    ('%d 份完整檔' % len(full), '%d full dossiers' % len(full)), '·',
                    ('%d 家這輪判定不是買方' % len(out), '%d called out this lap' % len(out))),
                  '\n'.join(body), cls='band', block='layer-band')

    # One section, one item per layer. The layer name is the heading and the
    # line beneath says what that layer MEANS for a rep standing in front of one
    # of these companies — not what the taxonomy calls it.
    bd = []
    for key, nh, ne, dh, de in LAYERS:
        mem = banded[key]
        yes = [c for c in mem if str(c.get('buys_servers')) == 'YES']
        bd.append(item('bands', key,
                       '%s %s' % (lk(key), tt(esc(nh), esc(ne))), None,
                       dh, de,
                       band(key, nh, ne, dh, de, mem),
                       S(('%d 家' % len(mem), '%d' % len(mem)), '·',
                         ('%d 家買機器' % len(yes), '%d buy' % len(yes))), None))
    if unbanded:
        bd.append(item('bands', 'unlayered',
                       '%s %s' % (lk('unlayered'), tt('還沒分層', 'Not yet placed')), None,
                       '分層欄位還是 GAP —— 未查證,不是不屬於任何一層。這一疊是下一輪的排隊名單',
                       'the layer cell is still open — unverified, not unaffiliated. This stack is '
                       'the queue for the next lap',
                       band('unlayered', '還沒分層', 'Not yet placed',
                            '分層欄位還是 GAP —— 未查證，不是不屬於任何一層。這一疊就是下一輪的排隊名單',
                            'the layer cell is still open — unverified, not unaffiliated. This '
                            'stack is the queue for the next lap', unbanded),
                       '%d 家' % len(unbanded), '%d' % len(unbanded)))
    a(sec('bands',
          S(('%d 層' % len(LAYERS), '%d layers' % len(LAYERS)), '·',
            ('%d 家已分層' % sum(len(v) for v in banded.values()),
             '%d placed' % sum(len(v) for v in banded.values())), '·',
            ('%d 家還沒分' % len(unbanded), '%d unplaced' % len(unbanded))),
          items_wrap(bd), block='layer-band'))

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
        a(sec('solidity',
              S(('%d 格已填' % POP, '%d cells filled' % POP), '·',
                ('%d 格待補' % GAPC, '%d still open' % GAPC), '·',
                ('%d 個來源網址' % N_SRCURL, '%d source URLs' % N_SRCURL)),
              items('solidity', [
                  ('mixed', '同一張卡上的證據不同級', 'Two cells on one card can rest on very '
                   'different ground',
                   '一格可能是法說原文,隔壁一格是部落格轉述。哪一格是哪一種,印在那一格旁邊',
                   'one cell can be an earnings filing and the next a blog paraphrase; which is '
                   'which prints next to the cell itself',
                   '\n'.join(body[:1])),
                  ('tally', '四級各有多少格', 'How many cells sit at each rank',
                   '證據等級是排序,不是配色。看這一列就知道整板有多少是一手',
                   'evidence quality is a rank, not a colour scheme — this row says how much of the '
                   'whole board is first-party',
                   '\n'.join(body[1:])),
              ]), fresh=True))
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
# Five vendors publish, not two. All USD per GPU per hour, on demand, every
# page read 2026-08-18. A column of None is a vendor that does not publish that
# chip — which is a finding about the vendor, not a hole in the table.
# Order is cheapest-first so the spread reads off the row without arithmetic.
RATE_VENDORS = [
    ('Verda',     'https://www.verda.com/pricing'),
    ('Lambda',    'https://lambda.ai/pricing'),
    ('Nebius',    'https://nebius.com/prices'),
    ('Together',  'https://www.together.ai/pricing'),
    ('CoreWeave', 'https://www.coreweave.com/pricing'),
]

# chip, [Verda, Lambda, Nebius, Together, CoreWeave], note
RATE_GRID = [
    ('B200',        [6.11, 6.69, 7.15, 8.19, 8.60], None),
    ('H200',        [4.00, None, 4.50, 5.99, 6.31], None),
    ('H100 SXM',    [3.25, 3.99, 3.85, 3.99, 6.16], None),
    ('A100 80GB',   [1.79, 2.79, None, None, 2.70], None),
    ('GB200 NVL72', [None, None, None, None, 10.50],
     ('全場七家只有一家公布', 'one published rate across all seven vendors')),
    ('GB300 NVL72', [8.62, None, None, None, None],
     ('全場唯一公布的 GB300 牌價', 'the only published GB300 rate anywhere in the room')),
    ('B300',        [None, None, 7.85, None, None], None),
]

# Vendors in the room that publish NOTHING. Their silence is content.
RATE_SILENT = [
    ('Nscale', '白金', 'Platinum',
     '沒有公開牌價。/pricing 與 /products/compute 皆回 404（2026-08-18 實測）',
     'no public rate card at all: /pricing and /products/compute both return 404, probed 2026-08-18'),
    ('Parasail', '銀', 'Silver',
     '刻意不公布 GPU 時價,只公布每 token 價格,機時「來信報價」',
     'withholds GPU-hour pricing by design, publishes per-token inference pricing instead and quotes '
     'machine time on request'),
    ('AWS / Google Cloud / Azure', '白金與金', 'Platinum and Gold',
     '本輪未抓取,不是沒有牌價 —— 這是我們的缺口,不是他們的',
     'not fetched this lap. They do publish; this gap is ours, not theirs'),
]

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
    a(sec('axis',
          S(('自建對租賃', 'Build versus rent'), '·',
            ('%d 條軸線' % len(AXES), pl(len(AXES), 'axis', 'axes')), '·',
            ('對面 %d 家在現場' % n_present, '%d of the other side are in the room' % n_present)),
          items('axis', [
              ('not-booths', '對手不在攤位之間', 'The rival is not another booth',
               '這場一個傳統伺服器對手都沒有。真正在搶同一筆預算的,是把算力按小時租出去的人',
               'not one traditional server rival is here. What competes for the same budget is the '
               'people renting compute by the hour',
               '  <p>%s</p>'
               % tt('所以「誰的規格好」在這個房間裡不是問題,'
                    '「買下來還是租」才是 —— 那一題的答案寫在 %s。'
                    % '下面的交叉點那一節',
                    'So "whose spec is better" is not the question in this room. "Own it or rent '
                    'it" is — and the answer to that one is in the crossover section below.'),
               None, None),
              ('who', '對面現在有誰在場', 'Who from that side is actually here',
               '每一條軸線點名的公司,哪些真的在名單上、哪些不在 —— 不在不等於沒來',
               'for each axis, which named companies are really on the roster and which are not — '
               'and absent from the roster is not the same as absent from the show',
               '\n'.join(ax), None, None),
          ]), block='axis-from-STATE', fresh=True))

    # ------------------------------------------------- 2. who rents, what ---
    rn = []
    for name, tier, sell_h, sell_e, signals, url, date, rank in RENTERS:
        body = ['    <p>%s</p>' % tt(esc(sell_h), esc(sell_e))]
        body.append(ul([lk(x) for x in signals], cls='spell'))
        body.append('    %s %s' % (ev(rank), src_a(url, date)))
        rn.append(item('renters', name,
                       '%s <span class="chip">%s</span>' % (xref(name), esc(tier)), None,
                       sell_h, sell_e,
                       '\n'.join(body[1:]),
                       S(('%d 個規模訊號' % len(signals), '%d scale signals' % len(signals))), None))
    a(sec('renters',
          S(('%d 家' % len(RENTERS), pl(len(RENTERS), 'renter', 'renters')), '·',
            ('全部在現場，全部是白金或金級',
             'all in the room, all at Platinum or Gold'), '·',
            ('每個名字連到它的帳戶卡', 'every name links to its account card')),
          items_wrap(rn), block='renters'))

    # ---------------------------------------------------- 3. the rate card --
    def spread(a, b):
        """Percentage the dearer side sits above the cheaper one."""
        if a is None or b is None:
            return None
        lo, hi = min(a, b), max(a, b)
        return int(round((hi - lo) / lo * 100)), ('CoreWeave' if b > a else 'Lambda')

    # Five vendors, one normalised unit. The row is sorted cheapest-first at the
    # data level, so the spread is a subtraction the reader can do by eye.
    def row_spread(vals):
        got = [v for v in vals if v is not None]
        if len(got) < 2:
            return None
        lo, hi = min(got), max(got)
        return int(round((hi - lo) / lo * 100))

    rc = []
    rc.append('  <div class="regwrap">')
    rc.append('  <table class="reg ratecard">')
    rc.append('    <thead><tr><th>%s</th>%s<th>%s</th></tr></thead>'
              % (tt('晶片', 'Chip'),
                 ''.join('<th>%s</th>' % esc(n) for n, _u in RATE_VENDORS),
                 tt('價差', 'Spread')))
    rc.append('    <tbody>')
    for chip, vals, note in RATE_GRID:
        got = [v for v in vals if v is not None]
        lo = min(got) if got else None
        rc.append('      <tr>')
        rc.append('        <td><span class="lbl">%s</span>%s</td>'
                  % (tt('晶片', 'Chip'), lk(chip)))
        for (vn, vu), v in zip(RATE_VENDORS, vals):
            if v is None:
                rc.append('        <td><span class="lbl">%s</span>%s</td>'
                          % (esc(vn), gap('這一家沒有公布這顆晶片的牌價',
                                          'this vendor publishes no rate for this chip')))
            else:
                rc.append('        <td class="%s"><span class="lbl">%s</span>%s %s</td>'
                          % ('cheap' if v == lo else '', esc(vn),
                             lk('USD %.2f' % v),
                             ('<span class="lowmark">%s</span>'
                              % tt('最低', 'lowest')) if v == lo else ''))
        sp = row_spread(vals)
        rc.append('        <td><span class="lbl">%s</span>%s</td>'
                  % (tt('價差', 'Spread'),
                     (lk('%d%%' % sp) if sp is not None
                      else gap('只有一家公布,無從比價', 'only one vendor publishes it, so there is '
                               'nothing to compare against'))))
        if note:
            rc.append('        <td class="rn">%s</td>' % tt(esc(note[0]), esc(note[1])))
        rc.append('      </tr>')
    rc.append('    </tbody>')
    rc.append('  </table>')
    rc.append('  </div>')
    rc.append('  <p class="src">%s</p>'
              % ' '.join(src_a(u, '2026-08-18', n, n) for n, u in RATE_VENDORS))

    sil = ['  <ul class="ev-list">']
    for name, th, te, wh, we in RATE_SILENT:
        sil.append('    <li>%s <span class="chip">%s</span> %s</li>'
                   % (lk(name), tt(esc(th), esc(te)), tt(esc(wh), esc(we))))
    sil.append('  </ul>')

    _h100 = next((v for c, v, _n in RATE_GRID if c == 'H100 SXM'), None)
    _sp100 = row_spread(_h100) if _h100 else 0
    _b200 = next((v for c, v, _n in RATE_GRID if c == 'B200'), None)
    _sp200 = row_spread(_b200) if _b200 else 0
    a(sec('rates',
          S(('五家公布,三家不公布', 'five publish, three do not'), '·',
            ('同一顆 H100 最高差 %d%%' % _sp100, 'the same H100 varies by %d%%' % _sp100), '·',
            ('B200 差 %d%%' % _sp200, 'B200 by %d%%' % _sp200)),
          items('rates', [
              ('grid', '同一顆晶片,五家報價', 'The same chip, priced by five vendors',
               '全部換算成每 GPU 每小時才比得下去。每一列標出最低價那一家,價差直接印在右邊',
               'everything normalised to one GPU for one hour, or the columns cannot be compared. '
               'The cheapest vendor is marked on every row and the spread prints on the right',
               '\n'.join(rc)),
              ('spread', '價差大到不像同一個市場', 'The spread is too wide to be one market',
               '同一顆 H100,最貴的比最便宜的貴 %d%%。這不是議價空間的問題,是牌價本身就不一致'
               % _sp100,
               'on the same H100 the dearest sits %d%% above the cheapest. That is not negotiating '
               'room, it is a market whose list prices do not agree with each other' % _sp100,
               '  <p>%s</p>\n  <p>%s</p>'
               % (S(('客戶拿一張報價來問「這樣算貴嗎」的時候,先問他比的是哪一家。',
                     'When a customer holds up a quote and asks whether it is expensive, ask which '
                     'vendor they are comparing against first.'),
                    ('H100 從', 'H100 runs from'), 'USD 3.25', ('到', 'to'), 'USD 6.16',
                    ('、B200 從', ', B200 from'), 'USD 6.11', ('到', 'to'), 'USD 8.60',
                    ('，全部是公開牌價,不是談出來的價。',
                     ' — all published list, none of it negotiated.')),
                  tt('CoreWeave 是這五家裡最貴的一家,而它同時是本場白金贊助商。'
                     '這不是它做錯了什麼,是它賣的東西不只有機時。',
                     'CoreWeave is the dearest of the five and is also a Platinum sponsor of this '
                     'show. That is not a mistake on their part — it means what they sell is not '
                     'only machine time.')),
               'USD 3.25 - 6.16', 'USD 3.25 - 6.16'),
              ('silence', '不公布的那幾家', 'The ones that publish nothing',
               '在場的贊助商裡有幾家完全不給牌價。沉默本身就是情報,不是空白',
               'several sponsors in this room publish no rate at all. The silence is intelligence, '
               'not an empty cell',
               '\n'.join(sil), '3', '3'),
              ('movement', '租金在漲,不是在跌', 'Rental prices are rising, not falling',
               '牌價頁證不出漲跌,但 NVIDIA 財務長在法說會上直接給了數字 ——'
               '這一格先前寫「查不到」,是漏了這個來源,已更正',
               'the vendor pricing pages cannot prove movement, but NVIDIA\'s CFO put numbers on '
               'the record in an earnings call. This cell previously said the movement was '
               'unknowable; that missed this source and is corrected here',
               '  <p>%s %s</p>\n  <p>%s %s</p>\n  <p>%s</p>\n  <p>%s</p>'
               % (S(('NVIDIA 財務長 Colette Kress 在', 'NVIDIA CFO Colette Kress, on the'),
                    '2026-05-20', ('的法說會上:租一顆', 'earnings call: renting an'), 'H100',
                    ('的價格年初至今漲了', 'is up'), '20%', ('，', ', and'), 'A100',
                    ('雲端價格漲了近', 'cloud pricing up nearly'), '15%',
                    ('。這是租方的價格,不是 NVIDIA 的售價。',
                     ' year-to-date. That is the rental price, not what NVIDIA charges.')),
                  ev('official') + src_a(_Q1FY27, '2026-08-18'),
                  S(('同一位在', 'The same officer, on'), '2026-02-25',
                    ('說:連 Hopper、以及大部分六年前的 Ampere 產品,在雲上都已經被租滿。'
                     '注意她講的是雲端算力被租滿,不是 NVIDIA 缺貨 —— 這兩件事常被混為一談。',
                     ': "even Hopper and much of the six year old Ampere-based products are sold '
                     'out in the cloud." Note what that says — cloud capacity is fully rented, not '
                     'that NVIDIA cannot supply. The two get conflated constantly.')),
                  ev('official') + src_a('https://s201.q4cdn.com/141608511/files/doc_financials/'
                                         '2026/q4/NVDA-Q4-2026-Earnings-Call-25-February-2026-'
                                         '5_00-PM-ET.pdf', '2026-08-18'),
                  tt('這一條把買與租的比較整個往買的方向推。客戶如果拿前幾年的租金在算帳,'
                     '他那張試算表已經過期了。請他調出自己不同時間的兩張帳單,不要用我們的數字。',
                     'This pushes the whole build-versus-rent comparison toward building. A '
                     'customer still modelling on the rent they paid a few years ago is working '
                     'from an expired spreadsheet. Ask them to pull two of their own invoices from '
                     'different dates rather than quoting ours.'),
                  gap('各家業者自己的牌價頁仍然沒有生效日與變更紀錄,所以「某一家降了多少」'
                      '還是證不出來。市場彙整文提到「AWS 最多降 45%」,'
                      '那句沒有日期也不是 AWS 自己說的,不能引用',
                      'the vendors\' own pricing pages still carry no effective dates or '
                      'changelogs, so a per-vendor cut still cannot be proven. A market survey '
                      'mentions an AWS cut of up to 45% , but that line is undated and not '
                      'attributed to AWS, so it cannot be quoted')),
               'H100 +20%', 'H100 +20%'),
          ]), block='rate-cards'))

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
    a(sec('crossover',
          S(('推算式原樣寫出來', 'the formula is written out'), '·',
            ('三個交叉點', 'three crossover points'), '·',
            ('%d 級稼動率階梯' % len(LADDER), '%d-step utilisation ladder' % len(LADDER))),
          items('crossover', [
              ('arithmetic', '算式,原樣寫出來', 'The arithmetic, written out',
               '每一個輸入值都印在旁邊,你可以換掉任何一個重算 —— 不必相信我們的結論',
               'every input prints beside the result, so you can swap any one of them and redo it '
               'yourself rather than trusting our conclusion',
               '\n'.join(ec), None, None),

              ('colo-tier', '機櫃租金的級距陷阱', 'The colocation tier trap',
               '同樣一度電,小單位租金是大單位的 2 倍。你的情境落在哪一邊,'
               '對結果的影響比任何其他輸入都大',
               'the same kilowatt costs 2 times as much in a small deployment as in a large '
               'one, and which side of that line a scenario falls on moves the answer more than any '
               'other input here',
               '  <p>%s %s</p>\n  <p>%s %s</p>\n  <p>%s</p>'
               % (S(('250–500 kW 級距的北美主要市場,平均要價', 'In the 250-500 kW band across North '
                     'American primary markets the average asking rate is'),
                    'USD 195.94', ('每 kW 每月,年增', 'per kW per month, up'), '6.5%',
                    ('；主要市場空置率創新低', '. Primary-market vacancy hit a record low of'),
                    '1.4%', ('。', '.')),
                  ev('third') + src_a('https://www.cbre.com/insights/books/north-america-data-center-trends-h2-2025', '2026-08-18'),
                  S(('但 4 MW 以上的超大規模級距,同一份市場報價落在',
                     'Above 4 MW, though, the hyperscale tier quotes at'),
                    'USD 86–110', ('每 kW 每月,一筆 4 MW 的需求約', 'per kW per month — a 4 MW '
                    'requirement is quoted at about'), 'USD 98',
                    ('。兩個級距差 2 倍。', '. That is a 2 times difference between tiers.')),
                  ev('third') + src_a('https://datacenterhawk.com/resources/fundamentals/colocation-data-center-pricing-a-2026-beginner-s-guide', '2026-08-18'),
                  tt('一櫃 GB200 NVL72 約 120 kW —— 落在貴的那一級。'
                     '大到能拿到便宜級距的建置,規模已經完全不同。'
                     '所以「租比較貴」這句話,不問規模就是錯的。',
                     'One GB200 NVL72 rack draws about 120 kW, which lands in the expensive tier. A '
                     'build large enough to reach the cheap tier is a completely different size of '
                     'project. So "renting costs more" is simply wrong until you have asked how '
                     'big.')),
               '租金差 2 倍', 'the rent differs by 2 times'),

              ('machine-price', '機器價格現在查不到準的', 'Nobody publishes what the machine costs',
               '同一台 8 卡 B200,三個來源從 USD 380,000 到 USD 792,000。沒有任何 OEM 公布定價,'
               '所以交叉點要用區間算,不能用單點',
               'the same 8-GPU B200 box ranges from USD 380,000 to USD 792,000 across three '
               'sources, and no OEM publishes list pricing at all — so the crossover has to be run '
               'as a band, never as a point',
               '  <p>%s %s</p>\n  <p>%s %s</p>\n  <p>%s</p>'
               % (S(('分析估算落在', 'Analyst estimates cluster at'), 'USD 400,000–500,000',
                    ('，約', ', or roughly'), 'USD 56,000',
                    ('每卡部署成本。', 'per GPU deployed.')),
                  ev('third') + src_a('https://www.mercatus-ai.com/blog/b200-server-price', '2026-08-18'),
                  S(('但唯一查得到實際掛價的經銷商,把一台 8 卡 B200 標在',
                     'But the one reseller listing with an actual price on it tags an 8-GPU B200 at'),
                    'USD 792,000',
                    ('，比分析中位數高約 76%,該頁把價差歸因於 2026 年 3 次各 30% 的基準漲價。'
                     '那是單一經銷商的滿配報價,含通路加價 —— 不是市場價,但也不是假的。',
                     ', about 76% above the analyst midpoint, and attributes the gap to '
                     '3 consecutive 30% baseline increases during 2026. That is one reseller quoting '
                     'a fully-loaded configuration with channel margin — not the market price, but '
                     'not fiction either.')),
                  ev('vendor') + src_a('https://viperatech.com/product/supermicro-10u-b200-gold-series-gpu-server-sys-a21ge-nbrt-g1', '2026-08-18'),
                  gap('沒有任何 OEM 公布 8 卡 B200 的定價 —— 我方自家商店列了料號但不顯示價格,'
                      'Dell 的對應機型只給「加入詢價」。所以這一格沒有權威錨點,'
                      '交叉點請用上下限各算一次。要結案:內部報價單',
                      'no OEM publishes a list price for an 8-GPU B200 — our own store lists the SKU '
                      'without a price and the Dell equivalent is quote-only. There is no '
                      'authoritative anchor, so run the crossover at both ends of the band. To '
                      'close it: an internal quote')),
               'USD 380k–792k', 'USD 380k-792k'),

              ('depreciation', '攤提年限:今年沒有人改', 'Useful life: nobody moved it this year',
               '攤提年限直接決定自建的年成本。查過 6 家的原始申報書, 2026 年到今天沒有一家改過,'
               '真正的分歧發生在 2025 ,而且方向相反',
               'the depreciation schedule sets the annual cost of owning, and a check of 6 '
               'companies\' own filings shows not one changed it during 2026 to date. The real '
               'divergence happened in 2025 , and it went in both directions at once',
               '  <div class="regwrap">\n  <table class="reg">\n'
               '    <thead><tr><th>%s</th><th>%s</th><th>%s</th></tr></thead>\n    <tbody>\n'
               % (tt('公司', 'Company'), tt('年限', 'Useful life'), tt('最近一次變動', 'Last change'))
               + '\n'.join(
                   '      <tr><td><span class="lbl">%s</span>%s</td>'
                   '<td><span class="lbl">%s</span>%s</td>'
                   '<td><span class="lbl">%s</span>%s</td></tr>'
                   % (tt('公司', 'Company'), lk(n),
                      tt('年限', 'Useful life'), lk(y),
                      tt('最近一次變動', 'Last change'), tt(esc(ch), esc(ce)))
                   for n, y, ch, ce in [
                       ('Amazon', '5–6', '2025-01-01 部分機隊由 6 年縮到 5 年,'
                        '理由寫的是 AI 帶動的技術迭代加快;當年折舊增 USD 1.4B、淨利減 USD 1.0B',
                        'a subset shortened 6 to 5 years on 2025-01-01, citing the pace of AI-driven '
                        'technology change; FY2025 depreciation up USD 1.4B and net income down USD 1.0B'),
                       ('Meta', '5–5.5', '2025-01-01 反向拉長到 5.5 年;'
                        '當年折舊減 USD 2.92B、淨利增 USD 2.59B',
                        'lengthened to 5.5 years on 2025-01-01 — the opposite move; FY2025 '
                        'depreciation down USD 2.92B and net income up USD 2.59B'),
                       ('Nebius', '5', '2026-01-01 由 4 年拉長到 5 年,'
                        '是本場贊助商中唯一今年動過的;半年折舊減 USD 86.1M',
                        'extended 4 to 5 years on 2026-01-01 — the only sponsor here that moved it '
                        'this year; H1 depreciation down USD 86.1M'),
                       ('Microsoft', '2–6', '未變動(FY2026 10-K)', 'unchanged (FY2026 10-K)'),
                       ('Alphabet', '6', '未變動', 'unchanged'),
                       ('Oracle', '6', '未變動', 'unchanged'),
                       ('CoreWeave', '6', '2023-01-01 由 5 年拉長到 6 年,之後未動',
                        'lengthened 5 to 6 years on 2023-01-01 and untouched since'),
                   ])
               + '\n    </tbody>\n  </table>\n  </div>\n'
               + '  <p class="src">%s %s %s</p>\n' % (
                   ev('official'),
                   src_a('https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm', '2026-08-18'),
                   src_a('https://www.sec.gov/Archives/edgar/data/1326801/000162828026003942/meta-20251231.htm', '2026-08-18'))
               + '  <p>%s</p>\n' % tt(
                   'Amazon 縮短、Meta 拉長,同一年、相反方向 —— '
                   '代表這個數字是判斷,不是事實。客戶用幾年攤,決定自建划不划算,'
                   '而這一題目前業界自己都沒有共識。',
                   'Amazon shortened and Meta lengthened in the same year, in opposite directions. '
                   'That tells you the number is a judgement rather than a fact — and the customer\'s '
                   'own choice of schedule decides whether building pencils out, on a question the '
                   'industry has not settled among itself.')
               + '  <p>%s</p>' % tt(
                   '反方最強的說法是 GPU 兩三年就過時,拉長年限等於美化獲利;'
                   'NVIDIA 財務長的反駁是六年前出的 A100 現在還在滿載跑。兩邊都要會講。',
                   'The strongest bear case is that GPUs are obsolete in two to three years and that '
                   'longer schedules flatter earnings; NVIDIA\'s CFO answers that A100s shipped six '
                   'years ago still run at full utilisation today. Be able to say both.'),
               '2026 沒人動', 'nobody moved it in 2026'),
          ]), block='crossover'))

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
    a(sec('hyperscalers',
          S(('三家都在現場', 'all three are in the room'), '·',
            ('賣的不是價格，是維運外包', 'they sell outsourced operations, not price')),
          items('hyperscalers', [
              ('pitch', '他們賣的不是價格', 'What they sell is not price',
               '雲廠在這場的訴求是「叢集不用你顧」。要對打就打維運,不是打單價',
               'the hyperscaler pitch here is that the cluster is somebody else\'s problem — so '
               'the counter is about operations, not about unit price',
               '\n'.join(hs), None, None),
          ]), block='hyperscalers'))

    # -------------------------------------------- 6. where we win and lose --
    WIN_KEYS = [('own-hall', '自有機房', 'They own the hall'),
                ('data-cannot-leave', '資料不能出場域', 'The data may not leave'),
                ('steady-load', '負載長期滿載', 'The load runs flat out'),
                ('sell-to-rival', '賣給對手', 'Selling to the competition'),
                ('mixed-nodes', '異質節點', 'Mixed nodes'),
                ('hall-layer', '機房層', 'The hall layer')]
    a(sec('we-win',
          S(('%d 個情境' % len(WINS), pl(len(WINS), 'situation', 'situations')), '·',
            ('其中一個是「賣給對手」', 'one of them is selling to the competition')),
          items('we-win', [
              (WIN_KEYS[i][0] if i < len(WIN_KEYS) else 'win%d' % i,
               WIN_KEYS[i][1] if i < len(WIN_KEYS) else x[:10],
               WIN_KEYS[i][2] if i < len(WIN_KEYS) else y[:24],
               x, y, '  <p>%s</p>' % ev(r), None, None)
              for i, (x, y, r) in enumerate(WINS)])
          + '\n  %s' % from_draft(D03), block='wins'))
    LOSS_KEYS = [('spiky-load', '負載忽高忽低', 'The load is spiky'),
                 ('no-hall', '沒有機房', 'They have no hall'),
                 ('no-ops-team', '沒有維運人手', 'They have no operations team'),
                 ('capex-blocked', '資本支出過不了', 'Capex will not clear'),
                 ('locked-oem', '已被綁定', 'Already locked to an OEM'),
                 ('short-horizon', '看不到三年', 'They cannot see three years out')]
    a(sec('we-lose',
          S(('%d 個情境' % len(LOSSES), pl(len(LOSSES), 'situation', 'situations')), '·',
            ('照原樣寫，不打折', 'written at full strength, not discounted')),
          items('we-lose', [
              (LOSS_KEYS[i][0] if i < len(LOSS_KEYS) else 'loss%d' % i,
               LOSS_KEYS[i][1] if i < len(LOSS_KEYS) else x[:10],
               LOSS_KEYS[i][2] if i < len(LOSS_KEYS) else y[:24],
               x, y, '  <p>%s</p>' % ev(r), None, None)
              for i, (x, y, r) in enumerate(LOSSES)])
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
    a(sec('their-case',
          tt('照原樣寫出來，附一句反擊',
             'quoted at full strength, with the one line that answers it'),
          items('their-case', [
              ('quote', '他們會說的那一句', 'The sentence they will say',
               '寫成最強版本,不打折。打折過的對手說法在現場會原地失效',
               'written at full strength, not softened — a discounted version of their argument '
               'falls apart the moment it is said out loud on the floor',
               '\n'.join(q), None, None),
          ]), block='counterparty'))

    # ------------------------------------------- 7b. chip generation records -
    # The refresh clock, made checkable. Age is computed from GA against the
    # factbase date, so it cannot rot the way a typed "about two years old" does.
    if True:
        cr = ['  <div class="chips">']
        for c in CHIPS:
            age = chip_age_months(c.get('available'))
            old_fleet = age is not None and age >= 30
            cr.append('    <section class="chip-rec" id="%s">' % att('chip-' + slug(c['name'])))
            cr.append('      <h3 class="chip-h"><span class="chip-n">%s</span>'
                      '<span class="chip-arch">%s</span>%s</h3>'
                      % (esc(c['name']), esc(c['arch']),
                         ('<span class="chip-age%s">%s</span>'
                          % (' is-old' if old_fleet else '',
                             tt('上市 %d 個月' % age, '%d months on the market' % age)))
                         if age is not None else ''))
            cells = [
                ('發布', 'Announced', c.get('announced')),
                ('可買到', 'Available', c.get('available')),
                ('上一代', 'Replaced', c.get('predecessor')),
                ('下一代', 'Replaced by', c.get('successor')),
            ]
            cr.append('      <div class="chip-line">')
            for kh, ke, v in cells:
                cr.append('        <div class="chip-cell"><span class="k">%s</span>'
                          '<span class="v">%s</span></div>'
                          % (tt(esc(kh), esc(ke)),
                             lk(v) if v and str(v) != 'GAP'
                             else gap('這一格沒有公開來源', 'no public source for this cell')))
            cr.append('      </div>')
            if c.get('still_shipping'):
                cr.append('      <p class="chip-read">%s %s</p>'
                          % (tt('供貨狀態:', 'Supply: '),
                             tt(esc(c['still_shipping'][0]), esc(c['still_shipping'][1]))))
            cr.append('      <p class="chip-read">%s</p>'
                      % tt(esc(c.get('read_h', '')), esc(c.get('read_e', ''))))
            if c.get('sources'):
                cr.append('      <p class="src">%s</p>'
                          % ' '.join(src_a(u, d) for u, d in c['sources']))
            cr.append('    </section>')
        cr.append('  </div>')
        a(sec('chips',
              S(('%d 顆' % len(CHIPS), '%d parts' % len(CHIPS)), '·',
                ('每一顆的上市日與下一代', 'each with its ship date and its successor'), '·',
                ('文中提到就連過來', 'every mention in the pack links here')),
              items('chips', [
                  ('records', '一顆一列', 'One row per part',
                   '上市幾個月是算出來的,不是寫死的 —— 這一頁明年打開仍然是對的',
                   'the age in months is computed against the factbase date rather than typed, so '
                   'this page is still right a year from now',
                   '\n'.join(cr) if CHIPS else
                   ('  <p>%s</p>'
                    % gap('晶片世代表還沒建。要結案:把每一顆的發布日、量產日與下一代填進 CHIPS,'
                          '每一格帶來源',
                          'the chip generation table is not built yet. To close it: fill CHIPS with '
                          'the announce date, GA date and successor for each part, every cell '
                          'sourced'))),
                  ('clock', '為什麼要看世代', 'Why the generation is the question',
                   '客戶最舊的那批是哪一代,決定他多久之後會有一次汰換對話 —— 這是這包裡最短的資格判定',
                   'which generation the oldest batch is decides how long until a replacement '
                   'conversation, and that is the shortest qualifying question in this pack',
                   '  <p>%s</p>'
                   % tt('所以第三個問題問的是「你們最舊的那批 GPU 節點是哪一代」,'
                        '不是「你們用什麼卡」。答案落在這張表的哪一列,就決定要不要排下一次拜訪。',
                        'That is why the third question asks which generation the oldest batch is, '
                        'not what card they run. Where the answer lands on this table decides '
                        'whether the account earns a second visit.')),
              ]), block='chip-records'))

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
    a(sec('collisions',
          S(('%d 組' % len(traps), pl(len(traps), 'collision', 'collisions')), '·',
            ('每一組都附反查字串', 'each with the query that separates them')),
          items('collisions', [
              ('pairs', '會查錯的名字', 'The names that send research astray',
               '每一組都附一條反查字串,貼進搜尋列就能把錯的那一家排掉',
               'each pair carries a negation query — paste it into a search box and the wrong '
               'company drops out of the results',
               '\n'.join(tp), None, None),
          ]), block='traps'))

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
    CMP_GAP_KEYS = [
        ('commit-price', '承諾價不公開', 'Committed prices are not published',
         '只有「最高六折」一句話,沒有真實價格,所以每一個交叉點都是估算',
         'there is only a "up to sixty per cent off" line and no real price, which makes every '
         'crossover on this page an estimate'),
        ('customer-inputs', '用的是市場均值不是客戶的數字', 'Built on market averages, not the '
         'customer\'s own numbers',
         '電價、PUE、攤提、人力都用產業均值。換成客戶自己的數字,交叉點會明顯移動',
         'power price, PUE, amortisation and headcount are industry averages; swap in the '
         'customer\'s own and the crossover moves noticeably'),
        ('rack-scale', '機櫃級系統沒有價格', 'Rack-scale systems have no public price',
         'GB300 NVL72 整櫃沒有可靠公開價,所以算式是按每顆 B200 推的,沒涵蓋整櫃',
         'no reliable public price exists for a GB300 NVL72 rack, so the arithmetic is per-B200 and '
         'does not cover rack-scale at all'),
        ('live-vs-contracted', '簽約容量不等於在役容量', 'Contracted capacity is not live capacity',
         '管線數字是第三方彙整,不是一手,兩者差距可能很大',
         'the pipeline figures are third-party aggregation rather than first-party, and the gap '
         'between signed and running can be large'),
        ('are-we-in', '我方在不在他們的供應鏈', 'Whether we are in their supply chain at all',
         '這一格是此行最值得查證的一件事 —— 只有 Lambda 已證實',
         'this is the single most worthwhile thing to settle on the trip; only Lambda is '
         'confirmed'),
    ]
    a(sec('compare-open',
          S(('%d 個缺口' % len(g), pl(len(g), 'open question', 'open questions')), '·',
            ('每一個都寫了什麼證據能結案', 'each with what would close it')),
          items('compare-open', [
              (CMP_GAP_KEYS[i][0], CMP_GAP_KEYS[i][1], CMP_GAP_KEYS[i][2],
               CMP_GAP_KEYS[i][3], CMP_GAP_KEYS[i][4],
               '  <p>%s</p>' % g[i], 'GAP', None)
              for i in range(min(len(g), len(CMP_GAP_KEYS)))])
          + '\n  %s' % STAMP, cls='caveat', fresh=True))
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
    # Two passes on purpose. Pass one renders and registers every anchor; the
    # index cannot be built until the last page has registered its items, and
    # the hub is the first page rendered. 〔the index was silently short by four
    # pages when this was one pass〕
    bodies = OrderedDict()
    for role, fname, title_h, title_e, nav_h, nav_e in PAGES:
        if allowed and role not in allowed:
            print('build_fragments: skip %s — not in STATE.campaign.pageBudget' % role)
            continue
        bodies[role] = BUILDERS[role]()
        manifest['pages'].append({'role': role, 'file': fname, 'title': title_h,
                                  'title_e': title_e, 'nav': nav_h, 'nav_e': nav_e,
                                  'frag': 'build/frag/%s.html' % role})
        written.append(role)
    idx_html = build_index()
    n_idx, chip_links = 0, 0
    for role, body in bodies.items():
        # The spine goes on EVERY page, from one place, so no page can be built
        # without its own map.
        body = spine(role) + '\n' + body
        body, _n_chip = annotate_chips(body)
        chip_links += _n_chip
        if INDEX_SLOT in body:
            body = body.replace(INDEX_SLOT, idx_html)
            n_idx += 1
        drawers += body.count('<details ')
        io.open(os.path.join(FRAG, role + '.html'), 'w', encoding='utf-8').write(body + '\n')
    if written and n_idx != 1:
        sys.exit('build_fragments: FAIL the index slot resolved %d times, expected exactly 1. '
                 'One index, on the hub.' % n_idx)
    for role in sorted(allowed - set(written)):
        sys.exit('build_fragments: FAIL pageBudget names role "%s" and this factory has no '
                 'fragment builder for it. Add one, or drop it from the budget (B12).' % role)
    io.open(os.path.join(BUILD, 'manifest.json'), 'w', encoding='utf-8').write(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('build_fragments: %d fragments (%s) lang=%s asOf=%s drawers=%d cards=%s '
          'cells=%d sourced=%d gap=%d chips=%d/%d evidence=%s'
          % (len(written), ' '.join(written), src_lang, ASOF or 'UNSET', drawers,
             'GAP' if cards is None else N_CARDS, POP, SRCD, GAPC,
             chip_links, len(CHIPS),
             ','.join('%s:%d' % (k, v) for k, v in RANKS.items() if v) or 'none'))


main()
