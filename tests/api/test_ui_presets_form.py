"""Every UI preset loads into the form and comes back out of the request builder with the same meaning, so all data
that flows into a call is visible in the form (not only in the JSON view)."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.schemas.request_v2 import TopicTreeRequestV2
from app.ui.presets import PRESETS

_ROOT = Path(__file__).resolve().parents[2]
# Presets that carry technical edu-sharing ids (`nodeId`): the line editor has no column for them by design, so they
# load into the JSON view only.
_JSON_ONLY = {"assign_only"}


def _normalized(payload: dict[str, Any]) -> dict[str, Any]:
    """Schema defaults filled in; item ids (the form numbers them anew) replaced by the items' titles."""
    data = TopicTreeRequestV2.model_validate(payload).model_dump(mode="json", by_alias=True)
    titles = {item["id"]: (item["properties"].get("cm:title") or [item["id"]])[0] for item in data["items"] or []}
    for item in data["items"] or []:
        item["id"] = titles[item["id"]]
        if item.get("fulltext") and item["fulltext"].get("text"):
            item["fulltext"]["text"] = item["fulltext"]["text"].strip()
    if data["items"]:
        data["items"].sort(key=lambda item: item["id"])

    def rename(folders: list[dict[str, Any]] | None) -> None:
        for folder in folders or []:
            folder["items"] = [titles.get(i, i) for i in folder["items"]]
            rename(folder["subcollections"])

    rename(data["folders"])
    return data


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    source = tmp_path_factory.mktemp("presets") / "presets.json"
    source.write_text(json.dumps(PRESETS), encoding="utf-8")
    script = _ROOT / "tests" / "ui_js" / "build_presets.cjs"
    proc = subprocess.run(
        ["node", str(script), str(source)], check=True, cwd=_ROOT, capture_output=True, text=True, timeout=60
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("preset", PRESETS, ids=[p["id"] for p in PRESETS])
def test_preset_survives_the_form(preset: dict[str, Any], built: dict[str, Any]) -> None:
    payload = built[preset["id"]]
    if preset["id"] in _JSON_ONLY:
        assert payload is None
        return
    assert payload is not None, "preset only fits the JSON view"
    assert _normalized(payload) == _normalized(preset["payload"])
