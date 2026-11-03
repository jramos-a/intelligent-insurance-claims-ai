"""Speech adapters. AzureSpeech* are SIMULATED/UNVERIFIED (no Azure account); Null* adapters work offline and only echo/placeholder."""
import os
class SpeechToText:
    def transcribe(self, audio: bytes, lang="en-US") -> str: raise NotImplementedError
class TextToSpeech:
    def synthesize(self, text: str, lang="en-US") -> bytes: raise NotImplementedError
class NullSTT(SpeechToText):
    def transcribe(self, audio, lang="en-US"): return audio.decode("utf-8", "ignore")  # treats bytes as text; offline stand-in, not real ASR
class NullTTS(TextToSpeech):
    def synthesize(self, text, lang="en-US"): return text.encode()
class AzureSTT(SpeechToText):
    def transcribe(self, audio, lang="en-US"):
        import urllib.request
        key, region = os.environ["AZURE_SPEECH_KEY"], os.environ["AZURE_SPEECH_REGION"]
        req = urllib.request.Request(f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={lang}", audio, {"Ocp-Apim-Subscription-Key": key, "Content-Type": "audio/wav"})
        import json
        with urllib.request.urlopen(req, timeout=20) as r: return json.load(r).get("DisplayText", "")
class AzureTTS(TextToSpeech):
    def synthesize(self, text, lang="en-US"):
        import urllib.request
        key, region = os.environ["AZURE_SPEECH_KEY"], os.environ["AZURE_SPEECH_REGION"]
        ssml = f"<speak version='1.0' xml:lang='{lang}'><voice xml:lang='{lang}' name='en-US-JennyNeural'>{text}</voice></speak>".encode()
        req = urllib.request.Request(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1", ssml, {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"})
        with urllib.request.urlopen(req, timeout=20) as r: return r.read()
def get_stt(): return AzureSTT() if os.getenv("SPEECH_PROVIDER") == "azure" else NullSTT()
def get_tts(): return AzureTTS() if os.getenv("SPEECH_PROVIDER") == "azure" else NullTTS()
