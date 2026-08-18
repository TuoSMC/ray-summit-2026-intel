#!/bin/bash
# make.sh — the ONLY writer order for this campaign (spine-plan-v2 §2 P3).
#
# ROOT is a literal, written by scaffold.sh. RULES B9: never read the campaign
# directory from args, $PWD, or an env var. If you are tempted to parameterise
# this, you are about to rebuild the wrong campaign.
ROOT='/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

set -uo pipefail
cd "$ROOT" || { echo "make: FAIL ROOT literal '$ROOT' does not exist" >&2; exit 1; }

STATE="$ROOT/STATE.json"
BIN="$ROOT/bin"
DOCS="$ROOT/docs"
DIFFDIR="$ROOT/data/.diff"
START_EPOCH="$(date +%s)"

# ---- the two order failures this sequence exists to prevent ----------------
# ORDER FAILURE 1 — i18n overlay (step 5) run before the source language was
#   frozen (steps 3-4). Every later source edit silently un-translated a page,
#   and the whole overlay had to be thrown away and redone. i18n is vocabulary,
#   not transcoding (B7); it may only run on frozen prose.
# ORDER FAILURE 2 — artifact merge/relink (step 8) run before docs/ was written
#   (step 7). Relink rewrote hrefs to files that did not exist yet, so the
#   website edition shipped with dead relative links while the sandbox copy
#   looked fine. docs/ ALWAYS lands before relink, and relink only runs when
#   host == artifact-sandbox.
# ---------------------------------------------------------------------------

say()  { printf 'make: %s\n' "$*"; }
fail() { printf 'make: FAIL %s\n' "$*" >&2; exit 1; }

state_get() {  # state_get <dotted.path> [default]
  python3 - "$STATE" "$1" "${2-}" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception as e:
    sys.exit("cannot read STATE.json: %s" % e)
cur = d
for k in sys.argv[2].split('.'):
    if isinstance(cur, dict) and k in cur:
        cur = cur[k]
    else:
        print(sys.argv[3] if len(sys.argv) > 3 else ''); raise SystemExit(0)
if isinstance(cur, (list, dict)):
    print(' '.join(str(x) for x in cur) if isinstance(cur, list) else json.dumps(cur, ensure_ascii=False))
else:
    print(cur)
PY
}

HOST="$(state_get campaign.host)"          || fail "STATE unreadable"
LANGS="$(state_get campaign.langs h)"
SRC_LANG="${LANGS%% *}"
# HARD STOP 5 belongs to P5, not to every target. check-fresh is a P1 freshness
# alarm and must work while host is still deliberately unset at P0 (see P0-intake:
# "host 留空 —— P5 才選"). Friction is legal at five named points only (s8.3);
# firing a P5 stop during a P0 freshness check is a friction-budget violation.
# 〔Ray-Summit-2026: check-fresh refused to run on the day the campaign was pinned〕
require_host() {
  [ -n "$HOST" ] || fail "HARD STOP 5 — STATE.campaign.host is unset. Set docs-local | private-acl | artifact-sandbox."
}

# Prose builders take exactly one language and it is the source language.
# A fragment written straight into a target language is not a translation, it
# is a second source of truth (B7). Refusing costs 2; not refusing costs a lap.
require_source_lang() {
  [ "$1" = "$SRC_LANG" ] && return 0
  printf 'make: FAIL prose builder called with lang "%s"; source language is "%s".\n' "$1" "$SRC_LANG" >&2
  printf '      Build the source, freeze it, then run step 5 (i18n overlay).\n' >&2
  exit 2
}

writer() {  # writer <step-no> <script> <human name>  -> runs it or fails loudly
  local n="$1" s="$2" name="$3"; shift 3
  [ -x "$BIN/$s" ] || [ -f "$BIN/$s" ] \
    || fail "step $n ($name) has no writer. Create $BIN/$s at P3. A build that silently skips a step is the defect."
  say "step $n — $name"
  if [ "${s##*.}" = "py" ]; then python3 "$BIN/$s" "$@" || fail "step $n ($name) exited $?"
  else bash "$BIN/$s" "$@" || fail "step $n ($name) exited $?"; fi
}

# ---------------------------------------------------------------- targets --
check_fresh() {
  # §7.6 — the freshness alarm. Exits NON-ZERO when staleAfter is past.
  # Wire to Skill(loop) or cron at T-14, daily inside T-7. Silence is a bug.
  python3 - "$STATE" <<'PY'
import datetime, json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
fb = d.get('factbase', {})
sa, asof = fb.get('staleAfter'), fb.get('asOf')
owner = (d.get('freshness') or {}).get('owner') or 'UNSET'
if not sa:
    sys.exit('make: FAIL factbase.staleAfter is unset. Nobody owns the alarm.')
today = datetime.date.today()
stale = datetime.date.fromisoformat(sa)
if today > stale:
    sys.exit('make: FAIL factbase STALE — asOf=%s staleAfter=%s today=%s owner=%s\n'
             '      Re-scrape the three catalogs, rebuild orgs.json, write data/.diff/%s.json, '
             'then bump factbase.asOf/staleAfter.' % (asof, sa, today, owner, today))
print('make: fresh — asOf=%s staleAfter=%s owner=%s' % (asof, sa, owner))
PY
}

cheap_gates() {
  local rc=0
  python3 "$BIN/check_facts.py"                 || rc=1
  python3 "$BIN/check_form.py"                  || rc=1
  [ "$(printf '%s' "$LANGS" | wc -w)" -gt 1 ] && { python3 "$BIN/check_i18n.py" || rc=1; }
  bash "$BIN/qa-gate.sh" "$DOCS"                || rc=1
  return $rc
}

record_cost() {  # record_cost <phase>
  python3 - "$STATE" "$1" "$(( $(date +%s) - START_EPOCH ))" <<'PY'
import datetime, io, json, sys
p, phase, secs = sys.argv[1], sys.argv[2], sys.argv[3]
state = json.load(open(p, encoding='utf-8'))
state.setdefault('cost', []).append({
    "phase": phase, "agents": 0, "outputTokens": 0,
    "at": datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
    "wallSeconds": int(secs)})
io.open(p, 'w', encoding='utf-8').write(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
print('make: STATE.cost[] += %s' % phase)
PY
}

build_all() {
  require_host
  check_fresh                                              || exit 1
  writer 1 test_units.py     "unit tests"
  writer 2 build_views.py    "rebuild views from JSON (D2: JSON wins, the view is rebuilt)"
  require_source_lang "$SRC_LANG"
  writer 3 build_fragments.py "fragment builders — source language only" --lang "$SRC_LANG"
  writer 4 wrap_pages.py     "page wrap"
  if [ "$(printf '%s' "$LANGS" | wc -w)" -gt 1 ]; then
    writer 5 i18n_overlay.py "i18n overlay (source language is frozen — see ORDER FAILURE 1)" --src "$SRC_LANG"
  else
    say "step 5 — i18n overlay skipped (single language: $SRC_LANG)"
  fi
  writer 6 structure_pass.py "structure pass"
  writer 7 write_docs.py     "write docs/ (relative links — see ORDER FAILURE 2)"
  if [ "$HOST" = "artifact-sandbox" ]; then
    writer 8 relink_artifact.py "artifact merge/relink + ASCII encode"
    python3 "$BIN/encode_regions.py" "$DOCS"/*.html || fail "step 8 ASCII encode failed"
  else
    say "step 8 — artifact merge/relink skipped (host=$HOST, not artifact-sandbox)"
  fi
  say "step 9 — cheap gates"
  cheap_gates || fail "HARD STOP 4 — a red mechanical gate. Craft never outranks it. Return to the last factory step."
  say "step 10 — update STATE.pages[], factbase.asOf, STATE.cost[]"
  writer 10 update_state.py  "STATE.pages[] + factbase.asOf"
  record_cost "P3-build"
  say "OK — host=$HOST src=$SRC_LANG"
}

build_dirty() {
  # §7.4 — rebuild only the roles the day's diff names. An empty diff still
  # bumps factbase.asOf: silence is a bug.
  local latest
  latest="$(ls -1 "$DIFFDIR"/*.json 2>/dev/null | tail -1)"
  [ -n "$latest" ] || fail "no data/.diff/<date>.json. Write one (even an empty diff) before a dirty rebuild."
  say "dirty rebuild from $(basename "$latest")"
  python3 - "$latest" "$BIN/page-role.json" <<'PY'
import json, sys
diff = json.load(open(sys.argv[1], encoding='utf-8'))
m = json.load(open(sys.argv[2], encoding='utf-8'))['_dirtyMap']
roles = set(diff.get('dirtyPages') or [])
for cat in ('sessions', 'speakers', 'sponsors'):
    blk = diff.get(cat) or {}
    if blk.get('added') or blk.get('removed'):
        roles |= set(m.get(cat + '.*', []))
    for ch in blk.get('changed') or []:
        key = '%s.%s' % (cat, ch.get('field'))
        roles |= set(m.get(key, m.get(cat + '.*', [])))
print('dirty roles: ' + (' '.join(sorted(roles)) or '(none — asOf bump only)'))
PY
  build_all
}

usage() {
  cat <<EOF
usage: make.sh [all|check-fresh|gates|dirty|views|docs]
  all          steps 1-10 in order (default)
  check-fresh  §7.6 freshness alarm; exits non-zero when factbase.staleAfter is past
  gates        step 9 only (facts, form, i18n, qa)
  dirty        rebuild only the roles data/.diff/<date>.json names, then all
  views        step 2 only (rebuild generated views from JSON)
  docs         step 7 only (write docs/)
ROOT=$ROOT  host=$HOST  src-lang=$SRC_LANG
EOF
}

case "${1:-all}" in
  all)          build_all ;;
  check-fresh)  check_fresh ;;
  gates)        cheap_gates || exit 1 ;;
  dirty)        build_dirty ;;
  views)        writer 2 build_views.py "rebuild views from JSON" ;;
  docs)         writer 7 write_docs.py "write docs/" ;;
  -h|--help|help) usage ;;
  *)            usage; exit 1 ;;
esac
