import re
from .engine import toks, engine
def answer(question, hits, provider=None):
    """Grounded answer with [clause_id] citations. Default provider is extractive (no LLM)."""
    if provider: return provider.generate(question, hits)
    if not hits: return "No supporting policy clause was found; escalate to a human specialist."
    return " ".join(f"{h['text']} [{h['clause_id']}]" for h in hits)
def faithfulness(ans, hits):
    byid = {h["clause_id"]: set(toks(h["text"])) for h in hits}; sents = [s for s in re.split(r"(?<=\])\s+", ans) if s.strip()]
    if not sents: return 0.0
    ok = 0
    for s in sents:
        cited = re.findall(r"\[([^\]]+)\]", s); body = set(toks(re.sub(r"\[[^\]]+\]", "", s)))
        if cited and all(c in byid for c in cited) and body and len(body & set().union(*[byid[c] for c in cited])) / len(body) >= .8: ok += 1
    return ok / len(sents)
def citation_accuracy(ans, relevant_ids):
    c = re.findall(r"\[([^\]]+)\]", ans); return (sum(x in relevant_ids for x in c) / len(c)) if c else 0.0
