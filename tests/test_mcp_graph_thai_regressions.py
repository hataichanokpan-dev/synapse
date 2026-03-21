from types import SimpleNamespace

import pytest

from synapse.layers import MemoryLayer
from synapse.nlp.preprocess import TextPreprocessor
from synapse.nlp.thai import ThaiSpellChecker
from synapse.services import SynapseService
from synapse.storage.qdrant_client import QdrantClient


def test_preprocess_for_extraction_can_disable_spellcheck(monkeypatch):
    def fake_correct(cls, text: str) -> str:
        return text.replace("โบ๊ท", "บท")

    monkeypatch.setattr(ThaiSpellChecker, "correct", classmethod(fake_correct))

    preprocessor = TextPreprocessor()
    original = 'ผู้ใช้งานชื่อ "โบ๊ท" Both ชอบทีมฟุตบอล "แมนยู"'

    default_result = preprocessor.preprocess_for_extraction(original)
    preserved_result = preprocessor.preprocess_for_extraction(original, spellcheck=False)

    assert "บท" in default_result.processed
    assert "โบ๊ท" in preserved_result.processed
    assert preserved_result.was_spellchecked is False


def test_qdrant_index_preprocessing_disables_spellcheck():
    spellcheck_args: list[bool | None] = []

    class StubPreprocessor:
        def preprocess_for_extraction(self, text: str, aggressive: bool = False, spellcheck=None):
            spellcheck_args.append(spellcheck)
            return SimpleNamespace(processed=text)

        def tokenize_for_fts(self, text: str) -> str:
            return text

    client = QdrantClient()
    client._preprocessor = StubPreprocessor()

    processed = client._preprocess_for_index('ผู้ใช้งานชื่อ "โบ๊ท" Both')

    assert spellcheck_args == [False]
    assert "โบ๊ท" in processed


class _FakeGraphiti:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def add_episode(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok"}


@pytest.mark.asyncio
async def test_synapse_service_add_memory_can_skip_graphiti_write():
    fake_graphiti = _FakeGraphiti()
    service = SynapseService(graphiti_client=fake_graphiti, user_id="test-user")

    await service.add_memory(
        name="user-note",
        episode_body="prefers concise replies",
        layer=MemoryLayer.USER_MODEL,
        persist_graphiti=False,
    )

    assert fake_graphiti.calls == []


@pytest.mark.asyncio
async def test_synapse_service_add_memory_can_still_write_graphiti_when_enabled():
    fake_graphiti = _FakeGraphiti()
    service = SynapseService(graphiti_client=fake_graphiti, user_id="test-user")

    await service.add_memory(
        name="user-note",
        episode_body="prefers concise replies",
        layer=MemoryLayer.USER_MODEL,
        persist_graphiti=True,
    )

    assert len(fake_graphiti.calls) == 1
