import logging
from typing import Tuple

from transformers import pipeline  # type: ignore

logger = logging.getLogger(__name__)

# Map (src, tgt) to HF model name. Prefer M2M100 for broader coverage; Marian for specific pairs.
# For simplicity and size, use Helsinki-NLP Marian for pairs we need.
MODEL_MAP = {
    ('en', 'zh'): 'Helsinki-NLP/opus-mt-en-zh',
    ('zh', 'en'): 'Helsinki-NLP/opus-mt-zh-en',
    ('en', 'ms'): 'Helsinki-NLP/opus-mt-en-ms',
    ('ms', 'en'): 'Helsinki-NLP/opus-mt-ms-en',
    ('ms', 'zh'): 'Helsinki-NLP/opus-mt-ms-zh',
    ('zh', 'ms'): 'Helsinki-NLP/opus-mt-zh-ms',
}

class Translator:
    def __init__(self) -> None:
        self._pipelines = {}

    def _get_pipe(self, src: str, tgt: str):
        key = (src, tgt)
        if src == tgt:
            return None
        model_name = MODEL_MAP.get(key)
        if not model_name:
            raise ValueError("Unsupported translation pair. Use en/zh/ms.")
        if key not in self._pipelines:
            logger.info("Loading translation model: %s", model_name)
            self._pipelines[key] = pipeline('translation', model=model_name)
        return self._pipelines[key]

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text or not text.strip():
            raise ValueError("Text must not be empty")
        s = source_lang.lower()
        t = target_lang.lower()
        if s == t:
            return text
        pipe = self._get_pipe(s, t)
        result = pipe(text, max_length=1000)
        return result[0]['translation_text']

_translator = None

def get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
