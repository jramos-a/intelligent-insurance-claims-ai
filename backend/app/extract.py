import re
from datetime import date
P = {"claim_ref": r"\bCLM-\d{6}\b", "policy_ref": r"\bPOL-\d{5}\b", "incident_date": r"\b(\d{4}-\d{2}-\d{2})\b",
     "amount_eur": r"EUR\s?(\d[\d.,]*)", "location": r"\bin ([A-Z][a-z]+)"}
def extract(text: str) -> dict:
    f = {}
    for k, p in P.items():
        m = re.search(p, text); f[k] = (m.group(1) if m and m.groups() else m.group(0)) if m else None
    if f["amount_eur"]: f["amount_eur"] = float(f["amount_eur"].rstrip(".,").replace(",", ""))
    missing = [k for k, v in f.items() if v is None]
    warnings = []
    dates = set(re.findall(P["incident_date"], text))
    if len(dates) > 1: warnings.append(f"inconsistent dates: {sorted(dates)}")
    if f["incident_date"]:
        try:
            if date.fromisoformat(f["incident_date"]) > date.today(): warnings.append("incident_date is in the future")
        except ValueError: warnings.append("incident_date is not a valid date")
    return {"fields": f, "missing": missing, "warnings": warnings}
