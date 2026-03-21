#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./tools/guarded_closeout.sh [options]

Runs the required closeout sequence under an atomic repository lock:
  1. bd dolt push
  2. git pull --rebase
  3. git push
  4. git status

Options:
  --dry-run                  Print the guarded steps without executing them.
  --hold-lock-seconds N      Keep the lock for N seconds before cleanup.
                             Intended only for verification.
  --force-clear-stale-lock   Remove a stale dead-PID lock before running.
  --clear-stale-lock-only    Remove a stale dead-PID lock and exit.
  --print-lock-path          Print the lock directory path and exit.
  -h, --help                 Show this help.
EOF
}

repo_root="$(git rev-parse --show-toplevel)"
git_dir="$(git -C "${repo_root}" rev-parse --git-dir)"
if [[ "${git_dir}" != /* ]]; then
  git_dir="${repo_root}/${git_dir}"
fi

lock_dir="${git_dir}/guarded-closeout.lock"
metadata_file="${lock_dir}/metadata"
dry_run=0
force_clear_stale_lock=0
clear_stale_lock_only=0
print_lock_path=0
hold_lock_seconds=0
command_value="$0"
if [[ $# -gt 0 ]]; then
  command_value+=" $*"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      dry_run=1
      ;;
    --hold-lock-seconds)
      shift
      if [[ $# -eq 0 || ! "$1" =~ ^[0-9]+$ ]]; then
        echo "error: --hold-lock-seconds requires a non-negative integer" >&2
        exit 1
      fi
      hold_lock_seconds="$1"
      ;;
    --force-clear-stale-lock)
      force_clear_stale_lock=1
      ;;
    --clear-stale-lock-only)
      clear_stale_lock_only=1
      ;;
    --print-lock-path)
      print_lock_path=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "${print_lock_path}" -eq 1 ]]; then
  printf '%s\n' "${lock_dir}"
  exit 0
fi

hostname_value="$(hostname)"
started_at_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

write_metadata() {
  local step="$1"
  local temp_file
  temp_file="${metadata_file}.tmp.$$"
  cat >"${temp_file}" <<EOF
pid=$$
host=${hostname_value}
started_at_utc=${started_at_utc}
repo_root=${repo_root}
current_step=${step}
command=${command_value}
EOF
  mv "${temp_file}" "${metadata_file}"
}

read_metadata_value() {
  local key="$1"
  [[ -f "${metadata_file}" ]] || return 1
  sed -n "s/^${key}=//p" "${metadata_file}" 2>/dev/null | head -n 1
}

pid_is_live() {
  local pid="$1"
  [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null
}

clear_stale_lock_if_requested() {
  [[ -d "${lock_dir}" ]] || return 0

  local existing_pid existing_host existing_started existing_step
  existing_pid="$(read_metadata_value pid || true)"
  existing_host="$(read_metadata_value host || true)"
  existing_started="$(read_metadata_value started_at_utc || true)"
  existing_step="$(read_metadata_value current_step || true)"

  if pid_is_live "${existing_pid}"; then
    cat >&2 <<EOF
error: guarded closeout is already running.
lock: ${lock_dir}
pid: ${existing_pid}
host: ${existing_host:-unknown}
started_at_utc: ${existing_started:-unknown}
current_step: ${existing_step:-unknown}

Wait for that run to finish. If it is truly stuck, inspect ${metadata_file} before clearing it.
EOF
    exit 1
  fi

  if [[ "${force_clear_stale_lock}" -eq 1 ]]; then
    rm -rf "${lock_dir}"
    return 0
  fi

  cat >&2 <<EOF
error: found a stale guarded closeout lock with a dead or missing PID.
lock: ${lock_dir}
pid: ${existing_pid:-unknown}
host: ${existing_host:-unknown}
started_at_utc: ${existing_started:-unknown}
current_step: ${existing_step:-unknown}

Refusing to continue automatically. Re-run with --force-clear-stale-lock after confirming the old process is gone.
EOF
  exit 1
}

clear_stale_lock_only_if_requested() {
  [[ "${clear_stale_lock_only}" -eq 1 ]] || return 0

  if [[ ! -d "${lock_dir}" ]]; then
    echo "No guarded closeout lock exists at ${lock_dir}."
    exit 0
  fi

  local existing_pid
  existing_pid="$(read_metadata_value pid || true)"
  if pid_is_live "${existing_pid}"; then
    echo "error: refusing to clear live guarded closeout lock owned by PID ${existing_pid}" >&2
    exit 1
  fi

  rm -rf "${lock_dir}"
  echo "Cleared stale guarded closeout lock at ${lock_dir}."
  exit 0
}

acquire_lock() {
  clear_stale_lock_if_requested

  if ! mkdir "${lock_dir}" 2>/dev/null; then
    clear_stale_lock_if_requested
    if ! mkdir "${lock_dir}" 2>/dev/null; then
      echo "error: unable to acquire guarded closeout lock at ${lock_dir}" >&2
      exit 1
    fi
  fi

  write_metadata "lock-acquired"
}

cleanup_lock() {
  local recorded_pid
  recorded_pid="$(read_metadata_value pid || true)"
  if [[ -d "${lock_dir}" && "${recorded_pid}" == "$$" ]]; then
    rm -rf "${lock_dir}"
  fi
}

run_step() {
  local step="$1"
  shift

  write_metadata "${step}"
  printf '==> %s\n' "${step}"

  if [[ "${dry_run}" -eq 1 ]]; then
    printf 'dry-run:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi

  "$@"
}

clear_stale_lock_only_if_requested
acquire_lock
trap cleanup_lock EXIT INT TERM

cd "${repo_root}"

run_step "bd dolt push" bd dolt push
run_step "git pull --rebase" git pull --rebase
GUARDED_CLOSEOUT_ALLOW_GIT_PUSH=1 run_step "git push" git push
run_step "git status" git status

if [[ "${hold_lock_seconds}" -gt 0 ]]; then
  write_metadata "holding-lock-for-verification"
  sleep "${hold_lock_seconds}"
fi
