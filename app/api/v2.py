"""POST /v2/topic-tree."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import run_context
from app.api.examples import REQUEST_EXAMPLES
from app.pipeline import orchestrator
from app.pipeline.run_context import RunContext
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import TopicTreeResponseV2

router = APIRouter()

# Documents the bearer scheme in OpenAPI; the actual check happens in run_context (mode detection, plan E3).
_bearer = HTTPBearer(auto_error=False, description="Delegations-Token der b-api oder Dienst-Schlüssel")

_ERROR = {"content": {"application/json": {"example": {"error": {"code": "…", "message": "…", "trace_id": "…"}}}}}

DESCRIPTION = """
Erzeugt einen Themenbaum für einen von vier Use Cases (`use_case`) oder entwickelt einen bestehenden Entwurf
weiter (`mode: refine`). Inhalte (`items`) werden den Knoten zugeordnet; ihre `nodeId` wird nur durchgereicht.

Was nicht gelingt, steht unter `warnings`, was unklar ist unter `questions`. Die Antwort enthält in
`metadata.generation` alle Vorgaben; für den nächsten Durchlauf `collection` und `metadata.generation` als
`current_tree` zurückgeben.

Laufzeit: synchron, je nach Baumgröße 10 bis 120 Sekunden.
"""


@router.post(
    "/v2/topic-tree",
    summary="Themenbaum erzeugen oder weiterentwickeln",
    description=DESCRIPTION,
    tags=["Themenbaum v2"],
    response_class=JSONResponse,
    responses={
        200: {"model": TopicTreeResponseV2, "description": "Themenbaum"},
        401: {"description": "Fehlende oder ungültige Anmeldung", **_ERROR},
        422: {"description": "Ungültige oder unvollständige Anfrage", **_ERROR},
        502: {"description": "Sprachmodell lieferte keine verwertbare Antwort", **_ERROR},
        503: {"description": "Sprachmodell nicht erreichbar oder nicht konfiguriert", **_ERROR},
    },
)
async def topic_tree_v2(
    request_body: Annotated[TopicTreeRequestV2, Body(openapi_examples=REQUEST_EXAMPLES)],
    rc: Annotated[RunContext, Depends(run_context)],
    _: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> JSONResponse:
    response = await orchestrator.run(request_body, rc)
    return JSONResponse(response.dump())
