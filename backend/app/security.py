import os, json, re, time
from collections import namedtuple, defaultdict, deque
from fastapi import Depends, Header, HTTPException, Request
Principal = namedtuple("Principal", "role sub")
PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"), (re.compile(r"\b[A-Z]{2}\d{2}(?: ?\d{4}){4,6}\b"), "[IBAN]"),
       (re.compile(r"\b\d{8}[A-Z]\b"), "[DNI]"), (re.compile(r"(?<!\w)(?:\+34 ?)?[6-9]\d{2}[ -]?\d{3}[ -]?\d{3}\b"), "[PHONE]")]
def mask(text: str) -> str:
    for rx, tag in PII: text = rx.sub(tag, text)
    return text
def principal(authorization: str = Header(None)) -> Principal:
    """Static-token auth for local use. OIDC-ready seam: replace this function with JWT validation (issuer/audience/JWKS) returning Principal(role, sub).
    CLAIMS_TOKENS env: {"<token>": "role" | "role:subject"}; never hardcoded."""
    toks = json.loads(os.getenv("CLAIMS_TOKENS", "{}")); t = (authorization or "").removeprefix("Bearer ").strip()
    if t not in toks: raise HTTPException(401, "invalid or missing token")
    role, _, sub = toks[t].partition(":"); return Principal(role, sub or role)
_hits = defaultdict(deque)
def rate_limit(p: Principal = Depends(principal)):
    lim = int(os.getenv("RATE_LIMIT_PER_MIN", "120")); q = _hits[p.sub]; now = time.time()
    while q and now - q[0] > 60: q.popleft()
    if len(q) >= lim: raise HTTPException(429, "rate limit exceeded")
    q.append(now); return p
def need(*roles):
    def dep(p: Principal = Depends(rate_limit)):
        if p.role not in roles: raise HTTPException(403, "forbidden for role")
        return p
    return dep
