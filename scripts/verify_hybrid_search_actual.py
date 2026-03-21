#!/usr/bin/env python
"""
Actual verification runner for the new hybrid-search functionality.

This script exercises the newly added hybrid-search behavior through:
- direct service-level calls with real SQLite-backed managers
- real HTTP calls against a temporary uvicorn server
- the existing pre-deploy smoke script in semantic-write mode

It is intentionally safe by default:
- Graphiti disabled
- Qdrant disabled
- all data written into temporary directories
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
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.models.memory import MemorySearchRequest
from api.models.oracle import ConsultRequest
from synapse.layers import LayerManager
from synapse.layers.episodic import EpisodicManager
from synapse.layers.procedural import ProceduralManager
from synapse.layers.semantic import SemanticManager
from synapse.layers.semantic_store import SemanticProjectionStore
from synapse.layers.user_model import UserModelManager
from synapse.layers.working import WorkingManager
from synapse.search import HybridSearchError, SearchWeights
from synapse.services.synapse_service import SynapseService


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    duration_ms: int
    section: str


class VerificationFailure(RuntimeError):
    """Raised when a verification step fails."""


class DummyVectorClient:
    """Offline vector client for deterministic actual tests."""

    enabled = True

    def upsert(self, *args, **kwargs):
        return None

    def search(self, *args, **kwargs):
        return []

    def delete(self, *args, **kwargs):
        return None

    def scroll(self, *args, **kwargs):
        return ([], None)


class HttpClient:
    """Minimal JSON HTTP client using urllib."""

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
        headers = {"Accept": "application/json"}
        payload = None
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
            raise VerificationFailure(f"{method.upper()} {path} failed: {exc}") from exc

        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = raw
        return status, data


def _set_env(name: str, value: Optional[str]) -> Optional[str]:
    previous = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    return previous


@contextmanager
def temporary_env(values: Dict[str, Optional[str]]):
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            _set_env(name, value)
        yield
    finally:
        for name, value in previous.items():
            _set_env(name, value)


def build_service(base_dir: Path) -> SynapseService:
    """Create a real SynapseService backed by temp SQLite files."""
    vector_client = DummyVectorClient()
    layer_manager = LayerManager(
        user_model_manager=UserModelManager(base_dir / "user_model.db"),
        procedural_manager=ProceduralManager(base_dir / "procedural.db", vector_client=vector_client),
        episodic_manager=EpisodicManager(base_dir / "episodic.db", vector_client=vector_client),
        semantic_manager=SemanticManager(
            graphiti_client=None,
            vector_client=vector_client,
            db_path=base_dir / "semantic.db",
        ),
        working_manager=WorkingManager(),
        user_id="test-user",
    )
    return SynapseService(graphiti_client=None, layer_manager=layer_manager, user_id="test-user")


def free_port() -> int:
    """Reserve a local free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ActualVerificationRunner:
    """Runs actual verification against service and API paths."""

    def __init__(self) -> None:
        self.results: List[CheckResult] = []
        self.errors: List[str] = []

    def record(self, section: str, name: str, ok: bool, detail: str, started_at: float) -> None:
        self.results.append(
            CheckResult(
                name=name,
                ok=ok,
                detail=detail,
                duration_ms=int((time.time() - started_at) * 1000),
                section=section,
            )
        )

    def check(self, section: str, name: str, condition: bool, detail: str, started_at: float) -> None:
        if not condition:
            self.record(section, name, False, detail, started_at)
            raise VerificationFailure(f"{name}: {detail}")
        self.record(section, name, True, detail, started_at)

    def check_status(
        self,
        section: str,
        name: str,
        expected: int,
        actual: int,
        payload: Any,
        started_at: float,
    ) -> None:
        detail = f"expected={expected} actual={actual} payload={payload}"
        self.check(section, name, actual == expected, detail, started_at)

    def run(self) -> Dict[str, Any]:
        try:
            self.run_service_checks()
            self.run_api_checks()
        except VerificationFailure as exc:
            self.errors.append(str(exc))
        return {
            "ok": not self.errors,
            "total_checks": len(self.results),
            "passed_checks": sum(1 for result in self.results if result.ok),
            "failed_checks": sum(1 for result in self.results if not result.ok),
            "errors": list(self.errors),
            "results": [asdict(result) for result in self.results],
        }

    def run_service_checks(self) -> None:
        section = "service"

        started_at = time.time()
        with temporary_env({"SYNAPSE_SEARCH_ENGINE": "legacy"}):
            request_model = MemorySearchRequest(query="hello")
            consult_model = ConsultRequest(query="hello")
        self.check(
            section,
            "request_model_default_mode_env",
            request_model.mode.value == "legacy" and consult_model.mode.value == "legacy",
            f"memory_mode={request_model.mode.value} consult_mode={consult_model.mode.value}",
            started_at,
        )

        started_at = time.time()
        weights = SearchWeights(path="config/hybrid_weights.yaml")
        exact_weights = weights.get("exact")
        self.check(
            section,
            "weights_file_load",
            weights.version == "1" and exact_weights.get("lexical") == 1.4 and exact_weights.get("graph") == 0.6,
            f"version={weights.version} exact_weights={exact_weights}",
            started_at,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            with temporary_env(
                {
                    "SYNAPSE_ENABLE_GRAPHITI": "false",
                    "SYNAPSE_ENABLE_QDRANT": "false",
                    "SYNAPSE_SEARCH_ENGINE": "hybrid_auto",
                    "SYNAPSE_HYBRID_TIMEOUT_MS": "800",
                    "SYNAPSE_HYBRID_LEXICAL_TIMEOUT_MS": "250",
                    "SYNAPSE_HYBRID_VECTOR_TIMEOUT_MS": "400",
                }
            ):
                service = build_service(base_dir)
                service.set_working_context("current_task", "deploy token actual in progress")

                episode = self._run_async(
                    service.add_memory(
                        name="Meeting",
                        episode_body="deploy token actual",
                        layer="EPISODIC",
                        metadata={"topics": ["deploy"], "outcome": "ok"},
                        source="verify",
                    )
                )
                procedure = self._run_async(
                    service.add_memory(
                        name="Deploy Procedure",
                        episode_body="run tests then deploy",
                        layer="PROCEDURAL",
                        metadata={
                            "trigger": "deploy token actual",
                            "steps": ["run tests", "deploy"],
                            "topics": ["deploy"],
                        },
                        source="verify",
                    )
                )
                semantic = self._run_async(
                    service.add_memory(
                        name="Python",
                        episode_body="python hybrid semantic token",
                        layer="SEMANTIC",
                        source="verify",
                    )
                )

                started_at = time.time()
                search_default = self._run_async(service.search_memory("deploy token actual", limit=5, explain=True))
                self.check(
                    section,
                    "service_search_default_hybrid",
                    (
                        search_default.get("mode_used") == "hybrid_auto"
                        and bool(search_default.get("results"))
                        and bool(search_default.get("pinned_context"))
                        and "lexical" in search_default.get("used_backends", [])
                        and all(item.get("layer") != "working" for item in search_default.get("results", []))
                    ),
                    f"payload={search_default}",
                    started_at,
                )

                started_at = time.time()
                consult_default = self._run_async(service.consult("deploy token actual", limit=5, explain=True))
                self.check(
                    section,
                    "service_consult_default_hybrid",
                    (
                        consult_default.get("mode_used") == "hybrid_auto"
                        and bool(consult_default.get("ranked_results"))
                        and bool(consult_default.get("summary"))
                        and "lexical" in consult_default.get("used_backends", [])
                    ),
                    f"payload={consult_default}",
                    started_at,
                )

                started_at = time.time()
                with temporary_env({"SYNAPSE_SEARCH_ENGINE": "legacy"}):
                    legacy_result = self._run_async(service.search_memory("deploy token actual", limit=5))
                self.check(
                    section,
                    "service_search_default_legacy_env",
                    legacy_result.get("mode_used") == "legacy" and legacy_result.get("used_backends") == ["legacy"],
                    f"payload={legacy_result}",
                    started_at,
                )

                started_at = time.time()
                first_cached = self._run_async(service.search_memory("deploy token actual", limit=5))
                new_episode = self._run_async(
                    service.add_memory(
                        name="Follow-up",
                        episode_body="deploy token actual new event",
                        layer="EPISODIC",
                        metadata={"topics": ["deploy"], "outcome": "new"},
                        source="verify",
                    )
                )
                second_cached = self._run_async(service.search_memory("deploy token actual", limit=10))
                second_ids = {item.get("uuid") for item in second_cached.get("results", [])}
                self.check(
                    section,
                    "cache_invalidation_after_write",
                    new_episode.get("uuid") in second_ids and first_cached != second_cached,
                    f"first={first_cached} second={second_cached}",
                    started_at,
                )

                started_at = time.time()
                _ = self._run_async(service.search_memory("deploy token actual", limit=5))
                _ = self._run_async(service.search_memory("deploy token actual", limit=5))
                metrics = service.hybrid_search.snapshot_metrics()
                cache_hits = int(metrics.get("counts", {}).get("cache_hit:query", 0))
                self.check(
                    section,
                    "query_cache_hit_recorded",
                    cache_hits >= 1,
                    f"counts={metrics.get('counts', {})}",
                    started_at,
                )

                started_at = time.time()
                original_fetch = service.layers.procedural.fetch_lexical_candidates

                def slow_fetch(*args, **kwargs):
                    time.sleep(0.05)
                    return original_fetch(*args, **kwargs)

                service.layers.procedural.fetch_lexical_candidates = slow_fetch
                try:
                    with temporary_env(
                        {
                            "SYNAPSE_HYBRID_TIMEOUT_MS": "20",
                            "SYNAPSE_HYBRID_LEXICAL_TIMEOUT_MS": "5",
                            "SYNAPSE_HYBRID_VECTOR_TIMEOUT_MS": "5",
                        }
                    ):
                        timeout_result = self._run_async(
                            service.search_memory("deploy token actual", layers=["PROCEDURAL"], limit=5, mode="hybrid_auto")
                        )
                finally:
                    service.layers.procedural.fetch_lexical_candidates = original_fetch
                self.check(
                    section,
                    "timeout_budget_degrades_request",
                    bool(timeout_result.get("degraded")) and bool(timeout_result.get("warnings")),
                    f"payload={timeout_result}",
                    started_at,
                )

                started_at = time.time()
                strict_failed = False
                strict_error = ""
                try:
                    self._run_async(
                        service.search_memory(
                            "python hybrid semantic token",
                            layers=["SEMANTIC"],
                            limit=5,
                            mode="hybrid_strict",
                            query_type="semantic",
                        )
                    )
                except HybridSearchError as exc:
                    strict_failed = True
                    strict_error = str(exc)
                self.check(
                    section,
                    "strict_semantic_fails_without_graph",
                    strict_failed,
                    f"error={strict_error}",
                    started_at,
                )

                started_at = time.time()
                reopened_store = SemanticProjectionStore(base_dir / "semantic.db")
                lexical_results = reopened_store.fetch_lexical_candidates("python hybrid semantic token", limit=5)
                self.check(
                    section,
                    "semantic_projection_survives_reopen",
                    any(item.get("record_id") == semantic.get("uuid") for item in lexical_results),
                    f"results={lexical_results}",
                    started_at,
                )

                started_at = time.time()
                stats = self._run_async(service.get_system_stats())
                self.check(
                    section,
                    "system_stats_expose_search_and_projection",
                    (
                        int(stats.get("search", {}).get("counts", {}).get("queries_total", 0)) >= 2
                        and int(stats.get("semantic_projection", {}).get("nodes", 0)) >= 1
                    ),
                    f"stats={stats}",
                    started_at,
                )

    def run_api_checks(self) -> None:
        section = "api"
        with tempfile.TemporaryDirectory() as temp_home:
            home_path = Path(temp_home)
            port = free_port()
            base_url = f"http://127.0.0.1:{port}"
            log_path = home_path / "uvicorn.log"
            env = os.environ.copy()
            env.update(
                {
                    "USERPROFILE": str(home_path),
                    "HOME": str(home_path),
                    "SYNAPSE_ENABLE_GRAPHITI": "false",
                    "SYNAPSE_ENABLE_QDRANT": "false",
                    "SYNAPSE_SEARCH_ENGINE": "hybrid_auto",
                    "SYNAPSE_API_KEY": "synapse-dev-key",
                }
            )

            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=str(Path(__file__).resolve().parents[1]),
                env=env,
                stdout=log_path.open("w", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            try:
                self._wait_for_server(base_url)
                client = HttpClient(base_url=base_url, api_key="synapse-dev-key")
                self._run_api_sequence(section, client, base_url)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

    def _run_api_sequence(self, section: str, client: HttpClient, base_url: str) -> None:
        token = f"actual-{int(time.time())}"

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/memory/",
            body={
                "name": "API Episode",
                "content": f"{token} episodic content",
                "layer": "EPISODIC",
                "metadata": {"topics": [token], "outcome": "ok"},
            },
        )
        self.check_status(section, "api_create_episode", 200, status, payload, started_at)
        episode_uuid = payload.get("uuid")

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/procedures/",
            body={
                "trigger": f"{token} procedure",
                "steps": ["step one", "step two"],
                "topics": [token],
            },
        )
        self.check_status(section, "api_create_procedure", 200, status, payload, started_at)

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/memory/",
            body={
                "name": "API Semantic",
                "content": f"{token} semantic concept",
                "layer": "SEMANTIC",
            },
        )
        self.check_status(section, "api_create_semantic", 200, status, payload, started_at)
        semantic_uuid = payload.get("uuid")

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/memory/search",
            body={"query": token, "limit": 10, "explain": True},
        )
        self.check_status(section, "api_search_default_mode", 200, status, payload, started_at)
        results = payload.get("results", [])
        result_ids = {item.get("uuid") for item in results if isinstance(item, dict)}
        self.check(
            section,
            "api_search_default_mode_body",
            (
                payload.get("mode_used") == "hybrid_auto"
                and bool(payload.get("query_type_detected"))
                and "lexical" in payload.get("used_backends", [])
                and episode_uuid in result_ids
                and any(item.get("sources") for item in results if isinstance(item, dict))
            ),
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/oracle/consult",
            body={"query": token, "limit": 5, "explain": True},
        )
        self.check_status(section, "api_consult_default_mode", 200, status, payload, started_at)
        self.check(
            section,
            "api_consult_default_mode_body",
            (
                payload.get("mode_used") == "hybrid_auto"
                and bool(payload.get("ranked_results"))
                and bool(payload.get("summary"))
                and "lexical" in payload.get("used_backends", [])
            ),
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/memory/search",
            body={
                "query": f"{token} semantic concept",
                "layers": ["SEMANTIC"],
                "mode": "hybrid_strict",
                "query_type": "semantic",
                "limit": 5,
            },
        )
        self.check(
            section,
            "api_strict_semantic_failure",
            status == 503 and bool(payload.get("detail", {}).get("degraded_backends")),
            f"status={status} payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = client.request(
            "POST",
            "/api/memory/search",
            body={"query": f"{token} semantic concept", "layers": ["SEMANTIC"], "limit": 10},
        )
        self.check_status(section, "api_semantic_lexical_search", 200, status, payload, started_at)
        self.check(
            section,
            "api_semantic_lexical_search_body",
            any(item.get("uuid") == semantic_uuid for item in payload.get("results", [])),
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        status, payload = client.request("GET", "/api/system/stats")
        self.check_status(section, "api_system_stats", 200, status, payload, started_at)
        self.check(
            section,
            "api_system_stats_body",
            (
                int(payload.get("search", {}).get("counts", {}).get("queries_total", 0)) >= 2
                and "semantic_projection" in payload.get("search", {})
            ),
            f"payload={payload}",
            started_at,
        )

        started_at = time.time()
        smoke_json = Path(tempfile.mkdtemp()) / "hybrid_smoke.json"
        process = subprocess.run(
            [
                sys.executable,
                "scripts/pre_deploy_smoke.py",
                "--base-url",
                base_url,
                "--api-key",
                "synapse-dev-key",
                "--semantic-write-check",
                "--output-json",
                str(smoke_json),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            timeout=180,
        )
        smoke_payload = json.loads(smoke_json.read_text(encoding="utf-8"))
        smoke_results = smoke_payload.get("results", [])
        smoke_failed = [item for item in smoke_results if not item.get("ok")]
        self.check(
            section,
            "pre_deploy_smoke_semantic_write",
            process.returncode == 0 and not smoke_failed,
            (
                f"returncode={process.returncode} "
                f"passed={sum(1 for item in smoke_results if item.get('ok'))} "
                f"total={len(smoke_results)} "
                f"stderr={process.stderr.strip()[:400]}"
            ),
            started_at,
        )

    def _wait_for_server(self, base_url: str) -> None:
        deadline = time.time() + 45
        last_error = None
        while time.time() < deadline:
            try:
                with request.urlopen(f"{base_url}/health", timeout=2) as response:
                    if response.getcode() == 200:
                        return
            except Exception as exc:
                last_error = exc
            time.sleep(1)
        raise VerificationFailure(f"Server did not become healthy: {last_error}")

    @staticmethod
    def _run_async(coro):
        import asyncio

        return asyncio.run(coro)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run actual hybrid-search verification.")
    parser.add_argument("--output-json", help="Optional path to write JSON results.")
    args = parser.parse_args()

    runner = ActualVerificationRunner()
    result = runner.run()

    print("Actual Hybrid Verification Summary")
    print("================================")
    for item in result["results"]:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"[{status}] {item['section']}::{item['name']} ({item['duration_ms']} ms)")
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
