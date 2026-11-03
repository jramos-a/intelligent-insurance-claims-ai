import time, threading
from fastapi import FastAPI, HTTPException, UploadFile, Depends, Request, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from .service import Store
from .security import need, mask, Principal
from .monitoring import M, psi
from . import assistant, speech
from .nlp import classify, evaluate as eval_cls
from .extract import extract
from .ner import entities
from .rag import retrieve
app = FastAPI(title="Insurance Claims AI", version="0.3.0"); S = Store()
ANY, SPEC = need("customer", "specialist"), need("specialist")
_cache = {}; _lock = threading.Lock()
@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter(); status = 500
    try: resp = await call_next(request); status = resp.status_code; return resp
    finally: M.record(request.scope.get("route").path if request.scope.get("route") else request.url.path, (time.perf_counter() - t0) * 1000, status)
def _err(status, code, msg): return JSONResponse({"error": {"code": code, "message": msg}}, status_code=status)
@app.exception_handler(HTTPException)
async def http_err(_, e): return _err(e.status_code, f"http_{e.status_code}", str(e.detail))
@app.exception_handler(RequestValidationError)
async def val_err(_, e): return _err(422, "validation_error", "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))
class NewClaim(BaseModel): statement: str = Field(min_length=10, max_length=20000)
class Note(BaseModel): note: str = Field(min_length=3)
class Assign(BaseModel): assignee: str
class DocRequest(BaseModel): items: list[str] = Field(min_length=1)
class Chat(BaseModel): message: str = Field(min_length=2, max_length=2000)
class Text(BaseModel): text: str = Field(min_length=3)
def _load(cid, p: Principal):
    c = S.get(cid)
    if not c or (p.role == "customer" and c["owner"] != p.sub): raise HTTPException(404, "claim not found")  # case-level isolation: 404, not 403, to avoid leaking existence
    return c
def _view(c, p):
    v = {k: x for k, x in c.items() if k not in ("hashes",)}; v["statement"] = mask(c["statement"]); v["documents"] = [{"name": d["name"], "text": mask(d["text"])} for d in c["documents"]]
    if p.role == "customer": v.pop("notes", None); v["analysis"] = v["analysis"] and {k: x for k, x in v["analysis"].items() if k != "review_package"}
    return v
@app.get("/health")
def health(): return {"status": "ok"}
@app.get("/auth/me")
def me(p=Depends(ANY)): return {"role": p.role, "sub": p.sub}
@app.post("/claims", status_code=201)
def create(b: NewClaim, p=Depends(ANY)): return _view(S.create(b.statement, p.sub), p)
@app.get("/claims")
def list_claims(status: str | None = None, assignee: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), p=Depends(ANY)):
    items, total = S.list(p.sub if p.role == "customer" else None, status, assignee, offset, limit)
    return {"items": [{k: i[k] for k in ("id", "status", "owner", "assignee", "created")} | {"claim_type": (i["analysis"] or {}).get("classification", {}).get("claim_type")} for i in items], "total": total, "offset": offset, "limit": limit}
@app.get("/claims/{cid}")
def get(cid: str, p=Depends(ANY)): return _view(_load(cid, p), p)
@app.delete("/claims/{cid}", status_code=204)
def erase(cid: str, p=Depends(SPEC)): _load(cid, p); S.delete(cid, p.sub)
@app.post("/claims/{cid}/documents", status_code=201)
async def upload(cid: str, file: UploadFile, p=Depends(ANY)):
    c = _load(cid, p)
    try: S.add_doc(c, file.filename, await file.read(), p.sub)
    except TypeError as e: raise HTTPException(415, str(e))
    except FileExistsError as e: raise HTTPException(409, str(e))
    except OverflowError as e: raise HTTPException(413, str(e))
    except Exception as e: raise HTTPException(422, f"unreadable document: {type(e).__name__}")
    return {"ok": True}
@app.post("/claims/{cid}/process")
def process(cid: str, p=Depends(ANY)):
    c = _load(cid, p)
    try: S.process(c, p.role)
    except ValueError as e: raise HTTPException(409, str(e))
    M.pred[c["analysis"]["classification"]["claim_type"]] += 1; return _view(S.get(cid), p)["analysis"]
@app.get("/claims/{cid}/summary")
def summary(cid: str, p=Depends(ANY)):
    a = _load(cid, p)["analysis"]
    if not a: raise HTTPException(409, "claim not processed yet")
    return {"summary": a["summary"], "warnings": a["validation"], "disclaimer": "AI-prepared; coverage decisions are made by a human specialist"}
@app.post("/claims/{cid}/chat")
def chat(cid: str, b: Chat, p=Depends(ANY)):
    c = _load(cid, p); r = assistant.chat(c, b.message, p.role); S.save(c); M.tokens += r["est_tokens"]; return r
@app.get("/claims/{cid}/messages")
def messages(cid: str, p=Depends(ANY)): return _load(cid, p)["messages"]
@app.post("/claims/{cid}/assign")
def assign(cid: str, b: Assign, p=Depends(SPEC)): c = _load(cid, p); S.assign(c, b.assignee, p.sub); return {"assignee": b.assignee}
@app.post("/claims/{cid}/notes", status_code=201)
def note(cid: str, b: Note, p=Depends(SPEC)): c = _load(cid, p); S.add_note(c, p.sub, b.note); return {"ok": True}
@app.post("/claims/{cid}/document-requests", status_code=201)
def doc_request(cid: str, b: DocRequest, p=Depends(SPEC)): c = _load(cid, p); S.request_docs(c, p.sub, b.items); return {"ok": True}
@app.post("/claims/{cid}/review")
def review(cid: str, b: Note, p=Depends(SPEC)):
    c = _load(cid, p)
    try: S.resolve(c, p.sub, b.note)
    except ValueError as e: raise HTTPException(409, str(e))
    return _view(c, p)
@app.get("/claims/{cid}/audit")
def audit(cid: str, p=Depends(SPEC)): _load(cid, p); return S.audit(cid)
@app.get("/review-queue")
def queue(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), p=Depends(SPEC)):
    items, total = S.list(None, "HUMAN_REVIEW", None, offset, limit)
    return {"items": [{"id": i["id"], "assignee": i["assignee"], "claim_type": i["analysis"]["classification"]["claim_type"], "warnings": i["analysis"]["validation"], "package": i["analysis"]["review_package"]} for i in items], "total": total}
@app.post("/classify")
def classify_ep(b: Text, p=Depends(ANY)): return classify(b.text)
@app.post("/extract")
def extract_ep(b: Text, p=Depends(ANY)): return extract(b.text) | {"entities": entities(b.text)}
@app.get("/policy/search")
def policy_search(q: str = Query(min_length=2), mode: str = Query("hybrid_rerank", pattern="^(vector|hybrid|hybrid_rerank|agentic)$"), claim_type: str | None = None, k: int = Query(3, ge=1, le=10), p=Depends(ANY)):
    return retrieve(q, claim_type, k, p.role, mode)
@app.post("/speech/transcribe")
async def transcribe(file: UploadFile, p=Depends(ANY)): return {"text": speech.get_stt().transcribe(await file.read())}
@app.get("/evaluation")
def evaluation(refresh: bool = False, p=Depends(SPEC)):
    from .evaluation import run_all
    with _lock:
        if refresh or "eval" not in _cache: _cache["eval"] = run_all(log=refresh)
    return _cache["eval"]
@app.get("/monitoring")
def monitoring(p=Depends(SPEC)):
    from .data import generate
    from collections import Counter
    ref = Counter(t for _, t in generate()); snap = M.snapshot(); snap["drift_psi_predicted_class_vs_training"] = round(psi(ref, M.pred), 4) if M.pred else None; return snap
@app.get("/dashboard")
def dashboard(p=Depends(SPEC)):
    items, total = S.list(None, None, None, 0, 100); from collections import Counter
    return {"total_claims": total, "by_status": dict(Counter(i["status"] for i in items)), "by_type": dict(Counter((i["analysis"] or {}).get("classification", {}).get("claim_type", "unclassified") for i in items)),
            "awaiting_review": sum(i["status"] == "HUMAN_REVIEW" for i in items)}
