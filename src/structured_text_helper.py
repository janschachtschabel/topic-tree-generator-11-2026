import json
from typing import Optional, List

from loguru import logger
from openai import AsyncOpenAI
from pydantic import ValidationError

from src.DTOs.collection import Collection
from src.DTOs.properties import Properties
from src.prompts import BASE_INSTRUCTIONS


async def generate_structured_text(
    client: AsyncOpenAI, prompt: str, model: str, max_description_length: int, require_list=True
) -> Optional[List[Collection] | dict]:
    """
    Schickt die Prompt-Anfrage an das konfigurierte LLM
    und parst das zurückgegebene reine JSON-Array in eine Liste von Collection-Objekten.
    """
    try:
        system_prompt = BASE_INSTRUCTIONS.format(max_description_length=max_description_length)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            # max_tokens=2000,
            # temperature=0.7,
        )
        content = resp.choices[0].message.content
        if not content.strip():
            raise Exception("The AI model returned an empty response.")

        # Entfernt mögliche Triple-Backticks oder JSON-Syntax, die stören könnten
        raw = content.strip().strip("```").strip("```json").strip()
        # Debug-Ausgabe
        # print(f"Raw response: {raw}")
        data = None
        json_data = None
        if require_list:
            data = json.loads(raw)
            # Falls nur ein Dict zurückkam, in eine Liste packen
            if not isinstance(data, list):
                data = [data]
        else:
            json_data = json.loads(raw)
            data = json_data["collections"]

        results = []
        for item in data:
            title = item.get("title", "")
            shorttitle = item.get("shorttitle", "")
            desc = item.get("description", "")
            keywords = item.get("keywords", [])

            if desc:
                # check the length of the description w.r.t. the word-limit (which is defined in prompts.py)
                logger.debug(f'Description length for "{title}": {len(desc.split())} words ({len(desc)} chars)')
                pass
            # Falls das Modell aus irgendeinem Grund leere Werte geliefert hat
            if not desc:
                desc = f"Beschreibung für {title}"
            if not keywords:
                keywords = [title.lower()]
            # Baue ein Properties-Objekt mit noch leeren URIs
            prop = Properties(
                cclom_general_keyword=keywords,
                ccm_collectionshorttitle=[shorttitle],
                ccm_educationalcontext=[],
                ccm_educationalintendedenduserrole=["http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"],
                ccm_taxonid=[],
                cm_description=[desc],
                cm_title=[title],
            )

            # Erstelle das Collection-Objekt
            c = Collection(title=title, shorttitle=shorttitle, properties=prop, subcollections=[])
            results.append(c)
        if require_list:
            return results
        else:
            json_data["collections"] = results
            return json_data
    except json.JSONDecodeError as jde:
        logger.error(f"JSON Decode Error: {jde}")
        return []  # ToDo: replace this dirty workaround with proper exception handling
        # raise Exception(f"JSON Decode Error: {jde}")
        # ToDo: there was not enough time for proper exception handling:
        #  raising Exceptions here causes Internal Server Errors
        #  when trying to collect the awaited task results with asyncio.gather() in main.py
    except ValidationError as ve:
        logger.error(f"Validation Error: {ve}")
        return []  # ToDo: replace this dirty workaround with proper exception handling
        # raise Exception(f"Validation Error: {ve}")
    except Exception as e:
        logger.error(f"General Error: {e}")
        return []  # ToDo: replace this dirty workaround with proper exception handling
        # raise Exception(f"Fehler bei der Anfrage: {e}")
