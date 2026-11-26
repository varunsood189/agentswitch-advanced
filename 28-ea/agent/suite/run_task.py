"""Run one suite task: seed fixtures, invoke the agent (or do-nothing), assert platform result.

From 28-ea/agent/:

  python -m suite.run_task --all --mode do-nothing   # draft tasks must FAIL
  python -m suite.run_task --all --mode expect-good  # checker accepts seeded good after
  python -m suite.run_task --all --mode agent        # real briefing path on FakeClient
  python -m suite.run_task seat28.meeting_draft --live
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)
_TESTS = os.path.join(_AGENT_ROOT, "tests")
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)

from suite.check_draft import evaluate
from suite.fixtures import (
    ME,
    TODAY,
    load_tasks_toml,
    snapshot_from_tables,
    tables_from_snapshot,
    task_by_id,
    world_for,
)


def _merge_task(task, world):
    out = dict(task)
    if world.get("free_slots") and not out.get("free_slots"):
        out["free_slots"] = world["free_slots"]
    return out


def run_do_nothing(task_id):
    task = task_by_id(task_id)
    world = world_for(task_id)
    before = world["before"]
    result = evaluate(_merge_task(task, world), before, before)
    return {
        "task_id": task_id,
        "mode": "do-nothing",
        "result": result,
        "seeded_ids": [m.get("id") for m in before.get("messages") or []],
    }


def run_expect_good(task_id):
    task = task_by_id(task_id)
    world = world_for(task_id)
    result = evaluate(_merge_task(task, world), world["before"], world["after_good"])
    return {"task_id": task_id, "mode": "expect-good", "result": result}


def run_agent_offline(task_id):
    """Invoke build_briefing (the agent's draft path) on FakeClient seeded from this task."""
    from fakes import FakeClient, FakeLLM
    from ea_agent.briefing import build_briefing

    task = task_by_id(task_id)
    world = world_for(task_id)
    before = world["before"]
    tables = tables_from_snapshot(before)
    client = FakeClient(dict(ME), tables, today=TODAY)
    client.drafts_created = 0
    client.instance = "keystone"

    kind = task.get("kind")
    draft_text = world.get("llm_draft") or (
        "Hi,\n\nThanks — I will follow up shortly.\n\nTeam 28b"
    )

    def reply(system, user):
        # Always draft for inbox mail so a distractor also gets a draft; target scoping must still pass.
        return json.dumps(
            {
                "needs_reply": True,
                "reason": "needs a reply",
                "summary": "sender asks for a reply",
                "needs_decision": task.get("check") == "status",
                "draft": draft_text,
            }
        )

    llm = FakeLLM(fn=reply) if kind == "normal" else None
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 12, 1, 4, 30, tzinfo=timezone.utc)
    briefing = build_briefing(
        client,
        dict(ME),
        TODAY,
        tz,
        llm=llm,
        save_drafts=True,
        mail_cap=25,
        now=now,
        model_parallel=1,
    )
    after = snapshot_from_tables(client.tables)
    result = evaluate(_merge_task(task, world), before, after)
    new_ids = [
        m.get("id")
        for m in after.get("messages") or []
        if m.get("id") not in {x.get("id") for x in before.get("messages") or []}
    ]
    return {
        "task_id": task_id,
        "mode": "agent-offline",
        "result": result,
        "new_message_ids": new_ids,
        "briefing_warnings": (briefing or {}).get("warnings"),
        "drafts_saved_flag": (briefing or {}).get("drafts_saved"),
    }


def run_live(task_id):
    needed = [
        "AGENTSWITCH_KEYSTONE_TOKEN or EA_PASSWORD_KEYSTONE (+ EA_EMAIL)",
        "OPENAI_BASE_URL + OPENAI_API_KEY + OPENAI_MODEL (unless using EA_LLM_* / --no-llm)",
    ]
    has = any(
        os.environ.get(k)
        for k in (
            "AGENTSWITCH_TOKEN",
            "AGENTSWITCH_KEYSTONE_TOKEN",
            "EA_PASSWORD_KEYSTONE",
        )
    )
    if not has:
        return {
            "task_id": task_id,
            "mode": "live",
            "result": {
                "passed": False,
                "score": 0.0,
                "evidence": "live blocked: missing credentials — need " + "; ".join(needed),
            },
            "blocker": needed,
        }
    from ea_agent import __main__ as cli

    code = cli.main(["--system", "keystone", "--no-file"])
    return {
        "task_id": task_id,
        "mode": "live",
        "exit_code": code,
        "result": {
            "passed": code == 0,
            "score": 1.0 if code == 0 else 0.0,
            "evidence": "live agent exit {}".format(code),
        },
        "note": "Paste before/after platform rows into check_draft.evaluate for the graded verdict.",
    }


def _mode_success(task, mode, passed):
    """Whether this mode invocation met suite expectations."""
    if mode == "do-nothing":
        if task.get("kind") == "normal":
            return not passed  # must fail the checker
        return passed  # refusal: unchanged passes
    return passed


def main(argv=None):
    p = argparse.ArgumentParser(description="Run a seat 28 suite task against seeded fixtures / the agent.")
    p.add_argument("task_id", nargs="?", help="e.g. seat28.meeting_draft")
    p.add_argument("--all", action="store_true", help="run every task in tasks.toml")
    p.add_argument(
        "--mode",
        choices=("do-nothing", "expect-good", "agent", "live"),
        default="do-nothing",
    )
    p.add_argument("--live", action="store_true", help="alias for --mode live")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if args.live:
        args.mode = "live"

    ids = [t["id"] for t in load_tasks_toml()] if args.all else ([args.task_id] if args.task_id else [])
    if not ids:
        p.error("pass a task_id or --all")

    runners = {
        "do-nothing": run_do_nothing,
        "expect-good": run_expect_good,
        "agent": run_agent_offline,
        "live": run_live,
    }
    rows = []
    failed = 0
    for task_id in ids:
        row = runners[args.mode](task_id)
        rows.append(row)
        task = task_by_id(task_id)
        passed = bool((row.get("result") or {}).get("passed"))
        ok = _mode_success(task, args.mode, passed)
        if not ok:
            failed += 1
        if not args.json:
            print(
                "{} [{}] checker_passed={} mode_ok={} evidence={}".format(
                    task_id,
                    args.mode,
                    passed,
                    ok,
                    (row.get("result") or {}).get("evidence"),
                )
            )
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
