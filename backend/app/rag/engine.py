import re, os, json, time, urllib.request
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue, MatchAny
from .corpus import CLAUSES
STOP = set("a an the of to is are in on for and or be if my i it with by at as that this do does what who which when how from not no".split())
def toks(t):
    return [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP]
class BM25:
    def __init__(self, docs, k1=1.5, b=.75):
        self.d = docs; self.k1, self.b = k1, b; self.avg = np.mean([len(d) for d in docs]); n = len(docs)
        df = Counter(w for d in docs for w in set(d)); self.idf = {w: np.log(1 + (n - c + .5) / (c + .5)) for w, c in df.items()}
    def score(self, q):
        out = np.zeros(len(self.d))
        for i, d in enumerate(self.d):
            tf = Counter(d)
            out[i] = sum(self.idf.get(w, 0) * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(d) / self.avg)) for w in set(q) if w in tf)
        return out
class QdrantIndex:
    """Local in-memory Qdrant (verified locally)."""
    def __init__(self, vecs, clauses):
        self.c = QdrantClient(":memory:"); self.c.create_collection("clauses", vectors_config=VectorParams(size=vecs.shape[1], distance=Distance.COSINE))
        self.c.upsert("clauses", [PointStruct(id=i, vector=v.tolist(), payload={"type": cl["type"], "restricted": cl["restricted"]}) for i, (v, cl) in enumerate(zip(vecs, clauses))])
    def search(self, vec, k, types, allow_restricted):
        must = [FieldCondition(key="type", match=MatchAny(any=types))] if types else []
        if not allow_restricted: must.append(FieldCondition(key="restricted", match=MatchValue(value=False)))
        r = self.c.query_points("clauses", query=vec.tolist(), limit=k, query_filter=Filter(must=must) if must else None).points
        return [(p.id, float(p.score)) for p in r]
class AzureSearchIndex:
    """Azure AI Search adapter. SIMULATED/UNVERIFIED: no Azure account was available; REST shape follows the public API docs.
    Requires AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX; index must hold a 'vector' field + 'type','restricted' fields."""
    def __init__(self): self.ep, self.key, self.idx = (os.environ[k] for k in ("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_KEY", "AZURE_SEARCH_INDEX"))
    def search(self, vec, k, types, allow_restricted):
        flt = " and ".join(([f"({' or '.join(f'type eq {chr(39)}{t}{chr(39)}' for t in types)})"] if types else []) + ([] if allow_restricted else ["restricted eq false"]))
        body = {"count": False, "top": k, "select": "id", "vectorQueries": [{"kind": "vector", "vector": vec.tolist(), "fields": "vector", "k": k}]}
        if flt: body["filter"] = flt
        req = urllib.request.Request(f"{self.ep}/indexes/{self.idx}/docs/search?api-version=2024-07-01", json.dumps(body).encode(), {"api-key": self.key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r: res = json.load(r)["value"]
        return [(int(x["id"]), float(x["@search.score"])) for x in res]
def rrf(*rankings, k=60):
    s = Counter()
    for r in rankings:
        for pos, i in enumerate(r): s[i] += 1 / (k + pos + 1)
    return [i for i, _ in s.most_common()]
class Engine:
    MODES = ("vector", "hybrid", "hybrid_rerank", "agentic")
    def __init__(self, index_factory=QdrantIndex, clauses=CLAUSES):
        self.cl = clauses; self.tt = [toks(c["text"]) for c in clauses]; self.bm = BM25(self.tt)
        self.tf = TfidfVectorizer(tokenizer=toks, lowercase=False, token_pattern=None, sublinear_tf=True); X = self.tf.fit_transform([c["text"] for c in clauses])
        self.svd = TruncatedSVD(12, random_state=0); self.V = normalize(self.svd.fit_transform(X)); self.X = X
        self.index = index_factory(self.V, clauses)
    def _ok(self, i, ct, role): c = self.cl[i]; return (role == "specialist" or not c["restricted"]) and (ct is None or c["type"] in (ct, "general"))
    def _vec(self, q, ct, role, n=10):
        e = normalize(self.svd.transform(self.tf.transform([q])))[0]
        return [i for i, _ in self.index.search(e, n, [ct, "general"] if ct else None, role == "specialist")]
    def _bm(self, q, ct, role, n=10):
        s = self.bm.score(toks(q)); return [int(i) for i in np.argsort(-s) if self._ok(i, ct, role) and s[i] > 0][:n]
    def _rerank(self, q, cand):
        qt = toks(q); qb = set(zip(qt, qt[1:])); bm = self.bm.score(qt); mx = bm.max() or 1; cos = (self.X @ self.tf.transform([q]).T).toarray().ravel()
        def sc(i):
            d = self.tt[i]; bi = len(qb & set(zip(d, d[1:]))) / (len(qb) or 1)
            return .5 * bm[i] / mx + .3 * cos[i] + .2 * bi
        return sorted(cand, key=lambda i: -sc(i))
    def _hybrid(self, q, ct, role): return rrf(self._vec(q, ct, role), self._bm(q, ct, role))
    def _agentic(self, q, ct, role):
        subs = [s.strip() for s in re.split(r"[;?]| and |, ", q) if len(toks(s)) >= 2] or [q]
        runs = [self._rerank(s, self._hybrid(s, ct, role)[:8]) for s in subs] + [self._rerank(q, self._hybrid(q, ct, role)[:8])]
        first = rrf(*runs)
        if first:  # pseudo-relevance feedback second pass using terms of the best clause
            q2 = q + " " + " ".join(self.tt[first[0]][:6]); first = rrf(first, self._rerank(q2, self._hybrid(q2, ct, role)[:8]))
        return first
    def search(self, q, mode="hybrid_rerank", claim_type=None, role="customer", k=3):
        ids = {"vector": lambda: self._vec(q, claim_type, role), "hybrid": lambda: self._hybrid(q, claim_type, role),
               "hybrid_rerank": lambda: self._rerank(q, self._hybrid(q, claim_type, role)[:10]), "agentic": lambda: self._agentic(q, claim_type, role)}[mode]()
        return [{"clause_id": self.cl[i]["id"], "doc_id": self.cl[i]["doc_id"], "section": self.cl[i]["section"], "text": self.cl[i]["text"], "rank": r + 1} for r, i in enumerate(ids[:k])]
_E = None
def engine():
    global _E
    if _E is None: _E = Engine()
    return _E
def retrieve(query, claim_type=None, k=2, role="customer", mode="hybrid_rerank"): return engine().search(query, mode, claim_type, role, k)
