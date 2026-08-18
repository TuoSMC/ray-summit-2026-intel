#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_fragments.py --lang <src> — make.sh step 3. One HTML fragment per page role.

Reads the factbase (data/*.json), the account board
(deliverables/accounts/cards.json) and whatever research markdown P2 left in
deliverables/research/, and writes ONE fragment per role into build/frag/.
A fragment is the inside of <main>; wrap_pages.py step 4 owns the skeleton.

The four rules this file exists to obey:

  B16  every count on every page is COMPUTED here from the JSON. A typed
       "50 sessions" is a defect even when it is currently true, because the
       next scrape makes it a lie and nothing catches it.
  B13  未知 != 無. Where a value is missing, print the literal GAP and the
       reason. Never 0, never 無, never "none" — those are findings, and we
       did not find them.
  B6   numbers, dates, room names, person names, company legal names and URLs
       are locked. They are emitted verbatim from the JSON, once, OUTSIDE the
       language layers wherever the sentence allows; where a figure must sit
       inside a sentence it is written into BOTH arms unchanged, and step 5
       proves the two arms carry the same locked tokens.
  B7   the second language is vocabulary, not transcoding. Every string in this
       file is authored twice, by hand, in tt(). There is no transliteration
       path and there is no machine in the loop.

Bilingual contract (DESIGN.md 7): a translatable run is a pair of sibling
spans, h first: <span data-t="h">…</span><span data-t="e">…</span>. Both
languages ship in the HTML; the toggle only switches visibility.

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
    ('glossary',       'glossary.html', '詞彙',   'Glossary',      '詞彙',   'Glossary'),
]

# key, ZH name, EN name, ZH description, EN description
LAYERS = [
    ('landlord', '房東', 'Landlord',
     '出租機房、電力與冷卻的一方（資料中心、colo）',
     'Rents out the hall, the power and the cooling (data centres, colo)'),
    ('operator', '營運商', 'Operator',
     '把 GPU 變成可租算力賣出去的一方（neocloud、雲）',
     'Turns GPUs into rentable compute and sells it (neoclouds, clouds)'),
    ('tenant', '租戶', 'Tenant',
     '買算力來跑自己模型與產品的一方（AI 實驗室、平台團隊）',
     'Buys compute to run its own models and products (AI labs, platform teams)'),
    ('channel', '通路', 'Channel',
     '把硬體或方案賣給上面三層的一方（OEM、經銷、系統整合）',
     'Sells hardware or solutions to the three layers above (OEM, reseller, SI)'),
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


def gap(why_h, why_e):
    """The only legal way to print a missing value (B13). A GAP always carries
    its reason — this helper cannot emit one without."""
    return ('<span class="gap">GAP</span> <span class="why">%s</span>'
            % tt(esc(why_h), esc(why_e)))


def ev(rank):
    """An evidence chip. rank is COMPUTED by evidence_of(), never typed."""
    h, e = EVIDENCE.get(rank, EVIDENCE['unverified'])
    return ('<span class="ev ev-%s"><span class="ev-mark" aria-hidden="true"></span>%s</span>'
            % (rank, tt(esc(h), esc(e))))


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

    The axis names its members in parentheses: "... (CoreWeave / Lambda / ...)".
    Matching is deliberately conservative and ordered, because the traps in
    STATE are exactly the collisions a loose matcher would create (Lambda Labs
    vs AWS Lambda): exact legal_name, then substring, then the org-id suffix,
    then — only if nothing else matched — a legal_name that is the leading
    word of the token (Google for "Google Cloud")."""
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


def evidence_ledger():
    """Rank every populated, sourced cell on the account board. Computed."""
    tally = OrderedDict((k, 0) for k in EVIDENCE)
    if not cards:
        return tally
    for c in cards:
        srcs = c.get('sources') or {}
        for key in ('layer', 'buys_servers', 'oem_lock', 'window', 'hq',
                    'classification', 'role_at_event', 'legal_name', 'crm'):
            v = c.get(key)
            if v in (None, '', [], {}):
                continue
            if isinstance(v, str) and v.strip().upper().startswith('GAP'):
                tally['gap'] += 1
                continue
            s = srcs.get(key) if isinstance(srcs.get(key), dict) else None
            tally[evidence_of((s or {}).get('source'), c.get('legal_name'))] += 1
    return tally


def research_notes():
    out = []
    if os.path.isdir(RESEARCH):
        for f in sorted(os.listdir(RESEARCH)):
            if not f.endswith('.md'):
                continue
            head = ''
            try:
                for ln in io.open(os.path.join(RESEARCH, f), encoding='utf-8', errors='replace'):
                    if ln.startswith('#'):
                        head = ln.lstrip('# ').strip()
                        break
            except OSError:
                head = ''
            out.append((f, head))
    return out


NOTES_MD = research_notes()


def day_counts_h():
    return '、'.join('%s %d' % (d, len(by_day[d])) for d in DAYS)


def day_counts_e():
    return ', '.join('%s %d' % (d, len(by_day[d])) for d in DAYS)


def tier_counts_h():
    return '、'.join('%s %d' % (t, tier_count[t]) for t in TIERS)


def tier_counts_e():
    return ', '.join('%s %d' % (t, tier_count[t]) for t in TIERS)


# ================================================================ fragments ==
def frag_command_center():
    h = []
    a = h.append

    axis_h, axis_e = [], []
    for axis, hits in AXIS_HITS:
        present = [o for o in hits if not o.startswith('!')]
        label = axis.split('(')[0].strip()
        axis_h.append('%s %d 家' % (esc(label), len(present)))
        axis_e.append('%s %d' % (esc(label), len(present)))

    a('<section class="verdict" data-block="verdict" data-fresh="1">')
    a('  <h1>%s</h1>' % tt('這一場的錢在<em>租算力</em>，不在買機器。我方以 scout 進場：收訊號，不擺攤。',
                           'The money in this room is spent <em>renting compute</em>, not buying '
                           'machines. We walk in as a scout: collect signal, hold no booth.'))
    a('  <p class="lede">%s</p>'
      % tt('沒有一家傳統伺服器對手在場。你要找的不是攤位對手，是誰在替這些人簽算力的帳。',
           'Not one traditional server rival is here. You are not looking for a rival booth — '
           'you are looking for whoever signs the compute bill for these people.'))
    a('  <ul class="grounds">')
    a('    <li>%s %s</li>'
      % (tt('到場 %d 家組織，兩條軸線都在現場：%s。' % (N_ORG, esc('、'.join(axis_h))),
            '%d organisations on site, and both axes are in the room: %s.'
            % (N_ORG, esc('; '.join(axis_e)))),
         ev('official')))
    a('    <li>%s %s</li>'
      % (tt('贊助 %d 家，依層級：%s。' % (N_SPO, esc(tier_counts_h())),
            '%d sponsors by tier: %s.' % (N_SPO, esc(tier_counts_e()))),
         ev('official')))
    if US:
        a('    <li>%s %s %s</li>'
          % (tt('我方定位：', 'Our position: '), esc(US), ev('unverified')))
    if cards is None:
        a('    <li>%s</li>'
          % gap('deliverables/accounts/cards.json 尚未產生，%d 家組織的買方分層還沒有結論' % N_ORG,
                'deliverables/accounts/cards.json has not been built, so the buyer layer for '
                'all %d organisations is still open' % N_ORG))
    else:
        layered = len([c for c in cards if band_key(c.get('layer'))])
        a('    <li>%s %s</li>'
          % (tt('%d / %d 家已分層（%s）。其餘是未查證，不是不屬於任何一層。'
                % (layered, len(cards), esc(' / '.join(k for k, _n, _e, _d, _de in LAYERS))),
                '%d of %d classified into a buyer layer (%s). The rest are unverified, '
                'not unaffiliated.'
                % (layered, len(cards), esc(' / '.join(k for k, _n, _e, _d, _de in LAYERS)))),
             ev('third')))
    a('  </ul>')
    a('  %s' % STAMP)
    a('</section>')

    # ---- four numbers, every one of them computed -------------------------
    if cards is None:
        cards_fig = ('<span class="gap">GAP</span>',
                     '已建帳戶卡', 'Account cards',
                     'deliverables/accounts/cards.json 尚未產生 —— 這是未知，不是零',
                     'deliverables/accounts/cards.json is not built yet — unknown, not zero', True)
    else:
        cards_fig = (str(len(cards)), '已建帳戶卡', 'Account cards',
                     'deliverables/accounts/cards.json · 計算值',
                     'deliverables/accounts/cards.json · computed', False)
    figs = [
        (str(N_SESS), '場次', 'Sessions',
         'data/sessions.json · 計算值（%s）' % day_counts_h(),
         'data/sessions.json · computed (%s)' % day_counts_e(), False),
        (str(N_ORG), '到場組織', 'Organisations on site',
         'data/orgs.json · 講者雇主 %d、贊助 %d、參展捕獲 %d（可重疊）'
         % (len(speaker_orgs), len(sponsor_orgs), len(exhibitor_orgs)),
         'data/orgs.json · speaker employers %d, sponsors %d, exhibitor captures %d (overlapping)'
         % (len(speaker_orgs), len(sponsor_orgs), len(exhibitor_orgs)), False),
        (str(N_SPO), '贊助商', 'Sponsors',
         'data/sponsors.json · %s' % tier_counts_h(),
         'data/sponsors.json · %s' % tier_counts_e(), False),
        cards_fig,
    ]
    a('<section data-block="four-numbers" data-fresh="1">')
    a('  <h2>%s</h2>' % tt('四個數字', 'Four numbers'))
    a('  <ol class="figs">')
    for v, kh, ke, sh, se, is_gap in figs:
        a('    <li class="fig%s"><span class="n">%s</span>'
          '<span class="k">%s</span><span class="src">%s</span></li>'
          % (' is-gap' if is_gap else '', v if is_gap else esc(v),
             tt(esc(kh), esc(ke)), tt(esc(sh), esc(se))))
    a('  </ol>')
    a('  %s' % STAMP)
    a('</section>')

    # ---- two actions, both computed ---------------------------------------
    top_tag = TAGS[0] if TAGS else ''
    rooms_for_tag = {}
    for s in sessions:
        if top_tag and top_tag in [str(t) for t in (s.get('tags') or [])]:
            r = str(s.get('room') or '')
            rooms_for_tag[r] = rooms_for_tag.get(r, 0) + 1
    best_room = max(rooms_for_tag, key=lambda k: (rooms_for_tag[k], k)) if rooms_for_tag else ''
    keynote = next((s for s in sessions if 'keynote' in str(s.get('title', '')).lower()), None)
    platinum = [oid for oid in sponsor_orgs
                if tier_of.get(oid) in ('presenting', 'diamond', 'platinum')]
    axis_a = [o for o in (AXIS_HITS[0][1] if AXIS_HITS else {}) if not o.startswith('!')]
    targets = list(OrderedDict.fromkeys(platinum + axis_a))

    a('<section data-block="two-actions">')
    a('  <h2>%s</h2>' % tt('兩個動作', 'Two actions'))
    a('  <ol class="acts">')
    a('    <li>')
    a('      <b>%s</b>' % tt('站對房間。', 'Stand in the right room.'))
    if best_room:
        a('      <p>%s %s%s</p>'
          % (tt('最大的主題是 %s，共 %d 場，其中 %d 場落在'
                % (esc(top_tag), tag_count.get(top_tag, 0), rooms_for_tag[best_room]),
                'The biggest track is %s with %d sessions, and %d of them land in'
                % (esc(top_tag), tag_count.get(top_tag, 0), rooms_for_tag[best_room])),
             lk(best_room),
             tt('。', '.')))
        if keynote:
            a('      <p>%s %s · %s · %s</p>'
              % (tt('主題演講，結束後直接過去', 'Keynote — walk straight over when it ends'),
                 lk(keynote.get('title')), lk(keynote.get('start_end') or ''),
                 lk(keynote.get('room') or '')))
    else:
        a('      <p>%s</p>' % gap('sessions.json 沒有標籤，排不出主場房間',
                                  'sessions.json carries no tags, so no home room can be ranked'))
    a('    </li>')
    a('    <li>')
    a('      <b>%s</b>' % tt('收帳戶卡。', 'Collect account cards.'))
    a('      <p>%s</p>'
      % tt('先收這 %d 家：白金以上 %d 家，加上第一條軸線的 %d 家，去重後 %d 家。'
           '本輪 FULL 上限 %d，還剩 %d 席。'
           % (len(targets), len(platinum), len(axis_a), len(targets),
              MAXFULL, max(0, MAXFULL - len(targets))),
           'Take these %d first: %d at platinum or above plus %d named on the first axis, '
           '%d after de-duplication. The FULL cap this lap is %d, with %d seats left.'
           % (len(targets), len(platinum), len(axis_a), len(targets),
              MAXFULL, max(0, MAXFULL - len(targets)))))
    if targets:
        a('      <p>%s</p>' % ' '.join(lk(org_name(o)) for o in targets))
    a('    </li>')
    a('  </ol>')
    a('</section>')
    a('<p class="stamp" data-block="asOf-stamp" data-fresh="1">%s</p>'
      % tt('狀態截至 %s' % esc(ASOF), 'Status as of %s' % esc(ASOF)))

    # ---- method goes BELOW the verdict, inside <details> (page-role.json) --
    ledger = evidence_ledger()
    a('<details class="method" data-block="method">')
    a('  <summary>%s</summary>' % tt('方法與來源', 'Method and sources'))
    a('  <div class="body">')
    a('    <p>%s</p>'
      % tt('頁上每一個數字都是建置時從 JSON 算出來的，沒有一個是打字打上去的。'
           '算不出來的欄位印 GAP 和原因，不印零。',
           'Every number on this page is computed from JSON at build time; none of them is '
           'typed. A field that cannot be computed prints GAP and its reason, never a zero.'))
    a('    <ul>')
    for name, n in (('data/sessions.json', N_SESS), ('data/speakers.json', N_SPK),
                    ('data/sponsors.json', N_SPO), ('data/orgs.json', N_ORG)):
        a('      <li><code>%s</code> %s</li>'
          % (esc(name), tt('%d 筆' % n, pl(n, 'record', 'records'))))
    a('      <li><code>deliverables/accounts/cards.json</code> %s</li>'
      % (tt('%d 筆' % len(cards), pl(len(cards), 'record', 'records')) if cards is not None
         else gap('尚未產生', 'not built yet')))
    if NOTES_MD:
        for f, head in NOTES_MD:
            a('      <li><code>deliverables/research/%s</code> %s</li>'
              % (esc(f), lk(head) if head else tt('（沒有標題行）', '(no title line)')))
    else:
        a('      <li><code>deliverables/research/</code> %s</li>'
          % gap('這一輪沒有研究筆記可引用', 'no research note to cite this lap'))
    a('    </ul>')
    if cards is not None:
        a('    <p>%s</p>' % tt('帳戶板每一格的證據等級（計算值）：',
                               'Evidence rank of every account-board cell (computed):'))
        a('    <p>')
        for rank, n in ledger.items():
            if n:
                a('      %s %s' % (ev(rank), tt('%d 格' % n, pl(n, 'cell', 'cells'))))
        a('    </p>')
    if SOURCE:
        a('    <p>%s <a href="%s">%s</a></p>'
          % (tt('目錄來源：', 'Catalogue source:'), att(SOURCE), esc(SOURCE)))
    gaps = factbase.get('gaps') or []
    if gaps:
        a('    <p>%s</p><ul>' % tt('已登記的缺口：', 'Registered gaps:'))
        for g in gaps:
            a('      <li>%s</li>' % gap(g, g))
        a('    </ul>')
    a('  </div>')
    a('</details>')
    return '\n'.join(h)


def frag_agenda():
    h = []
    a = h.append
    a('<section data-block="day-filter" data-fresh="1">')
    a('  <h2>%s</h2>' % tt('議程 —— %d 場' % N_SESS, 'Agenda — %d sessions' % N_SESS))
    a('  <p class="note">%s</p>'
      % tt('按日期切換。日期切換是純 CSS，不靠指令碼，離線也能用。',
           'Filter by day. The day filter is pure CSS, depends on no script, and works offline.'))
    a('  <div class="dayset">')
    a('    <input class="dayin" type="radio" name="day" id="day-all" checked>')
    a('    <label class="daylab" for="day-all">%s</label>'
      % tt('全部 %d' % N_SESS, 'All %d' % N_SESS))
    for i, d in enumerate(DAYS[:8], start=1):
        a('    <input class="dayin" type="radio" name="day" id="day-d%d">' % i)
        a('    <label class="daylab" for="day-d%d">%s %s</label>'
          % (i, lk(d), tt('%d 場' % len(by_day[d]), pl(len(by_day[d]), 'session', 'sessions'))))
    a('  </div>')
    if MISSING_DAYS:
        a('  <p>%s</p>'
          % gap('會期內的 %s 在目錄上一場都沒有 —— 是未公布，不是沒有場次'
                % '、'.join(MISSING_DAYS),
                'the catalogue publishes no session at all on %s inside the event window — '
                'unpublished, not absent' % ', '.join(MISSING_DAYS)))
    a('  <ol class="ses">')
    for i, d in enumerate(DAYS[:8], start=1):
        for s in by_day[d]:
            tags = [str(t) for t in (s.get('tags') or [])]
            a('    <li data-daykey="d%d" data-day="%s">' % (i, att(d)))
            a('      <p class="when">%s %s</p>'
              % (lk(d), lk(s.get('start_end') or s.get('start') or '')))
            a('      <h3>%s</h3>' % esc(s.get('title')))
            a('      <p class="where">%s %s · %s %s</p>'
              % (tt('會議室', 'Room'), lk(s.get('room') or ''),
                 tt('場次', 'Session'), lk(s.get('id') or '')))
            if tags:
                a('      <p class="tags">%s</p>'
                  % ''.join('<span class="chip">%s</span>' % esc(t) for t in tags))
            else:
                a('      <p class="tags">%s</p>'
                  % gap('目錄沒有給這一場標籤', 'the catalogue gives this session no tag'))
            a('    </li>')
    a('  </ol>')
    a('  %s' % STAMP)
    a('</section>')

    a('<section data-block="room">')
    a('  <h2>%s</h2>' % tt('會議室 —— %d 間' % len(ROOMS), 'Rooms — %d of them' % len(ROOMS)))
    a('  <ul class="rooms">')
    for r in ROOMS:
        a('    <li><span class="rn">%s</span><span class="rc">%s</span></li>'
          % (lk(r), tt('%d 場' % room_count[r], pl(room_count[r], 'session', 'sessions'))))
    a('  </ul>')
    a('  <p class="note">%s</p>'
      % tt('會議室名稱、時間、日期一律維持目錄原文，兩個語言版本逐字元相同。',
           'Room names, times and dates stay exactly as the catalogue prints them, '
           'byte-identical in both languages.'))
    a('</section>')

    a('<section class="caveat" data-block="seats-caveat" data-fresh="1">')
    a('  <h2>%s</h2>' % tt('兩件事目錄沒有給', 'Two things the catalogue does not give'))
    a('  <ul>')
    if seats_known:
        a('    <li>%s</li>'
          % tt('座位數：%d / %d 場有揭露。' % (len(seats_known), N_SESS),
               'Seat counts: disclosed for %d of %d sessions.' % (len(seats_known), N_SESS)))
    else:
        a('    <li>%s %s</li>'
          % (tt('座位數：', 'Seat counts: '), gap(SEAT_WHY_H, SEAT_WHY_E)))
        a('    <li>%s</li>'
          % tt('所以「會不會滿」這件事現在無法回答。現場以活動 App 為準，別在客戶面前用猜的。',
               'So "will it fill up" cannot be answered today. Defer to the event app on site; '
               'do not guess in front of a customer.'))
    a('    <li>%s %s</li>'
      % (tt('講者對應：', 'Speaker linkage: '), gap(LINK_WHY_H, LINK_WHY_E)))
    a('    <li>%s</li>'
      % tt('名單上的 %d 位講者來自官方活動頁，不是場次卡片 —— 誰講哪一場尚未證實。' % N_SPK,
           'The %d speakers we hold come from the official event page, not from the session '
           'cards, so who speaks where is still unverified.' % N_SPK))
    a('  </ul>')
    a('  %s' % STAMP)
    a('</section>')
    return '\n'.join(h)


def frag_gtm():
    h = []
    a = h.append
    a('<section>')
    a('  <h2>%s</h2>' % tt('打法 —— %d 個目標客群' % len(SEGMENTS),
                           'Plays — %d target segments' % len(SEGMENTS)))
    a('  <p class="lede">%s</p>'
      % tt('客群取自 STATE.campaign.segments。現場候選名單是從 orgs.json 的到場身分算出來的；'
           '真正的買方分層要等帳戶卡。',
           'Segments come from STATE.campaign.segments. The on-site shortlist is computed from '
           'presence in orgs.json; the real buyer layer waits on the account cards.'))
    a('</section>')

    for i, seg in enumerate(SEGMENTS, start=1):
        low = seg.lower()
        if 'neocloud' in low or 'gpu' in low:
            rule_h = 'STATE.campaign.axis 第一條軸線點名的公司'
            rule_e = 'companies named on the first axis in STATE.campaign.axis'
            oids = [o for o in (AXIS_HITS[0][1] if AXIS_HITS else {}) if not o.startswith('!')]
        elif 'lab' in low or 'model' in low:
            rule_h = 'orgs.json roles_at_event = speaker-employer'
            rule_e = 'orgs.json roles_at_event = speaker-employer'
            oids = speaker_orgs
        elif 'enterprise' in low or 'platform' in low:
            rule_h = 'orgs.json 的參展捕獲 exhibitor_capture'
            rule_e = 'exhibitor_capture rows in orgs.json'
            oids = exhibitor_orgs
        else:
            rule_h = rule_e = ''
            oids = []
        a('<section class="play" data-block="segment-play">')
        a('  <h2>%s</h2>' % lk(seg))
        a('  <dl>')
        a('    <dt>%s</dt>' % tt('現場候選', 'On-site shortlist'))
        if oids:
            a('    <dd>%s<span class="src">%s</span></dd>'
              % (''.join('<span class="chip">%s%s</span>'
                         % (esc(org_name(o)),
                            (' %s' % esc(tier_of[o])) if tier_of.get(o) else '')
                         for o in oids),
                 tt('依 %s，共 %d 家' % (esc(rule_h), len(oids)),
                    'by %s, %d in total' % (esc(rule_e), len(oids)))))
        else:
            a('    <dd>%s</dd>'
              % gap('orgs.json 沒有任何欄位可以把公司指派到這個客群',
                    'no field in orgs.json assigns a company to this segment'))
        a('    <dt>%s</dt>' % tt('站哪裡', 'Where to stand'))
        if TAGS:
            a('    <dd>%s</dd>'
              % ''.join('<span class="chip">%s %d</span>' % (esc(t), tag_count[t]) for t in TAGS))
        else:
            a('    <dd>%s</dd>' % gap('sessions.json 沒有標籤', 'sessions.json carries no tag'))
        a('    <dt>%s</dt>' % tt('買方分層', 'Buyer layer'))
        if cards is None:
            a('    <dd>%s</dd>'
              % gap('cards.json 尚未產生 —— 這一格是未知，不是「沒有」',
                    'cards.json is not built yet: this cell is unknown, not empty'))
        else:
            known = [c for c in cards if band_key(c.get('layer')) and str(c.get('org_id')) in oids]
            a('    <dd>%s</dd>'
              % tt('%d / %d 家已分層' % (len(known), len(oids)),
                   '%d of %d classified' % (len(known), len(oids))))
        a('    <dt>%s</dt>' % tt('離場前要拿到', 'Leave with'))
        a('    <dd>%s</dd>'
          % tt('D1 需求、D2 決策路徑、D3 時間窗。三格都填才算一次有效對話，見下方 D 登記簿。',
               'D1 need, D2 decision path, D3 timing window. A conversation only counts when '
               'all three are filled; see the D register below.'))
        a('  </dl>')
        a('</section>')

    cols = [('客群', 'Segment'),
            ('D1 需求', 'D1 Need'),
            ('D2 決策路徑', 'D2 Decision path'),
            ('D3 時間窗', 'D3 Timing window'),
            ('狀態', 'Status')]
    cells = [('他們現在缺的是算力，還是把算力變成產品的人手？',
              'Are they short of compute, or of the people who turn compute into product?'),
             ('誰簽？機房、雲，還是採購？',
              'Who signs — the facility, the cloud team, or procurement?'),
             ('下一次擴容或換約是什麼時候？',
              'When is the next expansion or contract renewal?')]
    a('<section data-block="d-register" data-fresh="1">')
    a('  <h2>%s</h2>' % tt('D 登記簿', 'D register'))
    a('  <p class="note">%s</p>'
      % tt('每一次現場對話結束後就地登記三格。空著的格子寫 GAP 和你缺什麼，不要寫「沒有」——'
           '沒問到和沒有是兩件事。',
           'Fill the three cells the moment a conversation ends. An empty cell gets GAP and what '
           'is missing, never "none": not asked and not there are different findings.'))
    a('  <div class="regwrap">')
    a('  <table class="reg">')
    a('    <thead><tr>%s</tr></thead>'
      % ''.join('<th>%s</th>' % tt(esc(ch), esc(ce)) for ch, ce in cols))
    a('    <tbody>')
    for seg in (SEGMENTS or ['STATE.campaign.segments']):
        a('      <tr>')
        a('        <td><span class="lbl">%s</span>%s</td>'
          % (tt(esc(cols[0][0]), esc(cols[0][1])), lk(seg)))
        for n, (ch, ce) in enumerate(cells):
            a('        <td><span class="lbl">%s</span>%s</td>'
              % (tt(esc(cols[n + 1][0]), esc(cols[n + 1][1])), tt(esc(ch), esc(ce))))
        a('        <td><span class="lbl">%s</span>%s</td>'
          % (tt(esc(cols[4][0]), esc(cols[4][1])),
             gap('展前，尚未登記', 'pre-show, not registered yet')))
        a('      </tr>')
    a('    </tbody>')
    a('  </table>')
    a('  </div>')
    a('  %s' % STAMP)
    a('</section>')
    return '\n'.join(h)


def _rows_from_org(oid):
    o = org_by_id.get(oid) or {}
    rows = [(('買方分層', 'Buyer layer'),
             gap('cards.json 尚未產生', 'cards.json is not built yet'), None)]
    if o.get('buys_servers') not in (None, '', 'GAP'):
        rows.append((('自購伺服器', 'Buys its own servers'), esc(o.get('buys_servers')), 'unverified'))
    else:
        rows.append((('自購伺服器', 'Buys its own servers'),
                     gap('orgs.json buys_servers=GAP，未查證',
                         'orgs.json buys_servers=GAP, unverified'), None))
    rows.append((('帳戶編號', 'Ledger id'),
                 lk('%s · %s' % (o.get('ledger_id') or '?', o.get('ledger_status') or '?')), None))
    if oid in exhibitor_of:
        rows.append((('捕獲來源', 'Capture'), esc(exhibitor_of[oid].get('capture') or ''),
                     evidence_of(exhibitor_of[oid].get('source'), org_name(oid))))
    return org_name(oid), org_badges(oid), rows


def _rows_from_card(c):
    name = str(c.get('legal_name') or c.get('org_id') or c.get('ledger_id') or '?')
    badges = []
    if c.get('org_id') and tier_of.get(str(c['org_id'])):
        badges.append(tier_of[str(c['org_id'])])
    role = c.get('role_at_event')
    for r in (role if isinstance(role, list) else [role] if role else []):
        badges.append(str(r))
    if c.get('classification') and not str(c['classification']).upper().startswith('GAP'):
        badges.append(str(c['classification']))
    rows = []
    fields = (('layer', '買方分層', 'Buyer layer', '卡片沒有填分層', 'the card carries no layer'),
              ('buys_servers', '自購伺服器', 'Buys its own servers', '未查證', 'unverified'),
              ('oem_lock', 'OEM 綁定', 'OEM lock-in', '未查證', 'unverified'),
              ('window', '時間窗', 'Timing window', '未查證', 'unverified'),
              ('hq', '總部', 'Headquarters', '未查證', 'unverified'))
    for key, lh, le, wh, we in fields:
        v = c.get(key)
        text = str(v).strip() if isinstance(v, str) else ''
        if v in (None, '') or text.upper().startswith('GAP'):
            tail = text[3:].strip(' -—:')
            rows.append(((lh, le), gap(tail or wh, tail or we), None))
        else:
            s = (c.get('sources') or {}).get(key)
            s = s if isinstance(s, dict) else {}
            rank = evidence_of(s.get('source'), name)
            tail = ('<span class="src">%s</span>' % esc('%s · %s' % (s.get('source') or '',
                                                                     s.get('date') or ''))) \
                if s.get('source') else ''
            rows.append(((lh, le), esc(v) + tail, rank))
    rows.append((('帳戶編號', 'Ledger id'),
                 lk('%s · %s' % (c.get('ledger_id') or '?', c.get('ledger_status') or '?')), None))
    return name, badges, rows


def frag_accounts():
    h = []
    a = h.append
    open_layer = cards is None or [c for c in cards if not band_key(c.get('layer'))]
    a('<section class="caveat%s" data-block="gap-visible" data-fresh="1">'
      % ('' if open_layer else ' is-clear'))
    if cards is None:
        a('  <h2>%s</h2>' % tt('帳戶板還沒有卡片', 'The account board has no cards yet'))
        a('  <p>%s</p>' % gap('deliverables/accounts/cards.json 尚未產生 —— account-intel 這一輪還沒跑',
                              'deliverables/accounts/cards.json has not been built — account-intel '
                              'has not run this lap'))
        a('  <p class="note">%s</p>'
          % tt('補上的方法：產生 %d 家組織的帳戶卡（FULL 上限 %d），再跑一次 make.sh all。'
               '在那之前，下面每一張卡的分層一律是 GAP，不是「未分類」，也不是零。'
               % (N_ORG, MAXFULL),
               'To close it: build account cards for all %d organisations (FULL cap %d), then run '
               'make.sh all again. Until then every layer below reads GAP — not "unclassified", '
               'and not zero.' % (N_ORG, MAXFULL)))
    else:
        no_layer = [c for c in cards if not band_key(c.get('layer'))]
        if no_layer:
            a('  <h2>%s</h2>' % tt('缺口', 'The gap'))
            a('  <p>%s</p>'
              % tt('%d / %d 張卡片還沒有分層。這是未查證，不是「不屬於任何一層」。'
                   % (len(no_layer), len(cards)),
                   '%d of %d cards carry no buyer layer. That is unverified — not "belongs to no '
                   'layer".' % (len(no_layer), len(cards))))
        else:
            a('  <h2>%s</h2>' % tt('分層已結案', 'Layering closed'))
            a('  <p>%s</p>'
              % tt('%d 張卡片全部落在某一層。分層這一格已經結案。' % len(cards),
                   'All %d cards land in a layer. That cell is closed.' % len(cards)))
        a('  <p class="note">%s</p>'
          % tt('還開著的欄位仍然逐格顯示在卡面上，附上為什麼還沒結案。',
               'Every cell that is still open prints on the card itself, with the reason it is '
               'still open.'))
    a('  %s' % STAMP)
    a('</section>')

    if cards is None:
        banded = OrderedDict((k, []) for k, _n, _e, _d, _de in LAYERS)
        unbanded = [('org', oid) for oid in org_by_id]
    else:
        banded = OrderedDict((k, []) for k, _n, _e, _d, _de in LAYERS)
        unbanded = []
        for c in cards:
            key = band_key(c.get('layer'))
            if key:
                banded[key].append(('card', c))
            else:
                unbanded.append(('card', c))
    n_unlayered = len(unbanded)

    def render_band(key, nh, ne, dh, de, items, gap_h=None, gap_e=None):
        a('<section class="band" data-block="layer-band">')
        a('  <div class="bandhead">')
        a('    <h2>%s %s</h2>' % (lk(key), tt(esc(nh), esc(ne))))
        a('    <p class="bandn">%s</p>'
          % tt('%d 家' % len(items), pl(len(items), 'account', 'accounts')))
        a('  </div>')
        a('  <p class="banddesc">%s</p>' % tt(esc(dh), esc(de)))
        a('  <ul class="accts" data-block="card-grid">')
        if not items:
            a('    <li class="acct is-gap"><p>%s</p></li>'
              % gap(gap_h or '這一層目前沒有可放的卡片',
                    gap_e or 'no card lands in this layer yet'))
        for kind, it in items:
            name, badges, rows = _rows_from_org(it) if kind == 'org' else _rows_from_card(it)
            a('    <li class="acct">')
            a('      <h3>%s</h3>' % lk(name))
            if badges:
                a('      <p>%s</p>'
                  % ''.join('<span class="chip">%s</span>' % esc(b) for b in badges))
            a('      <dl>')
            for (lh, le), value, rank in rows:
                a('        <dt>%s</dt>' % tt(esc(lh), esc(le)))
                a('        <dd>%s%s</dd>' % (value, (' ' + ev(rank)) if rank else ''))
            a('      </dl>')
            a('    </li>')
        a('  </ul>')
        a('</section>')

    for key, nh, ne, dh, de in LAYERS:
        render_band(key, nh, ne, dh, de, banded[key],
                    gap_h=('cards.json 尚未產生，這一層是未知，不是空的' if cards is None
                           else '%d 張卡片的分層還是 GAP —— 沒有人落到這一層是「未查證」，'
                                '不是「不屬於」' % n_unlayered),
                    gap_e=('cards.json is not built yet, so this layer is unknown, not empty'
                           if cards is None
                           else '%d cards still carry GAP for layer — nobody landing here means '
                                'unverified, not unaffiliated' % n_unlayered))
    if unbanded:
        def sort_key(item):
            kind, it = item
            oid = it if kind == 'org' else str(it.get('org_id') or '')
            return (TIER_RANK.get(tier_of.get(oid, ''), 9), org_name(oid))
        render_band('unlayered', '未分層', 'Unlayered',
                    '分層欄位是 GAP —— 未查證，不是不屬於任何一層。這一疊就是下一輪的排隊名單',
                    'The layer cell reads GAP — unverified, not unaffiliated. This stack is the '
                    'queue for the next lap',
                    sorted(unbanded, key=sort_key))
    return '\n'.join(h)


def frag_compare():
    h = []
    a = h.append
    a('<section data-block="axis-from-STATE" data-fresh="1">')
    a('  <h2>%s</h2>' % tt('對位 —— %d 條軸線' % len(AXES), 'Matchup — %d axes' % len(AXES)))
    a('  <p class="lede">%s</p>'
      % tt('軸線逐字取自 STATE.campaign.axis。我方只跟這一場真的到場的人比，不比去年的名單。',
           'The axes are taken verbatim from STATE.campaign.axis. We only compare against who is '
           'actually in this room — never last year\'s list.'))
    a('  <div class="axes">')
    for n, (axis, hits) in enumerate(AXIS_HITS, start=1):
        present = [o for o in hits if not o.startswith('!')]
        absent = [o[1:] for o in hits if o.startswith('!')]
        a('    <article class="axis" data-axis="%s">' % att(axis))
        a('      <h3>%s</h3>'
          % tt('軸線 %d · 現場 %d 家' % (n, len(present)),
               'Axis %d · %d present' % (n, len(present))))
        a('      <p class="axisfull">%s</p>' % esc(axis))
        a('      <ul class="axislist">')
        for oid in present:
            a('        <li><b>%s</b> %s<span class="src">%s</span></li>'
              % (esc(org_name(oid)),
                 ''.join('<span class="chip">%s</span>' % esc(b) for b in org_badges(oid)),
                 esc('data/orgs.json %s' % oid)))
        for tok in absent:
            a('        <li><b>%s</b> %s</li>'
              % (esc(tok), gap('軸線點名了，但 orgs.json 沒有這一家 —— 未到場尚未證實',
                               'named on the axis but absent from orgs.json; their absence is '
                               'itself unverified')))
        a('      </ul>')
        a('    </article>')
    a('  </div>')
    a('  %s' % STAMP)
    a('</section>')

    traps = campaign.get('traps') or []
    a('<section>')
    a('  <h2>%s</h2>' % tt('同名陷阱 —— %d 組' % len(traps),
                           'Name collisions — %d of them' % len(traps)))
    a('  <p class="note">%s</p>'
      % tt('認錯公司比認不出公司貴。以下取自 STATE.campaign.traps。',
           'Naming the wrong company costs more than naming none. Taken from '
           'STATE.campaign.traps.'))
    a('  <ul class="traps">')
    for t in traps:
        a('    <li class="trap">')
        a('      <p><span class="chip">%s</span></p>' % esc(t.get('kind') or ''))
        a('      <p class="ab"><b>A</b> %s</p>' % esc(t.get('a') or ''))
        a('      <p class="ab"><b>B</b> %s</p>' % esc(t.get('b') or ''))
        a('      <p class="neg">%s</p>' % esc(t.get('negation_query') or ''))
        a('    </li>')
    if not traps:
        a('    <li class="trap">%s</li>'
          % gap('STATE.campaign.traps 是空的', 'STATE.campaign.traps is empty'))
    a('  </ul>')
    a('</section>')
    return '\n'.join(h)


def frag_glossary():
    h = []
    a = h.append
    groups = []
    groups.append((('現場主題標籤', 'Track tags on site'),
                   'data/sessions.json tags',
                   [(t, ('', ''), ('%d 場' % tag_count[t], pl(tag_count[t], 'session', 'sessions')))
                    for t in TAGS]))
    groups.append((('贊助層級', 'Sponsor tiers'),
                   'data/sponsors.json tier',
                   [(t, ('', ''), ('%d 家' % tier_count[t], pl(tier_count[t], 'company', 'companies')))
                    for t in TIERS]))
    roles = {}
    for o in orgs:
        for r in (o.get('roles_at_event') or []):
            roles[str(r)] = roles.get(str(r), 0) + 1
    groups.append((('到場身分', 'Presence roles'),
                   'data/orgs.json roles_at_event',
                   [(r, ('', ''), ('%d 家' % roles[r], pl(roles[r], 'company', 'companies')))
                    for r in sorted(roles, key=lambda k: (-roles[k], k))]))
    groups.append((('帳戶分層', 'Account layers'),
                   'DESIGN.md · %d' % len(LAYERS),
                   [(k, (nh, ne), (dh, de)) for k, nh, ne, dh, de in LAYERS]))
    groups.append((('證據等級', 'Evidence ranks'),
                   'DESIGN.md · %d' % len(EVIDENCE),
                   [(EVIDENCE[k][1], (EVIDENCE[k][0], EVIDENCE[k][1]),
                     ({'official': '來源是官方目錄或活動自己的頁面',
                       'vendor': '來源是這家公司自己的網站',
                       'third': '來源是第三方媒體、法說或公開文件',
                       'unverified': '欄位有值但沒有來源紀錄',
                       'gap': '沒查到。不是沒有 —— 卡片上會寫什麼證據能結案'}[k],
                      {'official': 'the source is the official catalogue or the event\'s own page',
                       'vendor': 'the source is the company\'s own website',
                       'third': 'the source is third-party press, a filing or a public document',
                       'unverified': 'the cell is populated but carries no source record',
                       'gap': 'not found. Not absent — the card says what would close it'}[k]))
                    for k in EVIDENCE]))
    groups.append((('工廠用語', 'Factory words'),
                   'DESIGN.md · 3',
                   [('GAP', ('缺口', 'Gap'),
                     ('沒查到，不是沒有。任何一格印 GAP 都會附上原因',
                      'Not found, not absent. Any GAP cell carries its reason')),
                    ('asOf', ('狀態截至', 'Status as of'),
                     ('這一頁的事實停在哪一天；過期就要重抓',
                      'The day this page\'s facts stop; past it, re-scrape')),
                    ('ledger_id', ('帳戶編號', 'Ledger id'),
                     ('同一家公司跨活動的同一把鑰匙，避免重複研究',
                      'One key for one company across events, so nobody researches it twice'))]))
    tb = [t for t in (termbase.get('terms') or []) if t.get(src_lang) and t.get('e')]
    if tb:
        groups.append((('中英對照', 'Term pairs'),
                       'data/termbase.json',
                       [(t['e'], (t[src_lang], t['e']), ('', '')) for t in tb]))

    total = sum(len(g[2]) for g in groups)
    a('<section>')
    a('  <h2>%s</h2>' % tt('詞彙 —— %d 組' % total, 'Glossary — %d entries' % total))
    a('  <p class="lede">%s</p>'
      % tt('全部從資料算出來，沒有一個是背下來的。英文原詞不翻譯。',
           'All of it computed from the data, none of it remembered. English source terms are '
           'never translated.'))
    a('</section>')
    for (th, te), srcline, items in groups:
        a('<section>')
        a('  <h2>%s</h2>' % tt(esc(th), esc(te)))
        a('  <p class="src">%s</p>' % esc(srcline))
        a('  <ul class="terms">')
        for term, (cnh, cne), (tlh, tle) in items:
            a('    <li class="term" data-block="term-chip">')
            a('      <b>%s</b>' % esc(term))
            if cnh or cne:
                a('      <span class="cn">%s</span>' % tt(esc(cnh), esc(cne)))
            if tlh or tle:
                a('      <span class="tail">%s</span>' % tt(esc(tlh), esc(tle)))
            a('    </li>')
        if not items:
            a('    <li class="term" data-block="term-chip">%s</li>'
              % gap('這一組沒有可算的詞', 'nothing computable in this group'))
        a('  </ul>')
        a('</section>')
    return '\n'.join(h)


BUILDERS = {
    'command-center': frag_command_center,
    'agenda': frag_agenda,
    'gtm': frag_gtm,
    'accounts': frag_accounts,
    'compare': frag_compare,
    'glossary': frag_glossary,
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
    written = []
    for role, fname, title_h, title_e, nav_h, nav_e in PAGES:
        if allowed and role not in allowed:
            print('build_fragments: skip %s — not in STATE.campaign.pageBudget' % role)
            continue
        body = BUILDERS[role]()
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
    print('build_fragments: %d fragments (%s) lang=%s asOf=%s cards=%s evidence=%s'
          % (len(written), ' '.join(written), src_lang, ASOF or 'UNSET',
             'GAP' if cards is None else len(cards),
             ','.join('%s:%d' % (k, v) for k, v in evidence_ledger().items() if v) or 'none'))


main()
