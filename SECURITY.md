# Security Policy

## Supported Versions

Only the latest release is actively maintained with security updates.

| Version | Supported |
| ------- | --------- |
| latest  | ✅        |
| older   | ❌        |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do NOT open a public issue**. Instead, report it privately:

1. **Email**: Contact the repository owner through GitHub's private vulnerability reporting feature
2. **GitHub Security Advisories**: Go to the repository's **Security → Advisories → New draft security advisory**

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

## Security Best Practices for Users

- Always use the latest release
- Review the source code before running in production
- Do not commit API keys, tokens, or credentials to the repository
- Use environment variables or external config files for sensitive data
- Regularly update dependencies (`pip install --upgrade -r requirements.txt`)
- Enable GitHub Dependabot alerts for dependency vulnerability monitoring

## Scope

This security policy covers:
- The MCP server (`tools/hitran_mcp.py`)
- The desktop application (`app/hitran_app.py`)
- The core library (`tools/hitran.py`)
- Build and packaging scripts

This policy does **not** cover:
- Third-party dependencies (report to upstream maintainers)
- HITRANonline data or services (report to HITRAN team)
- User-generated configuration files or data
