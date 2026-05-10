#!/usr/bin/env python3
"""Lifecycle state-machine assertion suite for goalkeeper.

Walks every documented state transition in a temporary directory,
constructs the canonical state shapes per the spec, and asserts that
every transition produces the expected shape. Runs in seconds.

This is a *spec consistency* test, not a Claude Code skill integration
test — it codifies the canonical state shapes from skills/goal/SKILL.md
"Canonical state shapes" and verifies that constructing them per spec
produces the right thing. If a skill SKILL.md drifts from these shapes,
update both the spec and this test together.

Usage:
  python3 scripts/test-lifecycle.py [--keep] [-v]

Exit code 0 on all-pass, 1 on any failure.

Requires: stdlib only.
"""

from __future__ import annotations
import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Test harness
# ─────────────────────────────────────────────────────────────────────────────

class Test:
    """Group of related assertions; prints results and tracks pass/fail count."""

    def __init__(self, name: str, verbose: bool = False):
        self.name = name
        self.verbose = verbose
        self.checks: list[tuple[str, bool]] = []

    def check(self, desc: str, ok: bool) -> None:
        self.checks.append((desc, ok))
        if self.verbose:
            mark = "PASS" if ok else "FAIL"
            print(f"    [{mark}] {desc}")

    def report(self) -> tuple[int, int]:
        passes = sum(1 for _, ok in self.checks if ok)
        fails = len(self.checks) - passes
        if not self.verbose:
            mark = "OK" if fails == 0 else "FAIL"
            print(f"  [{mark}]  {self.name}  ({passes}/{len(self.checks)})")
        else:
            print(f"  → {self.name}: {passes}/{len(self.checks)} passed\n")
        if fails:
            for desc, ok in self.checks:
                if not ok:
                    print(f"      FAILED: {desc}")
        return passes, fails


def iso(t: str = "now") -> str:
    if t == "now":
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Spec-conformant state writers (must match skills/goal/SKILL.md shapes)
# ─────────────────────────────────────────────────────────────────────────────

def write_active_active(goals_dir: Path, slug: str, chain: str | None = None) -> dict:
    """Write active.json in the active shape per canonical spec."""
    payload: dict = {"slug": slug, "activated_at": iso()}
    if chain is not None:
        payload["chain"] = chain
    (goals_dir / "active.json").write_text(json.dumps(payload, indent=2))
    return payload


def write_active_terminal(
    goals_dir: Path,
    ended_reason: str,
    previous_slug: str | None = None,
    previous_chain: str | None = None,
) -> dict:
    """Write active.json in the terminal shape per canonical spec."""
    payload: dict = {
        "slug": None,
        "ended_at": iso(),
        "ended_reason": ended_reason,
    }
    if previous_slug is not None:
        payload["previous_slug"] = previous_slug
    if previous_chain is not None:
        payload["previous_chain"] = previous_chain
    (goals_dir / "active.json").write_text(json.dumps(payload, indent=2))
    return payload


def write_state(goals_dir: Path, slug: str, **fields) -> dict:
    """Write <slug>/state.json. Required fields default to sensible values."""
    slug_dir = goals_dir / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "active",
        "rejection_count": 0,
        "started_at": iso(),
        "started_at_commit": "abc1234",
        "started_at_dirty_paths": [],
        "last_checkpoint_at": None,
        "last_validator_result": None,
        "last_judge_verdict": None,
    }
    payload.update(fields)
    (slug_dir / "state.json").write_text(json.dumps(payload, indent=2))
    return payload


def write_chain(goals_dir: Path, name: str, slugs: list[str], cursor: int = 0,
                status: str = "active", link_approvals: list | None = None) -> dict:
    payload = {
        "name": name,
        "slugs": slugs,
        "cursor": cursor,
        "status": status,
        "started_at": iso(),
        "completed_at": None,
        "source_file": "synthetic",
        "link_approvals": link_approvals or [],
    }
    (goals_dir / "chain.json").write_text(json.dumps(payload, indent=2))
    return payload


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_pause(goals: Path, v: bool) -> Test:
    t = Test("/goal-pause: active → paused", v)
    write_state(goals, "lc1", status="active")
    write_active_active(goals, "lc1")
    # Apply pause: status → paused, paused_at set
    write_state(goals, "lc1", status="paused", paused_at=iso())
    state = read_json(goals / "lc1" / "state.json")
    active = read_json(goals / "active.json")
    t.check('state.status == "paused"', state["status"] == "paused")
    t.check("state.paused_at present", "paused_at" in state)
    t.check("state.rejection_count preserved at 0", state["rejection_count"] == 0)
    t.check("state.started_at preserved", "started_at" in state)
    t.check('active.json still slug="lc1" (pause is not termination)',
            active.get("slug") == "lc1")
    t.check("active.json has activated_at, NOT ended_at",
            "activated_at" in active and "ended_at" not in active)
    return t


def test_resume_from_paused(goals: Path, v: bool) -> Test:
    t = Test("/goal-resume: paused → active", v)
    write_state(goals, "lc1", status="paused", paused_at=iso())
    write_active_active(goals, "lc1")
    # Apply resume: status → active, resumed_at set, paused_at preserved
    paused_at_orig = read_json(goals / "lc1" / "state.json")["paused_at"]
    write_state(goals, "lc1", status="active", paused_at=paused_at_orig, resumed_at=iso())
    state = read_json(goals / "lc1" / "state.json")
    t.check('state.status == "active"', state["status"] == "active")
    t.check("state.resumed_at present", "resumed_at" in state)
    t.check("state.paused_at preserved (audit trail)", state.get("paused_at") == paused_at_orig)
    t.check("state.rejection_count preserved at 0", state["rejection_count"] == 0)
    return t


def test_clear_active(goals: Path, v: bool) -> Test:
    t = Test("/goal-clear: active → cleared+archived", v)
    archive = goals / "_archive"
    archive.mkdir(exist_ok=True)
    write_state(goals, "lc2", status="active")
    write_active_active(goals, "lc2")
    # Apply clear: mv slug dir to archive, write terminal active.json
    target = archive / "lc2-test"
    shutil.move(str(goals / "lc2"), str(target))
    write_active_terminal(goals, "cleared", previous_slug="lc2")
    active = read_json(goals / "active.json")
    t.check("active.json.slug is None", active["slug"] is None)
    t.check("active.json.ended_reason == 'cleared'", active["ended_reason"] == "cleared")
    t.check("active.json.previous_slug == 'lc2'", active.get("previous_slug") == "lc2")
    t.check("original lc2/ no longer exists", not (goals / "lc2").exists())
    t.check("archived contract dir exists", target.exists())
    t.check("archived state.json preserved", (target / "state.json").exists())
    return t


def test_resume_from_needs_human(goals: Path, v: bool) -> Test:
    t = Test("/goal-resume from needs_human (with counter reset)", v)
    write_state(goals, "lc3", status="needs_human", rejection_count=5,
                last_judge_verdict="reject", needs_human_at=iso())
    write_active_active(goals, "lc3")
    # Apply resume with reset choice: status → active, rejection_count → 0,
    # resumed_at set, needs_human_at + last_judge_verdict preserved
    needs_human_at_orig = read_json(goals / "lc3" / "state.json")["needs_human_at"]
    write_state(goals, "lc3", status="active", rejection_count=0,
                last_judge_verdict="reject",
                needs_human_at=needs_human_at_orig,
                resumed_at=iso())
    state = read_json(goals / "lc3" / "state.json")
    active = read_json(goals / "active.json")
    t.check('state.status flipped needs_human → active', state["status"] == "active")
    t.check("state.rejection_count reset to 0", state["rejection_count"] == 0)
    t.check("state.resumed_at present", "resumed_at" in state)
    t.check("state.needs_human_at preserved (audit)", "needs_human_at" in state)
    t.check('state.last_judge_verdict preserved as "reject"',
            state["last_judge_verdict"] == "reject")
    t.check('active.json still slug="lc3"', active.get("slug") == "lc3")
    t.check("active.json is active-shape", "activated_at" in active and "ended_at" not in active)
    return t


def test_max_rejections_threshold(goals: Path, v: bool) -> Test:
    t = Test("max_rejections threshold: 4 → 5 → needs_human", v)
    write_state(goals, "lc4", status="active", rejection_count=4,
                last_judge_verdict="reject")
    # Apply one more reject: rejection_count++ → 5; 5 >= max(5) → needs_human
    write_state(goals, "lc4", status="needs_human", rejection_count=5,
                last_judge_verdict="reject", needs_human_at=iso())
    state = read_json(goals / "lc4" / "state.json")
    t.check('state.status == "needs_human"', state["status"] == "needs_human")
    t.check("state.rejection_count == 5", state["rejection_count"] == 5)
    t.check("state.needs_human_at present", "needs_human_at" in state)
    t.check('state.last_judge_verdict == "reject"', state["last_judge_verdict"] == "reject")
    return t


def test_chain_completion(goals: Path, v: bool) -> Test:
    t = Test("chain completion: cursor reaches end → chain done", v)
    archive = goals / "_archive"
    archive.mkdir(exist_ok=True)
    # Set up a 2-link chain mid-flight on the second link
    write_chain(goals, "ch-done", ["ch-l1", "ch-l2"], cursor=1, status="active",
                link_approvals=[{"slug": "ch-l1", "approved_at": iso()}])
    write_state(goals, "ch-l1", status="done", chain_step=1)
    write_state(goals, "ch-l2", status="active", chain_step=2)
    write_active_active(goals, "ch-l2", chain="ch-done")
    # Apply judge approve on l2 → append link approval, advance cursor, mark chain done
    chain = read_json(goals / "chain.json")
    chain["link_approvals"].append({"slug": "ch-l2", "approved_at": iso()})
    chain["cursor"] = 2
    chain["status"] = "done"
    chain["completed_at"] = iso()
    (goals / "chain.json").write_text(json.dumps(chain, indent=2))
    write_state(goals, "ch-l2", status="done", chain_step=2, approved_at=iso())
    write_active_terminal(goals, "chain_completed",
                          previous_slug="ch-l2", previous_chain="ch-done")
    chain = read_json(goals / "chain.json")
    active = read_json(goals / "active.json")
    t.check('chain.status == "done"', chain["status"] == "done")
    t.check("chain.cursor == len(slugs)", chain["cursor"] == len(chain["slugs"]))
    t.check("chain.completed_at present", chain.get("completed_at") is not None)
    t.check("chain.link_approvals has 2 entries", len(chain["link_approvals"]) == 2)
    t.check("link_approvals[0].slug == 'ch-l1'", chain["link_approvals"][0]["slug"] == "ch-l1")
    t.check("link_approvals[1].slug == 'ch-l2'", chain["link_approvals"][1]["slug"] == "ch-l2")
    t.check("active.json.ended_reason == 'chain_completed'",
            active["ended_reason"] == "chain_completed")
    t.check("active.json.previous_chain == 'ch-done'",
            active.get("previous_chain") == "ch-done")
    return t


def test_chain_abort_via_clear(goals: Path, v: bool) -> Test:
    t = Test("/goal-clear during active chain: chain → aborted", v)
    archive = goals / "_archive"
    archive.mkdir(exist_ok=True)
    write_chain(goals, "ch-abort", ["ch-a1", "ch-a2"], cursor=0, status="active",
                link_approvals=[])
    write_state(goals, "ch-a1", status="active", chain_step=1)
    write_active_active(goals, "ch-a1", chain="ch-abort")
    # Pre-create unreached link contract (mimics start mode's "validate every slug
    # has a contract" pre-flight)
    (goals / "ch-a2").mkdir(exist_ok=True)
    (goals / "ch-a2" / "contract.md").write_text("---\nslug: ch-a2\n---\n")
    # Apply clear during chain: archive a1, set chain.status=aborted,
    # active.json terminal with ended_reason=cleared, NOT aborted
    shutil.move(str(goals / "ch-a1"), str(archive / "ch-a1-test"))
    chain = read_json(goals / "chain.json")
    chain["status"] = "aborted"
    chain["completed_at"] = iso()
    (goals / "chain.json").write_text(json.dumps(chain, indent=2))
    write_active_terminal(goals, "cleared",
                          previous_slug="ch-a1", previous_chain="ch-abort")
    chain = read_json(goals / "chain.json")
    active = read_json(goals / "active.json")
    t.check("chain.status flipped to 'aborted'", chain["status"] == "aborted")
    t.check("chain.completed_at set", chain.get("completed_at") is not None)
    t.check("chain.cursor stayed at 0 (no advance)", chain["cursor"] == 0)
    t.check("chain.link_approvals empty", chain["link_approvals"] == [])
    t.check("active.json.ended_reason == 'cleared' (not 'aborted')",
            active["ended_reason"] == "cleared")
    t.check("active.json.previous_chain == 'ch-abort' (chain context)",
            active.get("previous_chain") == "ch-abort")
    t.check("ch-a1/ archived", not (goals / "ch-a1").exists())
    t.check("ch-a2/ contract.md PRESERVED (unreached link)",
            (goals / "ch-a2" / "contract.md").exists())
    t.check("ch-a2/ has no state.json (never activated)",
            not (goals / "ch-a2" / "state.json").exists())
    return t


def test_judge_approve_standalone(goals: Path, v: bool) -> Test:
    t = Test("judge approve (standalone goal): active → done", v)
    write_state(goals, "j1", status="active", last_validator_result="pass")
    write_active_active(goals, "j1")
    # Apply judge approve: state.status=done, last_judge_verdict=approve, approved_at;
    # active.json terminal with ended_reason=done, previous_slug
    write_state(goals, "j1", status="done", last_validator_result="pass",
                last_judge_verdict="approve", approved_at=iso())
    write_active_terminal(goals, "done", previous_slug="j1")
    state = read_json(goals / "j1" / "state.json")
    active = read_json(goals / "active.json")
    t.check('state.status == "done"', state["status"] == "done")
    t.check('state.last_judge_verdict == "approve"', state["last_judge_verdict"] == "approve")
    t.check("state.approved_at present", "approved_at" in state)
    t.check("active.json.ended_reason == 'done'", active["ended_reason"] == "done")
    t.check("active.json.previous_slug == 'j1'", active.get("previous_slug") == "j1")
    t.check("active.json has no previous_chain (standalone goal)",
            "previous_chain" not in active)
    return t


def test_judge_reject_below_threshold(goals: Path, v: bool) -> Test:
    t = Test("judge reject (below threshold): rejection_count++, stays active", v)
    write_state(goals, "j2", status="active", rejection_count=2,
                last_validator_result="pass")
    # Apply reject: rejection_count++ (3), still < 5, status stays active
    write_state(goals, "j2", status="active", rejection_count=3,
                last_validator_result="pass", last_judge_verdict="reject")
    state = read_json(goals / "j2" / "state.json")
    t.check("state.status stays 'active'", state["status"] == "active")
    t.check("state.rejection_count incremented to 3", state["rejection_count"] == 3)
    t.check('state.last_judge_verdict == "reject"', state["last_judge_verdict"] == "reject")
    t.check("state has no needs_human_at (below threshold)", "needs_human_at" not in state)
    return t


def test_judge_advisory_no_state_change(goals: Path, v: bool) -> Test:
    """Per goal-judge.md "When invoked on demand (advisory)": advisory runs do
    NOT modify state.json, rejection_count, or active.json. The verdict is
    surfaced to the user but not persisted."""
    t = Test("judge advisory (on-demand): state NOT modified", v)
    initial = write_state(goals, "j3", status="active", rejection_count=2,
                          last_validator_result="pass",
                          last_judge_verdict=None)
    initial_active = write_active_active(goals, "j3")
    # Simulate advisory invocation: judge produces a verdict but skill spec says
    # "Do NOT modify state.json, rejection_count, or schedule wakeups."
    # The post-condition is: state.json and active.json are byte-identical to before.
    state_after = read_json(goals / "j3" / "state.json")
    active_after = read_json(goals / "active.json")
    t.check("state.status unchanged", state_after["status"] == initial["status"])
    t.check("state.rejection_count unchanged",
            state_after["rejection_count"] == initial["rejection_count"])
    t.check("state.last_judge_verdict unchanged (still None)",
            state_after.get("last_judge_verdict") == initial.get("last_judge_verdict"))
    t.check("active.json.slug unchanged", active_after.get("slug") == initial_active["slug"])
    t.check("active.json activated_at unchanged",
            active_after.get("activated_at") == initial_active["activated_at"])
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_pause,
    test_resume_from_paused,
    test_clear_active,
    test_resume_from_needs_human,
    test_max_rejections_threshold,
    test_chain_completion,
    test_chain_abort_via_clear,
    test_judge_approve_standalone,
    test_judge_reject_below_threshold,
    test_judge_advisory_no_state_change,
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print every assertion (not just per-test summaries)")
    parser.add_argument("--keep", action="store_true",
                        help="Keep the temp dir for inspection")
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="goalkeeper-lifecycle-"))
    print(f"goalkeeper lifecycle test — temp dir: {tmp}\n")

    total_pass = total_fail = 0
    for fn in ALL_TESTS:
        # Each test gets its own subdirectory so they don't interfere
        subdir = tmp / fn.__name__
        subdir.mkdir()
        t = fn(subdir, args.verbose)
        p, f = t.report()
        total_pass += p
        total_fail += f

    print()
    print(f"Result: {total_pass}/{total_pass + total_fail} assertions passed across {len(ALL_TESTS)} tests.")

    if not args.keep:
        shutil.rmtree(tmp)
    else:
        print(f"\nTemp dir kept at: {tmp}")

    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
