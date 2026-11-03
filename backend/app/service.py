import hashlib, itertools, datetime as dt, os, re, time
from sqlalchemy import create_engine, Column, String, Integer, JSON, select, func
from sqlalchemy.orm import declarative_base, sessionmaker
from .ingest import extract_text
from .rag import retrieve
from .llm.providers import sanitize
Base = declarative_base()
class ClaimRow(Base):
    __tablename__ = "claims"; id = Column(String, primary_key=True); status = Column(String, index=True); owner = Column(String, index=True); assignee = Column(String, index=True); created = Column(String); data = Column(JSON)
class AuditRow(Base):
    __tablename__ = "audit_log"; id = Column(Integer, primary_key=True, autoincrement=True); ts = Column(String); claim_id = Column(String, index=True); actor = Column(String); action = Column(String); detail = Column(JSON)
STATES = ["SUBMITTED", "INTAKE", "DOCUMENT_PROCESSING", "INFORMATION_VALIDATION", "POLICY_REVIEW", "HUMAN_REVIEW", "RESOLVED"]
MAX_UPLOAD = 10 * 1024 * 1024
class Store:
    def __init__(self, url=None):
        self.engine = create_engine(url or os.getenv("DATABASE_URL", "sqlite:///./claims.db")); Base.metadata.create_all(self.engine); self.S = sessionmaker(self.engine)
    def _now(self): return dt.datetime.now(dt.UTC).isoformat()
    def log(self, cid, actor, action, **d):
        with self.S.begin() as s: s.add(AuditRow(ts=self._now(), claim_id=cid, actor=actor, action=action, detail=d))
    def audit(self, cid):
        with self.S() as s: return [{"ts": a.ts, "claim": a.claim_id, "actor": a.actor, "action": a.action, **(a.detail or {})} for a in s.scalars(select(AuditRow).where(AuditRow.claim_id == cid).order_by(AuditRow.id))]
    def get(self, cid):
        with self.S() as s: r = s.get(ClaimRow, cid); return dict(r.data) if r else None
    def save(self, c):
        with self.S.begin() as s: s.merge(ClaimRow(id=c["id"], status=c["status"], owner=c["owner"], assignee=c.get("assignee"), created=c["created"], data=c))
    def create(self, statement, owner):
        with self.S() as s: n = s.scalar(select(func.count(ClaimRow.id))) + 1
        c = {"id": f"C{n:05d}-{hashlib.sha1(self._now().encode()).hexdigest()[:4]}", "status": "SUBMITTED", "owner": owner, "assignee": None, "created": self._now(), "statement": sanitize(statement),
             "documents": [], "hashes": [], "analysis": None, "review": None, "notes": [], "doc_requests": [], "messages": []}
        self.save(c); self.log(c["id"], owner, "created"); return c
    def list(self, owner=None, status=None, assignee=None, offset=0, limit=20):
        q = select(ClaimRow).order_by(ClaimRow.created.desc())
        for col, v in ((ClaimRow.owner, owner), (ClaimRow.status, status), (ClaimRow.assignee, assignee)):
            if v: q = q.where(col == v)
        with self.S() as s:
            total = s.scalar(select(func.count()).select_from(q.subquery())); return [dict(r.data) for r in s.scalars(q.offset(offset).limit(limit))], total
    def move(self, c, new, actor):
        if STATES.index(new) != STATES.index(c["status"]) + 1: raise ValueError(f"illegal transition {c['status']} -> {new}")
        self.log(c["id"], actor, "transition", frm=c["status"], to=new); c["status"] = new; self.save(c)
    def add_doc(self, c, name, data: bytes, actor="user"):
        name = os.path.basename(name or "unnamed")
        if len(data) > MAX_UPLOAD: raise OverflowError("file too large")
        text = sanitize(extract_text(name, data)); h = hashlib.sha256(data).hexdigest()
        if h in c["hashes"]: raise FileExistsError("duplicate document")
        c["hashes"].append(h); c["documents"].append({"name": name, "text": text}); self.save(c); self.log(c["id"], actor, "document_added", name=name)
    def process(self, c, role="customer"):
        from .agents.graph import run
        for st in STATES[1:5]: self.move(c, st, "pipeline")
        r = run(c["statement"], c["documents"], role)
        c["analysis"] = {"classification": r["claim_type"], "extraction": r["extraction"], "clauses": r["clauses"], "coverage": r["coverage"], "summary": r["summary"],
                         "validation": r["validation"], "review_package": r["review_package"], "agent_trail": r["trail"]}
        self.log(c["id"], "pipeline", "agents_completed", trail=r["trail"]); self.move(c, "HUMAN_REVIEW", "pipeline"); return c["analysis"]
    def resolve(self, c, reviewer, note):
        self.move(c, "RESOLVED", reviewer); c["review"] = {"reviewer": reviewer, "note": note, "at": self._now()}; self.save(c)
    def assign(self, c, who, actor): c["assignee"] = who; self.save(c); self.log(c["id"], actor, "assigned", to=who)
    def add_note(self, c, actor, text): c["notes"].append({"by": actor, "text": text, "at": self._now()}); self.save(c); self.log(c["id"], actor, "note_added")
    def request_docs(self, c, actor, items): c["doc_requests"].append({"by": actor, "items": items, "at": self._now()}); self.save(c); self.log(c["id"], actor, "documents_requested", items=items)
    def delete(self, cid, actor):
        with self.S.begin() as s: r = s.get(ClaimRow, cid); r and s.delete(r)
        self.log(cid, actor, "erased")
    def purge_resolved(self, days, actor="retention-job"):
        cut = (dt.datetime.now(dt.UTC) - dt.timedelta(days=days)).isoformat(); gone = []
        with self.S() as s: rows = [(r.id, (r.data.get("review") or {}).get("at", "")) for r in s.scalars(select(ClaimRow).where(ClaimRow.status == "RESOLVED"))]
        for cid, at in rows:
            if at and at < cut: self.delete(cid, actor); gone.append(cid)
        return gone
