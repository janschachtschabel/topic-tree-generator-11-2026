"""Tests for target-group-recommended default shapes and operator cap clamping."""

from app.pipeline.effective import effective_request
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


def test_omitted_shape_uses_three_levels_for_school_and_clamps_to_operator_caps() -> None:
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
    assert (default_eff.shape.main_topics.min, default_eff.shape.main_topics.max) == (6, 12)

    tight = Settings(_env_file=None, max_tree_depth=2, max_nodes_per_level=8)
    clamped = effective_request(req, tight)
    assert clamped.shape.depth == 2
    assert clamped.shape.main_topics.max == 8
    assert clamped.shape.children.max == 8


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
