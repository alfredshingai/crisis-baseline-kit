"""cbk command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="cbk",
        description="Crisis Baseline Kit: reproducible pre-crisis baselines from public data",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build a country baseline bundle")
    p_build.add_argument("country", help="ISO3 code (e.g. MWI) or path to a profile YAML")
    p_build.add_argument("--out", default="baselines", help="output root (default: ./baselines)")
    p_build.add_argument("--date", default=None, help="override the baseline date (YYYY-MM-DD)")
    p_build.add_argument("--force", action="store_true",
                         help="overwrite an existing bundle for the same date")

    p_serve = sub.add_parser("serve", help="serve a built bundle's map viewer locally")
    p_serve.add_argument("country", help="ISO3 code or path to a bundle directory")
    p_serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("adapters", help="list available source adapters")
    sub.add_parser("selftest", help="run the synthetic end-to-end pipeline test (no network)")

    p_diff = sub.add_parser("diff", help="diff the two latest bundles of a country")
    p_diff.add_argument("country", help="ISO3 code (e.g. MWI) or path to a baselines/<ISO> dir")

    args = parser.parse_args(argv)

    if args.command == "build":
        from .pipeline import build
        from .util import setup_logging

        setup_logging()
        bundle = build(args.country, Path(args.out), force=args.force, date=args.date)
        print(f"\nBaseline bundle: {bundle}")
        print(f"View it with:    cbk serve {bundle}")
        return 0

    if args.command == "serve":
        return _serve(args.country, args.port)

    if args.command == "diff":
        from .diff import run as run_diff
        from .util import setup_logging

        setup_logging()
        p = Path(args.country)
        if p.is_dir() and p.parent.name in ("baselines", "."):
            country_dir = p
        else:
            root = Path("baselines") / args.country.upper()
            if not root.is_dir():
                raise SystemExit(f"No bundles under {root}; run `cbk build` first")
            country_dir = root
        run_diff(country_dir)
        return 0

    if args.command == "adapters":
        from .adapters import ADAPTERS

        for name, cls in sorted(ADAPTERS.items()):
            print(f"{name:12s} {cls.description}")
        return 0

    if args.command == "selftest":
        from .selftest import run

        return 0 if run() else 1

    return 1


def _bundle_dir(country: str) -> Path:
    p = Path(country)
    if p.is_dir():
        return p
    root = Path("baselines") / country.upper()
    if not root.is_dir():
        raise SystemExit(f"No bundles under {root}; run `cbk build {country.upper()}` first")
    dated = sorted(d for d in root.iterdir() if d.is_dir())
    if not dated:
        raise SystemExit(f"No dated bundles under {root}")
    return dated[-1]


def _serve(country: str, port: int) -> int:
    import functools
    import http.server

    bundle = _bundle_dir(country)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(bundle))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        print(f"Serving {bundle}")
        print(f"Open http://127.0.0.1:{port}/index.html (Ctrl+C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
