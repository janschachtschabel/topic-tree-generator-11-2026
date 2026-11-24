"""Integration tests: orchestrator applies keyword hygiene and quality guards."""

import copy
import time

from app.domain.tree import Node
from app.pipeline import orchestrator
from app.pipeline.result import StrategyResult
from app.pipeline.run_context import RunContext
from app.schemas.common import OriginType, UseCase
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex

D60 = "wort " * 60


def _topic_node(title: str, keywords: list[str] | None = None) -> Node:
    return Node(
        key=None,
        title=title,
        description=D60,
        keywords=list(keywords or ["Linsen"]),
        origin=Origin(type=OriginType.topic),
    )


async def test_orchestrator_cleans_keywords_and_reports_quality_warnings() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["topic"] = "Optik"
    data["shape"] = {"depth": 1, "main_topics": {"min": 3, "max": 6}, "extra_topics": ["general"]}
    request = TopicTreeRequestV2.model_validate(data)

    async def fake_strategy(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
        return StrategyResult(
            roots=[
                _topic_node("Allgemeines", ["Unterricht", "Optik Grundlagen"]),
                _topic_node("Optik", ["Optik", "Arbeitsblatt", "Lichtlehre"]),
                _topic_node("Sonstiges", ["Material", "Spiegel"]),
                _topic_node("Arbeitsblätter", ["Brechung", "Arbeitsblatt", "brechung"]),
            ],
            title="Optik",
        )

    rc = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(request, rc, strategies={UseCase.topic: fake_strategy})

    by_title = {node.title: node for node in resp.collection}
    assert by_title["Allgemeines"].properties.values("cclom:general_keyword") == ["Optik Grundlagen"]
    assert by_title["Optik"].properties.values("cclom:general_keyword") == ["Lichtlehre"]
    assert by_title["Arbeitsblätter"].properties.values("cclom:general_keyword") == ["Brechung"]

    warning_codes = [(w.code, w.key) for w in resp.warnings]
    assert ("TOPIC_REPEAT", "k-optik") in warning_codes
    assert ("GENERIC_TITLE", "k-sonstiges") in warning_codes
    assert ("FACET_AS_NODE", "k-arbeitsblaetter") in warning_codes
    # Requested extra_topic "Allgemeines" must not be flagged.
    assert ("GENERIC_TITLE", "k-allgemeines") not in warning_codes


async def test_orchestrator_recognizes_history_discipline_for_temporal_headings() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["topic"] = "Europa in der Neuzeit"
    data["frame"]["discipline_uri"] = ["http://w3id.org/openeduhub/vocabs/discipline/240"]
    data["shape"] = {"depth": 1, "main_topics": {"min": 2, "max": 6}}
    request = TopicTreeRequestV2.model_validate(data)

    async def fake_strategy(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
        return StrategyResult(
            roots=[_topic_node("19. Jahrhundert"), _topic_node("20. Jahrhundert")],
            title="Europa in der Neuzeit",
        )

    rc = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(request, rc, strategies={UseCase.topic: fake_strategy})
    assert [w.code for w in resp.warnings] == []


async def test_orchestrator_allows_temporal_headings_when_chronological_order_requested() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["topic"] = "Entwicklung der Informatik"
    data["hints"]["order"] = "chronologisch"
    data["shape"] = {"depth": 1, "main_topics": {"min": 2, "max": 6}}
    request = TopicTreeRequestV2.model_validate(data)

    async def fake_strategy(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
        return StrategyResult(
            roots=[_topic_node("1960er Jahre"), _topic_node("1970er Jahre")],
            title="Entwicklung der Informatik",
        )

    rc = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(request, rc, strategies={UseCase.topic: fake_strategy})
    assert [w.code for w in resp.warnings] == []


async def test_refine_does_not_mutate_untouched_or_user_edited_keywords() -> None:
    request = TopicTreeRequestV2.model_validate(
        {
            "mode": "refine",
            "use_case": "topic",
            "topic": "Optik",
            "frame": copy.deepcopy(ex.FRAME),
            "shape": {"depth": 1, "main_topics": {"min": 2, "max": 6}},
            "current_tree": {
                "version": "v1",
                "collection": [
                    {
                        "key": "k-untouched",
                        "title": "Brechung",
                        "shorttitle": "Brechung",
                        "properties": {
                            "cm:title": ["Brechung"],
                            "cm:description": [D60],
                            "cclom:general_keyword": ["Brechung", "Arbeitsblatt"],
                        },
                        "subcollections": [],
                    },
                    {
                        "key": "k-edited",
                        "title": "Spiegel",
                        "shorttitle": "Spiegel",
                        "properties": {
                            "cm:title": ["Spiegel"],
                            "cm:description": [D60],
                            "cclom:general_keyword": ["Reflexion"],
                        },
                        "subcollections": [],
                    },
                ],
            },
            "feedback": {
                "changes": [
                    {
                        "op": "edit",
                        "key": "k-edited",
                        "properties": {"cclom:general_keyword": ["Arbeitsblatt", "Reflexion"]},
                    }
                ]
            },
        }
    )
    rc = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(request, rc)
    by_key = {node.key: node for node in resp.collection}
    assert by_key["k-untouched"].status == "unchanged"
    assert by_key["k-untouched"].properties.values("cclom:general_keyword") == ["Brechung", "Arbeitsblatt"]
    assert by_key["k-edited"].status == "changed"
    assert by_key["k-edited"].properties.values("cclom:general_keyword") == ["Arbeitsblatt", "Reflexion"]


async def test_assign_only_and_locked_refine_nodes_do_not_trigger_description_warnings() -> None:
    assign_only_req = TopicTreeRequestV2.model_validate(
        {
            "mode": "refine",
            "use_case": "folders",
            "frame": copy.deepcopy(ex.FRAME),
            "current_tree": {
                "version": "v1",
                "collection": [
                    {
                        "key": "k-optik",
                        "title": "Optik",
                        "shorttitle": "Optik",
                        "properties": {"cm:title": ["Optik"], "cm:description": ["Kurz."]},
                        "subcollections": [],
                    }
                ],
            },
            "options": {"assign_only": True, "assign_contents": False},
        }
    )
    rc = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(assign_only_req, rc)
    assert resp.warnings == []

    locked_req = TopicTreeRequestV2.model_validate(
        {
            "mode": "refine",
            "use_case": "topic",
            "topic": "Physik",
            "frame": copy.deepcopy(ex.FRAME),
            "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
            "current_tree": {
                "version": "v1",
                "collection": [
                    {
                        "key": "k-optik",
                        "title": "Optik",
                        "shorttitle": "Optik",
                        "properties": {"cm:title": ["Optik"], "cm:description": ["Kurz."]},
                        "subcollections": [
                            {"key": "k-spiegel", "title": "Spiegel", "shorttitle": "Spiegel", "subcollections": []},
                            {"key": "k-linsen", "title": "Linsen", "shorttitle": "Linsen", "subcollections": []},
                        ],
                    },
                    {
                        "key": "k-mechanik",
                        "title": "Mechanik",
                        "shorttitle": "Mechanik",
                        "properties": {"cm:title": ["Mechanik"], "cm:description": ["Kurz."]},
                        "subcollections": [],
                    },
                ],
            },
            "feedback": {"locked": ["k-optik"]},
        }
    )
    rc2 = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp2 = await orchestrator.run(locked_req, rc2)
    assert [w.code for w in resp2.warnings] == []


async def test_extra_topics_outside_topic_do_not_cause_false_shape_width_warnings() -> None:
    request = TopicTreeRequestV2.model_validate(
        {
            "mode": "create",
            "use_case": "contents",
            "topic": "Optik",
            "items": [{"id": "c1", "properties": {"cm:title": ["Linsen"]}}],
            "frame": copy.deepcopy(ex.FRAME),
            "shape": {
                "depth": 1,
                "main_topics": {"min": 2, "max": 6},
                "extra_topics": ["general", "methodology"],
            },
            "options": {"assign_contents": False},
        }
    )

    async def fake_contents(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
        return StrategyResult(
            roots=[_topic_node("Linsen"), _topic_node("Spiegel")],
            title="Optik",
        )

    rc = RunContext(llm=FakeLLM({}), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(request, rc, strategies={UseCase.contents: fake_contents})
    assert "Zusatzthemen" not in rc.context
    assert [w.code for w in resp.warnings] == []
