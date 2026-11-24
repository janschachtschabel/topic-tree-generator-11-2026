"""Lightweight HTTP OpenAI-compatible stub for live end-to-end tests (plan T6.3).

Accepts both `/v1/chat/completions` (standalone OpenAI) and `/api/v1/llm/router/chat/completions` (b-api router),
records all incoming requests (path, headers, body), and returns valid structured JSON per pipeline step.
"""

import json
import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Self

_D60 = " ".join(["Physikalischer", "Zusammenhang", "mit", "Alltagsbeispiel", "und", "Schülerexperiment."] * 10)


@dataclass
class RecordedCall:
    path: str
    headers: dict[str, str]
    body: dict[str, Any]


def _extract_keys(prompt: str) -> list[str]:
    return re.findall(r"^- key: (\S+) \|", prompt, flags=re.MULTILINE)


def _extract_ids(prompt: str) -> list[str]:
    return re.findall(r"^- id: (\S+) \|", prompt, flags=re.MULTILINE)


def _extract_section_refs(prompt: str) -> list[str]:
    return re.findall(r"^([A-Za-z0-9._:-]+:s\d+) \|", prompt, flags=re.MULTILINE)


def _step_payload(step: str, user_prompt: str) -> dict[str, Any]:
    if step == "plan_structure":
        want_depth_3 = "3 Ebenen" in user_prompt
        return {
            "order": "Themenfelder",
            "levels": ["Themenfeld", "Thema", "Fachbegriff"],
            "rationale": "Schulnah nach Themenfeldern gegliedert.",
            "description": _D60,
            "main_topics": [
                {
                    "title": f"Themenfeld {i}",
                    "shorttitle": f"TF {i}",
                    "from_inputs": False,
                    "children": [
                        {
                            "title": f"Thema {i}.{j}",
                            "shorttitle": f"T {i}.{j}",
                            "children": [
                                {"title": f"Begriff {i}.{j}.{g}", "shorttitle": f"B {i}.{j}.{g}", "children": []}
                                for g in range(1, 4)
                            ]
                            if want_depth_3
                            else [],
                        }
                        for j in range(1, 4)
                    ],
                }
                for i in range(1, 7)
            ],
        }
    if step == "describe_nodes":
        keys = _extract_keys(user_prompt)
        return {"nodes": [{"key": k, "description": _D60, "keywords": ["Physik", "Optik", "Unterricht"]} for k in keys]}
    if step == "assign_contents":
        ids = _extract_ids(user_prompt)
        tree_keys = re.findall(r"^(k-[a-z0-9-]+):", user_prompt, flags=re.MULTILINE)
        target = tree_keys[0] if tree_keys else "k-optik"
        return {
            "items": [
                {"id": item_id, "nodes": [{"key": target, "confidence": 0.9}], "off_topic": False, "excluded": False}
                for item_id in ids
            ]
        }
    if step == "map_outline":
        refs = _extract_section_refs(user_prompt)
        first = refs[:1]
        second = refs[1:2] or first
        return {
            "order": "Themenfelder",
            "levels": ["Themenfeld", "Thema"],
            "description": _D60,
            "nodes": [
                {
                    "title": "Wahrnehmung",
                    "shorttitle": "Wahrnehmung",
                    "section_ids": first,
                    "children": [
                        {"title": "Lichtquellen", "shorttitle": "Lichtquellen", "section_ids": first, "children": []},
                        {"title": "Schatten", "shorttitle": "Schatten", "section_ids": first, "children": []},
                        {"title": "Sehen", "shorttitle": "Sehen", "section_ids": first, "children": []},
                    ],
                },
                {
                    "title": "Grenzflächen",
                    "shorttitle": "Grenzflächen",
                    "section_ids": second,
                    "children": [
                        {"title": "Reflexion", "shorttitle": "Reflexion", "section_ids": second, "children": []},
                        {"title": "Brechung", "shorttitle": "Brechung", "section_ids": second, "children": []},
                        {"title": "Absorption", "shorttitle": "Absorption", "section_ids": second, "children": []},
                    ],
                },
            ],
        }
    if step == "improve_folders":
        return {"changes": [{"op": "rename", "key": "k-neuer-ordner-2", "title": "Spiegel"}]}
    if step == "group_contents":
        return {
            "order": "Themen",
            "levels": ["Thema", "Teilthema"],
            "description": _D60,
            "groups": [
                {
                    "title": f"Gruppe {i}",
                    "shorttitle": f"Gruppe {i}",
                    "description": _D60,
                    "keywords": ["Optik", "Licht", "Thema"],
                    "children": [
                        {
                            "title": f"Untergruppe {i}.{j}",
                            "shorttitle": f"UG {i}.{j}",
                            "description": _D60,
                            "keywords": ["Detail", "Beispiel", "Material"],
                            "children": [],
                        }
                        for j in range(1, 4)
                    ],
                }
                for i in range(1, 6)
            ],
        }
    if step == "interpret_feedback":
        return {"changes": [{"op": "add", "parent": None, "title": "Farben"}], "questions": []}
    if step == "split_node":
        return {
            "parts": [
                {"title": "Teil A", "child_keys": [], "content_ids": []},
                {"title": "Teil B", "child_keys": [], "content_ids": []},
            ]
        }
    return {"ok": True}


class StubOpenAIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.calls: list[RecordedCall] = []
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer((host, port), self._make_handler())
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="stub-openai", daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def reset(self) -> None:
        with self._lock:
            self.calls.clear()

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                headers = {k.lower(): v for k, v in self.headers.items()}
                with stub._lock:
                    stub.calls.append(RecordedCall(path=self.path, headers=headers, body=body))

                rf = body.get("response_format") or {}
                step = (rf.get("json_schema") or {}).get("name", "")
                messages = body.get("messages") or []
                user_prompt = messages[-1]["content"] if messages else ""
                payload = _step_payload(step, user_prompt)
                reply = {
                    "id": "chatcmpl-stub",
                    "object": "chat.completion",
                    "created": 1700000000,
                    "model": body.get("model", "stub-model"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 1200,
                        "completion_tokens": 200,
                        "total_tokens": 1400,
                        "prompt_tokens_details": {"cached_tokens": 1000},
                    },
                }
                raw = json.dumps(reply).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args: object) -> None:
                return

        return Handler

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()
