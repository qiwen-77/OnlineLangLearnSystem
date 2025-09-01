"""
Multilingual Translation Service
Using pretrained Hugging Face models for English, Chinese, and Malay translation
"""
import logging
from typing import Dict, Optional

try:
    from transformers import pipeline  # type: ignore
except ImportError as e:
    pipeline = None
    logging.warning(f"Transformers not available: {e}")

logger = logging.getLogger(__name__)

# Translation model mapping
# Using Facebook M2M100 for multilingual translation (more reliable)
TRANSLATION_MODELS = {
    ('en', 'zh'): 'facebook/m2m100_418M',
    ('zh', 'en'): 'facebook/m2m100_418M', 
    ('en', 'ms'): 'facebook/m2m100_418M',
    ('ms', 'en'): 'facebook/m2m100_418M',
    ('ms', 'zh'): 'facebook/m2m100_418M',
    ('zh', 'ms'): 'facebook/m2m100_418M',
}

# M2M100 language codes
M2M_LANG_CODES = {
    'en': 'en',
    'zh': 'zh',
    'ms': 'ms',
}

# Supported languages
SUPPORTED_LANGUAGES = {'en', 'zh', 'ms'}

class TranslationService:
    """
    Multilingual translation service using Hugging Face transformers.
    
    Features:
    - Support for English, Chinese, and Malay
    - Caches translation models for performance
    - Handles direct translation pairs
    - Fallback through English for unsupported pairs
    """
    
    def __init__(self):
        if pipeline is None:
            raise RuntimeError(
                "Transformers not available. Please install with: pip install transformers"
            )
        
        self._pipelines: Dict[tuple, any] = {}
        logger.info("Translation service initialized")
    
    def _get_pipeline(self, source_lang: str, target_lang: str):
        """
        Get or create translation pipeline for language pair.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translation pipeline
            
        Raises:
            ValueError: If language pair is not supported
        """
        if source_lang == target_lang:
            return None  # No translation needed
        
        key = (source_lang, target_lang)
        
        # Check if pipeline is cached
        if key in self._pipelines:
            return self._pipelines[key]
        
        # Get model name for this language pair
        model_name = TRANSLATION_MODELS.get(key)
        if not model_name:
            raise ValueError(f"Translation from {source_lang} to {target_lang} not supported")
        
        try:
            logger.info(f"Loading translation model: {model_name}")
            # For M2M100, we need to specify source and target languages
            if 'm2m100' in model_name.lower():
                pipe = pipeline(
                    'translation', 
                    model=model_name, 
                    tokenizer=model_name,
                    src_lang=M2M_LANG_CODES[source_lang],
                    tgt_lang=M2M_LANG_CODES[target_lang]
                )
            else:
                pipe = pipeline('translation', model=model_name, tokenizer=model_name)
            
            self._pipelines[key] = pipe
            logger.info(f"Translation model loaded successfully: {source_lang}->{target_lang}")
            return pipe
            
        except Exception as e:
            logger.error(f"Failed to load translation model {model_name}: {e}")
            raise RuntimeError(f"Failed to load translation model: {str(e)}")
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text between supported languages.
        
        Args:
            text: Text to translate
            source_lang: Source language code ('en', 'zh', 'ms')
            target_lang: Target language code ('en', 'zh', 'ms')
            
        Returns:
            Translated text
            
        Raises:
            ValueError: If text is empty or languages unsupported
            RuntimeError: If translation fails
        """
        if not text or not text.strip():
            raise ValueError("Text must not be empty")
        
        source_lang = source_lang.lower()
        target_lang = target_lang.lower()
        
        # Validate languages
        if source_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported source language '{source_lang}'. Supported: {SUPPORTED_LANGUAGES}")
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported target language '{target_lang}'. Supported: {SUPPORTED_LANGUAGES}")
        
        # No translation needed if same language
        if source_lang == target_lang:
            return text
        
        try:
            pipe = self._get_pipeline(source_lang, target_lang)
            if pipe is None:
                return text  # Same language
            
            logger.info(f"Translating {source_lang}->{target_lang}: {text[:50]}...")
            
            # Perform translation
            result = pipe(text, max_length=1000)
            translated_text = result[0]['translation_text']
            
            logger.info(f"Translation successful: {translated_text[:50]}...")
            return translated_text
            
        except Exception as e:
            logger.error(f"Translation failed {source_lang}->{target_lang}: {e}")
            raise RuntimeError(f"Translation failed: {str(e)}")
    
    def get_supported_languages(self) -> list:
        """Get list of supported language codes."""
        return list(SUPPORTED_LANGUAGES)
    
    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        return language.lower() in SUPPORTED_LANGUAGES
    
    def get_available_pairs(self) -> list:
        """Get list of available translation pairs."""
        return list(TRANSLATION_MODELS.keys())


# Global instance for caching
_translation_instance: Optional[TranslationService] = None

def get_translation_service() -> TranslationService:
    """
    Get cached translation service instance.
    
    Returns:
        TranslationService instance
    """
    global _translation_instance
    if _translation_instance is None:
        _translation_instance = TranslationService()
    return _translation_instance


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Convenience function to translate text.
    
    Args:
        text: Text to translate
        source_lang: Source language code ('en', 'zh', 'ms')
        target_lang: Target language code ('en', 'zh', 'ms')
        
    Returns:
        Translated text
    """
    service = get_translation_service()
    return service.translate(text, source_lang, target_lang)
