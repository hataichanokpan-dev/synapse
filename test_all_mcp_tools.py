#!/usr/bin/env python3
"""
Full MCP Tools Test Suite for Synapse
Tests all 15 MCP tools via HTTP transport
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class TestResult:
    """Single test result."""
    tool: str
    success: bool
    duration_ms: float
    response: Any
    error: str | None = None


class SynapseMCPTester:
    """Test all Synapse MCP tools via HTTP."""

    def __init__(self, base_url: str = "http://localhost:47780"):
        self.base_url = base_url
        self.session_id: str | None = None
        self.results: list[TestResult] = []
        self.client = httpx.AsyncClient(timeout=120.0)

    async def initialize(self) -> bool:
        """Initialize MCP session."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dev-full-test", "version": "1.0"}
            },
            "id": 1
        }

        try:
            resp = await self.client.post(f"{self.base_url}/mcp", json=payload, headers=headers)

            # Parse SSE response
            text = resp.text
            for line in text.split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "result" in data:
                        # Session ID might be in response headers or we can proceed
                        return True

            return False
        except Exception as e:
            print(f"Init error: {e}")
            return False

    async def call_tool(self, tool_name: str, arguments: dict) -> TestResult:
        """Call an MCP tool and record result."""
        start = time.time()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": int(time.time() * 1000)
        }

        try:
            resp = await self.client.post(f"{self.base_url}/mcp", json=payload, headers=headers)
            duration_ms = (time.time() - start) * 1000

            # Parse SSE response
            text = resp.text
            result_data = None

            for line in text.split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "result" in data:
                        result_data = data["result"]
                        # Extract content
                        if "content" in result_data and result_data["content"]:
                            result_data = result_data["content"][0].get("text", result_data)
                    elif "error" in data:
                        return TestResult(
                            tool=tool_name,
                            success=False,
                            duration_ms=duration_ms,
                            response=None,
                            error=data["error"].get("message", str(data["error"]))
                        )

            return TestResult(
                tool=tool_name,
                success=True,
                duration_ms=duration_ms,
                response=result_data
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return TestResult(
                tool=tool_name,
                success=False,
                duration_ms=duration_ms,
                response=None,
                error=str(e)
            )

    async def test_health(self) -> TestResult:
        """Test health endpoint."""
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            duration_ms = (time.time() - start) * 1000
            return TestResult(
                tool="health_endpoint",
                success=resp.status_code == 200,
                duration_ms=duration_ms,
                response=resp.json()
            )
        except Exception as e:
            return TestResult(
                tool="health_endpoint",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                response=None,
                error=str(e)
            )

    async def run_all_tests(self) -> dict:
        """Run all MCP tool tests."""
        print("=" * 60)
        print("SYNAPSE MCP TOOLS - FULL TEST SUITE")
        print("=" * 60)
        print()

        # Test 1: Health endpoint
        print("[1/16] Testing health endpoint...")
        result = await self.test_health()
        self.results.append(result)
        self._print_result(result)

        # Initialize session
        print("\n[*] Initializing MCP session...")
        if not await self.initialize():
            print("ERROR: Failed to initialize MCP session")
            return self._generate_report()
        print("OK: Session initialized")

        test_group = f"test_{int(time.time())}"

        # Test 2: get_status
        print(f"\n[2/16] Testing get_status...")
        result = await self.call_tool("get_status", {})
        self.results.append(result)
        self._print_result(result)

        # Test 3: add_memory (text)
        print(f"\n[3/16] Testing add_memory (text)...")
        result = await self.call_tool("add_memory", {
            "name": "Test Episode - Text",
            "episode_body": "This is a test episode for the Synapse MCP tools test suite. It contains information about testing knowledge graphs.",
            "source": "text",
            "source_description": "test suite text input",
            "group_id": test_group
        })
        self.results.append(result)
        self._print_result(result)

        # Test 4: add_memory (JSON)
        print(f"\n[4/16] Testing add_memory (JSON)...")
        result = await self.call_tool("add_memory", {
            "name": "Test Episode - JSON",
            "episode_body": json.dumps({
                "test_data": {
                    "project": "synapse",
                    "phase": 5,
                    "status": "testing",
                    "components": ["falkordb", "qdrant", "mcp-server"]
                }
            }),
            "source": "json",
            "source_description": "test suite json input",
            "group_id": test_group
        })
        self.results.append(result)
        self._print_result(result)

        # Wait for processing
        print("\n[*] Waiting for episode processing (30s)...")
        await asyncio.sleep(30)

        # Test 5: get_episodes
        print(f"\n[5/16] Testing get_episodes...")
        result = await self.call_tool("get_episodes", {
            "group_ids": [test_group],
            "last_n": 10
        })
        self.results.append(result)
        self._print_result(result)

        # Extract episode UUID for later tests
        episode_uuid = None
        if result.success and result.response:
            try:
                episodes_data = json.loads(result.response) if isinstance(result.response, str) else result.response
                if isinstance(episodes_data, dict) and "episodes" in episodes_data:
                    if episodes_data["episodes"]:
                        episode_uuid = episodes_data["episodes"][0].get("uuid")
            except:
                pass

        # Test 6: search_nodes
        print(f"\n[6/16] Testing search_nodes...")
        result = await self.call_tool("search_nodes", {
            "query": "test knowledge graph synapse",
            "group_ids": [test_group],
            "max_nodes": 10
        })
        self.results.append(result)
        self._print_result(result)

        # Test 7: search_memory_facts
        print(f"\n[7/16] Testing search_memory_facts...")
        result = await self.call_tool("search_memory_facts", {
            "query": "testing synapse components",
            "group_ids": [test_group],
            "max_facts": 10
        })
        self.results.append(result)
        self._print_result(result)

        # Test 8: get_entity_edge (will likely fail without valid UUID)
        print(f"\n[8/16] Testing get_entity_edge...")
        result = await self.call_tool("get_entity_edge", {
            "uuid": "00000000-0000-0000-0000-000000000000"  # Dummy UUID
        })
        self.results.append(result)
        self._print_result(result)

        # Test 9: delete_entity_edge (will likely fail without valid UUID)
        print(f"\n[9/16] Testing delete_entity_edge...")
        result = await self.call_tool("delete_entity_edge", {
            "uuid": "00000000-0000-0000-0000-000000000000"  # Dummy UUID
        })
        self.results.append(result)
        self._print_result(result)

        # Test 10: delete_episode
        if episode_uuid:
            print(f"\n[10/16] Testing delete_episode...")
            result = await self.call_tool("delete_episode", {
                "uuid": episode_uuid
            })
            self.results.append(result)
            self._print_result(result)
        else:
            print(f"\n[10/16] Testing delete_episode... SKIPPED (no episode UUID)")
            self.results.append(TestResult(
                tool="delete_episode",
                success=False,
                duration_ms=0,
                response=None,
                error="SKIPPED - no episode UUID available"
            ))

        # Thai NLP Tools
        print(f"\n[11/16] Testing detect_language...")
        result = await self.call_tool("detect_language", {
            "text": "สวัสดีครับ นี่คือการทดสอบภาษาไทย"
        })
        self.results.append(result)
        self._print_result(result)

        print(f"\n[12/16] Testing preprocess_for_extraction...")
        result = await self.call_tool("preprocess_for_extraction", {
            "text": "โปรเจค Synapse เป็นระบบ memory สำหรับ AI agents",
            "aggressive": False
        })
        self.results.append(result)
        self._print_result(result)

        print(f"\n[13/16] Testing preprocess_for_search...")
        result = await self.call_tool("preprocess_for_search", {
            "query": "ค้นหาข้อมูลเกี่ยวกับ knowledge graph"
        })
        self.results.append(result)
        self._print_result(result)

        print(f"\n[14/16] Testing tokenize_thai...")
        result = await self.call_tool("tokenize_thai", {
            "text": "ภาษาไทยเป็นภาษาที่ไม่มีวรรคตอนระหว่างคำ"
        })
        self.results.append(result)
        self._print_result(result)

        print(f"\n[15/16] Testing normalize_thai...")
        result = await self.call_tool("normalize_thai", {
            "text": "เเม่น้ำ  สำคัญ",  # Common Thai typos
            "level": "medium"
        })
        self.results.append(result)
        self._print_result(result)

        print(f"\n[16/16] Testing is_thai_text...")
        result = await self.call_tool("is_thai_text", {
            "text": "ภาษาไทย"
        })
        self.results.append(result)
        self._print_result(result)

        # Test 17: clear_graph (skip to preserve data)
        print(f"\n[*] clear_graph - SKIPPED (would delete test data)")

        return self._generate_report()

    def _print_result(self, result: TestResult):
        """Print test result."""
        status = "[PASS]" if result.success else "[FAIL]"
        print(f"  {status} | {result.duration_ms:.1f}ms")
        if result.error:
            print(f"  Error: {result.error}")
        if result.response and result.success:
            resp_str = str(result.response)[:200]
            if len(str(result.response)) > 200:
                resp_str += "..."
            print(f"  Response: {resp_str}")

    def _generate_report(self) -> dict:
        """Generate final report."""
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        total_duration = sum(r.duration_ms for r in self.results)

        print("\n" + "=" * 60)
        print("TEST REPORT")
        print("=" * 60)

        print(f"\nSUMMARY: Summary:")
        print(f"  Total Tests: {len(self.results)}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Success Rate: {(passed/len(self.results)*100):.1f}%" if self.results else "N/A")
        print(f"  Total Duration: {total_duration:.1f}ms")

        print(f"\nDETAIL: Detailed Results:")
        print("-" * 60)
        print(f"{'Tool':<30} {'Status':<10} {'Duration':<12}")
        print("-" * 60)
        for r in self.results:
            status = "[OK] PASS" if r.success else "[X] FAIL"
            print(f"{r.tool:<30} {status:<10} {r.duration_ms:.1f}ms")

        print("-" * 60)

        # Failed tests detail
        failed_tests = [r for r in self.results if not r.success]
        if failed_tests:
            print(f"\n[X] Failed Tests Detail:")
            for r in failed_tests:
                print(f"\n  {r.tool}:")
                print(f"    Error: {r.error}")

        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "success_rate": (passed/len(self.results)*100) if self.results else 0,
            "total_duration_ms": total_duration,
            "results": [
                {
                    "tool": r.tool,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "error": r.error
                }
                for r in self.results
            ]
        }

    async def close(self):
        """Close client."""
        await self.client.aclose()


async def main():
    tester = SynapseMCPTester()
    try:
        report = await tester.run_all_tests()

        # Save report to file
        report_path = "mcp_test_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFILE: Report saved to: {report_path}")

    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
