"""Discrete-event berth replay using integer minutes and synthetic inputs."""
from dataclasses import asdict, dataclass
from random import Random
from statistics import mean, median
from math import ceil

# Dedicated berths are filled first, leaving the flexible berth available to either class.
BERTHS = {"Cargo": {"cargo"}, "Tanker": {"tanker"}, "Flexible": {"cargo", "tanker"}}
POLICIES = ("fifo", "shortest", "aging")
SCENARIOS = {"steady": 310, "busy": 205, "disrupted": 205}
SEEDS = range(101, 141)
AGING_MINUTES = 720


@dataclass(frozen=True)
class Vessel:
    name: str
    kind: str
    eta: int
    arrival: int
    estimate: int
    handling: int


def manifest(seed, scenario):
    rng = Random(seed)
    vessels = []
    eta = 0
    for i in range(42):
        eta += rng.randint(50, 145) * SCENARIOS[scenario] // 100
        kind = "cargo" if rng.random() < .64 else "tanker"
        estimate = rng.randint(180, 620) if kind == "cargo" else rng.randint(325, 860)
        arrival = eta + rng.randint(-35, 150)
        if scenario == "disrupted" and i in range(12, 20):
            arrival = max(arrival, 3700)  # A group of arrivals is delayed into a common slot.
        handling = round(estimate * rng.randint(75, 140) / 100)
        vessels.append(Vessel(f"V{i+1:02}", kind, eta, arrival, estimate, handling))
    return vessels


def priority(vessel, policy, now):
    first = (vessel.arrival, vessel.name)
    if policy == "fifo":
        return first
    if policy == "aging":
        if now - vessel.arrival >= AGING_MINUTES:
            return (0, *first)
        return (1, vessel.estimate, *first)
    return (vessel.estimate, *first)


def replay(vessels, policy):
    """Assign arrived vessels without interrupting work already started."""
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    pending = sorted(vessels, key=lambda v: (v.arrival, v.name))
    waiting = []
    free_at = {berth: 0 for berth in BERTHS}
    timeline = []
    now = 0
    while pending or waiting:
        events = [pending[0].arrival] if pending else []
        if waiting:
            events.extend(free_at[b] for b, kinds in BERTHS.items()
                          if free_at[b] > now and any(v.kind in kinds for v in waiting))
        now = min(events)
        while pending and pending[0].arrival <= now:
            waiting.append(pending.pop(0))
        for berth, kinds in BERTHS.items():
            if free_at[berth] > now:
                continue
            options = [v for v in waiting if v.kind in kinds]
            if not options:
                continue
            vessel = min(options, key=lambda v: priority(v, policy, now))
            waiting.remove(vessel)
            finish = now + vessel.handling
            free_at[berth] = finish
            timeline.append({**asdict(vessel), "berth": berth, "start": now,
                             "finish": finish, "wait": now - vessel.arrival})
    return timeline


def metrics(timeline):
    waits = sorted(row["wait"] for row in timeline)
    return {"mean": round(mean(waits), 3), "p90": waits[ceil(.9 * len(waits)) - 1],
            "max": waits[-1], "over12": sum(wait >= 720 for wait in waits),
            "total": sum(waits), "count": len(waits)}


def experiment():
    result = {}
    for scenario in SCENARIOS:
        runs = []
        for seed in SEEDS:
            vessels = manifest(seed, scenario)
            schedules = {policy: replay(vessels, policy) for policy in POLICIES}
            runs.append({"seed": seed, "scores": {p: metrics(rows) for p, rows in schedules.items()},
                         "schedules": schedules if seed == SEEDS.start else None})
        summary = {}
        for policy in POLICIES:
            savings = [run["scores"]["fifo"]["total"] - run["scores"][policy]["total"] for run in runs]
            summary[policy] = {
                "mean": round(mean(run["scores"][policy]["mean"] for run in runs), 3),
                "median_savings": round(median(savings), 3),
                "better": sum(s > 0 for s in savings),
                "worse": sum(s < 0 for s in savings),
                "p90": round(mean(run["scores"][policy]["p90"] for run in runs), 3),
                "over12": sum(run["scores"][policy]["over12"] for run in runs),
            }
        result[scenario] = {"summary": summary, "runs": runs}
    return result
