# Live run

Blocked in this environment: no `AGENTSWITCH_*` / `EA_PASSWORD_*` / `OPENAI_*` secrets are available to the agent VM.

Required to unblock:

- `EA_EMAIL` + `EA_PASSWORD_KEYSTONE` (or `AGENTSWITCH_KEYSTONE_TOKEN`)
- `OPENAI_BASE_URL` + `OPENAI_API_KEY` + `OPENAI_MODEL` (or `EA_LLM_*`)

Offline substitute already run (FakeClient, no network):

```sh
python -m suite.run_task --all --mode do-nothing
python -m suite.run_task --all --mode expect-good
python -m suite.run_task --all --mode agent
```

All four tasks passed those modes. Paste a live Keystone table into the upstream PR body after #53 merges (team28b seed only; sent must stay 0).
