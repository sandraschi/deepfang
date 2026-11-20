# Contributing to deepfang

Small fleet repo, one maintainer plus collaborators, zero patience for process theatre. These rules exist so your contribution gets merged instead of stalled.

## Issues first

- **Search before you file.** Duplicates get closed.
- **One issue, one request.** Two features = two issues.
- **Bug reports need the reproducer**: the deepfang tool called, its operation and params, plus the exact error or receipt text. Without those, most reports cannot be reproduced.
- **Feature requests need a use case**: which agent workflow you are protecting, from what?

## Pull requests

- **File the issue first** (unless it's a trivial fix: typo, broken link, lint). The issue is where scope gets agreed before code exists.
- **Keep diffs small.** One concern per PR. Max 5 files per commit.
- **Tests required.** New behavior without a test is a draft, not a PR. Run `uv run pytest tests -q` before pushing.
- **Lint green:** `uv run ruff check src tests`.
- **The maintainer merges.** Don't merge your own PR.

## Pipeline rules: the hard parts

- **Stage 3 dispatch requires prior approval in the audit log.** Never bypass adjudication.
- **No stubs presented as implementations.** Unfinished code is explicit, never plausible-looking filler.
- **Timestamped `.bak` before any edit touching 3+ files.** Cleanup when satisfied.
- **No em dashes anywhere** (Unicode safety). ASCII prose.

## What this repo never does

- **No live execution traces in tests.** Mock the pipeline boundary; live verification is manual + documented.
- **No hardcoded secrets or tokens**, in code or examples. Keys come from env, always optional.
- **No fake verdicts.** No threat scores invented from memory — pipeline output or honest empty, never filler.

Issue forms: [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/) (bug report, feature request).
