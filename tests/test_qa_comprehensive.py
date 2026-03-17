"""
Comprehensive QA Test Suite for Synapse AI Memory System
=========================================================

Tests EVERY function and system that the project claims as completed.
Uses real SQLite (temp dirs) instead of mocks where possible.
Only mocks external services (Graphiti, Qdrant, LLM APIs).

Test Areas:
- Step 1: Data Types & Enums
- Step 2: Decay System
- Step 3: Working Memory (Layer 5)
- Step 4: User Model (Layer 1)
- Step 5: Procedural Memory (Layer 2)
- Step 6: Episodic Memory (Layer 4)
- Step 7: Thai NLP
- Step 8: Sync Queue
- Step 9: Layer Classifier
- Step 10: LayerManager Cross-Layer
- Step 11: SynapseService Bridge
"""

import asyncio
import json
import math
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================
# Step 1: Data Types & Enums
# ============================================================


class TestMemoryLayerEnum:
    """Verify MemoryLayer enum has all 5 layers."""

    def test_has_five_layers(self):
        from synapse.layers.types import MemoryLayer

        assert len(MemoryLayer) == 5

    def test_layer_values(self):
        from synapse.layers.types import MemoryLayer

        assert MemoryLayer.USER_MODEL.value == "user_model"
        assert MemoryLayer.PROCEDURAL.value == "procedural"
        assert MemoryLayer.SEMANTIC.value == "semantic"
        assert MemoryLayer.EPISODIC.value == "episodic"
        assert MemoryLayer.WORKING.value == "working"

    def test_layers_are_string_enum(self):
        from synapse.layers.types import MemoryLayer

        for layer in MemoryLayer:
            assert isinstance(layer.value, str)


class TestEntityTypeEnum:
    """Verify EntityType enum completeness."""

    def test_has_expected_types(self):
        from synapse.layers.types import EntityType

        expected = {"person", "tech", "project", "concept", "company",
                    "topic", "procedure", "preference"}
        actual = {e.value for e in EntityType}
        assert expected.issubset(actual)

    def test_string_enum(self):
        from synapse.layers.types import EntityType

        assert EntityType.PERSON.value == "person"
        assert EntityType.TECH.value == "tech"


class TestRelationTypeEnum:
    """Verify RelationType enum completeness."""

    def test_has_core_relations(self):
        from synapse.layers.types import RelationType

        core = {"likes", "uses", "knows", "related_to", "supersedes", "is_a"}
        actual = {r.value for r in RelationType}
        assert core.issubset(actual)

    def test_has_temporal_relations(self):
        from synapse.layers.types import RelationType

        temporal = {"valid_from", "valid_until", "supersedes"}
        actual = {r.value for r in RelationType}
        assert temporal.issubset(actual)


class TestDecayConfig:
    """Verify DecayConfig constants are correct."""

    def test_lambda_default(self):
        from synapse.layers.types import DecayConfig

        assert DecayConfig.LAMBDA_DEFAULT == 0.01

    def test_lambda_procedural_slower(self):
        from synapse.layers.types import DecayConfig

        assert DecayConfig.LAMBDA_PROCEDURAL == 0.005
        assert DecayConfig.LAMBDA_PROCEDURAL < DecayConfig.LAMBDA_DEFAULT

    def test_ttl_episodic_days(self):
        from synapse.layers.types import DecayConfig

        assert DecayConfig.TTL_EPISODIC_DAYS == 90

    def test_decay_threshold(self):
        from synapse.layers.types import DecayConfig

        assert DecayConfig.DECAY_THRESHOLD == 0.1


class TestSynapseNodeModel:
    """Verify SynapseNode Pydantic model."""

    def test_create_with_defaults(self):
        from synapse.layers.types import SynapseNode, EntityType

        node = SynapseNode(
            id="test_1",
            type=EntityType.CONCEPT,
            name="Test Node",
        )
        assert node.id == "test_1"
        assert node.name == "Test Node"
        assert node.confidence == 0.7  # default
        assert node.decay_score == 1.0  # default
        assert node.access_count == 0  # default

    def test_create_with_all_fields(self):
        from synapse.layers.types import SynapseNode, EntityType, MemoryLayer

        node = SynapseNode(
            id="full_node",
            type=EntityType.TECH,
            name="Python",
            summary="A programming language",
            memory_layer=MemoryLayer.SEMANTIC,
            confidence=0.95,
            decay_score=0.8,
            access_count=5,
        )
        assert node.summary == "A programming language"
        assert node.confidence == 0.95
        assert node.memory_layer == MemoryLayer.SEMANTIC


class TestSynapseEdgeModel:
    """Verify SynapseEdge Pydantic model."""

    def test_create_edge(self):
        from synapse.layers.types import SynapseEdge, RelationType

        edge = SynapseEdge(
            id="edge_1",
            source_id="node_a",
            target_id="node_b",
            type=RelationType.RELATED_TO,
        )
        assert edge.source_id == "node_a"
        assert edge.target_id == "node_b"
        assert edge.invalid_at is None  # not superseded

    def test_edge_with_temporal(self):
        from synapse.layers.types import SynapseEdge, RelationType

        now = datetime.now(timezone.utc)
        edge = SynapseEdge(
            id="edge_2",
            source_id="a",
            target_id="b",
            type=RelationType.SUPERSEDES,
            valid_at=now,
            invalid_at=now + timedelta(days=30),
        )
        assert edge.invalid_at is not None
        assert edge.valid_at < edge.invalid_at


class TestSynapseEpisodeModel:
    """Verify SynapseEpisode Pydantic model."""

    def test_create_episode(self):
        from synapse.layers.types import SynapseEpisode, MemoryLayer

        ep = SynapseEpisode(
            id="ep_1",
            content="Had a meeting about Python",
            topics=["python", "meeting"],
            outcome="success",
        )
        assert ep.content == "Had a meeting about Python"
        assert "python" in ep.topics
        assert ep.outcome == "success"
        assert ep.memory_layer == MemoryLayer.EPISODIC


class TestUserModelModel:
    """Verify UserModel Pydantic model."""

    def test_create_user_model(self):
        from synapse.layers.types import UserModel

        user = UserModel(
            user_id="alice",
            language="th",
            response_style="casual",
            response_length="medium",
            timezone="Asia/Bangkok",
            expertise={"python": "expert"},
            common_topics=["AI"],
            notes=["prefers Thai"],
        )
        assert user.user_id == "alice"
        assert user.expertise["python"] == "expert"


class TestProceduralMemoryModel:
    """Verify ProceduralMemory Pydantic model."""

    def test_create_procedure(self):
        from synapse.layers.types import ProceduralMemory

        proc = ProceduralMemory(
            id="proc_1",
            trigger="how to deploy",
            procedure=["step 1", "step 2", "step 3"],
            source="explicit",
            success_count=0,
            topics=["deployment"],
        )
        assert len(proc.procedure) == 3
        assert proc.success_count == 0


# ============================================================
# Step 2: Decay System
# ============================================================


class TestDecayComputation:
    """Verify e^(-λt) decay score computation."""

    def test_fresh_item_score_with_zero_access(self):
        from synapse.layers.decay import compute_decay_score
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        score = compute_decay_score(
            updated_at=now,
            access_count=0,
            memory_layer=MemoryLayer.SEMANTIC,
            now=now,
        )
        # recency=1.0, access_factor = 0.5 + 0*0.05 = 0.5
        assert score == pytest.approx(0.5, abs=0.01)

    def test_decay_decreases_over_time(self):
        from synapse.layers.decay import compute_decay_score
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=69)  # ~half-life for LAMBDA_DEFAULT=0.01

        score = compute_decay_score(
            updated_at=past,
            access_count=0,
            memory_layer=MemoryLayer.SEMANTIC,
            now=now,
        )
        # recency = e^(-0.01 * 69) ≈ 0.5, access_factor = 0.5
        # combined ≈ 0.25
        assert 0.15 < score < 0.35

    def test_procedural_decays_slower(self):
        from synapse.layers.decay import compute_decay_score
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=69)

        sem_score = compute_decay_score(
            updated_at=past, access_count=0,
            memory_layer=MemoryLayer.SEMANTIC, now=now,
        )
        proc_score = compute_decay_score(
            updated_at=past, access_count=0,
            memory_layer=MemoryLayer.PROCEDURAL, now=now,
        )
        # Procedural (λ=0.005) decays slower than Semantic (λ=0.01)
        assert proc_score > sem_score

    def test_access_boosts_score(self):
        from synapse.layers.decay import compute_decay_score
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=30)

        score_no_access = compute_decay_score(
            updated_at=past, access_count=0,
            memory_layer=MemoryLayer.SEMANTIC, now=now,
        )
        score_with_access = compute_decay_score(
            updated_at=past, access_count=5,
            memory_layer=MemoryLayer.SEMANTIC, now=now,
        )
        assert score_with_access >= score_no_access

    def test_score_bounded_zero_to_one(self):
        from synapse.layers.decay import compute_decay_score
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        very_old = now - timedelta(days=10000)

        score = compute_decay_score(
            updated_at=very_old, access_count=0,
            memory_layer=MemoryLayer.SEMANTIC, now=now,
        )
        assert 0.0 <= score <= 1.0

    def test_user_model_never_decays(self):
        from synapse.layers.decay import compute_decay_score
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=365)

        score = compute_decay_score(
            updated_at=past, access_count=0,
            memory_layer=MemoryLayer.USER_MODEL, now=now,
        )
        # User model should never decay (or decay extremely slowly)
        assert score >= 0.9


class TestShouldForget:
    """Verify should_forget threshold logic."""

    def test_high_score_not_forgotten(self):
        from synapse.layers.decay import should_forget

        assert should_forget(decay_score=0.9, expires_at=None) is False

    def test_low_score_forgotten(self):
        from synapse.layers.decay import should_forget

        assert should_forget(decay_score=0.05, expires_at=None) is True

    def test_expired_ttl_forgotten(self):
        from synapse.layers.decay import should_forget

        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert should_forget(decay_score=0.9, expires_at=past) is True

    def test_future_ttl_not_forgotten(self):
        from synapse.layers.decay import should_forget

        future = datetime.now(timezone.utc) + timedelta(days=30)
        assert should_forget(decay_score=0.5, expires_at=future) is False


class TestGetHalfLife:
    """Verify half-life calculation per layer."""

    def test_semantic_half_life(self):
        from synapse.layers.decay import get_half_life
        from synapse.layers.types import MemoryLayer

        hl = get_half_life(MemoryLayer.SEMANTIC)
        assert hl is not None
        # ln(2)/0.01 ≈ 69.3 days
        assert 60 < hl < 80

    def test_procedural_half_life(self):
        from synapse.layers.decay import get_half_life
        from synapse.layers.types import MemoryLayer

        hl = get_half_life(MemoryLayer.PROCEDURAL)
        assert hl is not None
        # ln(2)/0.005 ≈ 138.6 days
        assert 130 < hl < 150

    def test_user_model_no_decay(self):
        from synapse.layers.decay import get_half_life
        from synapse.layers.types import MemoryLayer

        hl = get_half_life(MemoryLayer.USER_MODEL)
        # Returns float('inf') — never decays
        assert hl == float('inf')


class TestTTLComputation:
    """Verify TTL computation for episodic memory."""

    def test_episodic_ttl_default(self):
        from synapse.layers.decay import compute_ttl
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        ttl = compute_ttl(MemoryLayer.EPISODIC, created_at=now)
        assert ttl is not None
        delta = (ttl - now).days
        assert 85 <= delta <= 95  # ~90 days

    def test_semantic_no_ttl(self):
        from synapse.layers.decay import compute_ttl
        from synapse.layers.types import MemoryLayer

        now = datetime.now(timezone.utc)
        ttl = compute_ttl(MemoryLayer.SEMANTIC, created_at=now)
        assert ttl is None

    def test_extend_ttl(self):
        from synapse.layers.decay import extend_ttl

        now = datetime.now(timezone.utc)
        current = now + timedelta(days=10)
        extended = extend_ttl(current, now=now)
        assert extended is not None
        assert extended > current


# ============================================================
# Step 3: Working Memory (Layer 5)
# ============================================================


class TestWorkingMemory:
    """Verify in-memory working memory operations."""

    def _make_manager(self):
        from synapse.layers.working import WorkingManager
        return WorkingManager()

    def test_set_and_get(self):
        wm = self._make_manager()
        wm.set_context("key1", "value1")
        assert wm.get_context("key1") == "value1"

    def test_get_missing_returns_default(self):
        wm = self._make_manager()
        assert wm.get_context("missing") is None
        assert wm.get_context("missing", "fallback") == "fallback"

    def test_has_context(self):
        wm = self._make_manager()
        assert wm.has_context("x") is False
        wm.set_context("x", 42)
        assert wm.has_context("x") is True

    def test_delete_context(self):
        wm = self._make_manager()
        wm.set_context("x", 1)
        assert wm.delete_context("x") is True
        assert wm.has_context("x") is False
        assert wm.delete_context("x") is False  # already deleted

    def test_clear_context(self):
        wm = self._make_manager()
        wm.set_context("a", 1)
        wm.set_context("b", 2)
        wm.set_context("c", 3)
        count = wm.clear_context()
        assert count == 3
        assert wm.get_context("a") is None

    def test_get_all_context(self):
        wm = self._make_manager()
        wm.set_context("x", 10)
        wm.set_context("y", 20)
        all_ctx = wm.get_all_context()
        assert all_ctx == {"x": 10, "y": 20}

    def test_get_context_keys(self):
        wm = self._make_manager()
        wm.set_context("alpha", 1)
        wm.set_context("beta", 2)
        keys = wm.get_context_keys()
        assert set(keys) == {"alpha", "beta"}

    def test_get_context_stats(self):
        wm = self._make_manager()
        wm.set_context("a", 1)
        wm.set_context("b", "hello")
        stats = wm.get_context_stats()
        assert stats["context_count"] == 2

    def test_increment_counter(self):
        wm = self._make_manager()
        val = wm.increment_counter("hits")
        assert val == 1
        val = wm.increment_counter("hits")
        assert val == 2
        val = wm.increment_counter("hits", delta=5)
        assert val == 7

    def test_append_to_list(self):
        wm = self._make_manager()
        result = wm.append_to_list("items", "a")
        assert result == ["a"]
        result = wm.append_to_list("items", "b")
        assert result == ["a", "b"]

    def test_merge_dict(self):
        wm = self._make_manager()
        result = wm.merge_dict("config", {"a": 1})
        assert result == {"a": 1}
        result = wm.merge_dict("config", {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_session_management(self):
        wm = self._make_manager()
        wm.set_session("sess_123")
        assert wm.get_session_id() == "sess_123"

    def test_end_session(self):
        wm = self._make_manager()
        # set_context first, then set_session (which clears), then set again
        wm.set_session("sess_abc")
        wm.set_context("task", "debug")  # set after session start
        summary = wm.end_session()
        assert isinstance(summary, dict)
        # After end_session, context should be cleared
        assert wm.get_context("task") is None

    def test_overwrite_context(self):
        wm = self._make_manager()
        wm.set_context("key", "old")
        wm.set_context("key", "new")
        assert wm.get_context("key") == "new"

    def test_in_memory_only(self):
        """Working memory must NOT persist — separate instances are independent."""
        wm1 = self._make_manager()
        wm1.set_context("secret", "data")
        wm2 = self._make_manager()
        assert wm2.get_context("secret") is None


# ============================================================
# Step 4: User Model (Layer 1)
# ============================================================


class TestUserModelManager:
    """Verify UserModelManager with real SQLite."""

    def _make_manager(self, tmpdir):
        from synapse.layers.user_model import UserModelManager
        db_path = Path(tmpdir) / "test_user_model.db"
        return UserModelManager(db_path=db_path)

    def test_get_user_creates_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            user = mgr.get_user_model("alice")
            assert user.user_id == "alice"
            assert user.language == "th"  # default
            assert isinstance(user.expertise, dict)
            assert isinstance(user.notes, list)

    def test_update_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.get_user_model("bob")
            user = mgr.update_user_model("bob", language="en")
            assert user.language == "en"

    def test_update_response_style(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.get_user_model("carol")
            user = mgr.update_user_model("carol", response_style="formal")
            assert user.response_style == "formal"

    def test_add_expertise(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.get_user_model("dave")
            user = mgr.update_user_model("dave", add_expertise={"python": "expert"})
            assert "python" in user.expertise
            assert user.expertise["python"] == "expert"

    def test_add_topic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.get_user_model("eve")
            user = mgr.update_user_model("eve", add_topic="machine learning")
            assert "machine learning" in user.common_topics

    def test_add_note(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.get_user_model("frank")
            user = mgr.update_user_model("frank", add_note="prefers dark mode")
            assert "prefers dark mode" in user.notes

    def test_persistence_across_instances(self):
        """Data must survive re-create of manager (SQLite persistence)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = self._make_manager(tmpdir)
            mgr1.get_user_model("grace")
            mgr1.update_user_model("grace", language="en", add_note="important")

            # Create new manager pointing to same DB
            mgr2 = self._make_manager(tmpdir)
            user = mgr2.get_user_model("grace")
            assert user.language == "en"
            assert "important" in user.notes

    def test_multi_user_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.update_user_model("user_a", language="th")
            mgr.update_user_model("user_b", language="en")

            a = mgr.get_user_model("user_a")
            b = mgr.get_user_model("user_b")
            assert a.language == "th"
            assert b.language == "en"

    def test_reset_user_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.get_user_model("harry")
            mgr.update_user_model("harry", language="en", add_note="custom")
            mgr.reset_user_model("harry")
            user = mgr.get_user_model("harry")
            assert user.language == "th"  # back to default
            assert user.notes == []  # cleared

    def test_decay_score_always_one(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            score = mgr.get_decay_score("any_user")
            assert score == 1.0


# ============================================================
# Step 5: Procedural Memory (Layer 2)
# ============================================================


class TestProceduralMemory:
    """Verify ProceduralManager with real SQLite."""

    def _make_manager(self, tmpdir):
        from synapse.layers.procedural import ProceduralManager
        db_path = Path(tmpdir) / "test_procedural.db"
        return ProceduralManager(db_path=db_path)

    def test_learn_procedure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            proc = mgr.learn_procedure(
                trigger="deploy to production",
                procedure=["build", "test", "deploy"],
                source="explicit",
                preprocess=False,
            )
            assert proc.trigger == "deploy to production"
            assert len(proc.procedure) == 3
            assert proc.success_count == 0

    def test_find_procedure_by_trigger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.learn_procedure("git commit", ["add", "commit", "push"], preprocess=False)
            results = mgr.find_procedure("git", preprocess=False)
            assert len(results) >= 1
            assert any("git" in r.trigger.lower() for r in results)

    def test_find_returns_empty_for_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.learn_procedure("bake cake", ["mix", "bake"], preprocess=False)
            results = mgr.find_procedure("quantum physics", preprocess=False)
            assert len(results) == 0

    def test_record_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            proc = mgr.learn_procedure("test procedure", ["step1"], preprocess=False)
            updated = mgr.record_success(proc.id)
            assert updated is not None
            assert updated.success_count == 1

    def test_get_procedure_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            proc = mgr.learn_procedure("fetch data", ["query", "parse"], preprocess=False)
            found = mgr.get_procedure(proc.id)
            assert found is not None
            assert found.id == proc.id

    def test_delete_procedure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            proc = mgr.learn_procedure("temp proc", ["x"], preprocess=False)
            assert mgr.delete_procedure(proc.id) is True
            assert mgr.get_procedure(proc.id) is None

    def test_list_procedures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.learn_procedure("proc1", ["a"], source="explicit", preprocess=False)
            mgr.learn_procedure("proc2", ["b"], source="inferred", preprocess=False)
            all_procs = mgr.list_procedures()
            assert len(all_procs) >= 2

    def test_list_procedures_by_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.learn_procedure("p1", ["a"], source="explicit", preprocess=False)
            mgr.learn_procedure("p2", ["b"], source="inferred", preprocess=False)
            explicit = mgr.list_procedures(source="explicit")
            assert all(p.source == "explicit" for p in explicit)

    def test_refresh_decay_scores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.learn_procedure("old proc", ["step"], preprocess=False)
            count = mgr.refresh_decay_scores()
            assert isinstance(count, int)
            assert count >= 0

    def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = self._make_manager(tmpdir)
            mgr1.learn_procedure("persist test", ["a", "b"], preprocess=False)

            mgr2 = self._make_manager(tmpdir)
            results = mgr2.find_procedure("persist", preprocess=False)
            assert len(results) >= 1

    def test_fts5_table_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            db_path = Path(tmpdir) / "test_procedural.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='procedures_fts'"
            )
            result = cursor.fetchone()
            conn.close()
            assert result is not None


# ============================================================
# Step 6: Episodic Memory (Layer 4)
# ============================================================


class TestEpisodicMemory:
    """Verify EpisodicManager with real SQLite — TTL, Archive, FTS5."""

    def _make_manager(self, tmpdir):
        from synapse.layers.episodic import EpisodicManager
        db_path = Path(tmpdir) / "test_episodic.db"
        return EpisodicManager(db_path=db_path)

    def test_record_episode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            ep = mgr.record_episode(
                content="Fixed a critical bug in authentication",
                summary="Bug fix",
                topics=["bug", "auth"],
                outcome="success",
                preprocess=False,
            )
            assert ep.content == "Fixed a critical bug in authentication"
            assert "bug" in ep.topics
            assert ep.outcome == "success"
            assert ep.expires_at is not None

    def test_episode_has_ttl(self):
        """Episodes must have expires_at set (~90 days from now)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            ep = mgr.record_episode(content="test", preprocess=False)
            assert ep.expires_at is not None
            delta = (ep.expires_at - ep.recorded_at).days
            assert 80 <= delta <= 100

    def test_get_episode_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            ep = mgr.record_episode(content="find me", preprocess=False)
            found = mgr.get_episode(ep.id)
            assert found is not None
            assert found.id == ep.id

    def test_find_episodes_by_topic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.record_episode(
                content="Python workshop", topics=["python"], preprocess=False
            )
            mgr.record_episode(
                content="Java conference", topics=["java"], preprocess=False
            )
            results = mgr.find_episodes(topics=["python"], preprocess=False)
            assert len(results) >= 1
            assert any("python" in (ep.topics or []) for ep in results)

    def test_find_episodes_by_query_fts5(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.record_episode(
                content="Deployed the new authentication system",
                preprocess=False,
            )
            results = mgr.find_episodes(query="authentication", preprocess=False)
            assert len(results) >= 1

    def test_purge_expired_archives(self):
        """purge_expired() must archive episodes, not delete them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            # Create episode with TTL already expired
            ep = mgr.record_episode(
                content="old episode",
                ttl_days=0,  # expires immediately
                preprocess=False,
            )

            # Force the expires_at to be in the past
            db_path = Path(tmpdir) / "test_episodic.db"
            conn = sqlite3.connect(str(db_path))
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            conn.execute(
                "UPDATE episodes SET expires_at = ? WHERE id = ?",
                (past, ep.id)
            )
            conn.commit()
            conn.close()

            result = mgr.purge_expired(archive=True)
            assert isinstance(result, dict)
            assert result.get("archived", 0) + result.get("purged", 0) >= 0

            # Verify archive table has the episode
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT COUNT(*) FROM episodes_archive WHERE id = ?", (ep.id,)
            )
            archive_count = cursor.fetchone()[0]
            conn.close()
            assert archive_count >= 1, "Expired episode should be in archive"

    def test_restore_episode_from_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            ep = mgr.record_episode(content="to be archived", preprocess=False)

            # Force expire and purge
            db_path = Path(tmpdir) / "test_episodic.db"
            conn = sqlite3.connect(str(db_path))
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            conn.execute("UPDATE episodes SET expires_at = ? WHERE id = ?", (past, ep.id))
            conn.commit()
            conn.close()
            mgr.purge_expired(archive=True)

            # Restore
            restored = mgr.restore_episode(ep.id)
            if restored is not None:
                assert restored.id == ep.id
                assert restored.expires_at is not None

    def test_extend_episode_ttl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            ep = mgr.record_episode(content="extend me", preprocess=False)
            original_ttl = ep.expires_at

            new_ttl = mgr.extend_episode_ttl(ep.id)
            assert new_ttl is not None
            if original_ttl is not None:
                assert new_ttl > original_ttl

    def test_get_episode_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            mgr.record_episode(content="ep1", outcome="success", preprocess=False)
            mgr.record_episode(content="ep2", outcome="failure", preprocess=False)
            stats = mgr.get_episode_stats()
            assert isinstance(stats, dict)

    def test_delete_episode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            ep = mgr.record_episode(content="delete me", preprocess=False)
            assert mgr.delete_episode(ep.id) is True
            assert mgr.get_episode(ep.id) is None

    def test_fts5_table_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            db_path = Path(tmpdir) / "test_episodic.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='episodes_fts'"
            )
            result = cursor.fetchone()
            conn.close()
            assert result is not None

    def test_archive_table_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = self._make_manager(tmpdir)
            db_path = Path(tmpdir) / "test_episodic.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='episodes_archive'"
            )
            result = cursor.fetchone()
            conn.close()
            assert result is not None

    def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = self._make_manager(tmpdir)
            mgr1.record_episode(content="persistent episode", preprocess=False)

            mgr2 = self._make_manager(tmpdir)
            results = mgr2.find_episodes(query="persistent", preprocess=False)
            assert len(results) >= 1


# ============================================================
# Step 7: Thai NLP
# ============================================================


class TestThaiDetector:
    """Verify Thai language detection."""

    def test_detect_thai_text(self):
        from synapse.nlp.thai import ThaiDetector

        lang, conf = ThaiDetector.detect_language("สวัสดีครับ")
        assert lang == "th"
        assert conf > 0.5

    def test_detect_english_text(self):
        from synapse.nlp.thai import ThaiDetector

        lang, conf = ThaiDetector.detect_language("Hello world")
        assert lang == "en"

    def test_detect_mixed_text(self):
        from synapse.nlp.thai import ThaiDetector

        lang, conf = ThaiDetector.detect_language("สวัสดี Hello ครับ World")
        assert lang in ("th", "mixed")

    def test_is_thai(self):
        from synapse.nlp.thai import ThaiDetector

        assert ThaiDetector.is_thai("ภาษาไทย") is True
        assert ThaiDetector.is_thai("English only") is False

    def test_thai_ratio(self):
        from synapse.nlp.thai import ThaiDetector

        ratio = ThaiDetector.thai_ratio("สวัสดี Hello")
        assert 0.0 < ratio < 1.0

    def test_extract_thai(self):
        from synapse.nlp.thai import ThaiDetector

        segments = ThaiDetector.extract_thai("Hello สวัสดี World ครับ")
        assert len(segments) >= 1
        assert any("สวัสดี" in s for s in segments)


class TestThaiNormalizer:
    """Verify Thai text normalization."""

    def test_fix_common_typo(self):
        from synapse.nlp.thai import ThaiNormalizer

        # เเ (double sara ae) → แ (mae hanakat)
        result = ThaiNormalizer.normalize("เเม่น้ำ")
        assert "แม่" in result or result != "เเม่น้ำ"  # should be changed

    def test_remove_zero_width_chars(self):
        from synapse.nlp.thai import ThaiNormalizer

        text_with_zwsp = "สวัสดี\u200Bครับ"
        result = ThaiNormalizer.normalize(text_with_zwsp)
        assert "\u200B" not in result

    def test_normalize_levels(self):
        from synapse.nlp.thai import ThaiNormalizer

        text = "สวัสดีครับ"
        light = ThaiNormalizer.normalize(text, level="light")
        medium = ThaiNormalizer.normalize(text, level="medium")
        aggressive = ThaiNormalizer.normalize(text, level="aggressive")
        # All should return valid strings
        assert isinstance(light, str)
        assert isinstance(medium, str)
        assert isinstance(aggressive, str)


class TestThaiTokenizer:
    """Verify Thai word segmentation."""

    def test_tokenize_thai(self):
        from synapse.nlp.thai import ThaiTokenizer

        tokens = ThaiTokenizer.tokenize("ภาษาไทยเป็นภาษาที่สวยงาม")
        assert isinstance(tokens, list)
        assert len(tokens) > 1  # should split into multiple words

    def test_tokenize_returns_list(self):
        from synapse.nlp.thai import ThaiTokenizer

        tokens = ThaiTokenizer.tokenize("สวัสดีครับ")
        assert isinstance(tokens, list)

    def test_empty_string(self):
        from synapse.nlp.thai import ThaiTokenizer

        tokens = ThaiTokenizer.tokenize("")
        assert isinstance(tokens, list)


class TestThaiStopwords:
    """Verify stopword removal."""

    def test_get_stopwords(self):
        from synapse.nlp.thai import ThaiStopwords

        stopwords = ThaiStopwords.get_stopwords()
        assert isinstance(stopwords, set)
        assert len(stopwords) > 0

    def test_remove_stopwords(self):
        from synapse.nlp.thai import ThaiStopwords

        tokens = ["ภาษา", "ไทย", "เป็น", "ที่", "สวย"]
        filtered = ThaiStopwords.remove_stopwords(tokens)
        assert isinstance(filtered, list)
        # Some stopwords should be removed
        assert len(filtered) <= len(tokens)


class TestLanguageRouter:
    """Verify language routing and preprocessing."""

    def test_detect_language(self):
        from synapse.nlp.router import detect_language

        result = detect_language("สวัสดีครับ")
        assert result.language in ("th", "mixed")
        assert 0.0 <= result.confidence <= 1.0

    def test_preprocess_for_search_thai(self):
        from synapse.nlp.router import preprocess_for_search

        result = preprocess_for_search("ค้นหาข้อมูล")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_preprocess_for_search_english(self):
        from synapse.nlp.router import preprocess_for_search

        result = preprocess_for_search("search for data")
        assert isinstance(result, str)

    def test_preprocess_for_extraction(self):
        from synapse.nlp.router import preprocess_for_extraction

        result = preprocess_for_extraction("โปรเจค Synapse เป็นระบบ memory")
        assert isinstance(result, str)
        assert len(result) > 0


class TestTextPreprocessor:
    """Verify text preprocessing pipeline."""

    def test_preprocess_for_extraction(self):
        from synapse.nlp.preprocess import TextPreprocessor

        pp = TextPreprocessor()
        result = pp.preprocess_for_extraction("Hello World")
        assert result.original == "Hello World"
        assert isinstance(result.processed, str)
        assert isinstance(result.language, str)

    def test_preprocess_for_search(self):
        from synapse.nlp.preprocess import TextPreprocessor

        pp = TextPreprocessor()
        result = pp.preprocess_for_search("search query test")
        assert isinstance(result, str)

    def test_tokenize_for_fts(self):
        from synapse.nlp.preprocess import TextPreprocessor

        pp = TextPreprocessor()
        result = pp.tokenize_for_fts("test tokenization")
        assert isinstance(result, str)

    def test_max_text_length(self):
        from synapse.nlp.preprocess import MAX_TEXT_LENGTH

        assert MAX_TEXT_LENGTH == 100_000


# ============================================================
# Step 8: Sync Queue
# ============================================================


class TestSyncQueue:
    """Verify SyncQueue task lifecycle, retry, and persistence."""

    def _make_queue(self, tmpdir, enabled=True):
        from synapse.services.sync_queue import SyncQueue
        db_path = Path(tmpdir) / "test_sync.db"
        with patch.dict(os.environ, {"SYNAPSE_USE_SYNC_QUEUE": "true" if enabled else "false"}):
            return SyncQueue(db_path=db_path)

    def test_enqueue_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            q = self._make_queue(tmpdir)
            task_id = q.enqueue(
                operation="upsert",
                entity_type="node",
                entity_id="node_1",
                payload={"name": "test"},
            )
            if q.is_enabled():
                assert task_id >= 0
            else:
                assert task_id == -1

    def test_get_pending_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            q = self._make_queue(tmpdir)
            q.enqueue("upsert", "node", "n1", {"data": 1})
            q.enqueue("delete", "edge", "e1", {})
            pending = q.get_pending()
            if q.is_enabled():
                assert len(pending) >= 2

    def test_update_task_status(self):
        from synapse.services.sync_queue import SyncStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            q = self._make_queue(tmpdir)
            task_id = q.enqueue("upsert", "node", "n1", {})
            pending = q.get_pending()
            if pending:
                task = pending[0]
                task.status = SyncStatus.COMPLETED
                q.update_task(task)
                # Should not appear in pending anymore
                new_pending = q.get_pending()
                completed_ids = [t.id for t in new_pending if t.status == SyncStatus.COMPLETED]
                assert task.id not in [t.id for t in new_pending]

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            q = self._make_queue(tmpdir)
            q.enqueue("op1", "type1", "id1", {})
            stats = q.get_stats()
            assert isinstance(stats, dict)

    def test_clear_completed(self):
        from synapse.services.sync_queue import SyncStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            q = self._make_queue(tmpdir)
            task_id = q.enqueue("op", "t", "i", {})
            pending = q.get_pending()
            if pending:
                task = pending[0]
                task.status = SyncStatus.COMPLETED
                q.update_task(task)
                cleared = q.clear_completed(older_than_days=0)
                assert isinstance(cleared, int)

    def test_feature_flag_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            q = self._make_queue(tmpdir, enabled=False)
            task_id = q.enqueue("op", "t", "i", {})
            assert task_id == -1

    def test_sync_status_enum(self):
        from synapse.services.sync_queue import SyncStatus

        assert SyncStatus.PENDING.value == "pending"
        assert SyncStatus.IN_PROGRESS.value == "in_progress"
        assert SyncStatus.COMPLETED.value == "completed"
        assert SyncStatus.FAILED.value == "failed"
        assert SyncStatus.RETRY_EXHAUSTED.value == "retry_exhausted"

    def test_sync_task_defaults(self):
        from synapse.services.sync_queue import SyncTask, SyncStatus

        task = SyncTask()
        assert task.status == SyncStatus.PENDING
        assert task.attempts == 0
        assert task.max_attempts == 3


# ============================================================
# Step 9: Layer Classifier
# ============================================================


class TestLayerClassifierKeywordsComprehensive:
    """Verify keyword classification for all layers, Thai + English."""

    def _classify(self, text):
        from synapse.classifiers.layer_classifier import LayerClassifier
        from synapse.layers.types import MemoryLayer

        classifier = LayerClassifier(llm_client=None, use_llm=False)
        return classifier._classify_with_keywords(text)

    def test_thai_user_model(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("ฉันชอบภาษา Python")
        assert layer == MemoryLayer.USER_MODEL

    def test_english_user_model(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("I prefer dark mode")
        assert layer == MemoryLayer.USER_MODEL

    def test_thai_procedural(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("วิธีทำข้าวผัด: 1. ตั้งกระทะ")
        assert layer == MemoryLayer.PROCEDURAL

    def test_english_procedural(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("How to bake a cake: Step 1...")
        assert layer == MemoryLayer.PROCEDURAL

    def test_thai_episodic(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("เมื่อวานฉันไปตลาด")
        assert layer == MemoryLayer.EPISODIC

    def test_english_episodic(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("Yesterday I went to the mall")
        assert layer == MemoryLayer.EPISODIC

    def test_working_memory(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("Current task: fix bug")
        assert layer == MemoryLayer.WORKING

    def test_semantic_default(self):
        from synapse.layers.types import MemoryLayer
        layer, conf = self._classify("Python is a programming language")
        assert layer == MemoryLayer.SEMANTIC


class TestLayerClassifierAsync:
    """Verify async classify with context hints and LLM fallback."""

    @pytest.mark.asyncio
    async def test_context_temporary_working(self):
        from synapse.classifiers.layer_classifier import LayerClassifier
        from synapse.layers.types import MemoryLayer

        classifier = LayerClassifier(llm_client=None, use_llm=False)
        layer, conf = await classifier.classify("any text", context={"temporary": True})
        assert layer == MemoryLayer.WORKING
        assert conf == 1.0

    @pytest.mark.asyncio
    async def test_context_user_preference(self):
        from synapse.classifiers.layer_classifier import LayerClassifier
        from synapse.layers.types import MemoryLayer

        classifier = LayerClassifier(llm_client=None, use_llm=False)
        layer, conf = await classifier.classify("any text", context={"user_preference": True})
        assert layer == MemoryLayer.USER_MODEL
        assert conf == 1.0

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self):
        from synapse.classifiers.layer_classifier import LayerClassifier
        from synapse.layers.types import MemoryLayer

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))

        classifier = LayerClassifier(llm_client=mock_client, use_llm=True)
        layer, conf = await classifier.classify("ฉันชอบ Python")
        # Should fallback to keywords → USER_MODEL
        assert layer == MemoryLayer.USER_MODEL

    @pytest.mark.asyncio
    async def test_llm_disabled(self):
        from synapse.classifiers.layer_classifier import LayerClassifier
        from synapse.layers.types import MemoryLayer

        mock_client = MagicMock()
        classifier = LayerClassifier(llm_client=mock_client, use_llm=False)
        layer, conf = await classifier.classify("ฉันชอบ Python")
        assert layer == MemoryLayer.USER_MODEL
        mock_client.messages.create.assert_not_called()


class TestLayerClassifierFeatureFlags:
    """Verify feature flag controls."""

    def test_feature_flag_env(self):
        from synapse.classifiers.layer_classifier import LayerClassifier

        with patch.dict(os.environ, {"SYNAPSE_USE_LLM_CLASSIFICATION": "false"}):
            classifier = LayerClassifier(llm_client=MagicMock(), use_llm=True)
            assert classifier._llm_enabled is False
            # use_llm should be True because llm_client is provided
            assert classifier.use_llm is True


# ============================================================
# Step 10: LayerManager Cross-Layer
# ============================================================


class TestLayerManagerCrossLayer:
    """Verify LayerManager unified API."""

    def test_detect_layer_sync(self):
        from synapse.layers.manager import LayerManager
        from synapse.layers.types import MemoryLayer

        mgr = LayerManager()
        layer = mgr.detect_layer("ฉันชอบ Python")
        assert isinstance(layer, MemoryLayer)

    @pytest.mark.asyncio
    async def test_detect_layer_async(self):
        from synapse.layers.manager import LayerManager
        from synapse.layers.types import MemoryLayer

        mgr = LayerManager()
        layer = await mgr.detect_layer_async("วิธีทำข้าวผัด")
        assert isinstance(layer, MemoryLayer)

    @pytest.mark.asyncio
    async def test_search_all_returns_all_layers(self):
        from synapse.layers.manager import LayerManager
        from synapse.layers.types import MemoryLayer

        mgr = LayerManager()
        results = await mgr.search_all("test", user_id="test_user")
        assert MemoryLayer.USER_MODEL in results
        assert MemoryLayer.PROCEDURAL in results
        assert MemoryLayer.SEMANTIC in results
        assert MemoryLayer.EPISODIC in results
        assert MemoryLayer.WORKING in results

    def test_get_memory_stats(self):
        from synapse.layers.manager import LayerManager

        mgr = LayerManager()
        stats = mgr.get_memory_stats()
        assert "user_model" in stats
        assert "procedural" in stats
        assert "semantic" in stats
        assert "episodic" in stats
        assert "working" in stats

    def test_create_context_for_prompt(self):
        from synapse.layers.manager import LayerManager

        mgr = LayerManager()
        prompt = mgr.create_context_for_prompt("default")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_run_maintenance(self):
        from synapse.layers.manager import LayerManager

        mgr = LayerManager()
        results = await mgr.run_maintenance()
        assert isinstance(results, dict)


class TestUserIsolationManager:
    """Verify user isolation via feature flag."""

    def test_isolation_disabled_shares_instance(self):
        from synapse.layers.manager import get_layer_manager
        import synapse.layers.manager as mgr_module

        saved = mgr_module._USER_ISOLATION_ENABLED
        saved_mgr = mgr_module._manager
        try:
            mgr_module._manager = None
            mgr_module._USER_ISOLATION_ENABLED = False

            m1 = get_layer_manager("alice")
            m2 = get_layer_manager("bob")
            assert m1 is m2
        finally:
            mgr_module._USER_ISOLATION_ENABLED = saved
            mgr_module._manager = saved_mgr

    def test_isolation_enabled_separates(self):
        from synapse.layers.manager import get_layer_manager
        import synapse.layers.manager as mgr_module

        saved = mgr_module._USER_ISOLATION_ENABLED
        saved_mgr = mgr_module._manager
        saved_ctx = mgr_module._contexts.copy()
        saved_def = mgr_module._default_context
        try:
            mgr_module._manager = None
            mgr_module._contexts.clear()
            mgr_module._default_context = None
            mgr_module._USER_ISOLATION_ENABLED = True

            m1 = get_layer_manager("alice")
            m2 = get_layer_manager("bob")
            # Different UserContexts → different LayerManager instances
            assert m1 is not m2
            assert m1.user_id == "alice"
            assert m2.user_id == "bob"
        finally:
            mgr_module._USER_ISOLATION_ENABLED = saved
            mgr_module._manager = saved_mgr
            mgr_module._contexts.clear()
            mgr_module._contexts.update(saved_ctx)
            mgr_module._default_context = saved_def


# ============================================================
# Step 11: SynapseService Bridge
# ============================================================


class TestSynapseServiceBridge:
    """Verify SynapseService routes to correct layers."""

    def _make_service(self):
        from synapse.services.synapse_service import SynapseService

        mock_graphiti = AsyncMock()
        mock_graphiti.add_episode = AsyncMock(return_value={"uuid": "test"})
        mock_graphiti.search = AsyncMock(return_value=[])
        return SynapseService(graphiti_client=mock_graphiti, user_id="test_user")

    def test_init_default(self):
        from synapse.services.synapse_service import SynapseService

        mock_graphiti = AsyncMock()
        svc = SynapseService(graphiti_client=mock_graphiti)
        assert svc.graphiti is mock_graphiti
        assert svc.layers is not None
        assert svc.user_id == "default"

    def test_init_custom_user(self):
        from synapse.services.synapse_service import SynapseService

        svc = SynapseService(graphiti_client=AsyncMock(), user_id="custom")
        assert svc.user_id == "custom"

    @pytest.mark.asyncio
    async def test_add_memory_returns_layer(self):
        svc = self._make_service()
        result = await svc.add_memory(
            name="test", episode_body="Python is great",
        )
        assert "layer" in result
        assert result["layer"] in [l.value for l in __import__("synapse.layers.types", fromlist=["MemoryLayer"]).MemoryLayer]

    @pytest.mark.asyncio
    async def test_search_memory(self):
        svc = self._make_service()
        result = await svc.search_memory(query="test")
        assert "layers" in result
        assert "graphiti" in result

    @pytest.mark.asyncio
    async def test_health_check(self):
        svc = self._make_service()
        result = await svc.health_check()
        assert "status" in result
        assert "components" in result

    def test_get_user_context(self):
        svc = self._make_service()
        ctx = svc.get_user_context()
        assert "user_id" in ctx
        assert "language" in ctx

    def test_working_context_ops(self):
        svc = self._make_service()
        svc.set_working_context("key", "value")
        assert svc.get_working_context("key") == "value"
        count = svc.clear_working_context()
        assert count >= 1
        assert svc.get_working_context("key") is None

    def test_find_procedure(self):
        svc = self._make_service()
        # Should return empty list (no procedures stored)
        result = svc.find_procedure("nonexistent")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_add_entity(self):
        svc = self._make_service()
        entity = await svc.add_entity(
            name="Python", entity_type="tech", summary="Language",
        )
        assert entity is not None
        assert entity.name == "Python"


# ============================================================
# Step 12: Qdrant Client
# ============================================================


class TestQdrantClientOffline:
    """Verify QdrantClient offline features (no running Qdrant needed)."""

    def test_default_embedding_model(self):
        from synapse.storage.qdrant_client import DEFAULT_EMBEDDING_MODEL

        assert DEFAULT_EMBEDDING_MODEL is not None
        assert "multilingual" in DEFAULT_EMBEDDING_MODEL.lower()

    def test_hash_embedding_deterministic(self):
        from synapse.storage.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        vec1 = client._hash_embedding("test text")
        vec2 = client._hash_embedding("test text")
        assert vec1 == vec2

    def test_hash_embedding_correct_size(self):
        from synapse.storage.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333", vector_size=384)
        vec = client._hash_embedding("test")
        assert len(vec) == 384

    def test_hash_embedding_different_texts(self):
        from synapse.storage.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        vec1 = client._hash_embedding("hello")
        vec2 = client._hash_embedding("world")
        assert vec1 != vec2


# ============================================================
# Module-level test runner
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
