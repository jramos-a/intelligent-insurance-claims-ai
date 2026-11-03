import os, json, time, urllib.request
from typing import Protocol
class LLMProvider(Protocol):
    name: str
    def generate(self, prompt: str, hits: list | None = None) -> str: ...
PROMPTS = {"case_summary@v1": "Summarize the insurance claim for a human specialist. Use only the facts and clause ids provided. Never state a coverage decision.\n{facts}"}
class TemplateProvider:
    """Deterministic, offline provider used by default and in tests."""
    name = "template"
    def generate(self, prompt, hits=None): return prompt
class AzureOpenAIProvider:
    """SIMULATED/UNVERIFIED adapter (no Azure account available). Needs AZURE_OPENAI_ENDPOINT/KEY/DEPLOYMENT."""
    name = "azure-openai"
    def __init__(self): self.ep, self.key, self.dep = (os.environ[k] for k in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "AZURE_OPENAI_DEPLOYMENT"))
    def generate(self, prompt, hits=None):
        body = json.dumps({"messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode()
        req = urllib.request.Request(f"{self.ep}/openai/deployments/{self.dep}/chat/completions?api-version=2024-06-01", body, {"api-key": self.key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)["choices"][0]["message"]["content"]
def get_provider() -> LLMProvider:
    return AzureOpenAIProvider() if os.getenv("LLM_PROVIDER") == "azure" else TemplateProvider()
def sanitize(text: str) -> str:
    """Prompt-injection guard: neutralise instruction-like lines in untrusted document text."""
    import re
    return re.sub(r"(?im)^.*(ignore (all|previous)|system prompt|you are now|disregard).*$", "[removed suspicious instruction]", text)
