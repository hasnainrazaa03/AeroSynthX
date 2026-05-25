# Security Policy

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Until a dedicated reporting channel is in place, report privately by
opening a [GitHub Security Advisory](https://github.com/hasnainrazaa03/AeroSynthX/security/advisories/new)
on this repository (once the repo is published), or by contacting the
maintainer directly through their GitHub profile.

When reporting, please include:

- A clear description of the issue.
- Steps to reproduce, including version / commit.
- Impact assessment (what an attacker could do).
- Any suggested mitigation.

## Supported Versions

During the `0.x` series, only the latest minor release is supported for
security fixes. Once `1.0.0` is released, this policy will be updated.

## Disclosure

We aim to acknowledge reports within a reasonable timeframe and to
coordinate disclosure responsibly. Fixed issues will be credited in the
release notes unless the reporter requests otherwise.

## Hardening Posture

- No secrets in the repository.
- Dependabot enabled for dependency updates.
- Secret scanning + push protection enabled on GitHub.
- CI runs lint, type checks, and tests on every PR.
- Additional security tooling (CodeQL, SBOM, signed artifacts) is added
  in Phase 7. See [docs/phases/PHASE_7.md](docs/phases/PHASE_7.md).
