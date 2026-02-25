#!/usr/bin/env bash
set -euo pipefail

workspace_root="${1:-.}"

python3 tools/check_intake_queue_sync.py --workspace-root "${workspace_root}"
