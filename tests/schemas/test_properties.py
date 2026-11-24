import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.properties import Properties


class Holder(BaseModel):
    properties: Properties = Properties()


def test_both_key_spellings_are_accepted_and_normalized_to_colon() -> None:
    p = Properties.model_validate({"cm_title": ["Optik"], "ccm:taxonid": ["u"], "cclom_general_keyword": ["Licht"]})
    assert p.dump_v2() == {"cm:title": ["Optik"], "ccm:taxonid": ["u"], "cclom:general_keyword": ["Licht"]}


def test_legacy_dump_uses_underscores() -> None:
    p = Properties.model_validate({"cm:title": ["Optik"], "cclom:general_keyword": ["Licht"]})
    assert p.dump_legacy() == {"cm_title": ["Optik"], "cclom_general_keyword": ["Licht"]}


def test_unknown_properties_are_kept() -> None:
    p = Properties.model_validate({"ccm:oeh_lrt": ["x"], "custom_field": ["y"]})
    assert p.dump_v2() == {"ccm:oeh_lrt": ["x"], "custom_field": ["y"]}


def test_scalars_become_single_item_lists() -> None:
    p = Properties.model_validate({"cm:title": "Optik", "ccm:year": 2024})
    assert p.dump_v2() == {"cm:title": ["Optik"], "ccm:year": ["2024"]}


def test_first_and_values_helpers() -> None:
    p = Properties.model_validate({"cm_title": ["Optik", "Licht"]})
    assert p.first("cm:title") == "Optik"
    assert p.first("cm_title") == "Optik"
    assert p.values("cm:description") == []
    assert p.first("cm:description") is None


def test_nested_objects_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Properties.model_validate({"cm:title": [{"a": 1}]})


def test_serializes_with_colon_keys_inside_models() -> None:
    h = Holder(properties=Properties.model_validate({"cm_title": ["Optik"]}))
    assert h.model_dump(mode="json") == {"properties": {"cm:title": ["Optik"]}}
