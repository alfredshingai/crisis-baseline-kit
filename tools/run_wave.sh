#!/usr/bin/env bash
# Build every country listed in tools/build_order.txt, one at a time,
# committing after each successful country (push included).
# Trims raw rasters/zips after each success to bound disk use; appends a
# one-line status per country to tools/build_status.txt.
set -u
cd "$(dirname "$0")/.."
CBK=.venv/Scripts/cbk
[ -x "$CBK" ] || CBK=.venv/bin/cbk
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python

ORDER="${1:-tools/build_order.txt}"
: > tools/build_status.txt
while read -r iso; do
  [ -z "$iso" ] && continue
  echo "=== building $iso ===" >&2
  if out=$("$CBK" build "$iso" --force 2>&1); then
    n=$("$PY" - "baselines/$iso" <<'EOF'
import json, glob, sys
d = sorted(glob.glob(sys.argv[1] + "/*/quality_report.json"))[-1]
q = json.load(open(d, encoding="utf-8"))
detail = next(c["detail"] for c in q["checks"] if c["check"] == "admin2_nonempty")
print(detail.split()[0])
EOF
)
    fac=$("$PY" - "baselines/$iso" <<'EOF'
import json, glob, sys
d = sorted(glob.glob(sys.argv[1] + "/*/manifest.json"))[-1]
m = json.load(open(d, encoding="utf-8"))
f = [l for l in m["layers"] if l["layer"] == "facilities"]
print(f[0]["metadata"].get("facility_count", "-") if f else "-")
EOF
)
    rm -f baselines/$iso/*/raw/*.tif baselines/$iso/*/raw/*.zip
    rm -rf baselines/$iso/*/raw/codab_extract
    echo "$iso OK admin2=$n facilities=$fac" >> tools/build_status.txt
    "$PY" tools/pin_counts.py >/dev/null 2>&1 || true
    git add -A
    git commit -q -m "baseline: $iso built (admin units: $n, facilities: $fac)" || true
    git push -q origin main 2>/dev/null || true
  else
    echo "$iso FAIL: $(echo "$out" | grep -E "Error|error" | tail -1)" >> tools/build_status.txt
  fi
done < "$ORDER"
echo "WAVE COMPLETE" >> tools/build_status.txt
