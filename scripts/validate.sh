#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m build

echo "Smoke-testing CLI against fixture libraries..."
python3 -m stepmania_song_validator.cli tests/fixtures/valid_library >/dev/null
if python3 -m stepmania_song_validator.cli tests/fixtures/broken_library >/dev/null; then
  echo "Expected broken_library fixture to fail validation (exit 1), but it passed." >&2
  exit 1
fi

echo "Validation passed."
