import time, os, json
from collections import Counter
from .data import generate_annotated
from .extract import extract
from .nlp import evaluate as eval_cls, classifier, classify
from .ner import entities
from .rag.bench import run as rag_bench
from .rag.engine import Engine
def eval_extraction():
    rows = generate_annotated(); fields = ["claim_ref", "incident_date", "location", "policy_ref", "amount_eur"]; out = {}
    for f in fields:
        tp = fp = fn = exact = 0
        for text, _, gold in rows:
            p = extract(text)["fields"][f]; g = gold[f]
            if p is not None and p == g: tp += 1
            elif p is not None: fp += 1; fn += g is not None
            elif g is not None: fn += 1
            exact += p == g
        out[f] = {"precision": round(tp / (tp + fp or 1), 4), "recall": round(tp / (tp + fn or 1), 4), "exact_match": round(exact / len(rows), 4)}
    return {"n": len(rows), "fields": out, "note": "gold = generator variables; malformed-policy and missing-amount edge cases are included on purpose"}
def eval_ner():
    rows = generate_annotated(); tp = fp = fn = 0
    for text, _, g in rows:
        gold = {("CLAIM_ID", g["claim_ref"]), ("DATE", g["incident_date"]), ("GPE", g["location"])}
        if "POL-" in text: gold.add(("POLICY_ID", g["policy_ref"]))
        if g["amount_eur"] is not None: gold.add(("MONEY", f"EUR {int(g['amount_eur'])}"))
        pred = {(l, t) for l, t in entities(text)}; tp += len(pred & gold); fp += len(pred - gold); fn += len(gold - pred)
    p, r = tp / (tp + fp or 1), tp / (tp + fn or 1); return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r or 1), 4), "type": "rule-based"}
def experiments():
    out = {}; texts = [t for t, _, _ in generate_annotated(200)]
    from .rag.engine import QdrantIndex
    dims = {}
    for d in (2, 4, 8, 12):
        e = Engine(); from sklearn.decomposition import TruncatedSVD; from sklearn.preprocessing import normalize
        e.svd = TruncatedSVD(d, random_state=0); e.V = normalize(e.svd.fit_transform(e.X)); e.index = QdrantIndex(e.V, e.cl)
        qs = [(q, c["id"]) for c in e.cl if not c["restricted"] for q in c["queries"]]
        dims[d] = round(sum(c in [h["clause_id"] for h in e.search(q, "vector", None, "customer", 3)] for q, c in qs) / len(qs), 4)
    out["embedding_dim_vs_vector_recall@3"] = dims
    clf = classifier(); t0 = time.perf_counter(); [classify(t) for t in texts]; single = time.perf_counter() - t0
    t0 = time.perf_counter(); clf.predict_proba(texts); batch = time.perf_counter() - t0
    out["batch_inference"] = {"single_ms_per_doc": round(single * 1000 / len(texts), 3), "batch_ms_per_doc": round(batch * 1000 / len(texts), 3)}
    from functools import lru_cache
    e = Engine(); q = "stolen bicycle lock receipt"; t0 = time.perf_counter(); [e.search(q, "agentic") for _ in range(50)]; nc = time.perf_counter() - t0
    c = lru_cache(256)(lambda q: e.search(q, "agentic")); t0 = time.perf_counter(); [c(q) for _ in range(50)]; ca = time.perf_counter() - t0
    out["caching_50_repeat_queries_ms"] = {"no_cache": round(nc * 1000, 2), "lru_cache": round(ca * 1000, 2)}
    conf = [classify(t)["confidence"] for t in texts]; out["model_routing"] = {"rule": "route to human/LLM if confidence < 0.6", "share_routed": round(sum(c < .6 for c in conf) / len(conf), 4)}
    out["not_run"] = ["chunk size (clauses are single sentences)", "prompt optimization (no LLM available)", "quantization (no transformer available offline)"]
    return out
def run_all(log=True):
    res = {"classification": eval_cls(), "extraction": eval_extraction(), "ner": eval_ner(), "rag": rag_bench(), "experiments": experiments()}
    if log:
        try:
            import mlflow, mlflow.sklearn
            mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")); mlflow.set_experiment("claims-ai")
            with mlflow.start_run(run_name="eval"):
                for m, v in res["classification"]["models"].items(): mlflow.log_metric(f"cls_{m.replace(chr(43),chr(95))}_f1", v["macro_f1"]); mlflow.log_metric(f"cls_{m.replace(chr(43),chr(95))}_acc", v["accuracy"])
                for m, v in res["rag"]["modes"].items(): mlflow.log_metric(f"rag_{m}_recall", v["recall@k"]); mlflow.log_metric(f"rag_{m}_mrr", v["mrr"])
                mlflow.log_metric("ner_f1", res["ner"]["f1"]); mlflow.log_param("dataset", "synthetic seed=42"); mlflow.log_dict(res, "eval_results.json")
                mlflow.sklearn.log_model(classifier(), "claim_type_classifier", registered_model_name="claim-type-classifier")
            res["mlflow"] = "logged"
        except Exception as e: res["mlflow"] = f"logging failed: {type(e).__name__}: {e}"
    return res
