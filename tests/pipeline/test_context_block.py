import copy

from app.pipeline.context_block import build_context_block
from app.schemas.request_v2 import TopicTreeRequestV2
from tests.fixtures import spec_examples as ex


def req(data: dict) -> TopicTreeRequestV2:
    return TopicTreeRequestV2.model_validate(copy.deepcopy(data))


def test_block_lists_frame_labels_hints_and_shape() -> None:
    block, unknown = build_context_block(req(ex.ALL_REQUESTS["full_options"]))
    assert "Thema: Optik" in block
    assert "Fach: Physik" in block
    assert "Bildungsstufe: Sekundarstufe I" in block
    assert "Zielgruppe: Lehrer/in" in block
    assert "Wellenoptik" in block and "Farben" in block
    assert "Ordnungsprinzip (Vorgabe): Themen" in block
    assert "3 Ebenen" in block and "6 bis 12" in block and "3 bis 8" in block
    assert "45 bis 72 Wörter (Ziel 60 Wörter)" in block
    assert unknown == []


def test_block_is_deterministic() -> None:
    assert build_context_block(req(ex.TOPIC)) == build_context_block(req(ex.TOPIC))


def test_unknown_vocab_uris_are_reported_and_shown_by_their_tail() -> None:
    data = copy.deepcopy(ex.TOPIC)
    data["frame"]["discipline_uri"] = ["http://w3id.org/openeduhub/vocabs/discipline/unbekannt99"]
    block, unknown = build_context_block(req(data))
    assert unknown == ["http://w3id.org/openeduhub/vocabs/discipline/unbekannt99"]
    assert "Fach: unbekannt99" in block


def test_without_order_hint_the_block_asks_for_detection() -> None:
    block, _ = build_context_block(req(ex.TOPIC))
    assert "Ordnungsprinzip: keine Vorgabe" in block


def test_context_block_differentiates_explicit_vs_omitted_shape() -> None:
    omitted_topic = req({"mode": "create", "use_case": "topic", "topic": "Optik", "frame": {}})
    block_omitted, _ = build_context_block(omitted_topic)
    assert "Empfehlungsrahmen" in block_omitted
    assert "höchstens 3 Ebenen" in block_omitted

    omitted_doc = req(ex.DOCUMENT)
    block_doc, _ = build_context_block(omitted_doc)
    assert "nach Struktur der Eingaben" in block_doc

    explicit_topic = req(ex.TOPIC)
    block_explicit, _ = build_context_block(explicit_topic)
    assert "(Vorgabe)" in block_explicit
