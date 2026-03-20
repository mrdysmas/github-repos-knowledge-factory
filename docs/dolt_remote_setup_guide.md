# Dolt Self-Hosted Remote Setup Guide

How to set up a self-hosted dolt remote — for standalone dolt databases or beads (bd) projects.

## Background

DoltHub (`doltremoteapi.dolthub.com`) is Dolt's hosted remote service, analogous to GitHub for git. It works for many use cases, but we've hit persistent server-side corruption (checksum errors on push, "Error fetching database" on the web UI) that isn't fixable from the client side. See `memory/project_dolt_push_troubleshooting.md` for the full investigation.

Self-hosted remotes avoid this dependency entirely.

## Remote Options

### 1. Filesystem Remote (file://)

The simplest option. No server process needed. Works anywhere you can mount a path.

**How it works:** Dolt writes chunk files directly to the target directory. The directory is *not* an initialized dolt repo — it's a storage location for Dolt's internal chunk format.

```bash
# Create the remote directory (do NOT run dolt init in it)
mkdir -p /path/to/remote/my-database

# Add it as a remote
dolt remote add origin file:///path/to/remote/my-database

# Push
dolt push origin main

# Clone from it later
dolt clone file:///path/to/remote/my-database
```

**Good for:** Single-user, local backup, and local-disk remotes on the same machine.

**Limitations:** No access control. No concurrent write safety across machines. The path must be mounted and accessible at push/pull time. Network-mounted filesystems can be risky for live Dolt writes.

#### Filesystem remote locations

| Location | Pros | Cons |
|----------|------|------|
| Local directory (e.g. `~/.dolt-remotes/`) | Always available, fast | No off-machine redundancy |
| SMB/NFS share (e.g. NAS) | Off-machine storage, existing infrastructure | Must be mounted, slower over network, spaces in mount paths can cause issues, and can fail on Dolt manifest / table-file updates during push |
| Taildrive (WebDAV via Tailscale) | Available anywhere on your tailnet, no port forwarding | Requires Tailscale running, WebDAV mount, newer feature with potential quirks |
| External drive / USB | Portable, offline backup | Must be physically connected |

#### Recommendation

Use a normal local-disk path for the live filesystem remote, for example `~/.dolt-remotes/<db>` or `~/.beads-remotes/<db>`.

If you want off-machine redundancy, mirror that local remote to SMB/NAS/backup storage separately. Do not use SMB/NFS as the primary live `dolt push` target unless you have already proven that your exact setup is stable under repeated push / clone cycles.

### 2. Taildrive (Tailscale File Sharing)

If you use Tailscale, Taildrive lets you share directories across your tailnet without setting up SMB/NFS. It runs a WebDAV server on `100.100.100.100:8080` while Tailscale is connected.

```bash
# On the machine hosting the remote, share a directory via Tailscale settings
# (Settings → File Sharing → Choose Shared Folders)

# On macOS, mount via Finder: Go → Connect to Server → http://100.100.100.100:8080

# Then use as a filesystem remote
dolt remote add origin file:///Volumes/Tailscale/machine-name/shared-dir/my-database
```

**Requirements:**
- Tailscale 1.64.0+ on both machines
- Node attributes `drive:share` (host) and `drive:access` (client) in your tailnet policy
- Tailscale must be connected for push/pull

**Docs:** https://tailscale.com/kb/1369/taildrive

### 3. Dolt remotesrv (Self-Hosted gRPC Server)

A lightweight server that implements Dolt's remote chunk store protocol over gRPC + HTTP. Ships in the Dolt source repo but must be built from source.

```bash
# Build from source
git clone https://github.com/dolthub/dolt.git
cd dolt/go/utils/remotesrv
go build .

# Run it
./remotesrv --http-port 1234 --dir /path/to/remote-storage

# This starts:
#   - gRPC listener on port 50051 (chunk store API)
#   - HTTP file server on port 1234

# Add as remote (use the gRPC port in the URL)
dolt remote add origin http://your-server:50051/org-name/repo-name
dolt push origin main
```

**Good for:** Multi-machine access without shared filesystems, LAN servers, more git-like workflow.

**Limitations:** Must build from source. No web UI. No auth (run on trusted networks or behind a VPN/Tailscale).

**Source & docs:**
- https://github.com/dolthub/dolt/tree/main/go/utils/remotesrv
- https://www.dolthub.com/blog/2021-07-19-remotes/

### 4. Cloud Storage (S3/GCS)

Dolt natively supports S3 and GCS as remote backends.

```bash
# AWS S3
dolt remote add origin aws://[your-bucket:your-prefix]/db-name

# Google Cloud Storage
dolt remote add origin gs://[your-bucket]/db-name
```

**Good for:** Durable, highly-available storage. Teams already using cloud infra.

**Limitations:** Requires cloud credentials configured. Cost per operation. Overkill for single-user issue tracking.

**Docs:** https://docs.dolthub.com/sql-reference/version-control/remotes

---

## Beads (bd) Integration

When using bd for issue tracking, the dolt remote is managed through bd's wrapper commands. bd runs a dolt sql-server process and maintains remote config at both the SQL and CLI levels — they must stay in sync.

### Setting up a remote for bd

```bash
# Add remote (registers in both SQL server and CLI config)
bd dolt remote add origin file:///path/to/remote

# Push
bd dolt push

# Pull
bd dolt pull

# Check remote config
bd dolt remote list

# Show full dolt config with connection status
bd dolt show
```

### Gotchas

**Spaces in paths:** bd splits `file://` URLs at spaces, creating a SQL/CLI config conflict. Use a symlink to a space-free path:

```bash
ln -s "/Volumes/my nas share/dolt/my-db" ~/.my-dolt-remote
bd dolt remote add origin file:///Users/you/.my-dolt-remote
```

**Server must be stopped for some operations:** `dolt archive --revert` and direct CLI operations on the database require stopping the bd server first:

```bash
bd dolt stop
# ... do CLI operations ...
bd dolt start
```

**Remote sync conflicts:** If SQL and CLI remotes get out of sync (shows `[CONFLICT]` in `bd dolt remote list`), force-remove and re-add:

```bash
bd dolt remote remove origin --force
bd dolt remote add origin file:///path/to/remote
```

**Network share failure mode:** A mounted SMB path can look healthy enough to read, clone, and even accept ordinary file writes, while `bd dolt push` / `dolt push` still fails during low-level NBS manifest updates. In this repo we saw:

- `unknown push error; open /Users/szilaa/.beads-remote/nbs_table_*: no such file or directory`
- `unknown push error; addTableFiles, updateManifestAddFiles: timed out reading database manifest`

Important nuance: `.beads/push-state.json` can remain stale even when part of the Beads history actually reached the remote, so do not assume "push-state did not advance" means "nothing landed." Verify by cloning the remote or checking `dolt branch -av` in the local repo.

If you hit this pattern:

1. Verify whether the remote is still readable with `dolt clone file:///path/to/remote /tmp/clone-check`.
2. Compare local `main` vs `remotes/origin/main` in the local Beads repo.
3. If reads work but pushes keep failing, rebuild the remote onto a local-disk path and repoint the symlink / remote URL there.

### Current project setup (github_repos)

- **Live remote path:** `/Users/szilaa/.beads-remotes/github_repos` (local disk)
- **Live symlink:** `/Users/szilaa/.beads-remote` → live remote path
- **Remote URL:** `file:///Users/szilaa/.beads-remote`
- **Archived SMB target:** `/Users/szilaa/.beads-remote-smb-backup` → `/Volumes/scripts opaio projects/dolt/github-repos`
- **Reason for migration:** the SMB-backed remote was readable and cloneable, but repeatedly failed on `bd dolt push` / `dolt push` during NBS table-file and manifest update steps

---

## Standalone Dolt (non-beads)

For a plain dolt database (no bd), remote setup is simpler — just use `dolt remote` directly:

```bash
cd /path/to/your/dolt/repo
dolt remote add origin file:///path/to/remote/storage
dolt push origin main
```

No server process to manage, no SQL/CLI sync issues. The same remote location options (filesystem, Taildrive, remotesrv, cloud) all apply.

---

## Dolt Archive Format Note (v1.75+)

Dolt 1.83+ enables the **archive storage format** by default. `dolt gc` produces `.darc` files instead of traditional table files. This is fine for local use and filesystem remotes, but has caused issues with DoltHub's API (checksum errors on push).

If you ever need to revert to legacy format:

```bash
# Stop any running server first
dolt archive --revert
```

To disable archive creation during GC, pass `--archive-level 0` or set the config before running GC.
