#!/usr/bin/env python
"""
Pre-deploy smoke test runner for the Synapse API.

Safe by default:
- validates auth
- validates core episodic/procedural/preferences/feed/system flows
- cleans up temporary episodic/procedural test data

Optional:
- --require-graph checks that FalkorDB is healthy through /api/system/status
- --semantic-write-check performs a semantic write/search check
  This leaves semantic test data behind and should be used in staging or an
  isolated environment only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, request
from uuid import uuid4


@dataclass
class StepResult:
    name: str
    ok: bool
    status_code: Optional[int]
    detail: str
    duration_ms: int


class SmokeFailure(RuntimeError):
    """Raised when a smoke step fails."""


class SmokeClient:
    """Minimal JSON HTTP client using the standard library."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        authenticated: bool = True,
    ) -> tuple[int, Any]:
        payload = None
        headers = {
            "Accept": "application/json",
        }
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            headers["X-API-Key"] = self.api_key

        req = request.Request(
            url=f"{self.base_url}{path}",
            data=payload,
            headers=headers,
            method=method.upper(),
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                status = response.getcode()
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8")
        except Exception as exc:
            raise SmokeFailure(f"{method.upper()} {path} failed: {exc}") from exc

        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = raw

        return status, data

    def stream_first_line(self, path: str, *, authenticated: bool = True) -> tuple[int, str]:
        """Open an SSE endpoint and return the first line."""
        headers = {
            "Accept": "text/event-stream",
        }
        if authenticated:
            headers["X-API-Key"] = self.api_key

        req = request.Request(
            url=f"{self.base_url}{path}",
            headers=headers,
            method="GET",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                status = response.getcode()
                first_line = response.readline().decode("utf-8")
        except error.HTTPError as exc:
            status = exc.code
            first_line = exc.read().decode("utf-8")
        except Exception as exc:
            raise SmokeFailure(f"GET {path} stream failed: {exc}") from exc

        return status, first_line


class SmokeRunner:
    """Runs smoke checks and tracks cleanup."""

    def __init__(self, client: SmokeClient, args: argparse.Namespace):
        self.client = client
        self.args = args
        self.results: list[StepResult] = []
        self.created_memory_id: Optional[str] = None
        self.created_procedure_id: Optional[str] = None
        self.semantic_uuid: Optional[str] = None
        self.token = uuid4().hex[:8]
        self.group_id = f"smoke_group_{self.token}"
        self.topic = f"smoke-topic-{self.token}"
        self.updated_procedure_trigger = f"smoke procedure {self.token} updated"

    def record(self, name: str, ok: bool, status_code: Optional[int], detail: str, started_at: float) -> None:
        self.results.append(
            StepResult(
                name=name,
                ok=ok,
                status_code=status_code,
                detail=detail,
                duration_ms=int((time.time() - started_at) * 1000),
            )
        )

    def assert_status(self, name: str, expected: int, actual: int, payload: Any, started_at: float) -> None:
        if actual != expected:
            detail = f"expected {expected}, got {actual}, payload={payload}"
            self.record(name, False, actual, detail, started_at)
            raise SmokeFailure(detail)
        self.record(name, True, actual, "ok", started_at)

    def assert_condition(self, name: str, condition: bool, status_code: Optional[int], detail: str, started_at: float) -> None:
        if not condition:
            self.record(name, False, status_code, detail, started_at)
            raise SmokeFailure(detail)
        self.record(name, True, status_code, detail, started_at)

    @staticmethod
    def parse_datetime(value: Any) -> Optional[datetime]:
        """Parse ISO timestamps and require timezone awareness."""
        if not value:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            raise SmokeFailure(f"Timestamp is missing timezone information: {value}")
        return parsed.astimezone(timezone.utc)

    def run(self) -> None:
        try:
            self.run_safe_checks()
            if self.args.semantic_write_check:
                self.run_semantic_check()
        finally:
            self.cleanup()

    def run_safe_checks(self) -> None:
        self.check_root()
        self.check_health()
        if not self.args.skip_auth_check:
            self.check_auth_enforcement()
        self.check_system_status()
        self.check_system_stats()
        self.check_maintenance_dry_run()
        self.check_preferences_round_trip()
        self.check_episodic_memory_flow()
        self.check_procedure_flow()
        self.check_hybrid_search_flow()
        self.check_oracle_consult_flow()
        self.check_search_stats()
        self.check_feed_history()
        self.check_feed_stream()

    def check_root(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/", authenticated=False)
        self.assert_status("root", 200, status, payload, started_at)

    def check_health(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/health", authenticated=False)
        self.assert_status("health", 200, status, payload, started_at)

    def check_auth_enforcement(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/api/memory/", authenticated=False)
        self.assert_status("auth_missing", 401, status, payload, started_at)

        started_at = time.time()
        rogue_client = SmokeClient(self.client.base_url, api_key="invalid-key", timeout=self.client.timeout)
        status, payload = rogue_client.request("GET", "/api/memory/")
        self.assert_status("auth_invalid", 401, status, payload, started_at)

    def check_system_status(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/api/system/status")
        self.assert_status("system_status_http", 200, status, payload, started_at)

        components = {
            component["name"]: component
            for component in payload.get("components", [])
            if isinstance(component, dict)
        }
        overall = payload.get("status")
        self.assert_condition(
            "system_status_body",
            overall in {"healthy", "degraded"},
            status,
            f"overall status={overall}",
            started_at,
        )

        if self.args.require_graph:
            graph_component = components.get("falkordb")
            self.assert_condition(
                "graph_required",
                bool(graph_component) and graph_component.get("status") == "healthy",
                status,
                f"falkordb component={graph_component}",
                started_at,
            )

            started_at = time.time()
            status, payload = self.client.request("GET", "/api/graph/nodes?limit=1")
            self.assert_status("graph_nodes_http", 200, status, payload, started_at)

    def check_system_stats(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/api/system/stats")
        self.assert_status("system_stats", 200, status, payload, started_at)
        self.assert_condition(
            "system_stats_shape",
            isinstance(payload, dict) and "memory" in payload and "storage" in payload,
            status,
            "memory/storage present",
            started_at,
        )

    def check_maintenance_dry_run(self) -> None:
        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/system/maintenance",
            body={
                "actions": ["purge_expired"],
                "dry_run": True,
            },
        )
        self.assert_status("maintenance_http", 200, status, payload, started_at)
        results = payload.get("results", [])
        first_result = results[0] if results else {}
        self.assert_condition(
            "maintenance_body",
            bool(results) and first_result.get("action") == "purge_expired",
            status,
            f"payload={payload}",
            started_at,
        )

    def check_preferences_round_trip(self) -> None:
        started_at = time.time()
        status, payload = self.client.request(
            "PUT",
            "/api/identity/preferences",
            body={
                "response_style": "balanced",
                "response_length": "detailed",
                "add_topics": [self.topic],
            },
        )
        self.assert_status("preferences_update_http", 200, status, payload, started_at)
        prefs = payload.get("preferences", {})
        self.assert_condition(
            "preferences_update_body",
            (
                prefs.get("response_style") == "auto"
                and prefs.get("response_length") == "detailed"
                and payload.get("user_id")
                and self.parse_datetime(payload.get("updated_at")) is not None
            ),
            status,
            f"preferences={prefs}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request("GET", "/api/identity/preferences")
        self.assert_status("preferences_get_http", 200, status, payload, started_at)
        prefs = payload.get("preferences", {})
        self.assert_condition(
            "preferences_get_body",
            self.topic in prefs.get("topics", []),
            status,
            f"topics={prefs.get('topics', [])}",
            started_at,
        )

    def check_episodic_memory_flow(self) -> None:
        name = f"smoke-episode-{self.token}"
        content = f"episodic smoke content {self.token}"

        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/memory/",
            body={
                "name": name,
                "content": content,
                "layer": "EPISODIC",
                "group_id": self.group_id,
                "metadata": {
                    "topics": [self.topic],
                    "outcome": "smoke",
                },
            },
        )
        self.assert_status("memory_create_http", 200, status, payload, started_at)
        self.created_memory_id = payload.get("uuid")
        self.assert_condition(
            "memory_create_body",
            (
                bool(self.created_memory_id)
                and payload.get("layer") == "EPISODIC"
                and self.parse_datetime(payload.get("created_at")) is not None
            ),
            status,
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request("GET", f"/api/memory/{self.created_memory_id}")
        self.assert_status("memory_get_http", 200, status, payload, started_at)
        self.assert_condition(
            "memory_get_body",
            payload.get("uuid") == self.created_memory_id and payload.get("content") == content,
            status,
            f"payload={payload}",
            started_at,
        )

        updated_content = f"{content} updated"
        started_at = time.time()
        status, payload = self.client.request(
            "PUT",
            f"/api/memory/{self.created_memory_id}",
            body={
                "content": updated_content,
                "metadata": {
                    "summary": name,
                    "topics": [self.topic, "updated"],
                    "outcome": "updated",
                },
            },
        )
        self.assert_status("memory_update_http", 200, status, payload, started_at)
        self.assert_condition(
            "memory_update_body",
            (
                payload.get("content") == updated_content
                and "updated" in payload.get("metadata", {}).get("topics", [])
                and self.parse_datetime(payload.get("updated_at")) is not None
            ),
            status,
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": self.token,
                "layers": ["EPISODIC"],
                "limit": 10,
            },
        )
        self.assert_status("memory_search_http", 200, status, payload, started_at)
        results = payload.get("results", [])
        self.assert_condition(
            "memory_search_body",
            any(item.get("uuid") == self.created_memory_id for item in results),
            status,
            f"results={results}",
            started_at,
        )

    def check_procedure_flow(self) -> None:
        trigger = f"smoke procedure {self.token}"

        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/procedures/",
            body={
                "trigger": trigger,
                "steps": ["step one", "step two"],
                "topics": [self.topic],
            },
        )
        self.assert_status("procedure_create_http", 200, status, payload, started_at)
        self.created_procedure_id = payload.get("uuid")
        self.assert_condition(
            "procedure_create_body",
            (
                bool(self.created_procedure_id)
                and payload.get("trigger") == trigger
                and self.parse_datetime(payload.get("created_at")) is not None
            ),
            status,
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request("GET", f"/api/procedures/{self.created_procedure_id}")
        self.assert_status("procedure_get_http", 200, status, payload, started_at)
        self.assert_condition(
            "procedure_get_body",
            payload.get("uuid") == self.created_procedure_id and payload.get("trigger") == trigger,
            status,
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request(
            "PUT",
            f"/api/procedures/{self.created_procedure_id}",
            body={
                "trigger": self.updated_procedure_trigger,
                "steps": ["step one", "step two", "verify result"],
                "topics": [self.topic, "updated"],
            },
        )
        self.assert_status("procedure_update_http", 200, status, payload, started_at)
        self.assert_condition(
            "procedure_update_body",
            (
                payload.get("trigger") == self.updated_procedure_trigger
                and "updated" in payload.get("topics", [])
                and self.parse_datetime(payload.get("updated_at")) is not None
            ),
            status,
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request("POST", f"/api/procedures/{self.created_procedure_id}/success")
        self.assert_status("procedure_success_http", 200, status, payload, started_at)
        self.assert_condition(
            "procedure_success_body",
            payload.get("success_count", 0) >= 1 and payload.get("trigger") == self.updated_procedure_trigger,
            status,
            f"payload={payload}",
            started_at,
        )

    def check_hybrid_search_flow(self) -> None:
        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": self.token,
                "limit": 10,
                "mode": "hybrid_auto",
                "query_type": "mixed",
                "explain": True,
            },
        )
        self.assert_status("hybrid_search_http", 200, status, payload, started_at)
        results = payload.get("results", [])
        result_ids = {item.get("uuid") for item in results if isinstance(item, dict)}
        self.assert_condition(
            "hybrid_search_body",
            (
                bool(results)
                and (self.created_memory_id in result_ids or self.created_procedure_id in result_ids)
                and payload.get("mode_used") == "hybrid_auto"
                and bool(payload.get("query_type_detected"))
                and "lexical" in payload.get("used_backends", [])
            ),
            status,
            f"payload={payload}",
            started_at,
        )
        self.assert_condition(
            "hybrid_search_explain",
            any(item.get("sources") for item in results if isinstance(item, dict)),
            status,
            f"results={results}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": self.token,
                "layers": ["SEMANTIC"],
                "limit": 5,
                "mode": "hybrid_strict",
            },
        )
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        strict_ok = status in {200, 503}
        if strict_ok and status == 503 and isinstance(detail, dict):
            strict_ok = bool(detail.get("degraded_backends"))
        self.assert_condition(
            "hybrid_strict_semantic",
            strict_ok,
            status,
            f"payload={payload}",
            started_at,
        )

    def check_oracle_consult_flow(self) -> None:
        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/oracle/consult",
            body={
                "query": self.token,
                "limit": 5,
                "mode": "hybrid_auto",
                "query_type": "mixed",
                "explain": True,
            },
        )
        self.assert_status("consult_http", 200, status, payload, started_at)
        ranked_results = payload.get("ranked_results", [])
        self.assert_condition(
            "consult_body",
            (
                bool(ranked_results)
                and payload.get("mode_used") == "hybrid_auto"
                and bool(payload.get("query_type_detected"))
                and bool(payload.get("summary"))
            ),
            status,
            f"payload={payload}",
            started_at,
        )
        self.assert_condition(
            "consult_explain",
            any(item.get("sources") for item in ranked_results if isinstance(item, dict)),
            status,
            f"ranked_results={ranked_results}",
            started_at,
        )

    def check_search_stats(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/api/system/stats")
        self.assert_status("system_stats_search_http", 200, status, payload, started_at)
        search = payload.get("search", {}) if isinstance(payload, dict) else {}
        counts = search.get("counts", {}) if isinstance(search, dict) else {}
        self.assert_condition(
            "system_stats_search_body",
            int(counts.get("queries_total", 0)) >= 2,
            status,
            f"search={search}",
            started_at,
        )

    def check_feed_history(self) -> None:
        started_at = time.time()
        status, payload = self.client.request("GET", "/api/feed/")
        self.assert_status("feed_http", 200, status, payload, started_at)
        self.assert_condition(
            "feed_body",
            isinstance(payload, dict) and "events" in payload,
            status,
            f"event_count={len(payload.get('events', []))}",
            started_at,
        )

    def check_feed_stream(self) -> None:
        started_at = time.time()
        status, first_line = self.client.stream_first_line("/api/feed/stream")
        self.assert_status("feed_stream_http", 200, status, first_line, started_at)
        self.assert_condition(
            "feed_stream_body",
            "\"connected\"" in first_line,
            status,
            f"first_line={first_line.strip()}",
            started_at,
        )

    def run_semantic_check(self) -> None:
        name = f"smoke-semantic-{self.token}"
        content = f"semantic smoke content {self.token}"

        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/memory/",
            body={
                "name": name,
                "content": content,
                "layer": "SEMANTIC",
                "group_id": self.group_id,
                "source_description": "semantic smoke check",
            },
        )
        self.assert_status("semantic_create_http", 200, status, payload, started_at)
        self.semantic_uuid = payload.get("uuid")
        self.assert_condition(
            "semantic_create_body",
            bool(self.semantic_uuid) and payload.get("layer") == "SEMANTIC",
            status,
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = self.client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": self.token,
                "layers": ["SEMANTIC"],
                "limit": 10,
            },
        )
        self.assert_status("semantic_search_http", 200, status, payload, started_at)
        results = payload.get("results", [])
        self.assert_condition(
            "semantic_search_body",
            any(item.get("uuid") == self.semantic_uuid for item in results),
            status,
            f"results={results}",
            started_at,
        )

    def cleanup(self) -> None:
        if self.args.keep_test_data:
            return

        if self.created_memory_id:
            try:
                self.client.request("DELETE", f"/api/memory/{self.created_memory_id}")
            except Exception:
                pass

        if self.created_procedure_id:
            try:
                self.client.request("DELETE", f"/api/procedures/{self.created_procedure_id}")
            except Exception:
                pass

    def print_summary(self) -> None:
        print("")
        print("Smoke Test Summary")
        print("==================")
        for result in self.results:
            status = "PASS" if result.ok else "FAIL"
            code = "-" if result.status_code is None else str(result.status_code)
            print(f"[{status}] {result.name} status={code} duration_ms={result.duration_ms} detail={result.detail}")

        passed = sum(1 for result in self.results if result.ok)
        total = len(self.results)
        print("")
        print(f"Passed {passed}/{total} checks")
        if self.args.semantic_write_check:
            print("Semantic write check was enabled and leaves semantic test data behind.")

    def write_json_report(self, path: str, *, exit_code: int, error_message: Optional[str]) -> None:
        """Persist smoke test output for release evidence."""
        report = {
            "base_url": self.client.base_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "group_id": self.group_id,
            "semantic_write_check": self.args.semantic_write_check,
            "require_graph": self.args.require_graph,
            "keep_test_data": self.args.keep_test_data,
            "exit_code": exit_code,
            "error_message": error_message,
            "results": [
                {
                    "name": result.name,
                    "ok": result.ok,
                    "status_code": result.status_code,
                    "detail": result.detail,
                    "duration_ms": result.duration_ms,
                }
                for result in self.results
            ],
        }
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Synapse API pre-deploy smoke checks.")
    parser.add_argument("--base-url", required=True, help="Base URL of the Synapse API, for example http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True, help="API key for the Synapse API")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds. Increase this in cold-start environments with slow first writes.",
    )
    parser.add_argument("--skip-auth-check", action="store_true", help="Skip the missing/invalid API key checks")
    parser.add_argument("--require-graph", action="store_true", help="Fail if the graph backend is not healthy")
    parser.add_argument(
        "--semantic-write-check",
        action="store_true",
        help="Run a semantic create/search round-trip. Use this only in staging or isolated environments.",
    )
    parser.add_argument("--keep-test-data", action="store_true", help="Do not delete episodic/procedural smoke test records")
    parser.add_argument("--output-json", help="Write a JSON smoke report to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = SmokeClient(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)
    runner = SmokeRunner(client, args)
    exit_code = 0
    error_message: Optional[str] = None

    try:
        runner.run()
    except SmokeFailure as exc:
        exit_code = 1
        error_message = str(exc)
    except KeyboardInterrupt:
        exit_code = 130
        error_message = "Smoke test interrupted."

    if args.output_json:
        runner.write_json_report(args.output_json, exit_code=exit_code, error_message=error_message)

    runner.print_summary()
    if exit_code == 1:
        print("")
        print(f"Smoke test failed: {error_message}")
    elif exit_code == 130:
        print("")
        print(error_message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
