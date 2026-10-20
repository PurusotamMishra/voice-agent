"""FastAPI layer (architecture §10). Thin on purpose: parse the request, stream run_turn's events."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from voice_agent.api.stream import TurnInput, VoiceServices, run_turn
from voice_agent.config import Settings
from voice_agent.telemetry.turnlog import append_turn

ServicesFactory = Callable[[Settings], AbstractAsyncContextManager[VoiceServices]]


class ClientTimings(BaseModel):
    """Browser stamps, epoch ms (J4). t_speech_end is the button release (or typed submit)."""

    t_speech_end: float | None = None
    t_first_audio: float


def create_app(settings: Settings, services: ServicesFactory) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services(settings) as svc:
            app.state.svc = svc
            yield

    app = FastAPI(title="Vyngo voice vehicle search", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        return {"session_id": uuid4().hex[:12]}

    @app.post("/api/turn")
    async def turn(
        request: Request,
        session_id: str = Form(...),
        text: str | None = Form(None),
        language: Literal["en", "hi-en"] = Form("en"),
        audio_seconds: float = Form(0.0),
        audio: UploadFile | None = File(None),  # noqa: B008 (FastAPI idiom)
    ) -> StreamingResponse:
        if audio is None and not (text and text.strip()):
            raise HTTPException(status_code=400, detail="send audio or text")
        inp = TurnInput(
            session_id=session_id,
            text=text,
            audio=await audio.read() if audio is not None else None,
            filename=(audio.filename if audio is not None else None) or "speech.webm",
            content_type=(audio.content_type if audio is not None else None) or "audio/webm",
            language=language,
            audio_seconds=audio_seconds,
        )
        events = run_turn(request.app.state.svc, inp)
        return StreamingResponse(_ndjson(events), media_type="application/x-ndjson")

    @app.post("/api/turn/{turn_id}/client-timings", status_code=204)
    async def client_timings(turn_id: str, body: ClientTimings) -> Response:
        first_audio = None
        if body.t_speech_end is not None:
            first_audio = round(body.t_first_audio - body.t_speech_end, 1)
        record = {
            "turn_id": turn_id,
            **body.model_dump(),
            "speech_end_to_first_audio_ms": first_audio,
        }
        append_turn(settings.client_timings_path, record)
        return Response(status_code=204)

    @app.get("/api/session/{session_id}/state")
    async def session_state(session_id: str, request: Request) -> dict[str, Any]:
        state: dict[str, Any] = await request.app.state.svc.runner.state(session_id)
        return state

    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        svc: VoiceServices = request.app.state.svc  # the lifespan opened the DB, so it is up
        return {
            "ok": True,
            "llm": settings.llm_provider,
            "stt": {lang: choice.stt.name for lang, choice in svc.stt.items()},
            "tts": svc.tts.name if svc.tts is not None else "client",
            "tts_mode": svc.tts_mode,
        }

    return app


async def _ndjson(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[bytes]:
    async for event in events:
        yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
