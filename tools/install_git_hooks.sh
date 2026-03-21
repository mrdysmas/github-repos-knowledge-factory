#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
git -C "${repo_root}" config core.hooksPath .githooks

echo "Configured git hooks path: .githooks"
echo "Pre-commit gate now enforces: python3 tools/check_intake_queue_sync.py --workspace-root ."
echo "Pre-push gate now enforces: ./tools/guarded_closeout.sh (or deliberate GUARDED_CLOSEOUT_BYPASS_PRE_PUSH=1 override)"
