# AGENTS.md — `scripts/`

Cross-folder entry points. This folder holds the repo-wide verification
dispatcher, not per-folder logic — read the repo-root `AGENTS.md` first.

---

## What's here

- `verify` — dispatches to each top-level folder's own `<folder>/scripts/verify`
  and aggregates PASS/SKIPPED/FAIL into one exit code.

```bash
scripts/verify                     # every folder that has a verify script
scripts/verify robot                # one folder only
scripts/verify robot digital-twin   # several folders
```

Exit code contract: `0` = PASS, non-zero = FAIL. A folder's own verify script
may exit `3` to mean SKIPPED (nothing to verify yet) — the dispatcher treats
that as neither pass nor fail, but a skip is still not a pass; say so when
reporting.

---

## Rules

- Do not add per-folder build/test logic here. That belongs in
  `<folder>/scripts/verify` inside the owning top-level folder — this
  dispatcher only calls out to it.
- Do not change the exit-code contract (`0` pass, non-zero fail, `3` skipped)
  without updating every folder's verify script and CI that depends on it.
- New top-level folders that get their own `scripts/verify` must be added to
  the default `TARGETS` list in `scripts/verify`, and to the table in the
  repo-root `AGENTS.md`.
