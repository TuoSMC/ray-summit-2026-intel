#!/bin/bash
# qa-gate.sh [dir-with-html] — the ship gate. Ported from event-warroom/bin.
#
# Scans every *.html: encoding (A1'), innerHTML (A2), external loads / egress
# (A3), node --check on inline scripts, contradiction detector (B2).
#
# A1' — THE ENCODING RULE IS NOW HOST-CONDITIONAL (RULES D1).
#   host == artifact-sandbox : pure ASCII, zero bytes >127. The artifact
#       wrapper's <meta charset> sits beyond the browser's 1024-byte prescan
#       window, so raw UTF-8 ships as mojibake. Run bin/encode_regions.py.
#   any other host (docs-local, private-acl) : UTF-8 is correct and encoding it
#       to entities is the defect. Require <meta charset="utf-8"> inside the
#       first 512 bytes so the prescan finds it.
#
# ROOT is a literal written by scaffold.sh (RULES B9). The dir argument only
# narrows WHICH built pages to scan; it never relocates the campaign.
ROOT='/Volumes/ClaudeNVME/26082426-RAY-SUMMIT'

set -u
DIR="${1:-$ROOT/docs}"
STATE="$ROOT/STATE.json"
FAIL=0

HOST="$(python3 - "$STATE" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception as e:
    sys.exit('unreadable STATE.json: %s' % e)
h = (d.get('campaign') or {}).get('host')
if not h:
    sys.exit('HARD STOP 5 - STATE.campaign.host is unset')
print(h)
PY
)" || { echo "qa-gate: FAIL cannot read STATE.campaign.host (see above)" >&2; exit 1; }

echo "qa-gate: host=$HOST dir=$DIR"

HOST="$HOST" python3 - "$DIR" <<'PY' || FAIL=1
import re, sys, glob, os, subprocess, tempfile, shutil

d = sys.argv[1]
host = os.environ['HOST']
strict_ascii = (host == 'artifact-sandbox')
files = sorted(glob.glob(os.path.join(d, '*.html')))
if not files:
    print("GATE: no html files in %s" % d); sys.exit(1)

HAVE_NODE = shutil.which('node') is not None
if not HAVE_NODE:
    print("GATE: WARN node not found - inline JS syntax NOT checked this run")

def dec(s):
    s = re.sub(r'&#x([0-9A-Fa-f]{2,6});', lambda m: chr(int(m.group(1), 16)), s)
    return re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), s)

SHIP = r'(已發表|已发表|出貨中|出货中|量產爬坡|量产爬坡)'
DEAD = r'(未上市|未量產|未量产|尚未發表|尚未发表)'
EXT  = re.compile(r'<(script|link|img|iframe)\b[^>]*\b(src|href)\s*=\s*"https?://', re.I)
EGRESS = re.compile(r'\b(fetch\s*\(|XMLHttpRequest|navigator\.sendBeacon|new\s+WebSocket)', re.I)
CHARSET = re.compile(rb'<meta[^>]+charset\s*=\s*["\']?\s*utf-?8', re.I)

bad = 0
for f in files:
    b = os.path.basename(f); errs = []
    raw = open(f, 'rb').read()

    # ---- A1' encoding, by host -------------------------------------------
    hi = next((i for i, c in enumerate(raw) if c > 127), -1)
    if strict_ascii:
        if hi >= 0:
            errs.append("A1 non-ASCII byte at offset %d (host=artifact-sandbox requires pure ASCII; "
                        "run bin/encode_regions.py)" % hi)
    else:
        if not CHARSET.search(raw[:512]):
            errs.append('A1 no <meta charset="utf-8"> in the first 512 bytes (host=%s). '
                        "The browser prescan gives up before it finds one and the page ships as "
                        "mojibake." % host)
        if hi < 0 and re.search(rb'&#x[0-9A-Fa-f]{4,6};', raw):
            errs.append("A1 host=%s but the file is entity-encoded. Entity encoding is for "
                        "artifact-sandbox only; ship real UTF-8 here." % host)

    s = raw.decode('ascii', 'replace') if strict_ascii else raw.decode('utf-8', 'replace')

    # ---- A2 innerHTML -----------------------------------------------------
    if re.search(r'\.innerHTML\s*=', s):
        errs.append("A2 innerHTML assignment")

    # ---- A1b entity inside <script> (never decoded => mojibake) -----------
    for m in re.finditer(r'<script\b[^>]*>(.*?)</script>', s, re.S | re.I):
        if re.search(r'&#x[0-9A-Fa-f]{2,6};', m.group(1)):
            errs.append("A1b HTML entity inside <script> (won't decode) - use \\uXXXX"); break

    # ---- A3 external loads / egress (plain <a href> citations are fine) ---
    if EXT.search(s):
        errs.append("A3 external resource load (script/link/img/iframe src)")
    if EGRESS.search(s):
        errs.append("A3 network egress call (fetch/XHR/beacon/WS)")

    # ---- inline JS syntax -------------------------------------------------
    if HAVE_NODE:
        for i, m in enumerate(re.finditer(r'<script\b[^>]*>(.*?)</script>', s, re.S | re.I)):
            body = m.group(1)
            if not body.strip():
                continue
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as t:
                t.write(body); p = t.name
            r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
            os.unlink(p)
            if r.returncode:
                head = (r.stderr.strip().splitlines() or [''])[0][:100]
                errs.append("JS syntax script#%d: %s" % (i, head))

    # ---- B2 contradiction: ship-tag within 40 chars of dead-tag ----------
    t = dec(s)
    for m in re.finditer(SHIP, t):
        w = t[max(0, m.start() - 40):m.end() + 40]
        if re.search(DEAD, w):
            errs.append("B2 contradiction: ...%s..." % w[:60].strip()); break

    if errs:
        bad += 1
        print("FAIL %s" % b)
        for e in errs:
            print("  - %s" % e)
    else:
        print("PASS %s" % b)

print("GATE: %d/%d pass" % (len(files) - bad, len(files)))
sys.exit(1 if bad else 0)
PY

exit $FAIL
