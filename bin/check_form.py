#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_form.py — the form gate. Runs at EVERY build (spine-plan-v2 §2 P4).

Blocks: scale, nowrap overflow, half-translation, octal CSS, and PAGE-BUDGET
OVERRUN (Y3). A page whose role is outside STATE.campaign.pageBudget.core union
.depth FAILS — the budget stops being prose and becomes a gate. Required and
forbidden blocks come from bin/page-role.json (§7.2); a block is the attribute
data-block="<name>" on any element.

ROOT is a literal written by scaffold.sh (RULES B9).
"""
ROOT = '/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

import io
import json
import os
import re
import sys

STATE_P = os.path.join(ROOT, 'STATE.json')
ROLES_P = os.path.join(ROOT, 'bin', 'page-role.json')
DOCS = os.path.join(ROOT, 'docs')

FAILS = []
NOTES = []


def fail(code, msg, fix=''):
    FAILS.append('FAIL %-22s %s%s' % (code, msg, ('\n     fix: ' + fix) if fix else ''))


def load(p, default=None):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except FileNotFoundError:
        return default


state = load(STATE_P)
roles_spec = load(ROLES_P)
if state is None or roles_spec is None:
    print('FAIL FM0 missing-input      need %s and %s' % (STATE_P, ROLES_P))
    sys.exit(1)

campaign = state.get('campaign') or {}
budget = campaign.get('pageBudget') or {}
allowed = set(budget.get('core') or []) | set(budget.get('depth') or [])
axes = set(campaign.get('axis') or [])
known_roles = {k for k in roles_spec if not k.startswith('_')}
forbid_patterns = roles_spec.get('_forbidPatterns') or {}
BLOCK_ATTR = roles_spec.get('_blockAttr') or 'data-block'

pages = state.get('pages') or []
by_file = {}
for p in pages:
    if p.get('file'):
        by_file[os.path.basename(p['file'])] = p

# ------------------------------------------------- FM1 page budget (Y3) ----
if not allowed:
    fail('FM1 page-budget', 'STATE.campaign.pageBudget names no roles',
         'B12: six core roles unless P0 named a deletion. An empty budget builds nothing')

seen_roles = {}
for p in pages:
    f, role = p.get('file', '?'), p.get('role')
    if not role:
        fail('FM1 page-role', '%s has no role' % f, 'every page declares exactly one role')
        continue
    if role not in known_roles:
        fail('FM1 unknown-role', '%s role "%s" is not in page-role.json' % (f, role),
             'use a role from the STATE-schema enum, or add its contract to the factory first')
    if role not in allowed:
        fail('FM1 page-budget', '%s role "%s" is outside pageBudget.core ∪ .depth (%s)'
             % (f, role, ', '.join(sorted(allowed)) or 'empty'),
             'B12: name the role in STATE.campaign.pageBudget.depth and say why, or delete the page. '
             'The 13th HTML file is not a feature')
    # ------------------------------------ one writer per role -------------
    if role in seen_roles and role not in ('company-full', 'archive'):
        fail('FM2 two-writers', 'role "%s" is claimed by both %s and %s'
             % (role, seen_roles[role], f),
             'one writer per role. Two pages owning one role means two truths and one of them is stale')
    seen_roles.setdefault(role, f)

# ----------------------------------------------------- files vs STATE ------
html_files = sorted(f for f in os.listdir(DOCS) if f.endswith('.html')) if os.path.isdir(DOCS) else []
for f in html_files:
    if f not in by_file:
        fail('FM0 unregistered-page', 'docs/%s is not in STATE.pages[]' % f,
             'A5: same filename => same URL forever. Register it (with its role) or delete it')
for f in by_file:
    if html_files and f not in html_files:
        NOTES.append('     note: STATE.pages[] lists %s, not built yet' % f)

# ------------------------------------------------------- per-file checks ---
HANT_ONLY = set('體網資據應為學電個說麼東這們會產業開關買賣過進場對時實發點認讓萬與價億'
                '導際單環總樣華複製質選項變準確與訊處點與線圖聲間')
HANS_ONLY = set('体网资据应为学电个说么东这们会产业开关买卖过进场对时实发点认让万与价亿'
                '导际单环总样华复制质选项变准确讯处线图声间')
CJK = re.compile(r'[㐀-鿿豈-﫿]')
NOWRAP = re.compile(r'white-space\s*:\s*nowrap', re.I)
FIXED_W = re.compile(r'\bwidth\s*:\s*(\d{3,})px', re.I)
FONT_PX = re.compile(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', re.I)
SCALE = re.compile(r'\b(transform\s*:[^;"\']*\bscale\s*\(|zoom\s*:\s*[0-9.]+)', re.I)
CSS_ESC = re.compile(r'content\s*:\s*["\'][^"\']*\\[0-7]{2,3}', re.I)
JS_OCTAL = re.compile(r'(?<![\w.])0[0-7]{1,}(?![\w.xX])')
STYLE_BLK = re.compile(r'<style\b[^>]*>(.*?)</style>', re.S | re.I)
SCRIPT_BLK = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)
HTML_LANG = re.compile(r'<html\b[^>]*\blang\s*=\s*["\']([^"\']+)["\']', re.I)


def page_lang(name, src):
    m = HTML_LANG.search(src)
    if m:
        v = m.group(1).lower()
        if 'hant' in v or v in ('zh-tw', 'zh-hk'):
            return 'h'
        if 'hans' in v or v in ('zh-cn', 'zh'):
            return 's'
        if v.startswith('en'):
            return 'e'
    stem = name[:-5]
    for suf, lang in (('.s', 's'), ('.e', 'e'), ('-s', 's'), ('-e', 'e')):
        if stem.endswith(suf):
            return lang
    langs = campaign.get('langs') or ['h']
    return langs[0]


def strip_tags(s):
    s = STYLE_BLK.sub(' ', s)
    s = SCRIPT_BLK.sub(' ', s)
    return re.sub(r'<[^>]+>', ' ', s)


for f in html_files:
    path = os.path.join(DOCS, f)
    src = io.open(path, encoding='utf-8', errors='replace').read()
    role = (by_file.get(f) or {}).get('role')
    blocks = set(re.findall(r'%s\s*=\s*["\']([^"\']+)["\']' % BLOCK_ATTR, src))

    # --------------------------------- FM3 required / forbidden blocks -----
    spec = roles_spec.get(role) or {}
    for need in spec.get('requires', []):
        if need not in blocks:
            fail('FM3 missing-block', '%s (role %s) ships without %s="%s"' % (f, role, BLOCK_ATTR, need),
                 'the role contract in page-role.json is the page budget in machine-readable form')
    for bad in spec.get('forbids', []):
        if bad in blocks:
            fail('FM3 forbidden-block', '%s (role %s) carries forbidden block "%s"' % (f, role, bad))
        pat = forbid_patterns.get(bad)
        if pat and not pat.startswith('__RESOLVED_AT_RUNTIME__') and re.search(pat, strip_tags(src)):
            fail('FM3 forbidden-shape', '%s (role %s) matches forbidden pattern for "%s"' % (f, role, bad),
                 'the reader does not care how many agents ran. Say the verdict')
    if role == 'command-center' and 'method-above-fold' not in blocks:
        vi = src.find('%s="verdict"' % BLOCK_ATTR)
        mi = src.find('%s="method"' % BLOCK_ATTR)
        if vi >= 0 and 0 <= mi < vi:
            fail('FM3 method-above-fold', '%s puts the method block before the verdict' % f,
                 'verdict first. Method lives below, or on another page')
    if role == 'compare':
        used = set(re.findall(r'data-axis\s*=\s*["\']([^"\']+)["\']', src))
        for a in sorted(used - axes):
            if axes:
                fail('FM3 axis-not-in-STATE', '%s compares on axis "%s", not in STATE.campaign.axis' % (f, a),
                     'we compare against who is AT THIS EVENT, named in STATE — not last year\'s list')

    styles = ' '.join(STYLE_BLK.findall(src)) + ' ' + ' '.join(re.findall(r'style\s*=\s*"([^"]*)"', src))

    # ------------------------------------------------------- FM4 scale -----
    for m in FONT_PX.finditer(styles):
        if float(m.group(1)) < 11:
            fail('FM4 scale', '%s font-size %spx' % (f, m.group(1)),
                 'below 11px is not a layout, it is a confession that the content does not fit')
    if SCALE.search(styles):
        fail('FM4 scale', '%s uses transform:scale()/zoom to make content fit' % f,
             'fix the content or the container. Scaling ships blurry text and breaks hit targets')

    # --------------------------------------------- FM5 nowrap overflow -----
    for rule in re.split(r'[{}]', styles):
        if NOWRAP.search(rule):
            w = FIXED_W.search(rule)
            if w and int(w.group(1)) > 343:
                fail('FM5 nowrap-overflow', '%s nowrap on a %spx fixed width (375 viewport - 32 padding = 343)'
                     % (f, w.group(1)), 'wrap it, truncate with a title attribute, or reflow the table')
    for m in re.finditer(r'<(t[dh]|span|div)\b[^>]*nowrap[^>]*>(.*?)</\1>', src, re.S | re.I):
        txt = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        est = sum(2 if CJK.match(c) else 1 for c in txt) * 8
        if est > 343:
            fail('FM5 nowrap-overflow', '%s nowrap run ~%dpx at 16px/375: "%s"' % (f, est, txt[:50]),
                 'run bin/measure_layout.py, then wrap or shorten')

    # -------------------------------------------- FM6 half-translation -----
    lang = page_lang(f, src)
    text = strip_tags(src)
    if lang == 's':
        stray = sorted(set(text) & HANT_ONLY)
        if stray:
            fail('FM6 half-translation', '%s is zh-Hans but carries %s' % (f, ''.join(stray[:12])),
                 'B7: Simplified is vocabulary work, not transcoding. Finish the overlay or revert it')
    elif lang == 'h':
        stray = sorted(set(text) & HANS_ONLY)
        if stray:
            fail('FM6 half-translation', '%s is zh-Hant but carries %s' % (f, ''.join(stray[:12])),
                 'B7: a character-conversion tool\'s output is an error, not a draft')
    elif lang == 'e':
        if CJK.search(text):
            fail('FM6 half-translation', '%s is the English edition and still carries CJK' % f,
                 'translate it or drop the page from the English budget')

    # ------------------------------------------------- FM7 octal CSS/JS ----
    if CSS_ESC.search(styles):
        fail('FM7 octal-css', '%s content: carries a backslash escape' % f,
             'CSS escapes are hex, not octal; put the literal character (or an HTML entity) in the markup')
    for js in SCRIPT_BLK.findall(src):
        for m in JS_OCTAL.finditer(js):
            if m.group(0) not in ('0',):
                fail('FM7 octal-js', '%s numeric literal %s (leading zero = octal / strict-mode error)'
                     % (f, m.group(0)), 'drop the leading zero, or quote it if it is a code not a number')
                break

for n in NOTES:
    print(n)
# --------------------------------- FM8 an item must not echo its own heading ---
# When an item repeats its own title and explainer inside a nested drawer, the
# reader clicks it, meets the same words behind another collapsed control, and
# concludes the page is pretending to have content. That is worse than an empty
# section, because an empty section at least admits it.
# 〔Ray-Summit-2026: the four layer bands each made the reader click twice to
#  reach the same sentence〕
def _vis(x):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', x)).strip()


for _name in sorted(by_file):
    _path = os.path.join(DOCS, _name)
    if not os.path.exists(_path):
        continue
    _doc = io.open(_path, encoding='utf-8').read()
    for _m in re.finditer(r'<section class="itm" id="([^"]+)">(.*?)</section>', _doc, re.S):
        _aid, _body = _m.group(1), _m.group(2)
        _h = re.search(r'<span class="itm-l">(.*?)</span>', _body, re.S)
        _w = re.search(r'<p class="itm-w">(.*?)</p>', _body, re.S)
        _in = re.search(r'<div class="itm-b">\s*(?:<[^>]+>\s*)*?<details[^>]*>\s*'
                        r'<summary>(.*?)</summary>', _body, re.S)
        if not (_h and _in):
            continue
        _label, _what = _vis(_h.group(1)), _vis(_w.group(1)) if _w else ''
        _summ = _vis(_in.group(1))
        if (_label and _label[:14] in _summ) or (_what and _what[:16] in _summ):
            fail('FM8 echo-layer',
                 '%s item "%s" repeats its own heading inside a nested drawer, so opening it '
                 'shows the reader nothing new' % (_name, _aid),
                 'the item IS the header. Put the thing the reader clicked for in its body, '
                 'not a second copy of the label')


if FAILS:
    print('\n'.join(FAILS))
    print('check_form: %d FAIL — HARD STOP 4. Return to the last factory step.' % len(FAILS))
    sys.exit(1)
print('check_form: PASS  pages=%d roles=%s budget=%s'
      % (len(html_files), len(seen_roles), len(allowed)))
