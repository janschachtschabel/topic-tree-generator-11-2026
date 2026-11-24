import importlib
import socket

import pytest

from app.vocab import labels as labels_module
from app.vocab.labels import label, snapshot_date

PHYSIK = "http://w3id.org/openeduhub/vocabs/discipline/460"


def test_known_uris_resolve_to_german_labels() -> None:
    assert label(PHYSIK) == "Physik"
    assert label("http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1") == "Sekundarstufe I"
    assert label("http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher") == "Lehrer/in"
    assert label("http://w3id.org/openeduhub/vocabs/hochschulfaechersystematik/n1") == "Geisteswissenschaften"


def test_scheme_entries_and_resolve_labels() -> None:
    from app.vocab.labels import entries, resolve_labels

    hs_top = entries("hochschulfaechersystematik", max_depth=2)
    assert any(e["uri"].endswith("/n1") for e in hs_top)
    assert all(e["depth"] <= 2 for e in hs_top)
    assert len(hs_top) < len(entries("hochschulfaechersystematik"))

    resolved = resolve_labels([PHYSIK, "http://w3id.org/openeduhub/vocabs/discipline/does-not-exist"])
    assert resolved == {PHYSIK: "Physik"}


def test_https_and_trailing_slash_variants_resolve() -> None:
    assert label("https://w3id.org/openeduhub/vocabs/discipline/460/") == "Physik"


def test_unknown_uri_returns_none() -> None:
    assert label("http://w3id.org/openeduhub/vocabs/discipline/does-not-exist") is None
    assert label("") is None


def test_snapshot_date_is_reported() -> None:
    assert len(snapshot_date()) == 10


def test_import_and_lookup_need_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("network access during vocab lookup")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    module = importlib.reload(labels_module)
    assert module.label(PHYSIK) == "Physik"
