"""Tests for target-group-recommended default shapes and operator cap clamping."""

from app.pipeline.effective import effective_request, explicit_shape
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings


def _req(data: dict) -> TopicTreeRequestV2:
    return TopicTreeRequestV2.model_validate(data)


def test_omitted_shape_adapts_to_elementarbereich() -> None:
    req = _req(
        {
            "mode": "create",
            "use_case": "topic",
            "topic": "Wasser entdecken",
            "frame": {
                "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/elementarbereich"]
            },
        }
    )
    eff = effective_request(req, Settings(_env_file=None))
    assert eff.shape.depth == 2
    assert (eff.shape.main_topics.min, eff.shape.main_topics.max) == (5, 10)
    assert explicit_shape(req) == explicit_shape(
        _req({"mode": "create", "use_case": "topic", "topic": "X", "frame": {}})
    )
    assert not explicit_shape(req).main_topics


def test_omitted_shape_adapts_to_fortbildung_and_organizations() -> None:
    req = _req(
        {
            "mode": "create",
            "use_case": "topic",
            "topic": "Datenschutz im Betrieb",
            "frame": {"educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/fortbildung"]},
        }
    )
    eff = effective_request(req, Settings(_env_file=None))
    assert eff.shape.depth == 2
    assert (eff.shape.main_topics.min, eff.shape.main_topics.max) == (5, 12)


def test_omitted_shape_uses_three_levels_and_5_to_15_for_school_and_clamps_to_operator_caps() -> None:
    req = _req(
        {
            "mode": "create",
            "use_case": "topic",
            "topic": "Optik",
            "frame": {
                "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"]
            },
        }
    )
    default_eff = effective_request(req, Settings(_env_file=None))
    assert default_eff.shape.depth == 3
    assert (default_eff.shape.main_topics.min, default_eff.shape.main_topics.max) == (5, 15)

    tight = Settings(_env_file=None, max_tree_depth=2, max_nodes_per_level=8)
    clamped = effective_request(req, tight)
    assert clamped.shape.depth == 2
    assert clamped.shape.main_topics.max == 8
    assert clamped.shape.children.max == 8


def test_omitted_shape_on_document_and_contents_allows_up_to_20_nodes_from_input() -> None:
    doc_req = _req(
        {
            "mode": "create",
            "use_case": "document",
            "items": [
                {
                    "id": "d1",
                    "use": ["structure"],
                    "fulltext": {"format": "markdown", "text": "# Lehrplan\n## A\n## B"},
                }
            ],
            "frame": {},
        }
    )
    doc_eff = effective_request(doc_req, Settings(_env_file=None))
    assert doc_eff.shape.depth == 3
    assert (doc_eff.shape.main_topics.min, doc_eff.shape.main_topics.max) == (2, 20)
    assert (doc_eff.shape.children.min, doc_eff.shape.children.max) == (2, 20)

    topic_with_struct = _req(
        {
            "mode": "create",
            "use_case": "topic",
            "topic": "Physik",
            "items": [
                {
                    "id": "d1",
                    "use": ["structure"],
                    "fulltext": {"format": "markdown", "text": "## A\n## B"},
                }
            ],
            "frame": {},
        }
    )
    struct_eff = effective_request(topic_with_struct, Settings(_env_file=None))
    assert (struct_eff.shape.main_topics.min, struct_eff.shape.main_topics.max) == (2, 20)


def test_explicit_shape_fields_are_preserved_while_omitted_siblings_get_defaults() -> None:
    req = _req(
        {
            "mode": "create",
            "use_case": "topic",
            "topic": "Wasser entdecken",
            "frame": {
                "educational_context_uri": ["http://w3id.org/openeduhub/vocabs/educationalContext/elementarbereich"]
            },
            "shape": {"depth": 3},
        }
    )
    eff = effective_request(req, Settings(_env_file=None))
    assert eff.shape.depth == 3
    assert (eff.shape.main_topics.min, eff.shape.main_topics.max) == (5, 10)
