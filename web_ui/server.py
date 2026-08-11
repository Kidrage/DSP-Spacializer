"""FastAPI adapter for the local-only calibration mixer."""

from __future__ import annotations

from pathlib import Path
import re

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from spatial_mixer.campaign import MixerService


STATIC_DIR = Path(__file__).with_name("static")


def create_app(service: MixerService) -> FastAPI:
    app = FastAPI(title="Seven-zone calibration mixer", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    @app.get("/api/state")
    def state():
        return service.open_campaign()

    @app.patch("/api/draft")
    def patch_draft(payload: dict = Body(...)):
        return service.patch_draft(payload)

    @app.patch("/api/monitor")
    def patch_monitor(payload: dict = Body(...)):
        return service.patch_monitor(payload)

    @app.patch("/api/audition")
    def patch_audition(payload: dict = Body(...)):
        return service.patch_audition(payload)

    @app.post("/api/preview")
    def preview(payload: dict = Body(...)):
        return service.request_preview(
            track_id=str(payload.get("track_id", "")),
            start_s=float(payload.get("start_s", 0.0)),
            duration_s=float(payload.get("duration_s", 20.0)),
        )

    @app.post("/api/extraction/analyze")
    def analyze_extraction(payload: dict = Body(...)):
        return service.analyze_extraction(
            track_id=str(payload.get("track_id", "")),
            start_s=float(payload.get("start_s", 0.0)),
            duration_s=float(payload.get("duration_s", 20.0)),
        )

    @app.post("/api/comparisons")
    def comparison(payload: dict = Body(...)):
        return service.record_comparison(
            track_id=str(payload.get("track_id", "")),
            category=str(payload.get("category", "")),
            choice=str(payload.get("choice", "")),
            scores=payload.get("scores", {}),
            objective_gate=payload.get("objective_gate", {}),
            notes=str(payload.get("notes", "")),
        )

    @app.post("/api/promote")
    def promote(payload: dict = Body(default={})):
        return service.promote_profile(override_reason=payload.get("override_reason"))

    @app.get("/api/audio/{preview_id}/{variant}")
    def audio(preview_id: str, variant: str):
        if not re.fullmatch(r"[0-9a-f]{24}", preview_id) or variant not in {"reference", "a", "b"}:
            raise HTTPException(status_code=404, detail="preview audio not found")
        path = (service.workspace_dir / "previews" / preview_id / f"{variant}.wav").resolve()
        if not path.is_relative_to(service.workspace_dir) or not path.is_file():
            raise HTTPException(status_code=404, detail="preview audio not found")
        return FileResponse(path, media_type="audio/wav", filename=f"{variant}.wav")

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc: ValueError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app
