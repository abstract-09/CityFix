#!/usr/bin/env python3
"""Start CityFix with one command:  python run.py

Builds the frontend when Node is installed (optional: the app also runs from the source files),
creates the database and demo data on first start, and serves API + UI on http://localhost:8000.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def build_frontend() -> None:
    if not shutil.which("node"):
        print("Node.js not found: serving the frontend from source (this works fine).")
        return
    result = subprocess.run(["node", "frontend/build.mjs"])
    if result.returncode != 0:
        sys.exit("Frontend build failed. Fix the error above, or run with --no-build.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CityFix server")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default 127.0.0.1)")
    parser.add_argument("--no-build", action="store_true", help="skip the frontend build")
    parser.add_argument("--reseed", action="store_true", help="reset to the three sample reports, then start")
    parser.add_argument("--extra", type=int, default=0, help="with --reseed: also add N random demo reports")
    args = parser.parse_args()

    if not args.no_build:
        build_frontend()

    from backend.app import create_app
    from backend.services import seed_service

    app = create_app(overrides={"auto_seed": not args.reseed} if args.reseed else None)
    if args.reseed:
        seed_service.seed_app(app, reset=True, extra=args.extra)
    port = app.extensions["cityfix"].settings.port
    print(f"\nCityFix is running at http://localhost:{port}\n")
    app.run(host=args.host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
