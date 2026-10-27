from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from app.actions import check, explain, practice
from app.config import settings
from app.llm import LLMError
from app.safety import check_safety
from app.schemas import ChatRequest, ChatResponse, IntentEnum

app = FastAPI(title="ShelterED AI")


@app.exception_handler(LLMError)
async def llm_error_handler(_, exc: LLMError):
    return JSONResponse(
        status_code=503,
        content={"code": "model_unavailable", "message": str(exc)},
    )


def auth(key: str | None) -> None:
    if key != settings.INTERNAL_KEY:
        raise HTTPException(status_code=401, detail={"code": "unauthorized"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ai/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, x_internal_key: str | None = Header(default=None)):  # <--- Додали async
    auth(x_internal_key)

    if req.action == "check" and req.task is None:
        raise HTTPException(status_code=422, detail={"code": "task_required"})

    if req.action == "practice" and req.task is None and not (req.topic or "").strip():
        raise HTTPException(status_code=422, detail={"code": "topic_required"})

    safe_text = check_safety(req.message or "")
    if safe_text:
        return ChatResponse(reply=safe_text, intent=IntentEnum.safety, topic_id=req.topic_id)

    handlers = {"explain": explain.run, "practice": practice.run, "check": check.run}
    return await handlers[req.action](req)  # <--- Додали await