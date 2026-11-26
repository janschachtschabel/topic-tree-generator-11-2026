"""Render docs/datenformat.md: every request and response field from the v2 JSON Schemas (a test checks it is current).

Run: uv run python -m scripts.export_schemas (writes the schemas and this reference together).
"""

from typing import Any

HEADER = """# Datenformat von POST /v2/topic-tree

Automatisch erzeugt aus den Pydantic-Modellen (`uv run python -m scripts.export_schemas`); nicht von Hand ändern.
Muster für einzelne und kombinierte Use Cases und für Änderungen an Bäumen: [`api.md`](api.md) und
[`examples/`](examples/). Maschinenlesbar: [`schemas/`](schemas/).

Spalten: **Pflicht** = muss gesendet werden; **Standard** = Wert, wenn das Feld fehlt.
"""


def _anchor(name: str, suffix: str) -> str:
    return f"{name} ({suffix})" if suffix else name


def _type(spec: dict[str, Any], suffix: str = "") -> str:
    if "$ref" in spec:
        name = spec["$ref"].rsplit("/", 1)[-1]
        slug = name.lower() + (f"-{suffix.lower()}" if suffix else "")
        return f"[`{name}`](#{slug})"
    if "anyOf" in spec:
        parts = [_type(s, suffix) for s in spec["anyOf"] if s.get("type") != "null"]
        return " oder ".join(parts) + (" oder null" if any(s.get("type") == "null" for s in spec["anyOf"]) else "")
    if "enum" in spec:
        return " | ".join(f"`{v}`" for v in spec["enum"])
    kind = spec.get("type", "beliebig")
    if kind == "array":
        return f"Liste von {_type(spec.get('items', {}), suffix)}"
    if kind == "object" and isinstance(spec.get("additionalProperties"), dict):
        return f"Objekt (Werte: {_type(spec['additionalProperties'], suffix)})"
    return {"string": "Text", "integer": "Ganzzahl", "number": "Zahl", "boolean": "ja/nein", "object": "Objekt"}.get(
        kind, kind
    )


def _limits(spec: dict[str, Any]) -> str:
    target = spec
    if "anyOf" in spec:
        target = next((s for s in spec["anyOf"] if s.get("type") != "null"), spec)
    parts = []
    for key, label in (("minimum", "≥"), ("maximum", "≤"), ("minLength", "min. Länge"), ("maxLength", "max. Länge")):
        if key in target:
            parts.append(f"{label} {target[key]}")
    for key, label in (("minItems", "min."), ("maxItems", "max.")):
        if key in target:
            parts.append(f"{label} {target[key]} Einträge")
    return f" ({', '.join(parts)})" if parts else ""


def _default(spec: dict[str, Any]) -> str:
    if "default" not in spec:
        return ""
    value = spec["default"]
    if value is None:
        return "–"
    if value in ([], {}):
        return f"`{value}`"
    return f"`{value!r}`".replace("'", '"') if isinstance(value, str) else f"`{value}`".replace("'", '"')


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _model(name: str, spec: dict[str, Any], suffix: str = "", heading: str | None = None) -> list[str]:
    lines = [f"### {heading or _anchor(name, suffix)}", ""]
    if spec.get("description"):
        lines += [_cell(spec["description"]), ""]
    if "enum" in spec:
        return [*lines, "Werte: " + ", ".join(f"`{v}`" for v in spec["enum"]), ""]
    props = spec.get("properties", {})
    if not props:
        extra = spec.get("additionalProperties")
        kind = _type(extra, suffix) if isinstance(extra, dict) else "beliebig"
        return [*lines, f"Freie Schlüssel; Werte: {kind}.", ""]
    required = set(spec.get("required", []))
    lines += ["| Feld | Typ | Pflicht | Standard | Bedeutung |", "|---|---|---|---|---|"]
    for field, fspec in props.items():
        lines.append(
            f"| `{field}` | {_cell(_type(fspec, suffix) + _limits(fspec))} | {'ja' if field in required else ''} | "
            f"{_cell(_default(fspec))} | {_cell(fspec.get('description', ''))} |"
        )
    return [*lines, ""]


def _section(title: str, schema: dict[str, Any], suffix: str) -> list[str]:
    defs = schema.get("$defs", {})
    root = {k: v for k, v in schema.items() if k not in {"$defs", "title"}}
    lines = [f"## {title}", ""] + _model(title, root, suffix, heading=f"{title}: oberste Ebene")
    for name in sorted(defs):
        lines += _model(name, defs[name], suffix)
    return lines


def render(request: dict[str, Any], response: dict[str, Any]) -> str:
    lines = [HEADER, *_section("Anfrage", request, ""), *_section("Antwort", response, "Antwort")]
    return "\n".join(lines).rstrip() + "\n"
