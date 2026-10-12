# ALIGNMENT.md — R13 alignment record (16 items)

Design source: `_r13_design.json` → repo `quota-aware-scheduler`,
domain 配额感知调度, sim `adjacent`. Date of record: 2026-10-11.

| # | Item | Evidence |
| --- | --- | --- |
| 1 | Repo name matches design entry | Directory `quota-aware-scheduler` == design JSON `name`. |
| 2 | Mechanism implemented as specified | Design mechanism "多源配额账本+滑动窗口计算+调度决策接口" → `QuotaLedger`, sliding-window `used()/available()`, `decide()/plan()` interface in core.py. |
| 3 | Pure Python standard library only | Imports: argparse, json, sys (+ os/tempfile in tests). No network calls anywhere. |
| 4 | CLI entry via argparse | `core.py main()` argparse with JSON spec input; README quickstart runs as written. |
| 5 | self_test.py ≥40 cases, three categories | Functional (ledger windows, decide/plan), exception paths (zero/negative/bool costs, unknown sources, impossible cost), extreme edge (window 0, negative timestamps, 5000 events, unicode names, empty jobs). |
| 6 | Final line `SUMMARY: PASS n/n` | `python self_test.py` ends with that exact line. |
| 7 | README first paragraph ≤60 words | Intro ~55 words (counted 2026-10-11). |
| 8 | README required sections present | All mandated sections incl. FAQ "When NOT to use" and 3 Core Assumptions. |
| 9 | why-not-X ≥3 alternatives with real anchors | Table lists rstrobl/rate_limited_scheduler (4★), ase-sketch/dsh-agent-swarm (6★), putflix/rate-limit-scheduler (0★) with stars from design JSON and paraphrased differences. |
| 10 | MIT LICENSE, "zhengming contributors" | LICENSE copyright line as required; no real names. |
| 11 | CHANGELOG v0.1.0 → v0.1.1 | CHANGELOG.md documents both versions dated 2026-10-11. |
| 12 | Two-round iteration, ≥1 dimension ≥20% | Round 2 added burst rule `min_interval_s` + `fairness_report()` + 11 new tests (43 → 54, +25.6% tests). Recorded in CHANGELOG v0.1.1. |
| 13 | Number discipline | Test counts quoted from self_test SUMMARY output (repro: `python self_test.py`); README makes no unverified performance claims. |
| 14 | Zero secrets / zero real names | No keys; contact placeholder only hcac4735@agent.qq.com if any; "zhengming contributors" copyright. |
| 15 | No >50-char text copied from anchors | Anchor facts reduced to name + stars + one paraphrased difference sentence. |
| 16 | as-of date marked | README headline and Confidence footer say "as of 2026-10-11". |
