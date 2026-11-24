"""Freezes the legacy response format of /generate-topic-tree. Any change here breaks existing consumers."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.legacy import router as legacy
from app.main import app


def _completion(payload: object) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])


class ScriptedAsyncOpenAI:
    """Answers the legacy prompts level by level: main topics (dict), then subtopics and curriculum topics (lists)."""

    def __init__(self, **_: object) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, *, messages: list[dict], **_: object) -> SimpleNamespace:
        prompt = messages[-1]["content"]
        if "Hauptthemen und Details" in prompt:
            return _completion(
                {
                    "description": "Physik gesamt",
                    "collections": [
                        {"title": "Mechanik", "shorttitle": "Mech", "description": "M", "keywords": ["Kraft"]}
                    ],
                }
            )
        if "Lehrplanthemen" in prompt:
            return _completion([{"title": "Bewegung", "shorttitle": "Bew", "description": "B", "keywords": []}])
        return _completion([{"title": "Kinematik", "shorttitle": "Kin", "description": "K", "keywords": ["Weg"]}])


def test_legacy_topic_tree_response_shape_is_frozen() -> None:
    with patch.object(legacy, "AsyncOpenAI", ScriptedAsyncOpenAI):
        response = TestClient(app).post(
            "/generate-topic-tree",
            json={
                "theme": "Physik",
                "num_main_topics": 1,
                "num_subtopics": 1,
                "num_curriculum_topics": 1,
                "discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
            },
            headers={"Authorization": "Bearer caller-key"},
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"metadata", "collection"}
    assert set(body["metadata"]) == {"title", "description", "target_audience", "created_at", "version", "author"}
    assert body["metadata"]["target_audience"] == "Lehrkräfte"
    assert body["metadata"]["author"] == "Themenbaum Generator"

    (main_topic,) = body["collection"]
    assert set(main_topic) == {"title", "shorttitle", "properties", "subcollections"}
    assert set(main_topic["properties"]) == {
        "cclom_general_keyword",
        "ccm_collectionshorttitle",
        "ccm_educationalcontext",
        "ccm_educationalintendedenduserrole",
        "ccm_taxonid",
        "cm_description",
        "cm_title",
    }
    assert main_topic["properties"]["ccm_taxonid"] == ["http://w3id.org/openeduhub/vocabs/discipline/460"]
    assert main_topic["properties"]["ccm_educationalintendedenduserrole"] == [
        "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"
    ]

    (sub_topic,) = main_topic["subcollections"]
    (leaf,) = sub_topic["subcollections"]
    assert leaf["title"] == "Bewegung"
    # Legacy quirk kept on purpose: leaves have no "subcollections" key; empty keywords fall back to the title.
    assert "subcollections" not in leaf
    assert leaf["properties"]["cclom_general_keyword"] == ["bewegung"]


def test_legacy_prompt_uses_german_vocab_labels_from_snapshot() -> None:
    seen: list[str] = []

    async def capture(*, prompt: str, require_list: bool = True, **_: object):
        seen.append(prompt)
        return {"collections": [], "description": "x"} if not require_list else []

    with (
        patch.object(legacy, "AsyncOpenAI", lambda **_: object()),
        patch.object(legacy, "generate_structured_text", capture),
    ):
        TestClient(app).post(
            "/generate-topic-tree",
            json={
                "theme": "Physik",
                "discipline_uri": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
                "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"],
            },
            headers={"Authorization": "Bearer k"},
        )
    assert "Fachbereich: ['Physik']" in seen[0]
    assert "Zielgruppe / Bildungsstufe: ['Sekundarstufe I']" in seen[0]
