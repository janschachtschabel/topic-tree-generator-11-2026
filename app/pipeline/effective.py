"""Fill settings the caller left out from `current_tree.generation` (Spec: "Fehlen in der Anfrage Vorgaben,
übernimmt der Dienst sie aus generation"). Only fields not explicitly sent are taken over."""

from app.schemas.request_v2 import TopicTreeRequestV2


def effective_request(req: TopicTreeRequestV2) -> TopicTreeRequestV2:
    generation = req.current_tree.generation if req.current_tree else None
    if generation is None:
        return req
    sent = req.model_fields_set
    updates = {}
    if "topic" not in sent and generation.topic:
        updates["topic"] = generation.topic
    for name in ("shape", "hints", "options"):
        if name not in sent and getattr(generation, name) is not None:
            updates[name] = getattr(generation, name)
    if "frame" in sent and not any(req.frame.model_dump().values()) and generation.frame is not None:
        updates["frame"] = generation.frame
    return req.model_copy(update=updates) if updates else req
