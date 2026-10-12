#!/usr/bin/env python3
"""Self-tests for quota-aware-scheduler. Run: python self_test.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def expect(cond, msg="assertion failed"):
    if not cond:
        raise AssertionError(msg)


def expect_raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return
    raise AssertionError("expected %s to be raised" % exc.__name__)


def ledger1():
    return core.QuotaLedger({"a": {"limit": 5, "window_s": 10.0}})


# ---------- functional: ledger ----------

@case
def t_available_fresh_equals_limit():
    expect(ledger1().available("a", 0.0) == 5, "fresh headroom wrong")


@case
def t_used_counts_window_events():
    led = ledger1()
    led.record("a", 1.0, 2)
    led.record("a", 5.0, 1)
    expect(led.used("a", 6.0) == 3, "used: %r" % led.used("a", 6.0))


@case
def t_window_left_boundary_exclusive():
    led = ledger1()  # window 10
    led.record("a", 1.0, 2)
    expect(led.used("a", 11.0) == 0, "event at exactly t-w must be excluded")


@case
def t_window_right_boundary_inclusive():
    led = ledger1()
    led.record("a", 1.0, 2)
    expect(led.used("a", 1.0) == 2, "event at exactly t must count")


@case
def t_record_reduces_available():
    led = ledger1()
    led.record("a", 0.0, 2)
    expect(led.available("a", 0.0) == 3, "headroom after record wrong")


@case
def t_unknown_source_errors():
    expect_raises(core.SchedulerError, ledger1().available, "ghost", 0.0)


@case
def t_record_unknown_source_errors():
    expect_raises(core.SchedulerError, ledger1().record, "ghost", 0.0)


@case
def t_zero_cost_rejected():
    expect_raises(core.SchedulerError, ledger1().record, "a", 0.0, 0)


@case
def t_negative_cost_rejected():
    expect_raises(core.SchedulerError, ledger1().record, "a", 0.0, -1)


@case
def t_bool_cost_rejected():
    expect_raises(core.SchedulerError, ledger1().record, "a", 0.0, True)


@case
def t_cost_over_limit_rejected():
    expect_raises(core.SchedulerError, ledger1().record, "a", 0.0, 6)


@case
def t_zero_limit_rejected():
    expect_raises(core.SchedulerError, core.QuotaLedger,
                  {"a": {"limit": 0, "window_s": 1}})


@case
def t_negative_window_rejected():
    expect_raises(core.SchedulerError, core.QuotaLedger,
                  {"a": {"limit": 1, "window_s": -1}})


@case
def t_float_limit_rejected():
    expect_raises(core.SchedulerError, core.QuotaLedger,
                  {"a": {"limit": 1.5, "window_s": 1}})


@case
def t_empty_name_rejected():
    expect_raises(core.SchedulerError, core.QuotaLedger,
                  {"": {"limit": 1, "window_s": 1}})


@case
def t_unicode_source_name_ok():
    led = core.QuotaLedger({"配额源-α": {"limit": 2, "window_s": 5}})
    led.record("配额源-α", 0.0, 1)
    expect(led.available("配额源-α", 0.0) == 1, "unicode source failed")


@case
def t_window_zero_has_no_memory():
    led = core.QuotaLedger({"a": {"limit": 1, "window_s": 0}})
    led.record("a", 3.0, 1)
    expect(led.used("a", 3.0) == 0, "window 0 must forget instantly")


@case
def t_float_timestamps():
    led = core.QuotaLedger({"a": {"limit": 10, "window_s": 1.5}})
    led.record("a", 2.25, 3)
    expect(led.used("a", 2.5) == 3, "float ts failed")


@case
def t_negative_timestamps_ok():
    led = ledger1()
    led.record("a", -5.0, 1)
    expect(led.used("a", -4.0) == 1, "negative ts failed")


# ---------- functional: decide / plan ----------

@case
def t_decide_picks_most_headroom():
    led = core.QuotaLedger({"a": {"limit": 5, "window_s": 10},
                            "b": {"limit": 9, "window_s": 10}})
    led.record("a", 0.0, 1)
    d = core.decide(led, 1.0, 1)
    expect(d["source"] == "b", "expected b, got %r" % d)


@case
def t_decide_tie_breaks_by_order():
    led = core.QuotaLedger({"x": {"limit": 5, "window_s": 10},
                            "y": {"limit": 5, "window_s": 10}})
    d = core.decide(led, 0.0, 1)
    expect(d["source"] == "x", "tie should keep first candidate")


@case
def t_decide_respects_candidate_order():
    led = core.QuotaLedger({"a": {"limit": 5, "window_s": 10},
                            "b": {"limit": 5, "window_s": 10}})
    d = core.decide(led, 0.0, 1, order=["b", "a"])
    expect(d["source"] == "b", "order override failed")


@case
def t_decide_waits_when_full():
    led = core.QuotaLedger({"a": {"limit": 2, "window_s": 10}})
    led.record("a", 0.0, 2)
    d = core.decide(led, 1.0, 1)
    expect(d["admitted"] is False and d["wait_s"] > 0, "got %r" % d)


@case
def t_decide_wait_equals_expiry():
    led = core.QuotaLedger({"a": {"limit": 2, "window_s": 10}})
    led.record("a", 0.0, 2)
    d = core.decide(led, 1.0, 1)
    expect(abs(d["wait_s"] - 9.0) < 1e-9, "wait: %r" % d["wait_s"])


@case
def t_decide_impossible_cost_errors():
    led = core.QuotaLedger({"a": {"limit": 1, "window_s": 10}})
    expect_raises(core.SchedulerError, core.decide, led, 0.0, 5)


@case
def t_decide_no_sources_errors():
    expect_raises(core.SchedulerError, core.decide, core.QuotaLedger(), 0.0, 1)


@case
def t_plan_sequentially_drains():
    led = core.QuotaLedger({"a": {"limit": 2, "window_s": 10}})
    sched = core.plan(led, [1, 1, 1], t0=0.0)
    expect(sched[0]["wait_s"] == 0 and sched[1]["wait_s"] == 0,
           "first two should be immediate: %r" % sched)
    expect(sched[2]["wait_s"] > 0, "third should wait: %r" % sched)


@case
def t_plan_deterministic():
    led_a = core.QuotaLedger({"a": {"limit": 3, "window_s": 5}})
    led_b = core.QuotaLedger({"a": {"limit": 3, "window_s": 5}})
    expect(core.plan(led_a, [1, 2, 1, 3]) == core.plan(led_b, [1, 2, 1, 3]),
           "plan must be deterministic")


@case
def t_plan_respects_quota():
    led = core.QuotaLedger({"a": {"limit": 3, "window_s": 100}})
    core.plan(led, [1, 1, 1], t0=0.0)
    expect(led.used("a", 0.0) == 3, "records missing")


@case
def t_plan_empty_jobs():
    led = ledger1()
    expect(core.plan(led, []) == [], "empty plan expected")


@case
def t_plan_huge_cost_waits():
    led = core.QuotaLedger({"a": {"limit": 4, "window_s": 10}})
    sched = core.plan(led, [4], t0=0.0)
    expect(sched[0]["wait_s"] == 0, "cost == limit should admit at once")


@case
def t_plan_uses_wait_then_records():
    led = core.QuotaLedger({"a": {"limit": 1, "window_s": 10}})
    sched = core.plan(led, [1, 1], t0=0.0)
    expect(sched[1]["start_t"] == 10.0, "second start: %r" % sched[1])


@case
def t_multi_source_plan_spreads():
    led = core.QuotaLedger({"a": {"limit": 1, "window_s": 100},
                            "b": {"limit": 1, "window_s": 100}})
    sched = core.plan(led, [1, 1], t0=0.0)
    expect(sched[0]["source"] != sched[1]["source"],
           "plan should spread across sources: %r" % sched)


@case
def t_earliest_admission_none_when_limit_too_small():
    led = core.QuotaLedger({"a": {"limit": 1, "window_s": 5}})
    expect(led.earliest_admission("a", 0.0, 5) is None,
           "limit < cost must yield None")


@case
def t_earliest_admission_now_when_free():
    led = core.QuotaLedger({"a": {"limit": 5, "window_s": 5}})
    expect(led.earliest_admission("a", 3.0, 2) == 3.0,
           "free source admits now")


# ---------- CLI + edge ----------

def _spec_file(d, spec):
    p = os.path.join(d, "spec.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    return p


@case
def t_cli_ok():
    d = tempfile.mkdtemp()
    p = _spec_file(d, {"sources": {"a": {"limit": 2, "window_s": 5}},
                       "jobs": [1, 1], "t0": 0.0})
    expect(core.main([p]) == 0, "CLI should exit 0")


@case
def t_cli_bad_jobs_exit_two():
    d = tempfile.mkdtemp()
    p = _spec_file(d, {"sources": {"a": {"limit": 2, "window_s": 5}},
                       "jobs": [0]})
    expect(core.main([p]) == 2, "zero-cost job must fail with exit 2")


@case
def t_cli_malformed_json_exit_two():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "bad.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{oops")
    expect(core.main([p]) == 2, "malformed input must exit 2")


@case
def t_cli_missing_file_exit_two():
    expect(core.main(["Z:/missing/spec.json"]) == 2, "missing input exits 2")


@case
def t_cli_empty_jobs_ok():
    d = tempfile.mkdtemp()
    p = _spec_file(d, {"sources": {"a": {"limit": 1, "window_s": 5}},
                       "jobs": []})
    expect(core.main([p]) == 0, "empty job list is valid")


@case
def t_many_events_performance():
    led = core.QuotaLedger({"a": {"limit": 10000, "window_s": 100000}})
    for i in range(5000):
        led.record("a", float(i), 1)
    expect(led.used("a", 99999.0) == 5000, "bulk recording failed")


@case
def t_json_output_serializable():
    led = core.QuotaLedger({"a": {"limit": 2, "window_s": 5}})
    sched = core.plan(led, [1])
    s = json.dumps({"schedule": sched}, ensure_ascii=True, sort_keys=True)
    expect("source" in s, "serializable schedule expected")


def run():
    ok = 0
    for i, fn in enumerate(CASES, 1):
        try:
            fn()
            ok += 1
        except Exception as e:
            print("FAIL %02d %s: %s: %s" % (i, fn.__name__,
                                            type(e).__name__, e))
    total = len(CASES)
    print("SUMMARY: %s %d/%d" % ("PASS" if ok == total else "FAIL", ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(run())
