"""Vocabulary URIs, frames and helpers shared by the test UI presets."""

from typing import Any

_V = "http://w3id.org/openeduhub/vocabs"
DISC_PHYS = f"{_V}/discipline/460"
DISC_BIO = f"{_V}/discipline/080"
DISC_CHEM = f"{_V}/discipline/100"
DISC_GEO = f"{_V}/discipline/220"
DISC_POL = f"{_V}/discipline/480"
DISC_SACHUNTERRICHT = f"{_V}/discipline/28010"
DISC_MECHATRONIK = f"{_V}/discipline/oeh04010"
DISC_ELEKTRO = f"{_V}/discipline/04005"
UNI_MATHEMATIK = f"{_V}/hochschulfaechersystematik/n37"
CTX_ELEMENTAR = f"{_V}/educationalContext/elementarbereich"
CTX_SEK1 = f"{_V}/educationalContext/sekundarstufe_1"
CTX_SEK2 = f"{_V}/educationalContext/sekundarstufe_2"
CTX_BERUF = f"{_V}/educationalContext/berufliche_bildung"
CTX_HOCHSCHULE = f"{_V}/educationalContext/hochschule"
ROLE_TEACHER = f"{_V}/intendedEndUserRole/teacher"
ROLE_LEARNER = f"{_V}/intendedEndUserRole/learner"


def frame(disciplines: list[str], context: str, role: str = ROLE_TEACHER) -> dict[str, list[str]]:
    return {"discipline_uri": disciplines, "educational_context_uri": [context], "intended_end_user_role_uri": [role]}


FRAME_PHYS_SEK1 = frame([DISC_PHYS], CTX_SEK1)
STRUCT = ("structure", "content")  # items that shape the tree and are sorted in


def material(item_id: str, title: str, keywords: list[str], description: str = "", use=("content",)) -> dict[str, Any]:
    """Item as the test UI's line editor produces it (no nodeId, no full text)."""
    properties: dict[str, list[str]] = {"cm:title": [title]}
    if keywords:
        properties["cclom:general_keyword"] = keywords
    if description:
        properties["cm:description"] = [description]
    return {"id": item_id, "use": list(use), "properties": properties}


def node(key: str, title: str, description: str, children: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
    """Fully described node of an earlier answer (refine presets start from described trees)."""
    return {
        "key": key,
        "title": title,
        "shorttitle": title,
        "properties": {"cm:title": [title], "cm:description": [description]},
        "subcollections": list(children),
    }
