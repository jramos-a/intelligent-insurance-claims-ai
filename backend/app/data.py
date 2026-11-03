"""Reproducible synthetic claims generator (template-based, seeded)."""
import random
TYPES = {
 "auto_collision": ["rear-ended at a traffic light","collided with another vehicle at an intersection","bumper damaged in a parking lot crash","car hit by a truck on the highway"],
 "property_damage": ["burst pipe flooded the kitchen","storm tore roof tiles off my house","fire damaged the living room wall","water leaking through the ceiling after heavy rain"],
 "theft": ["my bicycle was stolen from the garage","burglars broke in and took my laptop","phone stolen from my bag on the train","car broken into and stereo stolen"],
 "health": ["hospital visit after a fall, medical bills attached","broken wrist treated at emergency room","physiotherapy sessions after injury","surgery invoice for knee operation"],
}
CITIES = ["Madrid","Salamanca","Valencia","Sevilla","Bilbao"]
def generate_annotated(n=400, seed=42):
    """(text, claim_type, gold_fields) - gold comes from the generator variables, not from the extractor."""
    r = random.Random(seed); rows = []
    for i in range(n):
        t = r.choice(list(TYPES)); d = r.choice(TYPES[t]); date = f"2025-{r.randint(1,12):02d}-{r.randint(1,28):02d}"; city = r.choice(CITIES); pol = f"POL-{r.randint(10000,99999)}"; amt = r.randrange(200, 9000)
        gold = {"claim_ref": f"CLM-{100000+i}", "incident_date": date, "location": city, "policy_ref": pol, "amount_eur": float(amt)}
        text = f"Claim {gold['claim_ref']}. On {date} in {city}, {d}. Policy {pol}. Estimated damage EUR {amt}."
        if r.random() < .15: text = text.replace("Policy POL-", "Policy ")      # edge: malformed policy ref (gold keeps canonical id)
        if r.random() < .15: text = text.rsplit(" Estimated", 1)[0]; gold["amount_eur"] = None  # edge: amount absent
        rows.append((text, t, gold))
    return rows
def generate(n=400, seed=42): return [(x, t) for x, t, _ in generate_annotated(n, seed)]
