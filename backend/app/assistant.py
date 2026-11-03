import time, re
from .rag import retrieve
from .rag.answer import answer
def chat(c, message, role):
    t0 = time.perf_counter(); m = message.lower(); an = c.get("analysis"); cites = []
    if re.search(r"\bmissing\b|outstanding|what else|still (need|required)", m):
        miss = (an["extraction"]["missing"] if an else ["run the analysis first"]); ev = [x["requirement"] for x in (an or {}).get("coverage", []) if not x["evidence_found"]]
        text, intent = f"Missing fields: {miss or 'none'}. Evidence not yet found: {ev or 'none'}.", "missing_info"
    elif re.search(r"summar", m): text, intent = (an["summary"] if an else "No analysis yet; run processing first."), "summary"
    else:
        ct = an["classification"]["claim_type"] if an else None; hits = retrieve(message, ct, 3, role, "agentic"); text, intent = answer(message, hits), "policy_question"; cites = [{"clause_id": h["clause_id"], "doc_id": h["doc_id"], "section": h["section"]} for h in hits]
    tokens = int((len(message.split()) + len(text.split())) * 1.3)
    reply = {"answer": text, "intent": intent, "citations": cites, "latency_ms": round((time.perf_counter() - t0) * 1000, 2), "est_tokens": tokens, "est_cost_usd": 0.0, "provider": "extractive-local"}
    c["messages"] += [{"role": "user", "text": message}, {"role": "assistant", **reply}]; return reply
