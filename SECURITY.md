# Security Policy

## Supported Versions

Only the latest release is actively maintained with security updates.

| Version | Supported |
| ------- | --------- |
| latest  | Yes       |
| older   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do NOT open a public issue**. Instead, report it privately:

1. **GitHub Security Advisories**: Go to the repository's **Security → Advisories → New draft security advisory**
2. **Repository owner**: use the contact route shown on the GitHub profile

### What to include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact
- Suggested fix (if known)

## Response Timeline

- **Initial response**: Within 7 days
- **Assessment**: Within 14 days
- **Fix release**: As soon as a fix is available

## Security Controls

- **Local-only MCP**: the MCP server uses stdio, with no HTTP listener, public tunnel or bearer token.
- **Credential redaction**: HITRAN API keys are redacted from MCP responses, GUI messages and error logs before they leave the process.
- **Credential storage**: the API key is stored in the runtime data directory (`Hitran_Data/hitran_api_key.txt`), which is gitignored; release archives never include it.
- **Release whitelist**: release ZIP files contain only `HitranLab.exe` and `_internal`; `Hitran_Data`, `config.json`, `*.log`, `_update` and local databases are excluded.
- **Build privacy scrub**: numba `.nbc` caches (which can contain the builder's absolute paths) are removed before packaging, and the payload is re-scanned for builder paths.
- **Update integrity**: automatic updates use a fixed GitHub Release URL, require a SHA-256 digest from the GitHub API, and reject `http`, foreign hosts, size overruns, zip traversal, symlinks and non-whitelisted entries.
- **Dependency pinning**: direct runtime dependencies are pinned in `requirements.txt`; Dependabot monitors pip and GitHub Actions updates.
- **Automated gate**: `tools/security_check.py` scans tracked files, Git history, the working tree and release ZIPs for credentials, real user paths and dangerous calls; it runs in CI.

## Sensitive Data Inventory

Runtime data is intentionally kept outside Git and outside release ZIPs:

| Path | Content | Git | Release ZIP |
| --- | --- | --- | --- |
| `Hitran_Data/` | line-table cache, HAPI2 temp files, optional API key | ignored | excluded |
| `Hitran_Data/hitran_api_key.txt` | HITRAN API key (optional) | ignored | excluded |
| `config.json` | local HAPI2 settings | ignored | excluded |
| `local` / `*.db` | local HAPI2 SQLite data | ignored | excluded |
| `_update/` | downloaded update package and logs | ignored | excluded |
| `*.log` | local diagnostics | ignored | excluded |
| `xsc_data/` | user-downloaded cross-section files | ignored | excluded |

## Verification

Before publishing a release, run:

```powershell
python tools/security_check.py
```

Expected result: `"ok": true` and no `issues`. Local sensitive files may be listed as informational entries only when they are gitignored runtime files.

## Scope

This security policy covers:

- The MCP server (`tools/hitran_mcp.py`)
- The desktop application (`app/hitran_app.py`)
- The update and packaging code (`app/updater.py`, `tools/build_release.py`)
- The core library (`tools/hitran.py`)

This policy does **not** cover:

- Third-party dependencies (report to upstream maintainers)
- HITRANonline data or services (report to the HITRAN team)
- User-generated configuration files or data
