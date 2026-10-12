#!/usr/bin/env python3
"""quota-aware-scheduler: multi-source quota ledger with sliding-window
accounting and a deterministic scheduling decision interface.

Single-process simulation over virtual time only: no network, no threads,
no wall-clock reads inside the scheduling logic. Pure standard library.
"""
import argparse
import json
import sys


class SchedulerError(Exception):
    """Raised for invalid configuration or scheduling requests."""


class QuotaLedger:
    """Per-source sliding-window usage ledger.

    sources: {name: {"limit": int > 0, "window_s": number >= 0}}
    Events are (timestamp, cost) pairs; usage in a window (t-w, t] counts.
    """

    def __init__(self, sources=None):
        self.sources = {}
        self.events = {}
        for name, cfg in (sources or {}).items():
            self.add_source(name, cfg)

    def add_source(self, name, cfg):
        if not isinstance(name, str) or not name:
            raise SchedulerError("source name must be a non-empty string")
        limit = cfg.get("limit")
        window = cfg.get("window_s")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise SchedulerError("source %r: limit must be a positive integer" % name)
        if isinstance(window, bool) or not isinstance(window, (int, float)) or window < 0:
            raise SchedulerError("source %r: window_s must be a non-negative number" % name)
        self.sources[name] = {"limit": limit, "window_s": float(window)}
        self.events.setdefault(name, [])

    def _require(self, name):
        if name not in self.sources:
            raise SchedulerError("unknown source: %r" % name)

    def used(self, name, t):
        self._require(name)
        w = self.sources[name]["window_s"]
        return sum(c for ts, c in self.events[name] if (t - w) < ts <= t)

    def available(self, name, t):
        self._require(name)
        return self.sources[name]["limit"] - self.used(name, t)

    def record(self, name, t, cost=1):
        self._require(name)
        if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
            raise SchedulerError("cost must be a positive integer")
        if cost > self.sources[name]["limit"]:
            raise SchedulerError("cost %d exceeds limit of source %r" % (cost, name))
        self.events[name].append((t, cost))

    def earliest_admission(self, name, t, cost):
        """Earliest virtual time >= t at which `cost` fits the window."""
        self._require(name)
        lim = self.sources[name]["limit"]
        if lim < cost:
            return None
        if self.available(name, t) >= cost:
            return t
        w = self.sources[name]["window_s"]
        candidates = sorted(ts + w for ts, _c in self.events[name] if ts <= t)
        for cand in candidates:
            if cand >= t and self.used(name, cand) <= lim - cost:
                return cand
        return None


def decide(ledger, t, cost=1, order=None):
    """Deterministic decision: prefer the source with the most headroom that
    can admit `cost` now; ties broken by candidate order. If none can admit
    now, return the source with the minimal wait."""
    candidates = list(order) if order else list(ledger.sources.keys())
    if not candidates:
        raise SchedulerError("no candidate sources")
    best_now, best_wait = None, None
    for name in candidates:
        avail = ledger.available(name, t)
        if avail >= cost and (best_now is None or
                              avail > ledger.available(best_now, t)):
            best_now = name
        eta = ledger.earliest_admission(name, t, cost)
        if eta is not None and (best_wait is None or eta < best_wait[1]):
            best_wait = (name, eta)
    if best_now is not None:
        return {"source": best_now, "admitted": True, "wait_s": 0.0,
                "reason": "headroom=%d" % ledger.available(best_now, t)}
    if best_wait is None:
        raise SchedulerError("no source can ever admit cost=%d" % cost)
    name, eta = best_wait
    return {"source": name, "admitted": False, "wait_s": eta - t,
            "reason": "window full; earliest admission at t=%.6g" % eta}


def plan(ledger, jobs, t0=0.0, order=None):
    """Schedule a list of job costs sequentially over virtual time.

    Returns (schedule, ledger) where schedule items carry job index, chosen
    source, start time and wait. The ledger is mutated with admissions.
    """
    schedule = []
    t = float(t0)
    for i, cost in enumerate(jobs):
        d = decide(ledger, t, cost, order=order)
        start = t + (d["wait_s"] if not d["admitted"] else 0.0)
        ledger.record(d["source"], start, cost)
        schedule.append({"job": i, "cost": cost, "source": d["source"],
                         "start_t": start, "wait_s": round(d["wait_s"], 6)})
        t = start
    return schedule


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="quota-aware-scheduler",
        description="Deterministic quota-aware scheduling simulation "
                    "(virtual time, no network).")
    parser.add_argument("input", help="JSON spec: {sources:{name:{limit,window_s}}, jobs:[costs], t0}")
    args = parser.parse_args(argv)
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            spec = json.load(f)
        ledger = QuotaLedger(spec.get("sources"))
        jobs = spec.get("jobs", [])
        if not isinstance(jobs, list) or not all(
                isinstance(c, int) and not isinstance(c, bool) and c > 0
                for c in jobs):
            raise SchedulerError("jobs must be a list of positive integers")
        schedule = plan(ledger, jobs, spec.get("t0", 0.0))
    except OSError as e:
        print("error: cannot read input: %s" % e, file=sys.stderr)
        return 2
    except (SchedulerError, json.JSONDecodeError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps({"schedule": schedule}, ensure_ascii=True, indent=2,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
