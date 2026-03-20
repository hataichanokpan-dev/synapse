# Synapse Production Release Checklist

Last updated: March 20, 2026

Use this checklist as the final gate before deploying the Synapse API.

## Release Gate

- [ ] `pytest api/tests -q` passes on the release candidate.
- [ ] `python scripts/pre_deploy_smoke.py --base-url <url> --api-key <key> --output-json artifacts/pre_deploy_smoke.json` passes against the target environment.
- [ ] If graph features are required in this environment, smoke test passes with `--require-graph`.
- [ ] If semantic writes must be validated before release, run smoke test in staging with `--semantic-write-check`.
- [ ] Attach both `pytest` output and the JSON smoke report to the release evidence.

## Canonical Commands

Use these commands as the default release gate:

```bash
pytest api/tests -q
python scripts/pre_deploy_smoke.py --base-url http://127.0.0.1:8000 --api-key "$SYNAPSE_API_KEY" --output-json artifacts/pre_deploy_smoke.json
```

If the target environment has slow cold-start writes, increase the per-request timeout explicitly, for example `--timeout 60`.

If graph is required:

```bash
python scripts/pre_deploy_smoke.py --base-url http://127.0.0.1:8000 --api-key "$SYNAPSE_API_KEY" --require-graph --output-json artifacts/pre_deploy_smoke.json
```

If semantic writes must be verified in staging:

```bash
python scripts/pre_deploy_smoke.py --base-url http://127.0.0.1:8000 --api-key "$SYNAPSE_API_KEY" --require-graph --semantic-write-check --output-json artifacts/pre_deploy_smoke.semantic.json
```

## Environment

- [ ] `DEBUG` is set to a production-safe value such as `false`, `off`, `prod`, `production`, or `release`.
- [ ] `SYNAPSE_API_KEY` is set and is not the default development key.
- [ ] `CORS_ORIGINS` only includes approved origins.
- [ ] Persistent storage for `~/.synapse` or the configured SQLite path is mounted and backed up.
- [ ] Required secrets are present for the chosen backend mode.

## Backend Readiness

- [ ] API process starts cleanly with no startup config error.
- [ ] SQLite-backed layers are writable.
- [ ] If graph mode is required, FalkorDB is reachable and healthy.
- [ ] If semantic/vector mode is required, Qdrant is reachable and healthy.
- [ ] `SYNAPSE_REQUIRE_GRAPHITI=true` is only enabled when graph backend availability is guaranteed.

## Functional Checks

- [ ] Protected endpoints reject missing or invalid API keys with `401`.
- [ ] Episodic memory create returns a real `uuid` and is readable immediately.
- [ ] Procedural memory create returns a real `uuid` and is readable immediately.
- [ ] Memory update works for episodic and procedural items.
- [ ] Layer-filtered search returns only the requested layer.
- [ ] Procedure update returns persisted data and is readable immediately.
- [ ] Procedure success recording increments `success_count`.
- [ ] Preferences update/get round-trips canonical values for `response_style` and `response_length`.
- [ ] Maintenance dry-run succeeds for at least `purge_expired`.
- [ ] Feed history loads without datetime errors.
- [ ] Feed SSE stream returns the initial `connected` event.
- [ ] Graph endpoints return `503` when graph driver is unavailable instead of false success.

## Staging-Only Checks

Run these in staging or an isolated environment, not against live production data.

- [ ] `python scripts/pre_deploy_smoke.py --base-url <url> --api-key <key> --require-graph --semantic-write-check --output-json artifacts/pre_deploy_smoke.semantic.json`
- [ ] Create and search a semantic memory item successfully.
- [ ] Verify graph data is written for the isolated test group.
- [ ] If testing graph cleanup, use a unique isolated `group_id` only.

## Deployment

- [ ] Deployment artifact or image tag is immutable and recorded.
- [ ] Rollback target is known and available.
- [ ] Maintenance window and release owner are defined.
- [ ] Logs, metrics, and alert channels are ready before cutover.

## Post-Deploy

- [ ] Run `python scripts/pre_deploy_smoke.py --base-url <prod-url> --api-key <prod-key> --require-graph --output-json artifacts/post_deploy_smoke.json` after rollout if graph is required.
- [ ] Confirm `/health` and `/api/system/status` remain stable for at least one observation window.
- [ ] Review application logs for auth failures, Graphiti write errors, and SQLite errors.
- [ ] Confirm feed activity appears for real traffic after deploy.

## Rollback Triggers

Rollback immediately if any of the following occurs:

- [ ] Auth is bypassed on protected endpoints.
- [ ] Memory create returns empty or inconsistent IDs.
- [ ] Search or feed endpoints return `500`.
- [ ] Graph-required environments report degraded graph health.
- [ ] Semantic writes fail in a mode where semantic persistence is required.

## Evidence To Capture

- [ ] Test output from `pytest api/tests -q`
- [ ] Smoke script stdout output
- [ ] Smoke script JSON output
- [ ] Deployed version, git SHA, and timestamp
- [ ] Any known exceptions or release notes for this deploy
