"""Routes for the optional built-in test UI (`/ui/`). Hidden from OpenAPI and disabled when `UI_ENABLED=false`."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.ui.presets import PRESETS
from app.version import service_version
from app.vocab.labels import scheme_options

_STATIC = Path(__file__).parent / "static"
_ASSETS: dict[str, str] = {
    "styles.css": "text/css; charset=utf-8",
    "tree.js": "application/javascript; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}

router = APIRouter(include_in_schema=False)


@router.get("/ui")
async def ui_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui/", status_code=307)


@router.get("/ui/")
async def ui_index() -> FileResponse:
    return FileResponse(_STATIC / "index.html", media_type="text/html; charset=utf-8")


@router.get("/ui/assets/{name}")
async def ui_asset(name: str) -> FileResponse:
    media_type = _ASSETS.get(name)
    if media_type is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(_STATIC / name, media_type=media_type)


@router.get("/ui/presets")
async def ui_presets() -> JSONResponse:
    return JSONResponse(
        {
            "version": service_version(),
            "presets": PRESETS,
            "vocabs": {
                "discipline": scheme_options("discipline"),
                "hochschulfaechersystematik": scheme_options("hochschulfaechersystematik", max_depth=2),
                "educationalContext": scheme_options("educationalContext"),
                "intendedEndUserRole": scheme_options("intendedEndUserRole"),
            },
        }
    )
