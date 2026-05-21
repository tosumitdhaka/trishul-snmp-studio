# GitHub Workflow

This repo uses stable delivery IDs from [issue_tracker.md](issue_tracker.md) to
keep GitHub issues, milestones, pull requests, and the publish path tied to the
shipped release line.

## CI And Image Publish

The repo ships one GitHub Actions workflow:

- `.github/workflows/ghcr-publish.yml`

That workflow runs automatically on every push to `main`.

Responsibilities:

- build the merged application image from the repo `Dockerfile`
- publish a multi-architecture manifest for `linux/amd64` and `linux/arm64`
- push `ghcr.io/<owner>/trishul-snmp-suite:latest`
- push `ghcr.io/<owner>/trishul-snmp-suite:${APP_VERSION}`

`${APP_VERSION}` is loaded from the repo `.env`, so version bumps must be in
the tree before pushing the release commit to `main`.

## ID Rules

Two ID families:

- release-bound implementation slices: `S0` through `S13`
- deferred follow-up items: `POST-200-*` and `POST-210-*`

Every scoped issue or PR should reference at least one primary ID.

Recommended title format:

- Issue: `[S13] Final shell consolidation and test cleanup`
- PR: `[POST-210-003] Add notification history replay to Traps page`

## Branch Naming

- `release/s13-shell-consolidation`
- `post-200/post-200-003-bundle-import-export`
- `post-210/post-210-003-history-replay`

## Labels

Recommended groups:

- type: `type:feature`, `type:fix`, `type:docs`, `type:release`
- area: `area:backend`, `area:frontend`, `area:docs`, `area:runtime`, `area:packaging`
- release: `release:2.0.0` or `release:post-2.0`

## Milestones

- `v2.0.0`
- `post-v2.0.0`

Each issue belongs to one milestone only.

## Pull Requests

Pull requests should:

1. reference the primary ID in the title and body
2. list the verification steps that were actually run
3. call out docs or changelog updates when behavior changed
4. use `.github/pull_request_template.md`

Do not mark a tracker item `Done` until code, docs, and verification have all
landed together.
