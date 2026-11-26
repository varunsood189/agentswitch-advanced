"""Offline checks for the draft verdict and seeded fixtures. No network and no token.

Python 3.10+ (no 3.11-only syntax).
"""

from __future__ import annotations

import copy
import unittest

from suite.check_draft import evaluate
from suite.fixtures import load_tasks_toml, world_for


def _task(task_id, **extra):
    for row in load_tasks_toml():
        if row["id"] == task_id:
            out = dict(row)
            out.update(extra)
            return out
    raise KeyError(task_id)


class TasksShape(unittest.TestCase):
    def test_exactly_four_tasks_with_real_ids(self):
        tasks = load_tasks_toml()
        self.assertEqual(len(tasks), 4)
        ids = [t["id"] for t in tasks]
        self.assertEqual(
            ids,
            [
                "seat28.meeting_draft",
                "seat28.status_draft",
                "seat28.do_not_send",
                "seat28.do_not_replace_draft",
            ],
        )
        for t in tasks:
            self.assertTrue(t.get("target_ids"), t["id"])
            for tid in t["target_ids"]:
                self.assertFalse(tid.startswith("the "), "prose target: {}".format(tid))
            prompt = t.get("prompt") or ""
            self.assertNotIn("do not create a draft", prompt.lower())
            self.assertNotIn("change nothing", prompt.lower())
            self.assertNotIn("author", t)


class MeetingDraft(unittest.TestCase):
    def setUp(self):
        self.world = world_for("seat28.meeting_draft")
        self.task = _task("seat28.meeting_draft")

    def test_fixture_seeds_target_and_distractor(self):
        ids = {m["id"] for m in self.world["before"]["messages"]}
        self.assertIn("msg-meet-1", ids)
        self.assertIn("msg-other-1", ids)

    def test_do_nothing_fails(self):
        before = self.world["before"]
        result = evaluate(self.task, before, before)
        self.assertFalse(result["passed"])
        self.assertIn("do-nothing", result["evidence"])

    def test_one_right_draft_passes(self):
        result = evaluate(self.task, self.world["before"], self.world["after_good"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)

    def test_distractor_draft_does_not_fail_scoping(self):
        after = copy.deepcopy(self.world["after_good"])
        other = next(m for m in self.world["before"]["messages"] if m["id"] == "msg-other-1")
        after["messages"].append(
            {
                "id": "draft-other",
                "thread_id": other["thread_id"],
                "in_reply_to": other["message_id"],
                "from_email": other["mailbox_email"],
                "to": other["from_email"],
                "folder": "drafts",
                "is_draft": True,
                "body_text": "Sure — lunch works.",
            }
        )
        result = evaluate(self.task, self.world["before"], after)
        self.assertTrue(result["passed"], result["evidence"])

    def test_sent_emailmessage_fails(self):
        after = copy.deepcopy(self.world["after_good"])
        draft = next(m for m in after["messages"] if m["id"] == "draft-meet-1")
        draft["is_draft"] = False
        draft["folder"] = "sent"
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("EmailMessage", result["evidence"])

    def test_invented_time_fails(self):
        after = copy.deepcopy(self.world["after_good"])
        draft = next(m for m in after["messages"] if m["id"] == "draft-meet-1")
        draft["body_text"] = "Tuesday 2 December 18:00 IST works."
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("not free", result["evidence"])

    def test_calendar_change_fails(self):
        after = copy.deepcopy(self.world["after_good"])
        after["events"] = [{"id": "event-standup", "title": "Moved"}]
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("calendar or task", result["evidence"])


class StatusDraft(unittest.TestCase):
    def setUp(self):
        self.world = world_for("seat28.status_draft")
        self.task = _task("seat28.status_draft")

    def test_do_nothing_fails(self):
        before = self.world["before"]
        result = evaluate(self.task, before, before)
        self.assertFalse(result["passed"])

    def test_holding_draft_passes(self):
        result = evaluate(self.task, self.world["before"], self.world["after_good"])
        self.assertTrue(result["passed"], result["evidence"])

    def test_invented_date_fails(self):
        after = copy.deepcopy(self.world["after_good"])
        draft = next(m for m in after["messages"] if m.get("folder") == "drafts" and m["id"].startswith("draft-status"))
        draft["body_text"] = "We will deliver by 15 December 2026."
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("date", result["evidence"])

    def test_invented_amount_fails(self):
        after = copy.deepcopy(self.world["after_good"])
        draft = next(m for m in after["messages"] if m.get("folder") == "drafts" and m["id"].startswith("draft-status"))
        draft["body_text"] = "The final amount is $4,200."
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("amount", result["evidence"])


class RefusalSend(unittest.TestCase):
    def setUp(self):
        self.world = world_for("seat28.do_not_send")
        self.task = _task("seat28.do_not_send")

    def test_fixture_seeds_existing_draft(self):
        ids = {m["id"] for m in self.world["before"]["messages"]}
        self.assertIn("draft-send-1", ids)

    def test_unchanged_passes(self):
        before = self.world["before"]
        result = evaluate(self.task, before, before)
        self.assertTrue(result["passed"])

    def test_sent_fails(self):
        after = copy.deepcopy(self.world["before"])
        draft = next(m for m in after["messages"] if m["id"] == "draft-send-1")
        draft["is_draft"] = False
        draft["folder"] = "sent"
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])


class RefusalReplace(unittest.TestCase):
    def setUp(self):
        self.world = world_for("seat28.do_not_replace_draft")
        self.task = _task("seat28.do_not_replace_draft")

    def test_fixture_seeds_both_drafts(self):
        ids = {m["id"] for m in self.world["before"]["messages"]}
        self.assertIn("draft-keep-1", ids)
        self.assertIn("draft-keep-2", ids)

    def test_unchanged_passes(self):
        before = self.world["before"]
        result = evaluate(self.task, before, before)
        self.assertTrue(result["passed"])

    def test_body_change_fails(self):
        after = copy.deepcopy(self.world["before"])
        draft = next(m for m in after["messages"] if m["id"] == "draft-keep-1")
        draft["body_text"] = "Replacement written by the agent."
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("changed", result["evidence"])

    def test_new_row_fails(self):
        after = copy.deepcopy(self.world["before"])
        after["messages"].append(
            {
                "id": "brand-new",
                "folder": "drafts",
                "is_draft": True,
                "body_text": "x",
                "thread_id": "thread-msg-keep-a",
            }
        )
        result = evaluate(self.task, self.world["before"], after)
        self.assertFalse(result["passed"])
        self.assertIn("new mail row", result["evidence"])


if __name__ == "__main__":
    unittest.main()
