import copy
import time
from pathlib import Path

from app.domain.tree import walk
from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.pipeline.strategies.document import build
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex

LEHRPLAN = (Path(__file__).parents[2] / "fixtures" / "lehrplan_physik_auszug.md").read_text(encoding="utf-8")
D60 = "wort " * 60


def doc(item_id: str = "d1", text: str = LEHRPLAN, use: list | None = None, fmt: str = "markdown") -> dict:
    return {
        "id": item_id,
        "nodeId": f"n-{item_id}",
        "use": use or ["structure"],
        "properties": {"cm:title": [f"Lehrplan {item_id}"]},
        "fulltext": {"format": fmt, "text": text},
    }


def req(items: list[dict], **extra) -> TopicTreeRequestV2:
    data = {
        "mode": "create",
        "use_case": "document",
        "items": items,
        "frame": ex.FRAME,
        "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
    }
    return TopicTreeRequestV2.model_validate(copy.deepcopy({**data, **extra}))


MAPPING = {
    "order": "Themenfelder",
    "levels": ["Themenfeld", "Fachbegriff"],
    "description": "Physik nach Lehrplan",
    "nodes": [
        {
            "title": "Wahrnehmung",
            "shorttitle": "Wahrnehmung",
            "section_ids": ["d1:s2"],
            "children": [
                {"title": "Licht und Sehen", "shorttitle": "Sehen", "section_ids": ["d1:s2"], "children": []},
                {"title": "Schatten", "shorttitle": "Schatten", "section_ids": ["d1:s99"], "children": []},
            ],
        },
        {
            "title": "Optische Phänomene",
            "shorttitle": "Phänomene",
            "section_ids": ["d1:s4", "d1:s5"],
            "children": [
                {"title": "Reflexion", "shorttitle": "Reflexion", "section_ids": ["d1:s5"], "children": []},
                {"title": "Brechung", "shorttitle": "Brechung", "section_ids": ["d1:s5"], "children": []},
            ],
        },
    ],
}


def describe(prompt: str) -> dict:
    keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
    return {"nodes": [{"key": k, "description": D60, "keywords": ["x"]} for k in keys]}


def rc(llm: FakeLLM) -> RunContext:
    return RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, context="CTX")


async def test_llm_sees_the_compact_outline_not_the_full_text() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc()]), rc(llm))
    prompt = llm.prompts("map_outline")[0]
    # The lone title heading (d1:s1) is dropped, so the Themenfelder are level 1.
    assert "d1:s4 | Ebene 1 | Seite 14 | Themenfeld 2: Optische Phänomene an Grenzflächen" in prompt
    assert "Reflexion, Brechung, Absorption." not in prompt


async def test_nodes_carry_document_origin_with_section_and_page() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    result = await build(req([doc()]), rc(llm))
    phaen = result.roots[1]
    assert (phaen.origin.type, phaen.origin.id, phaen.origin.section, phaen.origin.page) == (
        "document",
        "d1",
        "Themenfeld 2: Optische Phänomene an Grenzflächen",
        14,
    )
    assert result.structure.order == "Themenfelder" and result.structure.source == "input"
    assert all(n.description for n, _, _ in walk(result.roots))


async def test_unknown_section_ids_are_dropped_and_reported() -> None:
    context = rc(FakeLLM({"map_outline": MAPPING, "describe_nodes": describe}))
    result = await build(req([doc()]), context)
    schatten = result.roots[0].children[1]
    assert schatten.origin.type == "document" and schatten.origin.section is None
    assert [w.code for w in context.warnings] == ["SECTION_UNKNOWN"]


async def test_descriptions_get_section_excerpts() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc()]), rc(llm))
    assert "Reflexion, Brechung, Absorption." in llm.prompts("describe_nodes")[0]


async def test_several_documents_are_merged_into_one_outline() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc("d1"), doc("d2", "# Zusatz\n## Farben\nSpektrum")]), rc(llm))
    prompt = llm.prompts("map_outline")[0]
    assert "d2:s2 | Ebene 1 | Farben" in prompt and "d1:s2" in prompt


async def test_plain_text_document_next_to_a_markdown_outline_is_not_dropped() -> None:
    # Audit 2026-11-25 #6: a `text` document beside a Markdown outline used to vanish without a warning.
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    plain = doc("d2", "# kein Titel\nFarben entstehen durch Brechung.", fmt="text")
    await build(req([doc("d1"), plain]), rc(llm))
    assert "d2:s1 | Ebene 1 | Lehrplan d2" in llm.prompts("map_outline")[0]


async def test_document_without_headings_sends_an_excerpt() -> None:
    llm = FakeLLM(
        {
            "map_outline": {
                **MAPPING,
                "nodes": [
                    {"title": "Licht", "shorttitle": "Licht", "section_ids": [], "children": []},
                    {"title": "Schall", "shorttitle": "Schall", "section_ids": [], "children": []},
                ],
            },
            "describe_nodes": describe,
        }
    )
    result = await build(req([doc(text="Licht breitet sich aus. Schall braucht ein Medium.", fmt="text")]), rc(llm))
    assert "Licht breitet sich aus" in llm.prompts("map_outline")[0]
    assert result.roots[0].origin.id == "d1"


async def test_structure_only_document_is_not_assigned_but_content_document_is() -> None:
    assign = {"items": [{"id": "d1", "nodes": [{"key": "k-wahrnehmung", "confidence": 0.9}]}]}
    for use, expected in ((["structure"], False), (["structure", "content"], True)):
        llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe, "assign_contents": assign})
        context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
        await orchestrator.run(req([doc(use=use)]), context)
        assert bool(llm.prompts("assign_contents")) is expected


async def test_end_to_end_uses_hints_in_the_context() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req([doc()], hints={"exclude": ["Wahlpflicht"]}), context)
    assert "Ausschließen: Wahlpflicht" in llm.prompts("map_outline")[0]
    assert resp.collection[0].origin.type == "document"


async def test_trimming_to_the_shape_is_reported() -> None:
    deep = copy.deepcopy(MAPPING)
    deep["nodes"][0]["children"][0]["children"] = [
        {"title": "zu tief", "shorttitle": "t", "section_ids": [], "children": []}
    ]
    deep["nodes"] += [
        {"title": f"Extra {i}", "shorttitle": f"E{i}", "section_ids": [], "children": []} for i in range(6)
    ]
    context = rc(FakeLLM({"map_outline": deep, "describe_nodes": describe}))
    result = await build(req([doc()]), context)
    assert len(result.roots) == 6
    assert {"SHAPE_DEPTH", "SHAPE_WIDTH"} <= {w.code for w in context.warnings}


TITLED = """# Lehrplan Physik (Auszug)

## Themenfeld 1: Licht
Text eins.

### Lichtquellen
Quellen.

### Schatten
Schatten.

## Themenfeld 2: Grenzflächen

### Reflexion
Spiegel.

### Brechung
Glas.

## Wahlpflicht: Wellenoptik
Beugung.
"""


async def test_lone_document_title_heading_is_not_offered_as_a_level() -> None:
    llm = FakeLLM({"map_outline": MAPPING, "describe_nodes": describe})
    await build(req([doc(text=TITLED)]), rc(llm))
    outline = llm.prompts("map_outline")[0]
    assert "Lehrplan Physik (Auszug)" not in outline
    assert "d1:s2 | Ebene 1 | Themenfeld 1: Licht" in outline
    assert "d1:s3 | Ebene 2 | Lichtquellen" in outline


async def test_collapsed_llm_mapping_falls_back_to_the_document_outline() -> None:
    chain = {
        "order": "Themenfelder",
        "levels": ["Ebene 1", "Ebene 2"],
        "description": "Baum",
        "nodes": [
            {
                "title": "Licht",
                "shorttitle": "Licht",
                "section_ids": ["d1:s2"],
                "children": [
                    {
                        "title": "Lichtquellen",
                        "shorttitle": "Quellen",
                        "section_ids": ["d1:s3"],
                        "children": [{"title": "Schatten", "shorttitle": "Schatten", "children": []}],
                    }
                ],
            }
        ],
    }
    llm = FakeLLM({"map_outline": chain, "describe_nodes": describe})
    run = rc(llm)
    result = await build(req([doc(text=TITLED)], hints={"exclude": ["Wahlpflicht"]}), run)
    assert [r.title for r in result.roots] == ["Themenfeld 1: Licht", "Themenfeld 2: Grenzflächen"]
    assert [c.title for c in result.roots[1].children] == ["Reflexion", "Brechung"]
    assert result.roots[0].origin.section == "Themenfeld 1: Licht"
    assert all(n.description for n, _, _ in walk(result.roots))
    codes = [w.code for w in run.warnings]
    assert "OUTLINE_FALLBACK" in codes and "SHAPE_DEPTH" not in codes


async def test_whitespace_only_structure_item_is_ignored_when_valid_doc_follows() -> None:
    blank = doc("d-blank", text="   \n  ")
    valid = doc("d-real", text=TITLED)
    llm = FakeLLM(
        {
            "map_outline": {
                "order": "Themenfelder",
                "levels": ["Ebene 1"],
                "description": "Baum",
                "nodes": [
                    {"title": "Frei A", "shorttitle": "A", "section_ids": ["unknown:s1"], "children": []},
                    {"title": "Frei B", "shorttitle": "B", "section_ids": ["unknown:s2"], "children": []},
                ],
            },
            "describe_nodes": describe,
        }
    )
    result = await build(req([blank, valid]), rc(llm))
    assert result.roots[0].origin.id == "d-real"


async def test_document_without_explicit_shape_keeps_all_20_curriculum_main_areas() -> None:
    sections_md = "# Rahmenlehrplan\n" + "\n".join(
        f"## Themenfeld {i}: Bereich {i}\n### Teil {i}.1\n### Teil {i}.2" for i in range(1, 21)
    )
    mapped_20 = {
        "order": "Themenfelder",
        "levels": ["Themenfeld", "Thema"],
        "description": "Vollständiger Lehrplan mit 20 Hauptbereichen",
        "nodes": [
            {
                "title": f"Bereich {i}",
                "shorttitle": f"B{i}",
                "section_ids": [f"d1:s{1 + (i - 1) * 3 + 1}"],
                "children": [
                    {"title": f"Teil {i}a", "shorttitle": f"T{i}a", "section_ids": [], "children": []},
                    {"title": f"Teil {i}b", "shorttitle": f"T{i}b", "section_ids": [], "children": []},
                ],
            }
            for i in range(1, 21)
        ],
    }
    raw_req = TopicTreeRequestV2.model_validate(
        {
            "mode": "create",
            "use_case": "document",
            "items": [doc(text=sections_md)],
            "frame": ex.FRAME,
        }
    )
    llm = FakeLLM({"map_outline": mapped_20, "describe_nodes": describe})
    run = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(raw_req, run)
    assert len(resp.collection) == 20
    assert "SHAPE_WIDTH" not in [w.code for w in resp.warnings]
    assert "nach Struktur der Eingaben (bis höchstens 20 Knoten)" in llm.prompts("map_outline")[0]


async def test_document_falls_back_to_deterministic_outline_when_llm_unavailable() -> None:
    from app.llm.client import LLMStepError

    llm = FakeLLM(
        {
            "map_outline": LLMStepError("map_outline", "http_error", 429),
            "describe_nodes": LLMStepError("describe_nodes", "http_error", 429),
        }
    )
    run = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60, mode="bapi")
    resp = await orchestrator.run(req([doc(text=TITLED)], hints={"exclude": ["Wahlpflicht"]}), run)
    assert [n.title for n in resp.collection] == ["Themenfeld 1: Licht", "Themenfeld 2: Grenzflächen"]
    codes = [w.code for w in resp.warnings]
    assert "LLM_DEGRADED" in codes and "DESCRIBE_FAILED" in codes
