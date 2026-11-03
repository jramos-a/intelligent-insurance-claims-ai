"""RAG benchmark on the synthetic corpus: every query has exactly 1 relevant clause (its source). Results are computed, not asserted."""
import time
from .corpus import CLAUSES
from .engine import Engine
from .answer import answer, faithfulness, citation_accuracy
def run(k=3):
    e = Engine(); qs = [(q, c["id"], c["type"]) for c in CLAUSES if not c["restricted"] for q in c["queries"]]; out = {"n_queries": len(qs), "k": k, "modes": {}}
    for mode in Engine.MODES:
        p = r = mrr = h1 = faith = cit = 0; t0 = time.perf_counter()
        for q, rel, _ in qs:
            hits = e.search(q, mode, None, "customer", k); ids = [h["clause_id"] for h in hits]; hit = rel in ids
            p += hit / k; r += hit; h1 += ids[:1] == [rel]; mrr += 1 / (ids.index(rel) + 1) if hit else 0
            a = answer(q, hits); faith += faithfulness(a, hits); cit += citation_accuracy(a, {rel})
        n = len(qs); out["modes"][mode] = {"precision@k": round(p / n, 4), "recall@k": round(r / n, 4), "mrr": round(mrr / n, 4), "hit@1": round(h1 / n, 4),
            "context_precision": round(p / n, 4), "context_recall": round(r / n, 4), "faithfulness": round(faith / n, 4), "citation_accuracy": round(cit / n, 4),
            "latency_ms_per_query": round((time.perf_counter() - t0) * 1000 / n, 2)}
    return out
