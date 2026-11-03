"""Rule-based NER on spaCy (blank English pipeline + custom regex/gazetteer component). Not a trained statistical model."""
import re, spacy
from spacy.language import Language
from spacy.util import filter_spans
from .data import CITIES
RX = [("CLAIM_ID", r"\bCLM-\d{6}\b"), ("POLICY_ID", r"\bPOL-\d{5}\b"), ("DATE", r"\b\d{4}-\d{2}-\d{2}\b"), ("MONEY", r"\bEUR\s?\d[\d.,]*\d|\bEUR\s?\d\b"),
      ("GPE", r"\b(?:" + "|".join(CITIES) + r")\b"), ("ORG", r"\b[A-Z][a-z]+ (?:Insurance|Assurance|Hospital|Workshop)\b")]
@Language.component("claims_rules")
def _rules(doc):
    spans = []
    for label, rx in RX:
        for m in re.finditer(rx, doc.text):
            sp = doc.char_span(m.start(), m.end(), label=label, alignment_mode="expand")
            if sp is not None: spans.append(sp)
    doc.ents = filter_spans(spans); return doc
_nlp = spacy.blank("en"); _nlp.add_pipe("claims_rules")
def entities(text): return [(e.label_, e.text) for e in _nlp(text).ents]
