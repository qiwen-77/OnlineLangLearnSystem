import os
import uuid
import logging
from pathlib import Path
from typing import Tuple

from django.conf import settings

try:
    # Coqui TTS
    from TTS.api import TTS  # type: ignore
except Exception as e:  # pragma: no cover
    TTS = None

logger = logging.getLogger(__name__)

LANG_MAP = {
    'en': 'en',       # English
    'zh': 'zh-cn',    # Chinese (Simplified)
    'ms': 'ms',       # Malay (may fallback/accent depending on model)
}

class MultilingualTTS:
    """Multilingual TTS using Coqui XTTS v2.

    Primary model: tts_models/multilingual/multi-dataset/xtts_v2
    """

    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2") -> None:
        if TTS is None:
            raise RuntimeError("Coqui TTS is not installed. Please install 'TTS'.")
        # Lazy init path creation
        self.media_root = Path(getattr(settings, 'MEDIA_ROOT', Path.cwd() / 'media'))
        self.output_dir = self.media_root / 'tts'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Loading TTS model: %s", model_name)
        # progress_bar False for server usage
        self.tts = TTS(model_name=model_name, progress_bar=False)

    def synthesize(self, text: str, language: str) -> Tuple[str, str]:
        """Synthesize speech from text for given language.

        Returns: (absolute_path, relative_media_url)
        """
        if not text or not text.strip():
            raise ValueError("Text must not be empty")

        lang = LANG_MAP.get(language.lower())
        if not lang:
            raise ValueError("Unsupported language. Use one of: en, zh, ms")

        filename = f"tts_{uuid.uuid4().hex[:10]}.wav"
        abs_path = str(self.output_dir / filename)

        # XTTS expects language arg for conditioning
        try:
            self.tts.tts_to_file(text=text, file_path=abs_path, language=lang)
        except TypeError:
            # Older versions may not accept 'language'; try without
            self.tts.tts_to_file(text=text, file_path=abs_path)

        rel_url = f"/media/tts/{filename}"
        logger.info("Generated TTS file: %s", abs_path)
        return abs_path, rel_url

# Singleton accessor
_tts_instance = None

def get_tts_instance() -> MultilingualTTS:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = MultilingualTTS()
    return _tts_instance
