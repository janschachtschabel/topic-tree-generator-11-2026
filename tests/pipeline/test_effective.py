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

    # Refining an input-driven tree whose generation stored the automatic 2..20 width keeps main_topics non-explicit.
    refine_doc = _req(
        {
            "mode": "refine",
            "use_case": "document",
            "current_tree": {
                "collection": [{"key": "k-a", "title": "Einziges Kapitel"}],
                "generation": {"shape": doc_eff.shape.model_dump()},
            },
            "feedback": {"text": "Unterpunkt ergänzen"},
            "frame": {},
        }
    )
    assert explicit_shape(refine_doc, Settings(_env_file=None)).main_topics is False


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


def _refine(generation: dict, **extra) -> TopicTreeRequestV2:
    tree = {"version": "v2", "collection": [{"title": "Optik"}], "generation": {"use_case": "topic", **generation}}
    return _req({"mode": "refine", "use_case": "topic", "frame": {}, "current_tree": tree, **extra})


def test_partly_sent_options_keep_the_other_inherited_options() -> None:
    req = _refine({"options": {"multi_assign": False, "min_confidence": 0.9}}, options={"assign_only": True})
    eff = effective_request(req)
    assert eff.options.assign_only is True
    assert eff.options.multi_assign is False
    assert eff.options.min_confidence == 0.9


def test_sent_options_override_inherited_ones_but_assign_only_is_never_inherited() -> None:
    req = _refine({"options": {"assign_only": True, "min_confidence": 0.9}}, options={"min_confidence": 0.5})
    eff = effective_request(req)
    assert eff.options.min_confidence == 0.5
    assert eff.options.assign_only is False


def test_partly_sent_hints_keep_the_other_inherited_hints() -> None:
    inherited = {"order": "Epochen", "exclude": ["Krieg"], "description_length": 120, "context": "alt"}
    eff = effective_request(_refine({"hints": inherited}, hints={"context": "Klasse 8"}))
    assert eff.hints.context == "Klasse 8"
    assert (eff.hints.order, eff.hints.exclude, eff.hints.description_length) == ("Epochen", ["Krieg"], 120)


def test_a_range_with_one_bound_takes_the_other_from_the_recommendation() -> None:
    base = {"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {}}
    eff = effective_request(_req({**base, "shape": {"main_topics": {"max": 4}, "children": {"max": 2}}}))
    assert (eff.shape.main_topics.min, eff.shape.main_topics.max) == (4, 4)
    assert (eff.shape.children.min, eff.shape.children.max) == (2, 2)
    eff = effective_request(_req({**base, "shape": {"main_topics": {"min": 15}}}), Settings(_env_file=None))
    assert (eff.shape.main_topics.min, eff.shape.main_topics.max) == (15, 15)
    eff = effective_request(_req({**base, "shape": {"main_topics": {"min": 3}}}), Settings(_env_file=None))
    assert (eff.shape.main_topics.min, eff.shape.main_topics.max) == (3, 15)
