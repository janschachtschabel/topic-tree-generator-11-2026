import copy
import time

from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex

D60 = "wort " * 60


def node(key: str, title: str, *children: dict, contents: list | None = None) -> dict:
    return {
        "key": key,
        "title": title,
        "shorttitle": title[:20],
        "properties": {"cm:title": [title], "cm:description": [D60], "cclom:general_keyword": ["x"]},
        "contents": contents or [],
        "subcollections": list(children),
    }


CURRENT = {
    "version": "v1",
    "collection": [
        node("k-optik", "Optik", node("k-linsen", "Linsen"), node("k-spiegel", "Spiegel")),
        node("k-mechanik", "Mechanik", node("k-kraft", "Kraft"), node("k-bewegung", "Bewegung")),
        node(
            "k-akustik",
            "Akustik",
            node("k-schall", "Schall"),
            node("k-echo", "Echo"),
            contents=[{"id": "c1", "nodeId": "n1", "confidence": 0.9}],
        ),
    ],
    "generation": {
        "mode": "create",
        "use_case": "topic",
        "topic": "Physik",
        "shape": {"depth": 2, "main_topics": {"min": 2, "max": 6}, "children": {"min": 2, "max": 6}},
        "hints": {"description_length": 60},
        "structure": {"order": "Themen", "levels": ["Thema", "Teilthema"], "source": "detected"},
        "feedback": [],
    },
}


def describe(prompt: str) -> dict:
    keys = [line.split("key: ")[1].split(" |")[0] for line in prompt.splitlines() if line.startswith("- key: ")]
    return {"nodes": [{"key": k, "description": D60, "keywords": ["neu"]} for k in keys]}


def request(feedback: dict | None = None, **extra) -> TopicTreeRequestV2:
    data = {"mode": "refine", "use_case": "topic", "current_tree": copy.deepcopy(CURRENT), "frame": ex.FRAME}
    if feedback is not None:
        data["feedback"] = feedback
    return TopicTreeRequestV2.model_validate({**data, **extra})


async def run(req: TopicTreeRequestV2, answers: dict):
    llm = FakeLLM({"describe_nodes": describe, **answers})
    context = RunContext(llm=llm, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    return await orchestrator.run(req, context), llm


def by_key(nodes, key):
    for n in nodes:
        if n.key == key:
            return n
        found = by_key(n.subcollections, key)
        if found:
            return found
    return None


async def test_structured_changes_need_no_interpretation_call() -> None:
    resp, llm = await run(request({"changes": [{"op": "move", "key": "k-akustik", "to": "k-mechanik"}]}), {})
    assert llm.prompts("interpret_feedback") == []
    assert by_key(resp.collection, "k-akustik") in by_key(resp.collection, "k-mechanik").subcollections
    assert by_key(resp.collection, "k-akustik").status == "moved"
    assert by_key(resp.collection, "k-optik").status == "unchanged"
    assert [(c.op, c.source) for c in resp.changes] == [("move", "feedback_changes")]
    assert resp.metadata.version == "v2" and resp.metadata.based_on == "v1"


async def test_text_feedback_is_interpreted_applied_and_described() -> None:
    interpretation = {
        "changes": [
            {"op": "add", "parent": None, "title": "Farben"},
            {"op": "rename", "key": "k-kraft", "title": "Kräfte"},
        ],
        "questions": [],
    }
    resp, llm = await run(
        request({"text": "Farben als Hauptthema, Kraft heißt Kräfte"}), {"interpret_feedback": interpretation}
    )
    assert "Farben als Hauptthema" in llm.prompts("interpret_feedback")[0]
    farben = by_key(resp.collection, "k-farben")
    assert farben.status == "new" and farben.properties.first("cm:description") == D60.strip()
    kraefte = by_key(resp.collection, "k-kraft")
    assert (kraefte.title, kraefte.status) == ("Kräfte", "changed")
    assert kraefte.properties.first("cclom:general_keyword") == "neu"
    assert [c.source for c in resp.changes] == ["feedback_text", "feedback_text"]
    described = llm.prompts("describe_nodes")[0]
    assert "k-farben" in described and "k-kraft" in described and "k-linsen" not in described


async def test_structured_changes_win_over_conflicting_text() -> None:
    interpretation = {"changes": [{"op": "move", "key": "k-akustik", "to": "k-optik"}], "questions": []}
    resp, _ = await run(
        request({"text": "Akustik zu Optik", "changes": [{"op": "move", "key": "k-akustik", "to": "k-mechanik"}]}),
        {"interpret_feedback": interpretation},
    )
    assert by_key(resp.collection, "k-akustik") in by_key(resp.collection, "k-mechanik").subcollections
    assert "CHANGE_REJECTED" in [w.code for w in resp.warnings]


async def test_unclear_text_returns_questions_and_keeps_the_tree() -> None:
    interpretation = {"changes": [], "questions": ["Welches Thema meinst du mit „das Ding“?"]}
    resp, _ = await run(request({"text": "das Ding woanders hin"}), {"interpret_feedback": interpretation})
    assert [q.text for q in resp.questions] == ["Welches Thema meinst du mit „das Ding“?"]
    assert all(n.status == "unchanged" for n in resp.collection)


async def test_locked_branches_stay_untouched() -> None:
    interpretation = {
        "changes": [{"op": "rename", "key": "k-linsen", "title": "X"}, {"op": "remove", "key": "k-optik"}],
        "questions": [],
    }
    resp, _ = await run(request({"text": "…", "locked": ["k-optik"]}), {"interpret_feedback": interpretation})
    assert by_key(resp.collection, "k-linsen").title == "Linsen"
    assert by_key(resp.collection, "k-optik") is not None
    assert [w.code for w in resp.warnings].count("CHANGE_REJECTED") == 2


async def test_removed_nodes_release_their_contents() -> None:
    resp, _ = await run(request({"changes": [{"op": "remove", "key": "k-akustik"}]}), {})
    assert [(u.id, u.reason, u.node_id) for u in resp.unassigned] == [("c1", "no_matching_node", "n1")]


async def test_assign_only_keeps_structure_and_adds_assignments() -> None:
    assign = {"items": [{"id": "c9", "nodes": [{"key": "k-spiegel", "confidence": 0.9}]}]}
    req = request(None, items=[ex.content_item("c9", "Spiegelbild")], options={"assign_only": True})
    resp, llm = await run(req, {"assign_contents": assign})
    assert llm.prompts("describe_nodes") == [] and llm.prompts("interpret_feedback") == []
    assert [c.id for c in by_key(resp.collection, "k-spiegel").contents] == ["c9"]
    assert [c.id for c in by_key(resp.collection, "k-akustik").contents] == ["c1"]
    assert all(n.status == "unchanged" for n in resp.collection)


async def test_missing_settings_come_from_generation() -> None:
    resp, _ = await run(request({"changes": [{"op": "rename", "key": "k-echo", "title": "Nachhall"}]}), {})
    gen = resp.metadata.generation
    assert gen.topic == "Physik"
    assert gen.shape.depth == 2 and gen.shape.main_topics.max == 6
    assert gen.structure.order == "Themen"
    assert [f.version for f in gen.feedback] == ["v2"]


async def test_split_divides_a_node_by_hint() -> None:
    split = {
        "parts": [{"title": "Kräfte", "child_keys": ["k-kraft"]}, {"title": "Bewegungen", "child_keys": ["k-bewegung"]}]
    }
    resp, llm = await run(
        request({"changes": [{"op": "split", "key": "k-mechanik", "hint": "Kräfte vs Bewegung"}]}),
        {"split_node": split},
    )
    mechanik = by_key(resp.collection, "k-mechanik")
    assert mechanik is None
    titles = [n.title for n in resp.collection]
    assert titles[1:3] == ["Kräfte", "Bewegungen"]
    assert by_key(resp.collection, "k-kraft") in resp.collection[1].subcollections
    assert [(c.op, c.key) for c in resp.changes] == [("split", "k-mechanik")]
    assert "Kräfte vs Bewegung" in llm.prompts("split_node")[0]


async def test_locked_node_without_description_is_not_described() -> None:
    current = copy.deepcopy(CURRENT)
    current["collection"][0]["properties"]["cm:description"] = []
    req = request({"changes": [{"op": "rename", "key": "k-echo", "title": "Nachhall"}], "locked": ["k-optik"]})
    req = req.model_copy(update={"current_tree": req.current_tree.model_validate(current)})
    resp, llm = await run(req, {})
    described = "\n".join(llm.prompts("describe_nodes"))
    assert "k-optik" not in described
    assert by_key(resp.collection, "k-optik").properties.first("cm:description") is None


async def test_removed_node_contents_are_not_reassigned_or_duplicated() -> None:
    assign = {"items": [{"id": "c1", "nodes": [{"key": "k-optik", "confidence": 0.9}]}]}
    req = request(
        {"changes": [{"op": "remove", "key": "k-akustik"}]},
        items=[ex.content_item("c1", "Schall")],
    )
    resp, llm = await run(req, {"assign_contents": assign})
    assert llm.prompts("assign_contents") == []
    assert [u.id for u in resp.unassigned] == ["c1"]
    assert all(c.id != "c1" for n in resp.collection for c in n.contents)


async def test_refine_keeps_tree_title_and_description_from_current_tree() -> None:
    data = copy.deepcopy(CURRENT)
    data["title"] = "Physik Sek I"
    data["description"] = "Gesamtbeschreibung des Baums."
    req = TopicTreeRequestV2.model_validate(
        {
            "mode": "refine",
            "use_case": "topic",
            "current_tree": data,
            "frame": ex.FRAME,
            "options": {"assign_only": True},
        }
    )
    response, _ = await run(req, {})
    assert response.metadata.title == "Physik Sek I"
    assert response.metadata.description == "Gesamtbeschreibung des Baums."


async def test_refine_without_stored_description_stays_compatible() -> None:
    response, _ = await run(request(options={"assign_only": True}), {})
    assert response.metadata.title == "Physik"
    assert response.metadata.description == ""


async def test_refine_combines_feedback_with_assigning_new_items_into_added_node() -> None:
    interpretation = {
        "changes": [{"op": "add", "parent": None, "title": "Farben"}],
        "questions": [],
    }
    assign = {"items": [{"id": "c99", "nodes": [{"key": "k-farben", "confidence": 0.92}]}]}
    req = request(
        {"text": "Farben als Hauptthema ergänzen"},
        items=[ex.content_item("c99", "Spektralfarben am Prisma")],
    )
    resp, llm = await run(req, {"interpret_feedback": interpretation, "assign_contents": assign})
    farben = by_key(resp.collection, "k-farben")
    assert farben is not None and farben.status == "new"
    assert [c.id for c in farben.contents] == ["c99"]
    assert "k-farben: Farben" in llm.prompts("assign_contents")[0]
