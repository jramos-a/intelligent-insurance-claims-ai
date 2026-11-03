"""LangGraph claims orchestration. Agents prepare evidence for a human; none makes a coverage decision (review_package['decision'] is always None)."""
import re
from typing import TypedDict
from langgraph.graph import StateGraph, END
from ..nlp import classify
from ..extract import extract
from ..rag import retrieve
from ..llm.providers import get_provider, sanitize
EVIDENCE = {"police report": r"police|accident report|denuncia", "repair estimate": r"repair estimate|estimate|quote", "photos": r"photo|picture",
            "proof of ownership": r"proof of ownership|receipt|invoice of purchase", "medical report": r"medical report|hospital|medical bills",
            "invoices": r"invoice|bill", "prescription": r"prescription", "inventory list": r"inventory", "lock receipt": r"lock receipt",
            "third party details": r"third party|other (driver|party)", "prior authorization": r"authori[sz]ation"}
class State(TypedDict, total=False):
    statement: str; documents: list; text: str; role: str; claim_type: dict; extraction: dict; clauses: list; coverage: list
    summary: str; validation: list; review_package: dict; trail: list; retries: int
def _t(s, n): s["trail"] = s.get("trail", []) + [n]; return s
def intake(s): s["text"] = sanitize(" ".join([s["statement"]] + [d["text"] for d in s.get("documents", [])])); return _t(s, "intake")
def classification(s): s["claim_type"] = classify(s["text"]); return _t(s, "classification")
def document(s): s["extraction"] = extract(s["text"]); return _t(s, "document")
def policy_retrieval(s): s["clauses"] = retrieve(s["text"], s["claim_type"]["claim_type"], 3, s.get("role", "customer"), "agentic"); return _t(s, "policy_retrieval")
def coverage_analysis(s):
    """Compares evidence to what clauses ask for. Output is a checklist, never a decision."""
    out = []
    for c in s["clauses"]:
        req = [e for e in EVIDENCE if e in c["text"].lower() or (e == "police report" and "accident report" in c["text"].lower())]
        for e in req: out.append({"clause_id": c["clause_id"], "requirement": e, "evidence_found": bool(re.search(EVIDENCE[e], s["text"], re.I))})
    s["coverage"] = out; return _t(s, "coverage_analysis")
def case_summary(s):
    f = s["extraction"]["fields"]; miss = [c["requirement"] + f" ({c['clause_id']})" for c in s["coverage"] if not c["evidence_found"]]
    facts = (f"Claim {f['claim_ref'] or '?'} classified '{s['claim_type']['claim_type']}' (conf {s['claim_type']['confidence']}). Incident {f['incident_date'] or 'unknown'} in {f['location'] or 'unknown'}; "
             f"claimed EUR {f['amount_eur'] if f['amount_eur'] is not None else 'unknown'}. Clauses: {', '.join(c['clause_id'] for c in s['clauses'])}. Evidence not found: {miss or 'none'}. Missing fields: {s['extraction']['missing'] or 'none'}. "
             "Evidence-preparation summary only; coverage is decided by a human specialist.")
    s["summary"] = get_provider().generate(facts); return _t(s, "case_summary")
def validation(s):
    w = list(s["extraction"]["warnings"]); ids = {c["clause_id"] for c in s["clauses"]}
    for cid in re.findall(r"\b[A-Z-]+#\d+\.\d+\b", s["summary"]):
        if cid not in ids: w.append(f"summary cites unknown clause {cid}")
    a = s["extraction"]["fields"]["amount_eur"]
    if a is not None and f"EUR {a}" not in s["summary"]: w.append("amount in summary does not match extraction")
    if re.search(r"\b(approved|rejected|denied)\b", s["summary"], re.I): w.append("summary contains a coverage decision")
    if a and a > 5000: w.append("high-value claim: escalate to senior specialist (internal guideline)")
    s["validation"] = w; return _t(s, "validation")
def human_review(s):
    s["review_package"] = {"decision": None, "requires_human": True, "summary": s["summary"], "clauses": s["clauses"], "coverage_checklist": s["coverage"], "warnings": s["validation"], "missing_fields": s["extraction"]["missing"]}
    return _t(s, "human_review")
def _after_validation(s):
    if any("coverage decision" in w for w in s["validation"]) and s.get("retries", 0) < 1: s["retries"] = 1; return "case_summary"
    return "human_review"
def build():
    g = StateGraph(State)
    for n, f in [("intake", intake), ("classification", classification), ("document", document), ("policy_retrieval", policy_retrieval), ("coverage_analysis", coverage_analysis),
                 ("case_summary", case_summary), ("validation", validation), ("human_review", human_review)]: g.add_node(n, f)
    g.set_entry_point("intake")
    for a, b in [("intake", "classification"), ("classification", "document"), ("document", "policy_retrieval"), ("policy_retrieval", "coverage_analysis"), ("coverage_analysis", "case_summary"), ("case_summary", "validation")]: g.add_edge(a, b)
    g.add_conditional_edges("validation", _after_validation, {"case_summary": "case_summary", "human_review": "human_review"}); g.add_edge("human_review", END)
    return g.compile()
GRAPH = build()
def run(statement, documents, role="customer"): return GRAPH.invoke({"statement": statement, "documents": documents, "role": role, "trail": []})
