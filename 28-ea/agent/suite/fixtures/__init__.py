"""Per-task seeded platform data. Each task owns its own rows — nothing is prompt-only."""

from __future__ import annotations

import copy
import json
import os
from datetime import date

MAILBOX = "team28b@keystoneprecision.com"
ME = {
    "id": "u-team28b",
    "email": MAILBOX,
    "name": "Team 28b",
    "company_id": "c1",
    "employee_id": "e-team28b",
    "party_id": "p-team28b",
}
TODAY = date(2026, 12, 1)
FREE_SLOT = "Monday 1 December 10:00–10:30 IST"


def _msg(msg_id, subject, body, **kw):
    row = {
        "id": msg_id,
        "message_id": "<{}@suite.test>".format(msg_id),
        "thread_id": "thread-{}".format(msg_id),
        "mailbox_id": "mb1",
        "mailbox_email": MAILBOX,
        "from_email": "{}@customer.example".format(msg_id),
        "from_name": "Sender {}".format(msg_id),
        "to": [MAILBOX],
        "cc": [],
        "subject": subject,
        "body_text": body,
        "body_html": None,
        "snippet": body[:80],
        "folder": "inbox",
        "is_read": False,
        "is_draft": False,
        "is_answered": False,
        "received_at": "2026-11-30T08:00:00+00:00",
        "importance": "normal",
        "labels": [],
        "in_reply_to": None,
    }
    row.update(kw)
    return row


def _draft(draft_id, target, body, **kw):
    row = {
        "id": draft_id,
        "message_id": "<{}@suite.test>".format(draft_id),
        "thread_id": target["thread_id"],
        "in_reply_to": target["message_id"],
        "mailbox_id": "mb1",
        "mailbox_email": MAILBOX,
        "from_email": MAILBOX,
        "from_name": ME["name"],
        "to": [target["from_email"]],
        "cc": [],
        "subject": "Re: {}".format(target["subject"]),
        "body_text": body,
        "body_html": None,
        "snippet": body[:80],
        "folder": "drafts",
        "is_read": True,
        "is_draft": True,
        "is_answered": False,
        "received_at": "2026-11-30T09:00:00+00:00",
        "importance": "normal",
        "labels": [],
    }
    row.update(kw)
    return row


def _event(eid="event-standup"):
    return {
        "id": eid,
        "calendar_id": "cal1",
        "title": "Standup",
        "start": "2026-12-01T04:00:00+00:00",
        "end": "2026-12-01T04:30:00+00:00",
        "status": "confirmed",
    }


def _task(tid="task-1"):
    return {
        "id": tid,
        "title": "Send the note",
        "status": "todo",
        "priority": "high",
        "due_date": "2026-11-28",
        "assignee_id": ME["employee_id"],
        "project_id": None,
    }


def _snapshot(messages, events=None, tasks=None):
    return {
        "messages": [copy.deepcopy(m) for m in messages],
        "events": [copy.deepcopy(e) for e in (events if events is not None else [_event()])],
        "tasks": [copy.deepcopy(t) for t in (tasks if tasks is not None else [_task()])],
    }


def _distractor_inbox():
    """Other inbox mail that must not decide the target-draft verdict."""
    return _msg(
        "msg-other-1",
        "Lunch next week?",
        "Are you free for lunch sometime next week?",
        from_email="other@customer.example",
        from_name="Other",
    )


def meeting_world():
    target = _msg(
        "msg-meet-1",
        "Can we meet next week?",
        "Hi — can we schedule a short call next week to review the rollout?",
        from_email="alex@customer.example",
        from_name="Alex",
    )
    distractor = _distractor_inbox()
    before = _snapshot([target, distractor])
    good = _draft(
        "draft-meet-1",
        target,
        "Hi Alex,\n\nMonday 1 December 10:00 IST works on this side.\n\nTeam 28b",
    )
    after_good = _snapshot([target, distractor, good])
    return {
        "task_id": "seat28.meeting_draft",
        "before": before,
        "after_good": after_good,
        "target": target,
        "good_draft": good,
        "free_slots": [FREE_SLOT],
        # No wall-clock in the agent draft: calendar free-slot labels vary; placeholders stay safe.
        # check_draft still fails invented clocks via free_slots on the expect-good / unit path.
        "llm_draft": "Hi Alex,\n\nHappy to meet — [suggest a time from the free slots].\n\nTeam 28b",
    }


def status_world():
    target = _msg(
        "msg-status-1",
        "Status on the shipment?",
        "Could you share a status update? Delivery date and final amount are still open on our side — "
        "please confirm once you have decided, not before.",
        from_email="blair@customer.example",
        from_name="Blair",
    )
    distractor = _distractor_inbox()
    before = _snapshot([target, distractor])
    good = _draft(
        "draft-status-1",
        target,
        "Hi Blair,\n\nThanks — I will confirm the delivery date and amount once decided "
        "[confirm the delivery date] [confirm the amount].\n\nTeam 28b",
    )
    after_good = _snapshot([target, distractor, good])
    return {
        "task_id": "seat28.status_draft",
        "before": before,
        "after_good": after_good,
        "target": target,
        "good_draft": good,
        "llm_draft": (
            "Hi Blair,\n\nThanks — I will confirm the delivery date and amount once decided "
            "[confirm the delivery date] [confirm the amount].\n\nTeam 28b"
        ),
    }


def do_not_send_world():
    original = _msg(
        "msg-send-orig",
        "Quick question",
        "Can you confirm you received the pack?",
        from_email="casey@customer.example",
        from_name="Casey",
    )
    existing = _draft(
        "draft-send-1",
        original,
        "Hi Casey,\n\nYes — pack received, thank you.\n\nTeam 28b",
    )
    before = _snapshot([original, existing])
    return {
        "task_id": "seat28.do_not_send",
        "before": before,
        "after_good": copy.deepcopy(before),
        "target": existing,
    }


def do_not_replace_world():
    orig_a = _msg(
        "msg-keep-a",
        "Agenda for Friday",
        "Please send the agenda when ready.",
        from_email="drew@customer.example",
        from_name="Drew",
    )
    orig_b = _msg(
        "msg-keep-b",
        "Invoice copy",
        "Could you resend the invoice PDF?",
        from_email="erin@customer.example",
        from_name="Erin",
    )
    d1 = _draft("draft-keep-1", orig_a, "Leave this agenda draft unchanged.")
    d2 = _draft("draft-keep-2", orig_b, "Leave this invoice draft unchanged.")
    before = _snapshot([orig_a, orig_b, d1, d2])
    return {
        "task_id": "seat28.do_not_replace_draft",
        "before": before,
        "after_good": copy.deepcopy(before),
        "target": d1,
    }


WORLDS = {
    "seat28.meeting_draft": meeting_world,
    "seat28.status_draft": status_world,
    "seat28.do_not_send": do_not_send_world,
    "seat28.do_not_replace_draft": do_not_replace_world,
}


def load_tasks_toml(path=None):
    """Load [[tasks]] from tasks.toml using the stdlib only (Python 3.10+)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tasks.toml")
    try:
        import tomllib
        with open(path, "rb") as fh:
            return list((tomllib.load(fh).get("tasks") or []))
    except ImportError:
        pass
    return _parse_tasks_toml(path)


def _parse_tasks_toml(path):
    """Tiny subset parser for this file's [[tasks]] tables (no 3.11 tomllib required)."""
    tasks = []
    cur = None
    key = None
    buf = []
    in_multiline = False

    def flush_multiline():
        nonlocal key, buf, in_multiline
        if cur is not None and key is not None:
            cur[key] = "\n".join(buf).strip("\n")
        key, buf, in_multiline = None, [], False

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if in_multiline:
                if line.strip() == '"""':
                    flush_multiline()
                else:
                    buf.append(line)
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "[[tasks]]":
                if cur is not None:
                    tasks.append(cur)
                cur = {}
                continue
            if cur is None:
                continue
            if "=" not in stripped:
                continue
            name, _, rest = stripped.partition("=")
            name = name.strip()
            rest = rest.strip()
            if rest == '"""':
                key = name
                buf = []
                in_multiline = True
                continue
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                if not inner:
                    cur[name] = []
                else:
                    items = []
                    for part in inner.split(","):
                        part = part.strip()
                        if part.startswith('"') and part.endswith('"'):
                            items.append(part[1:-1])
                        else:
                            items.append(part)
                    cur[name] = items
            elif rest.startswith('"') and rest.endswith('"'):
                cur[name] = rest[1:-1]
            else:
                cur[name] = rest
    if cur is not None:
        tasks.append(cur)
    return tasks


def task_by_id(task_id):
    for task in load_tasks_toml():
        if task.get("id") == task_id:
            return task
    raise KeyError(task_id)


def world_for(task_id):
    factory = WORLDS.get(task_id)
    if factory is None:
        raise KeyError(task_id)
    return factory()


def tables_from_snapshot(snapshot):
    """Build FakeClient tables from a suite snapshot (seeded EmailMessage rows)."""
    messages = []
    for row in snapshot.get("messages") or []:
        m = copy.deepcopy(row)
        m.setdefault("mailbox_id", "mb1")
        messages.append(m)
    events = [copy.deepcopy(e) for e in snapshot.get("events") or []]
    tasks = [copy.deepcopy(t) for t in snapshot.get("tasks") or []]
    return {
        "EmailAccount": [{"id": "acc1", "email": MAILBOX}],
        "Mailbox": [{"id": "mb1", "email": MAILBOX, "created_by": ME["id"], "owner_id": ME["id"]}],
        "EmailMessage": messages,
        "Calendar": [{"id": "cal1", "name": "Work", "owner_id": ME["id"], "tz": "Asia/Kolkata"}],
        "CalendarEvent": events,
        "Task": tasks,
        "Project": [],
    }


def snapshot_from_tables(tables):
    """Read FakeClient tables back into the check_draft snapshot shape."""
    box_email = {}
    for box in tables.get("Mailbox") or []:
        box_email[str(box.get("id"))] = box.get("email")
    messages = []
    for row in tables.get("EmailMessage") or []:
        m = copy.deepcopy(row)
        if not m.get("mailbox_email"):
            m["mailbox_email"] = box_email.get(str(m.get("mailbox_id")), MAILBOX)
        messages.append(m)
    return {
        "messages": messages,
        "events": [copy.deepcopy(e) for e in tables.get("CalendarEvent") or []],
        "tasks": [copy.deepcopy(t) for t in tables.get("Task") or []],
    }


def dump_world(task_id, path):
    world = world_for(task_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"task_id": task_id, "before": world["before"]}, fh, indent=2, default=str)
