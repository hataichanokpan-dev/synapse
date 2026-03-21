"""
High-signal API smoke and regression tests.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from api.routes.feed import feed_stream


def test_auth_enforcement(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/api/memory/").status_code == 401
    assert client.get("/api/memory/", headers={"X-API-Key": "wrong"}).status_code == 401


def test_memory_create_honors_forced_layer_and_returns_real_uuid(client, api_headers, synapse_service):
    response = client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Remember meeting",
            "content": "Met Alice and discussed project timeline",
            "layer": "EPISODIC",
            "metadata": {"topics": ["project"], "outcome": "scheduled"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["uuid"]
    assert data["layer"] == "EPISODIC"
    assert data["metadata"]["summary"] == "Remember meeting"

    episode = synapse_service.layers.episodic.get_episode(data["uuid"])
    assert episode is not None
    assert episode.summary == "Remember meeting"
    assert episode.content == "Met Alice and discussed project timeline"


def test_memory_create_and_update_procedural_round_trip(client, api_headers, synapse_service):
    create_response = client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Deploy app",
            "content": "Run tests before deployment",
            "layer": "PROCEDURAL",
            "metadata": {
                "trigger": "Deploy app safely",
                "steps": ["Run tests", "Deploy"],
                "topics": ["deploy"],
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["uuid"]
    assert created["layer"] == "PROCEDURAL"
    assert created["name"] == "Deploy app safely"
    assert created["metadata"]["steps"] == ["Run tests", "Deploy"]

    procedure = synapse_service.layers.procedural.get_procedure(created["uuid"])
    assert procedure is not None
    assert procedure.trigger == "Deploy app safely"
    assert procedure.procedure == ["Run tests", "Deploy"]

    update_response = client.put(
        f"/api/memory/{created['uuid']}",
        headers=api_headers,
        json={
            "metadata": {
                "trigger": "Deploy app safely v2",
                "steps": ["Run tests", "Deploy", "Verify"],
                "topics": ["deploy", "release"],
            }
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Deploy app safely v2"
    assert updated["metadata"]["steps"] == ["Run tests", "Deploy", "Verify"]
    assert updated["metadata"]["topics"] == ["deploy", "release"]


def test_memory_search_respects_layer_filter(client, api_headers):
    client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Deploy app",
            "content": "Run tests before deployment",
            "layer": "PROCEDURAL",
            "metadata": {"steps": ["Run tests before deployment"]},
        },
    )
    client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Daily note",
            "content": "Deployment meeting happened today",
            "layer": "EPISODIC",
        },
    )

    response = client.post(
        "/api/memory/search",
        headers=api_headers,
        json={"query": "deploy", "layers": ["PROCEDURAL"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(result["layer"] == "PROCEDURAL" for result in data["results"])
    assert data["layers_searched"] == ["PROCEDURAL"]
    assert data["mode_used"] == "hybrid_auto"
    assert "lexical" in data["used_backends"]


def test_memory_search_finds_new_episodic_items_by_query(client, api_headers):
    create_response = client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Release note",
            "content": "Smoke token episodic-search-token is present in this memory",
            "layer": "EPISODIC",
            "metadata": {"topics": ["release"], "outcome": "documented"},
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()

    search_response = client.post(
        "/api/memory/search",
        headers=api_headers,
        json={"query": "episodic-search-token", "layers": ["EPISODIC"]},
    )

    assert search_response.status_code == 200
    data = search_response.json()
    assert data["total"] >= 1
    assert any(result["uuid"] == created["uuid"] for result in data["results"])
    assert all(result["layer"] == "EPISODIC" for result in data["results"])


def test_memory_search_explain_and_strict_mode_paths(client, api_headers):
    create_response = client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Semantic note",
            "content": "Python is a programming language",
            "layer": "SEMANTIC",
        },
    )
    assert create_response.status_code == 200

    explain_response = client.post(
        "/api/memory/search",
        headers=api_headers,
        json={"query": "Python", "layers": ["SEMANTIC"], "explain": True},
    )
    assert explain_response.status_code == 200
    explain_data = explain_response.json()
    assert explain_data["results"]
    assert explain_data["results"][0]["score_breakdown"] is not None

    strict_response = client.post(
        "/api/memory/search",
        headers=api_headers,
        json={"query": "Python", "layers": ["SEMANTIC"], "mode": "hybrid_strict"},
    )
    assert strict_response.status_code == 503


def test_procedure_endpoints_return_real_ids_and_trigger(client, api_headers):
    create_response = client.post(
        "/api/procedures/",
        headers=api_headers,
        json={
            "trigger": "Backup DB",
            "steps": ["Stop writes", "Dump DB"],
            "topics": ["ops"],
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["uuid"]
    assert created["trigger"] == "Backup DB"

    success_response = client.post(
        f"/api/procedures/{created['uuid']}/success",
        headers=api_headers,
    )
    assert success_response.status_code == 200
    succeeded = success_response.json()
    assert succeeded["uuid"] == created["uuid"]
    assert succeeded["trigger"] == "Backup DB"
    assert succeeded["success_count"] == 1


def test_preferences_round_trip_normalizes_response_style_and_length(client, api_headers):
    update_response = client.put(
        "/api/identity/preferences",
        headers=api_headers,
        json={
            "response_style": "balanced",
            "response_length": "detailed",
            "add_topics": ["ai"],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["user_id"] == "test-user"
    assert updated["updated_at"] is not None
    assert updated["preferences"]["response_style"] == "auto"
    assert updated["preferences"]["response_length"] == "detailed"

    get_response = client.get("/api/identity/preferences", headers=api_headers)
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["user_id"] == "test-user"
    assert fetched["preferences"]["response_style"] == "auto"
    assert fetched["preferences"]["response_length"] == "detailed"
    assert fetched["preferences"]["topics"] == ["ai"]


def test_feed_history_works(client, api_headers):
    client.post(
        "/api/memory/",
        headers=api_headers,
        json={
            "name": "Remember meeting",
            "content": "Met Alice and discussed project timeline",
            "layer": "EPISODIC",
        },
    )

    feed_response = client.get("/api/feed/", headers=api_headers)
    assert feed_response.status_code == 200
    feed = feed_response.json()
    assert feed["events"]
    datetime.fromisoformat(feed["events"][0]["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_feed_stream_emits_connected_event(event_bus):
    response = await feed_stream(event_bus=event_bus)
    assert response.media_type == "text/event-stream"

    first_chunk = await anext(response.body_iterator)
    if isinstance(first_chunk, bytes):
        first_chunk = first_chunk.decode("utf-8")
    assert "\"connected\"" in first_chunk

    await response.body_iterator.aclose()


def test_system_maintenance_and_graph_unavailable_paths(client, api_headers):
    maintenance = client.post(
        "/api/system/maintenance",
        headers=api_headers,
        json={"actions": ["purge_expired"], "dry_run": True},
    )
    assert maintenance.status_code == 200
    maintenance_body = maintenance.json()
    assert maintenance_body["results"][0]["action"] == "purge_expired"
    assert "Would purge" in maintenance_body["results"][0]["message"]

    clear_graph = client.request(
        "DELETE",
        "/api/system/graph",
        headers=api_headers,
        json={"confirm": True},
    )
    assert clear_graph.status_code == 503

    delete_node = client.delete("/api/graph/nodes/test-node", headers=api_headers)
    assert delete_node.status_code == 503

    delete_edge = client.delete("/api/graph/edges/test-edge", headers=api_headers)
    assert delete_edge.status_code == 503


def test_system_stats_include_search_metrics(client, api_headers):
    search_response = client.post(
        "/api/memory/search",
        headers=api_headers,
        json={"query": "nothing", "layers": ["PROCEDURAL"]},
    )
    assert search_response.status_code == 200

    stats = client.get("/api/system/stats", headers=api_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert "search" in body
    assert "counts" in body["search"]
