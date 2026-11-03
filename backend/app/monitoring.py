import time, math
from collections import defaultdict, Counter
class Metrics:
    def __init__(self): self.lat = defaultdict(list); self.err = Counter(); self.n = Counter(); self.pred = Counter(); self.tokens = 0
    def record(self, route, ms, status):
        self.lat[route].append(ms); self.n[route] += 1; self.err[route] += status >= 500
    def snapshot(self):
        out = {}
        for r, v in self.lat.items():
            s = sorted(v); out[r] = {"count": self.n[r], "errors": self.err[r], "p50_ms": round(s[len(s) // 2], 2), "p95_ms": round(s[min(len(s) - 1, int(len(s) * .95))], 2)}
        return {"routes": out, "predicted_classes": dict(self.pred), "est_tokens_total": self.tokens}
def psi(expected: dict, actual: dict, eps=1e-4):
    ks = set(expected) | set(actual); te, ta = sum(expected.values()) or 1, sum(actual.values()) or 1
    return sum((actual.get(k, 0) / ta + eps - (expected.get(k, 0) / te + eps)) * math.log((actual.get(k, 0) / ta + eps) / (expected.get(k, 0) / te + eps)) for k in ks)
M = Metrics()
