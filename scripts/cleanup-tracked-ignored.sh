#!/usr/bin/env bash
set -euo pipefail

# Removes files that are currently tracked by git but now matched by .gitignore.
# Default mode is dry-run (shows what would be removed from the index).
#
# Usage:
#   scripts/cleanup-tracked-ignored.sh           # dry-run
#   scripts/cleanup-tracked-ignored.sh --apply   # remove from git index

MODE="dry-run"
if [[ "${1:-}" == "--apply" ]]; then
  MODE="apply"
elif [[ "${1:-}" != "" ]]; then
  echo "Unknown option: $1"
  echo "Usage: $0 [--apply]"
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: run this script inside a git repository."
  exit 1
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

# -c: cached(tracked), -i: ignored, --exclude-standard: .gitignore + global excludes
git ls-files -ci --exclude-standard -z >"$tmp_file"

if [[ ! -s "$tmp_file" ]]; then
  echo "No tracked files matched by .gitignore were found."
  exit 0
fi

echo "Tracked files currently ignored by rules:"
while IFS= read -r -d '' path; do
  echo "  $path"
done <"$tmp_file"

if [[ "$MODE" == "dry-run" ]]; then
  echo
  echo "Dry-run only. Re-run with --apply to untrack these files."
  exit 0
fi

git rm -r --cached --pathspec-from-file="$tmp_file" --pathspec-file-nul
echo
echo "Done. Files were removed from git tracking (working-tree files remain on disk)."
echo "Next: review with 'git status' and commit the cleanup."
