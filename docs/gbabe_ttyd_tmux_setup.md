# gbabe: Browser Terminal Setup (ttyd + tmux)

## Purpose

Persistent terminal sessions on gbabe accessible from a browser tab, surviving Mac lid closure.
Replaces Paseo's session-persistence role for interactive terminal work (Claude Code, Codex CLI, general shell).

## What's Running

| Component | Details |
|---|---|
| **ttyd** | systemd service, auto-starts on boot |
| **tmux session** | `main` — persists across browser closes and reconnects |
| **Browser URL** | `https://gbabe.tailca7be8.ts.net:8443/` |
| **TLS** | Tailscale serve on port 8443 |
| **Paseo** | Unaffected, still at `https://gbabe.tailca7be8.ts.net/` on port 443 |

## systemd Unit

`/etc/systemd/system/ttyd.service`:

```ini
[Unit]
Description=ttyd browser terminal
After=network.target

[Service]
ExecStart=/usr/bin/ttyd -p 7681 -W tmux new -A -s main
Restart=always
User=abe
Group=abe

[Install]
WantedBy=multi-user.target
```

The `tmux new -A -s main` flag means: attach to existing session `main` if it exists, create it if not.
`-W` enables write access (required — ttyd is readonly by default).

## Tailscale Serve Config

Port 8443 serves ttyd, separate from Paseo on 443:

```bash
sudo tailscale serve --bg --https 8443 http://localhost:7681
```

To check current serve config:
```bash
tailscale serve status
```

To remove ttyd from serve:
```bash
sudo tailscale serve --https=8443 off
```

## Auth

No HTTP basic auth — Tailscale ACLs are the access boundary.
Only devices on the tailnet can reach `gbabe.tailca7be8.ts.net`.

## Accessing the Terminal

### From a browser (any device on tailnet)
Open: `https://gbabe.tailca7be8.ts.net:8443/`

### From Mac (native UX via iTerm2)
Requires iTerm2. SSH into gbabe then run:

```bash
tmux -CC new -A -s main
```

iTerm2 control mode maps tmux windows to native iTerm2 tabs and panes.
`Cmd+T` creates a new tmux window. `Cmd+D` splits into a tmux pane.
Closing iTerm2 leaves the session running on gbabe.

Both access methods attach to the same `main` tmux session.

## tmux Quick Reference

| Key | Action |
|---|---|
| `Ctrl+B c` | New window |
| `Ctrl+B n` / `Ctrl+B p` | Next / previous window |
| `Ctrl+B w` | Visual window picker |
| `Ctrl+B ,` | Rename current window |
| `Ctrl+B d` | Detach (session keeps running) |
| `Ctrl+B [` | Scroll mode (q to exit) |

## Default Working Directory

To start every tmux shell in a specific directory, add to `~/.bashrc` on gbabe:

```bash
# cd to working directory when inside tmux
if [ -n "$TMUX" ]; then
    cd /your/path
fi
```

This scopes the `cd` to tmux sessions only — plain SSH sessions are unaffected.

## Notes

- ttyd uses xterm.js with xterm-256color — Claude Code and Codex CLI render correctly
- tmux prefix is `Ctrl+B` by default; keyboard passthrough in the browser works correctly
- ttyd is bound to all interfaces on port 7681 (not loopback-only); firewall/ACL relies on Tailscale
- If the session ever disappears, `ttyd` will create a fresh `main` session on next browser connect
