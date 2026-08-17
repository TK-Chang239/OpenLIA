# Security Policy

## Supported versions

OpenLIA is pre-1.0 and moves quickly. Security fixes are applied to the
`main` branch and shipped in the next release. Please run the latest
release (or `main`) before reporting an issue — older revisions are not
patched in place.

| Version | Supported |
|---|---|
| `main` / latest release | Yes |
| Older tagged releases | No |

## Reporting a vulnerability

OpenLIA is self-hosted and stores users' third-party API keys (encrypted
at rest). Please treat any weakness that could expose those secrets,
bypass authentication, or allow remote code execution as sensitive.

**Do not open a public issue for a security problem.** Report it
privately through GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability** (GitHub Security Advisories).
3. Describe the issue, affected version/commit, deployment mode
   (personal or company), and reproduction steps.

Direct link:
<https://github.com/TK-Chang239/OpenLIA/security/advisories/new>

## What to expect

- We aim to acknowledge a report within **5 business days**.
- We will confirm the issue, work on a fix, and keep you updated on
  progress.
- Once a fix is released, we are happy to credit you in the advisory
  unless you prefer to stay anonymous.

Please give us reasonable time to release a fix before any public
disclosure.
