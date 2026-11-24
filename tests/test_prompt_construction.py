import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.DTOs.collection import Collection
from src.DTOs.properties import Properties
from src.structured_text_helper import generate_structured_text

# Importing the application otherwise fetches remote vocabularies at module load time.
with patch("rdflib.Graph.parse"):
    import main


class RecordingChatClient:
    def __init__(self):
        self.messages: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create_completion))

    async def create_completion(self, *, messages: list[dict], **_: object) -> SimpleNamespace:
        self.messages.append(messages)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))])


def _collection(title: str) -> Collection:
    return Collection(
        title=title,
        shorttitle=title,
        properties=Properties(
            cclom_general_keyword=[title.lower()],
            cm_description=[f"Ausführliche Beschreibung für {title}"],
            cm_title=[title],
        ),
    )


def test_system_prompt_contains_the_requested_max_description_length() -> None:
    chat_client = RecordingChatClient()

    asyncio.run(
        generate_structured_text(client=chat_client, prompt="Prompt", model="test-model", max_description_length=123)
    )

    system_prompt = chat_client.messages[0][0]["content"]
    assert "MAXIMAL 123 Wörter" in system_prompt
    assert "{max_description_length}" not in system_prompt


def test_topic_tree_prompts_list_previous_topics_by_title_only() -> None:
    prompts: list[str] = []

    async def generate_fake_topics(*, prompt: str, require_list: bool = True, **_: object):
        prompts.append(prompt)
        if not require_list:
            return {"collections": [_collection("Mechanik")], "description": "Physik"}
        if len(prompts) == 2:
            return [_collection("Kinematik")]
        return []

    with (
        patch.object(main, "AsyncOpenAI", lambda **_: object()),
        patch.object(main, "generate_structured_text", generate_fake_topics),
    ):
        response = TestClient(main.app).post(
            "/generate-topic-tree",
            json={"theme": "Physik", "num_main_topics": 1},
            headers={"Authorization": "Bearer caller-b-api-key"},
        )

    assert response.status_code == 200
    _, sub_topic_prompt, curriculum_prompt = prompts
    assert "- Mechanik\n" in sub_topic_prompt
    assert "- Kinematik\n" in curriculum_prompt
    for prompt in (sub_topic_prompt, curriculum_prompt):
        assert "properties=" not in prompt
        assert "Ausführliche Beschreibung" not in prompt
