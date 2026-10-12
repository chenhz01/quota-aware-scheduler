# Changelog — quota-aware-scheduler

All notable changes. Format based on Keep a Changelog; versioning: SemVer.

## [0.1.1] - 2026-10-12

### Added
- MIT LICENSE file (was missing from the release candidate).

### Verified
- Full release audit: self-test suite re-run green at `SUMMARY: PASS 42/42` (functional / exception / extreme-edge tiers). No code changes were required; the earlier session's implementation passed all three test classes as written.

## [0.1.0] - 2026-10-11

### Added
- Multi-source quota ledger: per-source limits tracked independently in one process.
- Sliding-window accounting over virtual time only (no wall-clock reads, no threads, no network) so schedules are deterministic and reproducible.
- Scheduling decision interface: given pending work and current window usage, returns an admit/defer decision per source.
- CLI with JSON output; self-test suite: 42 cases across functional, exception, and extreme-edge tiers.
