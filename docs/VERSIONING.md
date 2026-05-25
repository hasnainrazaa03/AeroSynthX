# AeroSynthX — Versioning & Release Strategy

---

## 1. Versioning Scheme

AeroSynthX follows [Semantic Versioning 2.0.0](https://semver.org/).

`MAJOR.MINOR.PATCH`:

- **MAJOR** — incompatible API or schema changes, or a documented break in
  user-visible behavior.
- **MINOR** — backwards-compatible functionality additions.
- **PATCH** — backwards-compatible bug fixes and internal changes.

Pre-1.0 status: the public API is considered unstable. We will still
respect SemVer mechanics, but minor bumps may carry breaking changes
during 0.x. The transition to `1.0.0` happens at the end of Phase 7.

Pre-releases use the `-rc.N`, `-beta.N`, `-alpha.N` suffix, e.g.
`v0.4.0-rc.1`.

---

## 2. What Counts as a Breaking Change

- Removal or renaming of a public function, module, class, CLI flag, env
  var, or API endpoint.
- Change in the shape of a persisted schema (DB or run manifest) without
  a migration.
- Change in the meaning of an existing field, even if the type is the
  same.
- Change in the structure of generated OpenFOAM cases that would prevent
  a previously valid run from re-running.

Non-breaking:
- Adding optional fields with sensible defaults.
- Adding new modules, CLI commands, endpoints.
- Internal refactors that preserve external behavior.

---

## 3. Changelog Discipline

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/).

Sections per release:
- `### Added`
- `### Changed`
- `### Deprecated`
- `### Removed`
- `### Fixed`
- `### Security`

Every PR updates the `## [Unreleased]` section. At release time the
unreleased block becomes the new versioned section with a date.

---

## 4. Release Cadence

There is no fixed time-based cadence. Releases are cut **at phase
boundaries** and ad-hoc for important fixes.

Each phase ends with at minimum one tagged release:

| Phase | Target Release |
|---|---|
| 0 | `v0.0.1` |
| 1 | `v0.1.0` |
| 2 | `v0.2.0` |
| 3 | `v0.3.0` |
| 4 | `v0.4.0` |
| 5 | `v0.5.0` |
| 6 | `v0.6.0` |
| 7 | `v1.0.0` |

Patch releases (`v0.X.Y` where `Y > 0`) are cut as needed.

---

## 5. Release Procedure

1. Confirm `main` is green on CI.
2. Update `CHANGELOG.md` — move `[Unreleased]` to a new
   `[X.Y.Z] - YYYY-MM-DD` section.
3. Bump version in `pyproject.toml` (and any other versioned manifests).
4. Open a PR titled `chore(release): vX.Y.Z`. Merge after CI green.
5. Tag the merge commit: `git tag vX.Y.Z -m "vX.Y.Z" && git push --tags`.
6. `release.yml` builds artifacts and publishes the GitHub Release.
7. Announce in `README.md` "Latest release" badge (auto-updates) and in
   the project board.

---

## 6. Hotfix Procedure

1. Branch from the tag: `git switch -c fix/<topic> vX.Y.Z`.
2. Apply the fix with tests.
3. Open a PR targeting `main`. Merge after CI green.
4. Cut a patch release `vX.Y.(Z+1)`.

Long-lived hotfix branches are not maintained pre-1.0 — only the latest
minor is supported.

---

## 7. Schema Versioning

Persisted artifacts (run manifests, project DB rows, OpenFOAM case
manifests) carry their own `schema_version` field, independent of the
software version. Schema migrations are explicit (Alembic for DB,
versioned readers for manifests).
