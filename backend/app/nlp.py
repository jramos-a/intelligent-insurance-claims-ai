from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
from .data import generate
def _lr(): return make_pipeline(TfidfVectorizer(ngram_range=(1, 2)), LogisticRegression(max_iter=1000))
def _rf(): return make_pipeline(TfidfVectorizer(), RandomForestClassifier(200, random_state=0))
_model = None
def classifier():
    global _model
    if _model is None:
        X, y = zip(*generate()); _model = _lr().fit(X, y)
    return _model
def classify(text):
    m = classifier(); p = m.predict_proba([text])[0]; i = p.argmax()
    return {"claim_type": m.classes_[i], "confidence": round(float(p[i]), 3), "model": "tfidf+logreg"}
def evaluate():
    X, y = zip(*generate()); Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.2, random_state=0, stratify=y)
    out = {"dataset": "synthetic template data (seed=42), 80/20 stratified split", "models": {}}
    for name, mk in (("tfidf+logreg", _lr), ("tfidf+random_forest", _rf)):
        pred = mk().fit(Xtr, ytr).predict(Xte)
        out["models"][name] = {"accuracy": round(accuracy_score(yte, pred), 4), "macro_f1": round(f1_score(yte, pred, average="macro"), 4),
                               "per_class": classification_report(yte, pred, output_dict=True, zero_division=0)}
    return out
LABELS = ["auto_collision", "property_damage", "theft", "health"]
def llm_classify(text, provider):
    """LLM-based classification via the provider abstraction. Only meaningful with a real LLM (Azure adapter = UNVERIFIED); returns None if the output is not a valid label."""
    out = provider.generate(f"Classify the insurance claim into exactly one of {LABELS}. Answer with the label only.\n\n{text}").strip().lower()
    return out if out in LABELS else None
