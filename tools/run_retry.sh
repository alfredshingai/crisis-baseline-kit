#!/usr/bin/env bash
# Build every country listed in tools/retry_order.txt, one at a time.
# Trims raw rasters/zips after each success to bound disk use; appends a
# one-line status per country to tools/retry_status.txt.
set -u
cd "$(dirname "$0")/.."
CBK=.venv/Scripts/cbk
[ -x "$CBK" ] || CBK=.venv/bin/cbk
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python

: > tools/retry_status.txt
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
    echo "$iso OK admin2=$n facilities=$fac" >> tools/retry_status.txt
  else
    echo "$iso FAIL: $(echo "$out" | grep -E "Error|error" | tail -1)" >> tools/retry_status.txt
  fi
done < tools/retry_order.txt
echo "WAVE COMPLETE" >> tools/retry_status.txt
