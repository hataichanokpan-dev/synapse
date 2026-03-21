#!/usr/bin/env python
"""
Actual verification runner for hybrid search healthy mode.

This script starts the current worktree via uvicorn, points it at live
Qdrant + FalkorDB backends, and verifies that lexical, vector, and graph
retrieval all participate in the hybrid runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, parse, request
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    duration_ms: int


class VerificationFailure(RuntimeError):
    """Raised when an actual verification step fails."""


class HttpClient:
    """Minimal JSON client for local verification."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, Any]:
        headers = {
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

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
            raise VerificationFailure(f"{method.upper()} {path} failed: {exc}") from exc

        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = raw
        return status, data


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class HealthyModeVerifier:
    """Runs live healthy-mode checks against the current worktree."""

    def __init__(self) -> None:
        self.results: List[CheckResult] = []
        self.errors: List[str] = []

    def record(self, name: str, ok: bool, detail: str, started_at: float) -> None:
        self.results.append(
            CheckResult(
                name=name,
                ok=ok,
                detail=detail,
                duration_ms=int((time.time() - started_at) * 1000),
            )
        )

    def check(self, name: str, condition: bool, detail: str, started_at: float) -> None:
        if not condition:
            self.record(name, False, detail, started_at)
            raise VerificationFailure(f"{name}: {detail}")
        self.record(name, True, detail, started_at)

    def check_status(self, name: str, expected: int, actual: int, payload: Any, started_at: float) -> None:
        self.check(name, actual == expected, f"expected={expected} actual={actual} payload={payload}", started_at)

    def run(self) -> Dict[str, Any]:
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        api_key = "synapse-dev-key"

        with tempfile.TemporaryDirectory() as temp_home:
            home_path = Path(temp_home)
            log_path = home_path / "uvicorn_healthy.log"
            env = os.environ.copy()
            env.update(
                {
                    "USERPROFILE": str(home_path),
                    "HOME": str(home_path),
                    "SYNAPSE_ENABLE_GRAPHITI": "true",
                    "SYNAPSE_ENABLE_QDRANT": "true",
                    "SYNAPSE_SEARCH_ENGINE": "hybrid_auto",
                    "SYNAPSE_API_KEY": api_key,
                    "GRAPHITI_TELEMETRY_ENABLED": "false",
                    "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
                    "QDRANT_URL": "http://127.0.0.1:6333",
                    "FALKORDB_HOST": "127.0.0.1",
                    "FALKORDB_PORT": "6379",
                    "FALKORDB_DATABASE": "user-bfipa",
                    "FALKORDB_PASSWORD": "",
                }
            )

            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=log_path.open("w", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            try:
                client = HttpClient(base_url=base_url, api_key=api_key)
                self._wait_for_server(base_url, server)
                self._run_sequence(client, base_url)
            except VerificationFailure as exc:
                self.errors.append(str(exc))
                self.errors.append(log_path.read_text(encoding="utf-8")[-4000:])
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

        return {
            "ok": not self.errors,
            "total_checks": len(self.results),
            "passed_checks": sum(1 for result in self.results if result.ok),
            "failed_checks": sum(1 for result in self.results if not result.ok),
            "errors": list(self.errors),
            "results": [asdict(result) for result in self.results],
        }

    def _run_sequence(self, client: HttpClient, base_url: str) -> None:
        token = f"gvh{uuid4().hex[:12]}"
        group_id = f"g{token}"
        semantic_query = f"{token} semantic vector graph retrieval testing"

        started_at = time.time()
        status, payload = client.request("GET", "/health")
        self.check_status("health_http", 200, status, payload, started_at)

        started_at = time.time()
        status, payload = client.request("GET", "/api/system/status")
        self.check_status("system_status_http", 200, status, payload, started_at)
        components = {
            component["name"]: component
            for component in payload.get("components", [])
            if isinstance(component, dict) and component.get("name")
        }
        self.check(
            "graph_component_healthy",
            components.get("falkordb", {}).get("status") == "healthy",
            f"components={components}",
            started_at,
        )

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/memory/",
            body={
                "name": "Graph Token Probe",
                "content": f"{token} is associated with semantic vector graph retrieval testing",
                "layer": "SEMANTIC",
                "group_id": group_id,
            },
        )
        self.check_status("semantic_create_http", 200, status, payload, started_at)
        semantic_uuid = str(payload.get("uuid") or "")
        self.check("semantic_create_body", bool(semantic_uuid), f"payload={payload}", started_at)

        graph_node = self._wait_for_graph_node(client, token)
        graph_edge = self._fetch_node_edges(client, graph_node["uuid"], token)

        search_payload = self._wait_for_search(
            client,
            body={
                "query": semantic_query,
                "layers": ["SEMANTIC"],
                "mode": "hybrid_auto",
                "query_type": "semantic",
                "limit": 20,
                "explain": True,
            },
            required_backends={"lexical", "vector", "graph"},
            require_not_degraded=True,
            token=token,
        )

        started_at = time.time()
        self.check(
            "hybrid_auto_uses_all_backends",
            (
                set(search_payload.get("used_backends", [])) >= {"lexical", "vector", "graph"}
                and not search_payload.get("degraded")
                and any("graph" in (item.get("sources") or []) and token in json.dumps(item).lower() for item in search_payload.get("results", []))
                and any(any(source in {"lexical", "vector"} for source in (item.get("sources") or [])) for item in search_payload.get("results", []))
            ),
            f"payload={search_payload}",
            started_at,
        )

        started_at = time.time()
        strict_status, strict_payload = client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": semantic_query,
                "layers": ["SEMANTIC"],
                "mode": "hybrid_strict",
                "query_type": "semantic",
                "limit": 10,
                "explain": True,
            },
        )
        self.check(
            "hybrid_strict_semantic_success",
            strict_status == 200
            and set(strict_payload.get("used_backends", [])) >= {"vector", "graph"}
            and not strict_payload.get("degraded"),
            f"status={strict_status} payload={strict_payload}",
            started_at,
        )

        started_at = time.time()
        consult_status, consult_payload = client.request(
            "POST",
            "/api/oracle/consult",
            body={
                "query": semantic_query,
                "layers": ["SEMANTIC"],
                "mode": "hybrid_auto",
                "query_type": "semantic",
                "limit": 10,
                "explain": True,
            },
        )
        self.check(
            "consult_hybrid_auto_success",
            consult_status == 200
            and set(consult_payload.get("used_backends", [])) >= {"lexical", "vector", "graph"}
            and not consult_payload.get("degraded")
            and any("graph" in (item.get("sources") or []) for item in consult_payload.get("ranked_results", [])),
            f"status={consult_status} payload={consult_payload}",
            started_at,
        )

        started_at = time.time()
        status, _ = client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": semantic_query,
                "layers": ["SEMANTIC"],
                "mode": "hybrid_auto",
                "query_type": "semantic",
                "limit": 10,
            },
        )
        self.check_status("cache_seed_search", 200, status, None, started_at)

        started_at = time.time()
        status, _ = client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": semantic_query,
                "layers": ["SEMANTIC"],
                "mode": "hybrid_auto",
                "query_type": "semantic",
                "limit": 10,
            },
        )
        self.check_status("cache_repeat_search", 200, status, None, started_at)

        started_at = time.time()
        status, stats_payload = client.request("GET", "/api/system/stats")
        self.check_status("system_stats_http", 200, status, stats_payload, started_at)
        search_counts = stats_payload.get("search", {}).get("counts", {})
        self.check(
            "system_stats_search_counts",
            (
                int(search_counts.get("backend_used:graph", 0)) >= 1
                and int(search_counts.get("backend_used:vector", 0)) >= 1
                and int(search_counts.get("backend_used:lexical", 0)) >= 1
                and int(search_counts.get("cache_hit:query", 0)) >= 1
            ),
            f"search_counts={search_counts}",
            started_at,
        )

        started_at = time.time()
        smoke_json = Path(tempfile.mkdtemp()) / "healthy_smoke.json"
        process = subprocess.run(
            [
                sys.executable,
                "scripts/pre_deploy_smoke.py",
                "--base-url",
                base_url,
                "--api-key",
                client.api_key,
                "--require-graph",
                "--semantic-write-check",
                "--output-json",
                str(smoke_json),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        smoke_payload = json.loads(smoke_json.read_text(encoding="utf-8"))
        smoke_results = smoke_payload.get("results", [])
        smoke_failed = [item for item in smoke_results if not item.get("ok")]
        self.check(
            "pre_deploy_smoke_require_graph",
            process.returncode == 0 and not smoke_failed,
            (
                f"returncode={process.returncode} "
                f"passed={sum(1 for item in smoke_results if item.get('ok'))} "
                f"total={len(smoke_results)} "
                f"stderr={process.stderr.strip()[:400]}"
            ),
            started_at,
        )

        started_at = time.time()
        self.check(
            "graph_node_and_edge_match_token",
            token in json.dumps(graph_node).lower() and token in json.dumps(graph_edge).lower(),
            f"graph_node={graph_node} graph_edge={graph_edge}",
            started_at,
        )

        started_at = time.time()
        self.check(
            "created_semantic_retrievable",
            any(item.get("uuid") == semantic_uuid for item in search_payload.get("results", [])),
            f"semantic_uuid={semantic_uuid} payload={search_payload}",
            started_at,
        )

    def _wait_for_graph_node(self, client: HttpClient, token: str) -> Dict[str, Any]:
        deadline = time.time() + 90
        last_payload: Any = None
        while time.time() < deadline:
            started_at = time.time()
            status, payload = client.request("GET", f"/api/graph/nodes?query={parse.quote(token)}&limit=10")
            self.check_status("graph_nodes_http", 200, status, payload, started_at)
            nodes = payload.get("nodes", [])
            for node in nodes:
                lowered = json.dumps(node).lower()
                if token in lowered:
                    self.record("graph_nodes_token_match", True, f"node={node}", started_at)
                    return node
            last_payload = payload
            time.sleep(4)
        raise VerificationFailure(f"graph_nodes_token_match: token {token} not found, payload={last_payload}")

    def _fetch_node_edges(self, client: HttpClient, node_id: str, token: str) -> Dict[str, Any]:
        deadline = time.time() + 60
        last_payload: Any = None
        while time.time() < deadline:
            started_at = time.time()
            status, payload = client.request("GET", f"/api/graph/nodes/{node_id}/edges?limit=10")
            self.check_status("graph_node_edges_http", 200, status, payload, started_at)
            edges = payload.get("edges", [])
            for edge in edges:
                if token in json.dumps(edge).lower():
                    self.record("graph_node_edges_token_match", True, f"edge={edge}", started_at)
                    return edge
            last_payload = payload
            time.sleep(3)
        raise VerificationFailure(f"graph_node_edges_token_match: token {token} not found, payload={last_payload}")

    def _wait_for_search(
        self,
        client: HttpClient,
        *,
        body: Dict[str, Any],
        required_backends: set[str],
        require_not_degraded: bool,
        token: str,
    ) -> Dict[str, Any]:
        deadline = time.time() + 90
        last_payload: Any = None
        while time.time() < deadline:
            status, payload = client.request("POST", "/api/memory/search", body=body)
            if (
                status == 200
                and required_backends.issubset(set(payload.get("used_backends", [])))
                and (not require_not_degraded or not payload.get("degraded"))
                and token in json.dumps(payload).lower()
            ):
                return payload
            last_payload = payload
            time.sleep(4)
        raise VerificationFailure(f"hybrid_auto_uses_all_backends: payload={last_payload}")

    def _wait_for_server(self, base_url: str, server: subprocess.Popen[Any]) -> None:
        deadline = time.time() + 120
        last_error = None
        while time.time() < deadline:
            if server.poll() is not None:
                raise VerificationFailure(f"uvicorn exited early with code {server.returncode}")
            try:
                with request.urlopen(f"{base_url}/health", timeout=3) as response:
                    if response.getcode() == 200:
                        return
            except Exception as exc:
                last_error = exc
            time.sleep(2)
        raise VerificationFailure(f"server did not become healthy: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hybrid-search healthy-mode verification.")
    parser.add_argument("--output-json", help="Optional path to write JSON results.")
    args = parser.parse_args()

    runner = HealthyModeVerifier()
    result = runner.run()

    print("Hybrid Healthy Mode Verification Summary")
    print("======================================")
    for item in result["results"]:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"[{status}] {item['name']} ({item['duration_ms']} ms)")
        if not item["ok"]:
            print(f"  detail: {item['detail']}")
    print(
        f"Passed {result['passed_checks']}/{result['total_checks']} checks; "
        f"failed {result['failed_checks']}"
    )

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
