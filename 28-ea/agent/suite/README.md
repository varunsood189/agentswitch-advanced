# Seat 28 — four draft checks

Exactly four tasks for the combined agent in this folder. A normal task passes only when `check_draft.py` finds one new unsent `EmailMessage` draft that replies to the **target** message (other inbox drafts are ignored). A do-nothing agent fails those two draft tasks. A refusal passes only when no mail, calendar event, or task changed.

Each task **seeds its own fixtures** in `fixtures.py` (real message / draft ids). Prompts do not describe records that are not seeded, and refusal prompts do not say “change nothing” or “do not create a draft”.

## Run

```sh
cd 28-ea/agent
python -m pytest suite/test_check_draft.py -q
python -m suite.run_task --all --mode do-nothing
python -m suite.run_task --all --mode expect-good
python -m suite.run_task --all --mode agent
```

`do-nothing` must fail the two draft tasks and pass the two refusals. `agent` runs `build_briefing` on an in-memory FakeClient seeded from each task (no network, no token).

Live (optional; needs seat credentials):

```sh
python -m suite.run_task seat28.meeting_draft --live
```

Requires `AGENTSWITCH_KEYSTONE_TOKEN` or `EA_EMAIL` + `EA_PASSWORD_KEYSTONE`, plus `OPENAI_*` / `EA_LLM_*` unless you only exercise login. Harness live URLs stay read-only by agent contract.

## Layout

| File | Role |
|---|---|
| `tasks.toml` | The four tasks (real `target_ids`) |
| `fixtures/` | Per-task seeded before/after platform rows |
| `check_draft.py` | Platform verdict (target scoping, dates/amounts, EmailMessage draft/sent) |
| `run_task.py` | Runnable path: seed → agent or do-nothing → evaluate |
| `test_check_draft.py` | Offline tests (Python 3.10+) |

Nothing under `34-eval-harness/` or `28-ea/varun/`.
