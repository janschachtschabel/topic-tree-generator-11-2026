"""Render the field reference (every request and response field from the v2 JSON Schemas) in German and English:
docs/de/datenformat.md and docs/en/data-format.md (a test checks both are current).

Run: uv run python -m scripts.export_schemas (writes the schemas and both references together).
Field descriptions are the German API texts of the models (AGENTS.md: user-facing API texts are German); the English
reference translates everything around them.
"""

from typing import Any

HEADERS = {
    "de": """# Datenformat von POST /v2/topic-tree

> 🇬🇧 English version: [`../en/data-format.md`](../en/data-format.md)

Automatisch erzeugt aus den Pydantic-Modellen (`uv run python -m scripts.export_schemas`); nicht von Hand ändern.
Muster für einzelne und kombinierte Use Cases und für Änderungen an Bäumen: [`api.md`](api.md) und
[`examples/`](../examples/). Maschinenlesbar: [`schemas/`](../schemas/).

Spalten: **Pflicht** = muss gesendet werden; **Standard** = Wert, wenn das Feld fehlt.
""",
    "en": """# Data format of POST /v2/topic-tree

> 🇩🇪 Deutsche Fassung: [`../de/datenformat.md`](../de/datenformat.md)

Generated from the Pydantic models (`uv run python -m scripts.export_schemas`); do not edit by hand.
Patterns for single and combined use cases and for changes to trees: [`api.md`](api.md) and
[`examples/`](../examples/). Machine-readable: [`schemas/`](../schemas/).

Columns: **Required** = must be sent; **Default** = value when the field is missing. The *Meaning* column holds the
field descriptions exactly as the API publishes them in `/openapi.json`, which are German.
""",
}

WORDS = {
    "de": {
        "or": "oder",
        "or_null": "oder null",
        "list_of": "Liste von",
        "object_values": "Objekt (Werte: {kind})",
        "any": "beliebig",
        "types": {"string": "Text", "integer": "Ganzzahl", "number": "Zahl", "boolean": "ja/nein", "object": "Objekt"},
        "min_len": "min. Länge",
        "max_len": "max. Länge",
        "min_items": "min. {n} Einträge",
        "max_items": "max. {n} Einträge",
        "values": "Werte",
        "free_keys": "Freie Schlüssel; Werte: {kind}.",
        "columns": "| Feld | Typ | Pflicht | Standard | Bedeutung |",
        "yes": "ja",
        "top_level": "{title}: oberste Ebene",
        "request": "Anfrage",
        "response": "Antwort",
    },
    "en": {
        "or": "or",
        "or_null": "or null",
        "list_of": "list of",
        "object_values": "object (values: {kind})",
        "any": "any",
        "types": {
            "string": "string",
            "integer": "integer",
            "number": "number",
            "boolean": "boolean",
            "object": "object",
        },
        "min_len": "min. length",
        "max_len": "max. length",
        "min_items": "min. {n} entries",
        "max_items": "max. {n} entries",
        "values": "Values",
        "free_keys": "Free keys; values: {kind}.",
        "columns": "| Field | Type | Required | Default | Meaning |",
        "yes": "yes",
        "top_level": "{title}: top level",
        "request": "Request",
        "response": "Response",
    },
}


class _Renderer:
    def __init__(self, lang: str) -> None:
        self.w = WORDS[lang]

    def type(self, spec: dict[str, Any], suffix: str = "") -> str:
        w = self.w
        if "$ref" in spec:
            name = spec["$ref"].rsplit("/", 1)[-1]
            slug = name.lower() + (f"-{suffix.lower()}" if suffix else "")
            return f"[`{name}`](#{slug})"
        if "anyOf" in spec:
            parts = [self.type(s, suffix) for s in spec["anyOf"] if s.get("type") != "null"]
            nullable = any(s.get("type") == "null" for s in spec["anyOf"])
            return f" {w['or']} ".join(parts) + (f" {w['or_null']}" if nullable else "")
        if "enum" in spec:
            return " | ".join(f"`{v}`" for v in spec["enum"])
        kind = spec.get("type", w["any"])
        if kind == "array":
            return f"{w['list_of']} {self.type(spec.get('items', {}), suffix)}"
        if kind == "object" and isinstance(spec.get("additionalProperties"), dict):
            return w["object_values"].format(kind=self.type(spec["additionalProperties"], suffix))
        return w["types"].get(kind, kind)

    def limits(self, spec: dict[str, Any]) -> str:
        w = self.w
        target = spec
        if "anyOf" in spec:
            target = next((s for s in spec["anyOf"] if s.get("type") != "null"), spec)
        parts = []
        for key, label in (
            ("minimum", "≥"),
            ("maximum", "≤"),
            ("minLength", w["min_len"]),
            ("maxLength", w["max_len"]),
        ):
            if key in target:
                parts.append(f"{label} {target[key]}")
        for key, label in (("minItems", w["min_items"]), ("maxItems", w["max_items"])):
            if key in target:
                parts.append(label.format(n=target[key]))
        return f" ({', '.join(parts)})" if parts else ""

    def model(self, name: str, spec: dict[str, Any], suffix: str = "", heading: str | None = None) -> list[str]:
        w = self.w
        anchor = f"{name} ({suffix})" if suffix else name
        lines = [f"### {heading or anchor}", ""]
        if spec.get("description"):
            lines += [_cell(spec["description"]), ""]
        if "enum" in spec:
            return [*lines, f"{w['values']}: " + ", ".join(f"`{v}`" for v in spec["enum"]), ""]
        props = spec.get("properties", {})
        if not props:
            extra = spec.get("additionalProperties")
            kind = self.type(extra, suffix) if isinstance(extra, dict) else w["any"]
            return [*lines, w["free_keys"].format(kind=kind), ""]
        required = set(spec.get("required", []))
        lines += [w["columns"], "|---|---|---|---|---|"]
        for field, fspec in props.items():
            lines.append(
                f"| `{field}` | {_cell(self.type(fspec, suffix) + self.limits(fspec))} | "
                f"{w['yes'] if field in required else ''} | {_cell(_default(fspec))} | "
                f"{_cell(fspec.get('description', ''))} |"
            )
        return [*lines, ""]

    def section(self, title: str, schema: dict[str, Any], suffix: str) -> list[str]:
        defs = schema.get("$defs", {})
        root = {k: v for k, v in schema.items() if k not in {"$defs", "title"}}
        lines = [f"## {title}", ""] + self.model(title, root, suffix, heading=self.w["top_level"].format(title=title))
        for name in sorted(defs):
            lines += self.model(name, defs[name], suffix)
        return lines


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


def render(request: dict[str, Any], response: dict[str, Any], lang: str = "de") -> str:
    r = _Renderer(lang)
    lines = [
        HEADERS[lang],
        *r.section(WORDS[lang]["request"], request, ""),
        *r.section(WORDS[lang]["response"], response, WORDS[lang]["response"]),
    ]
    return "\n".join(lines).rstrip() + "\n"
