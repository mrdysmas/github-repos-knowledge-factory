# Guarded Closeout Wrapper

Primary closeout entrypoint:

```bash
./tools/guarded_closeout.sh
```

This wrapper is the enforced path for the end-of-session landing sequence. It runs:

1. `bd dolt push`
2. `git pull --rebase`
3. `git push`
4. `git status`

The wrapper waits for each command to exit before starting the next one. It is designed to prevent overlapping closeout flows and stale pre-push status checks.

## Lock Behavior

The wrapper creates an atomic lock directory under the active repo git directory:

```text
.git/guarded-closeout.lock/
```

Inside the lock directory it writes:

```text
metadata
```

`metadata` is a line-oriented file with:

- `pid`: PID that owns the lock
- `host`: hostname where the wrapper started
- `started_at_utc`: UTC start timestamp
- `repo_root`: absolute repo root
- `current_step`: current guarded step
- `command`: wrapper invocation string

## Concurrent Invocation Handling

If another wrapper run is active and its PID is still alive, the second invocation fails immediately and prints the lock path plus the recorded metadata. It does not wait or retry silently.

## Stale Lock Handling

If the lock exists but the recorded PID is dead or missing, the wrapper treats it as stale and refuses to continue automatically.

Clear a confirmed stale lock and exit with:

```bash
./tools/guarded_closeout.sh --clear-stale-lock-only
```

To clear a stale lock and then continue directly into the guarded closeout flow, use:

```bash
./tools/guarded_closeout.sh --force-clear-stale-lock
```

Neither flag removes a live lock.

## Backup Hook

The repo `pre-push` hook blocks direct `git push` attempts unless they come from the guarded wrapper, which sets `GUARDED_CLOSEOUT_ALLOW_GIT_PUSH=1` for its own `git push` step.

For an intentional manual bypass, set:

```bash
GUARDED_CLOSEOUT_BYPASS_PRE_PUSH=1 git push
```

Use that only when you mean to bypass the backup enforcement.
