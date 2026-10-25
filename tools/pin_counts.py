"""Pin expected admin-unit counts into profiles from completed builds.

Reads each passing bundle's quality report and inserts an "as built"
expected_admin2_count gate (+/-3) into the country profile. Idempotent:
profiles that already carry a count gate are skipped.

Usage: python tools/pin_counts.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pinned, skipped = [], []
    for qfile in sorted((ROOT / "baselines").glob("*/*/quality_report.json")):
        iso = qfile.parts[-3]
        q = json.loads(qfile.read_text(encoding="utf-8"))
        if not q.get("passed"):
            skipped.append(f"{iso} (quality FAIL)")
            continue
        detail = next((c["detail"] for c in q["checks"] if c["check"] == "admin2_nonempty"), None)
        if not detail:
            skipped.append(f"{iso} (no count)")
            continue
        n = int(detail.split()[0])
        prof = ROOT / "profiles" / f"{iso}.yaml"
        if not prof.exists():
            skipped.append(f"{iso} (no profile)")
            continue
        text = prof.read_text(encoding="utf-8")
        if "expected_admin2_count" in text:
            skipped.append(f"{iso} (already pinned)")
            continue
        date = qfile.parts[-2]
        text = text.replace(
            "checks:\n",
            f"checks:\n  # As built {date} (COD-AB feature count {n}); +/-3 for minor source updates.\n"
            f"  expected_admin2_count: [{max(1, n - 3)}, {n + 3}]\n",
            1,
        )
        prof.write_text(text, encoding="utf-8")
        pinned.append(f"{iso}={n}")
    print("pinned:", " ".join(pinned))
    print("skipped:", " ".join(skipped) or "-")


if __name__ == "__main__":
    main()
