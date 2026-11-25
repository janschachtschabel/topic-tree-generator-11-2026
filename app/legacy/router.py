import asyncio
import inspect
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

from app.context.tracing import get_trace, outgoing_headers
from app.legacy.auth import LegacyTarget, resolve_target
from app.legacy.dtos.collection import Collection
from app.legacy.dtos.description_request import DescriptionRequest
from app.legacy.dtos.properties import Properties
from app.legacy.dtos.topic_tree_request import TopicTreeRequest
from app.legacy.prompts import (
    DESCRIPTION_PROMPT_TEMPLATE,
    LP_PROMPT_TEMPLATE,
    MAIN_PROMPT_TEMPLATE,
    SUB_PROMPT_TEMPLATE,
)
from app.legacy.structured_text_helper import generate_structured_text
from app.legacy.vocab_helper import get_discipline_pref_labels, get_educational_context_pref_labels
from app.llm.client import acquire_llm_slot, shared_http_client
from app.settings import Settings, get_settings
from app.version import service_version

# ToDo: allow dynamic prompt updates
#  - prompts and basic instructions should allow for dynamic updates
#    - e.g. by fetching the prompt string from an edu-sharing node
#    - or via edu-sharing admin-tools

# ToDo: fix variable names and prompt placeholders
#  - either use German as our domain language for everything
#  - or properly translate everything to English

# Erlaubt, dass das Collection-Modell sich selbst referenziert (subcollections)
Collection.model_rebuild()
# ToDo: figure out why model_rebuild() is called here

API_VERSION = service_version()
settings = get_settings()
_DEFAULT_SETTINGS = settings
_REAL_ASYNC_OPENAI = AsyncOpenAI

b_api_key_scheme = HTTPBearer(auto_error=False)


def _active_settings(request: Request) -> Settings:
    if settings is not _DEFAULT_SETTINGS:
        return settings
    return getattr(request.app.state, "settings", None) or settings


def _build_openai_client(target: LegacyTarget) -> Any:
    kwargs: dict[str, Any] = {
        "api_key": target.api_key,
        "base_url": target.base_url,
        "max_retries": target.max_retries,
    }
    headers = outgoing_headers(get_trace())
    if AsyncOpenAI is _REAL_ASYNC_OPENAI:
        kwargs["default_headers"] = headers
        kwargs["http_client"] = shared_http_client()
        return AsyncOpenAI(**kwargs)
    try:
        params = inspect.signature(AsyncOpenAI).parameters
    except (TypeError, ValueError):
        return AsyncOpenAI(**kwargs)
    if "default_headers" in params:
        kwargs["default_headers"] = headers
    return AsyncOpenAI(**kwargs)


async def resolve_legacy_target(
    request: Request,
    _: Annotated[HTTPAuthorizationCredentials | None, Security(b_api_key_scheme)] = None,
) -> LegacyTarget:
    return resolve_target(request, _active_settings(request))


# Frozen legacy endpoints (v1). Behaviour must stay unchanged; new work goes to the v2 pipeline.
router = APIRouter()


@router.post(
    "/generate-topic-tree",
    response_model=dict,
    summary="Generiere einen Themenbaum",
    description="""
    Generiert einen strukturierten Themenbaum basierend auf den übergebenen Parametern.

    Der Themenbaum wird in folgender Hierarchie erstellt:
    1. Hauptthemen (z.B. "Mechanik", "Thermodynamik")
    2. Unterthemen (z.B. "Kinematik", "Dynamik")
    3. Lehrplanthemen (z.B. "Gleichförmige Bewegung", "Newtonsche Gesetze")

    Jeder Knoten im Themenbaum enthält:
    - Titel und Kurztitel
    - Beschreibung
    - Schlagworte (Keywords)
    - Standardisierte Metadaten (Properties)

    Optional können URIs für Fach und Bildungsstufe übergeben werden (via ``discipline_uri`` und ``educational_context_uri``). 
    Die URIs von Fach und Bildungsstufe werden als Metadaten in die Collections eingebettet und fließen als Kontext in die AI-Prompts ein.
    """,
    responses={
        200: {
            "description": "Erfolgreich generierter Themenbaum",
            "content": {
                "application/json": {
                    "example": {
                        "metadata": {
                            "title": "Physik in Anlehnung an die Lehrpläne der Sekundarstufe 2",
                            "description": "Themenbaum für Physik in der Sekundarstufe II",
                            "created_at": "2025-02-05T11:28:40+01:00",
                            "version": API_VERSION,
                            "author": "Themenbaum Generator",
                        },
                        "collection": [
                            {
                                "title": "Allgemeines",
                                "shorttitle": "Allg",
                                "properties": {
                                    "cclom:general_keyword": ["physik", "grundlagen", "sekundarstufe"],
                                    "ccm:collectionshorttitle": ["Mechanik"],
                                    "ccm:educationalcontext": [
                                        "http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_2"
                                    ],
                                    "ccm:educationalintendedenduserrole": [
                                        "http://w3id.org/openeduhub/vocabs/intendedEndUserRole/teacher"
                                    ],
                                    "ccm:taxonid": ["http://w3id.org/openeduhub/vocabs/discipline/460"],
                                    "cm:description": [
                                        "Mechanische Bewegungen und Kräfte bilden das Fundament der Physik. Schüler entdecken die Gesetze der Kinematik und Dynamik durch praktische Experimente und mathematische Modelle."
                                    ],
                                    "cm:title": ["Mechanik"],
                                },
                                "subcollections": [],
                            }
                        ],
                    }
                }
            },
        },
        401: {
            "description": "Fehlender oder ungültiger Authorization-Bearer-Header",
            "content": {"application/json": {"example": {"detail": "Authorization Bearer token required"}}},
        },
    },
    tags=["Themenbaum-Generator"],
)
async def generate_topic_tree(
    topic_tree_request: TopicTreeRequest,
    target: Annotated[LegacyTarget, Depends(resolve_legacy_target)],
):
    """
    Generiert einen strukturierten Themenbaum basierend auf den Eingabeparametern.

    - ``theme``: Hauptthema
    - ``num_main_topics``: Anzahl der Hauptthemen (1 bis 30)
    - ``num_subtopics``: Anzahl der Unterthemen pro Hauptthema (0 bis 20)
    - ``num_curriculum_topics``: Anzahl der Lehrplanthemen pro Unterthema (0 bis 20)
    - ``include_general_topic``: Falls True, fügt ein Hauptthema "Allgemeines" hinzu
    - ``include_methodology_topic``: Falls True, fügt ein Hauptthema "Methodik und Didaktik" hinzu
    - ``max_description_length``: Maximale Anzahl von Wörtern für Beschreibungstexte (Default: 70, Bereich: 40-200)
    - ``discipline_uri``: Falls übergeben, werden diese URIs in den ``ccm:taxonid``-Properties eingebettet und fließen als Kontext in die AI-Prompts ein
    - ``educational_context_uri``: Falls übergeben, werden diese URIs in den ``ccm:educationalcontext``-Properties eingebettet und fließen als Kontext in die AI-Prompts ein
    - ``model``: Optionaler Legacy-Parameter, der ignoriert wird. Das Modell wird ausschließlich serverseitig ausgewählt.
    """
    logger.info(
        f"Legacy topic-tree request received (main={topic_tree_request.num_main_topics}, "
        f"sub={topic_tree_request.num_subtopics}, lp={topic_tree_request.num_curriculum_topics})"
    )
    try:
        client = _build_openai_client(target)
    except Exception:
        raise HTTPException(status_code=500, detail="LLM-Client-Initialisierung fehlgeschlagen.")

    try:
        # 2) Spezialanweisungen für Hauptthemen (z.B. Allgemeines, Methodik etc.)
        special_instructions = []
        if topic_tree_request.include_general_topic:
            special_instructions.append("1) Hauptthema 'Allgemeines' an erster Stelle")
        if topic_tree_request.include_methodology_topic:
            special_instructions.append("2) Hauptthema 'Methodik und Didaktik' an letzter Stelle")
        special_instructions = (
            "\n".join(special_instructions) if special_instructions else "Keine besonderen Anweisungen."
        )

        # 2a)
        context_info = []
        if topic_tree_request.discipline_uri:
            context_info.append(f"Fachbereich-URIs: {', '.join(topic_tree_request.discipline_uri)}")
            if isinstance(topic_tree_request.discipline_uri, list):
                _discipline_set = set()
                for _discipline_uri in topic_tree_request.discipline_uri:  # type: str
                    _discipline_pref_labels = get_discipline_pref_labels(_discipline_uri)
                    if _discipline_pref_labels:
                        _discipline_set.update(_discipline_pref_labels)
                if _discipline_set:
                    context_info.append(f"Fachbereich: {list(_discipline_set)}")
        if topic_tree_request.educational_context_uri:
            context_info.append(f"Bildungsstufe-URIs: {', '.join(topic_tree_request.educational_context_uri)}")
            if isinstance(topic_tree_request.educational_context_uri, list):
                _edu_context_set = set()
                for _uri in topic_tree_request.educational_context_uri:  # type: str
                    # example _uri value: "http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1"
                    _edu_context_pref_labels = get_educational_context_pref_labels(_uri)
                    if _edu_context_pref_labels:
                        _edu_context_set.update(_edu_context_pref_labels)
                if _edu_context_set:
                    context_info.append(f"Zielgruppe / Bildungsstufe: {list(_edu_context_set)}")
        context_instructions = f"Kontext-Informationen:\n{'\n'.join(context_info)}" if context_info else ""

        logger.info(f"Generating {topic_tree_request.num_main_topics} main topics ('Hauptthemen') ...")

        # 3) Hauptthemen generieren
        response = await generate_structured_text(
            client=client,
            prompt=MAIN_PROMPT_TEMPLATE.format(
                themenbaumthema=topic_tree_request.theme,
                num_main=topic_tree_request.num_main_topics,
                existing_titles="",
                special_instructions=special_instructions,
                context_instructions=context_instructions,
            ),
            model=target.model,
            max_description_length=topic_tree_request.max_description_length,
            concurrency=target.concurrency,
            require_list=False,
        )
        if not response:
            raise HTTPException(status_code=500, detail="Fehler bei der Generierung der Hauptthemen")

        main_topics = response["collections"]
        description = response["description"]
        logger.info(f"Received {len(main_topics)} main topics. Generating subtopics next.")
        # we need to keep track of existing main topics
        # (to avoid duplicates and improve the quality of the generated descriptions below)
        _previous_main_topic_titles = [f"- {main_topic.title}" for main_topic in main_topics]
        _previous_main_topic_titles = (
            "\n".join(_previous_main_topic_titles)
            if _previous_main_topic_titles
            else "Keine weiteren Hauptthemen vorhanden."
        )

        # 4) Für jedes Hauptthema die Unterthemen generieren
        sub_topic_tasks = []
        for main_topic in main_topics:
            logger.info(f"Creating subtopic ('Unterthemen') task for '{main_topic.title}'")
            _subtopic_prompt = SUB_PROMPT_TEMPLATE.format(
                themenbaumthema=topic_tree_request.theme,
                main_theme=main_topic.title,
                num_sub=topic_tree_request.num_subtopics,
                context_instructions=context_instructions,
                previous_main_topics=_previous_main_topic_titles,
            )
            _task = generate_structured_text(
                client=client,
                prompt=_subtopic_prompt,
                model=target.model,
                max_description_length=topic_tree_request.max_description_length,
                concurrency=target.concurrency,
            )
            sub_topic_tasks.append(_task)

        sub_topic_results = await asyncio.gather(*sub_topic_tasks)

        for i, main_topic in enumerate(main_topics):
            sub_topics = sub_topic_results[i]
            if sub_topics:
                main_topic.subcollections = sub_topics

        logger.info("Received subtopics ('Unterthemen'). Beginning generation of curriculum ('Lehrplan') next.")

        # 5) Für jedes Unterthema die Lehrplanthemen generieren
        lp_tasks = []
        lp_mapping = []  # List to track which main_topic and sub_topic each task corresponds to
        for main_topic in main_topics:
            # keep track of previously generated sub_topic titles (to reduce duplicates and improve the context)
            _previous_sub_topic_titles = [f"- {sub_topic.title}" for sub_topic in main_topic.subcollections]
            _previous_sub_topic_titles = (
                "\n".join(_previous_sub_topic_titles)
                if _previous_sub_topic_titles
                else "Keine weiteren Unterthemen vorhanden."
            )

            for sub_topic in main_topic.subcollections:
                logger.info(f"Generating curriculum ('Lehrplan') task for '{sub_topic.title}'")
                _lp_prompt = LP_PROMPT_TEMPLATE.format(
                    themenbaumthema=topic_tree_request.theme,
                    main_theme=main_topic.title,
                    sub_theme=sub_topic.title,
                    num_lp=topic_tree_request.num_curriculum_topics,
                    context_instructions=context_instructions,
                    previous_main_topics=_previous_main_topic_titles,
                    previous_sub_topics=_previous_sub_topic_titles,
                )
                _lp_task = generate_structured_text(
                    client=client,
                    prompt=_lp_prompt,
                    model=target.model,
                    max_description_length=topic_tree_request.max_description_length,
                    concurrency=target.concurrency,
                )
                lp_tasks.append(_lp_task)
                lp_mapping.append((main_topic, sub_topic))

        lp_results = await asyncio.gather(*lp_tasks)

        for i, (main_topic, sub_topic) in enumerate(lp_mapping):
            lp_topics = lp_results[i]
            if lp_topics:
                sub_topic.subcollections = lp_topics

        # 6) Properties für alle Knoten nochmal updaten mit den (ggf.) übergebenen URIs
        for main_topic in main_topics:
            main_topic.properties = Properties(
                cm_title=[main_topic.title],
                ccm_collectionshorttitle=[main_topic.shorttitle],
                cm_description=main_topic.properties.cm_description,
                cclom_general_keyword=main_topic.properties.cclom_general_keyword,
                ccm_taxonid=topic_tree_request.discipline_uri or [],
                ccm_educationalcontext=topic_tree_request.educational_context_uri or [],
            )

            for sub_topic in main_topic.subcollections:
                sub_topic.properties = Properties(
                    cm_title=[sub_topic.title],
                    ccm_collectionshorttitle=[sub_topic.shorttitle],
                    cm_description=sub_topic.properties.cm_description,
                    cclom_general_keyword=sub_topic.properties.cclom_general_keyword,
                    ccm_taxonid=topic_tree_request.discipline_uri or [],
                    ccm_educationalcontext=topic_tree_request.educational_context_uri or [],
                )

                for lp_topic in sub_topic.subcollections:
                    lp_topic.properties = Properties(
                        cm_title=[lp_topic.title],
                        ccm_collectionshorttitle=[lp_topic.shorttitle],
                        cm_description=lp_topic.properties.cm_description,
                        cclom_general_keyword=lp_topic.properties.cclom_general_keyword,
                        ccm_taxonid=topic_tree_request.discipline_uri or [],
                        ccm_educationalcontext=topic_tree_request.educational_context_uri or [],
                    )

        # 7) Finale Daten strukturieren (Metadaten + Collection-Liste)
        final_data = {
            "metadata": {
                "title": topic_tree_request.theme,
                "description": description,
                "target_audience": "Lehrkräfte",
                "created_at": datetime.now().isoformat(),
                "version": API_VERSION,
                "author": "Themenbaum Generator",
            },
            "collection": [topic.to_dict() for topic in main_topics],
        }

        # ToDo: actually return a JSON object (instead of a python dict) as soon as you're done with debugging
        return final_data

    except HTTPException:
        raise
    except Exception:
        logger.error("Unhandled error while generating legacy topic tree")
        raise HTTPException(status_code=500, detail="Fehler bei der Generierung.")


@router.post(
    path="/generate-collection-description",
    response_model=str,
    tags=["Sammlungsbeschreibungen generieren"],
    responses={
        401: {
            "description": "Fehlender oder ungültiger Authorization-Bearer-Header",
            "content": {"application/json": {"example": {"detail": "Authorization Bearer token required"}}},
        },
    },
    description="""
    Generiert eine ansprechende Beschreibung für eine Sammlung von Bildungsressourcen
    basierend auf gegebenem Text und Kontext.
    
    **Parameter:**
    - `max_description_length`: Maximale Anzahl von Wörtern für Beschreibungstexte (Default: 70, Bereich: 40-200)
    - `model`: Optionaler Legacy-Parameter, der aus Kompatibilitätsgründen akzeptiert, aber ignoriert wird. Das Modell wird ausschließlich serverseitig ausgewählt.
    - `text_context`: Text und Kontext für die Beschreibung (z.B. Thema, Zielgruppe, Inhalte)
    """,
)
async def generate_collection_description(
    description_request: DescriptionRequest,
    target: Annotated[LegacyTarget, Depends(resolve_legacy_target)],
) -> str:
    """
    Generiert eine ansprechende Sammlungsbeschreibung basierend auf gegebenem Text und Kontext.

    :param description_request: Request mit text_content, max_description_length und optionalem, ignoriertem model-Parameter
    :return: Generierter Beschreibungstext als `str`
    :raises HTTPException: Falls ein Fehler bei der Generierung aufgetreten ist
    """
    logger.info(
        f"Legacy collection-description request received (max_words={description_request.max_description_length})"
    )

    try:
        client = _build_openai_client(target)
    except Exception:
        raise HTTPException(status_code=500, detail="LLM-Client-Initialisierung fehlgeschlagen.")

    try:
        # prepare the prompt with the given parameters
        formatted_prompt = DESCRIPTION_PROMPT_TEMPLATE.format(
            text_context=description_request.text_context,
            max_description_length=description_request.max_description_length,
        )
        # ToDo: the "AI" generally ignores the max_description_length parameter
        #  because it has no concept of character length and does not count characters.
        # see: https://help.openai.com/en/articles/5072518-controlling-the-length-of-openai-model-responses
        # GPT-5 offers "verbosity"-settings, which might be a solution
        _system_prompt: ChatCompletionSystemMessageParam = ChatCompletionSystemMessageParam(
            content="Du bist ein Experte für die Erstellung ansprechender Beschreibungstexte für Bildungsressourcen. "
            "Antworte IMMER nur mit dem reinen Beschreibungstext. "
            "NIEMALS mit JSON, Strukturen oder Anführungszeichen. NUR der reine Text. "
            "WICHTIG: Nutze die VOLLSTÄNDIGE erlaubte Zeichenlänge - "
            "schreibe ausführlich und detailliert bis zum Maximum.",
            role="system",
        )
        _user_prompt: ChatCompletionUserMessageParam = ChatCompletionUserMessageParam(
            content=formatted_prompt,
            role="user",
        )
        _ts_before: datetime = datetime.now()
        async with acquire_llm_slot(target.concurrency):
            response = await client.chat.completions.create(
                model=target.model,
                messages=[
                    _system_prompt,
                    _user_prompt,
                ],
                # temperature=0.7,
            )
        # attention: setting the `max_token`-Parameter causes the API to return more text than requested.
        # e.g.: when setting a max_token limit of 600 while also using a max_description_length of 200,
        # it will rarely result in a response within the 200-char limit!

        _ts_after: datetime = datetime.now()
        _delta: timedelta = _ts_after - _ts_before
        logger.debug(f"LLM-API-Call took {_delta.total_seconds()} seconds.")

        _description = response.choices[0].message.content
        return _description
    except HTTPException:
        raise
    except Exception:
        logger.error("Error while generating legacy collection description")
        raise HTTPException(status_code=500, detail="Fehler bei der Generierung.")


@router.get(path="/", include_in_schema=False)
async def root_endpoint():
    return {
        "message": "Hi there! The API Documentation is available in two formats: "
        "Please take a look at the /docs endpoint (for the Swagger UI) - or - "
        "take a look at the /redoc endpoint for an alternative documentation (by Redoc).",
        "API docs": {"swagger": "/docs", "redoc": "/redoc"},
    }
