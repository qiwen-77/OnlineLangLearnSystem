"""
Dictionary Service for Language Learning Platform
Provides word lookup functionality with online API and offline fallbacks
"""
import os
import re
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

class DictionaryDefinition:
    """Data class for dictionary definition"""
    def __init__(self, word: str, part_of_speech: str = "", definition: str = "", 
                 example: str = "", pronunciation: str = "", language: str = "en"):
        self.word = word
        self.part_of_speech = part_of_speech
        self.definition = definition
        self.example = example
        self.pronunciation = pronunciation
        self.language = language
        self.source = ""
    
    def to_dict(self):
        return {
            'word': self.word,
            'part_of_speech': self.part_of_speech,
            'definition': self.definition,
            'example': self.example,
            'pronunciation': self.pronunciation,
            'language': self.language,
            'source': self.source
        }

class DictionaryService:
    """
    Dictionary lookup service with multiple data sources:
    1. Free Dictionary API (online)
    2. WordNet via NLTK (offline)
    3. Local word cache
    """
    
    def __init__(self):
        self.cache = {}
        self.nltk_available = False
        self.wordnet_available = False
        self._init_nltk()
        
        # API configuration
        self.api_timeout = 5  # seconds
        self.max_retries = 2
        
        # Supported languages mapping
        self.language_mapping = {
            'en': 'english',
            'zh': 'chinese',
            'ms': 'malay'
        }
    
    def _init_nltk(self):
        """Initialize NLTK and WordNet for offline functionality"""
        try:
            import nltk
            from nltk.corpus import wordnet
            self.nltk = nltk
            self.wordnet = wordnet
            self.nltk_available = True
            
            # Try to download required data if not available
            try:
                self.wordnet.synsets('test')
                self.wordnet_available = True
                logger.info("✅ WordNet is available for offline dictionary lookup")
            except LookupError:
                logger.info("📥 Downloading WordNet data...")
                try:
                    self.nltk.download('wordnet', quiet=True)
                    self.nltk.download('omw-1.4', quiet=True)  # For multilingual support
                    self.wordnet_available = True
                    logger.info("✅ WordNet data downloaded successfully")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to download WordNet data: {e}")
                    
        except ImportError:
            logger.warning("⚠️ NLTK not available. Dictionary will use online API only.")
    
    def is_single_word(self, text: str) -> bool:
        """Check if the text contains exactly one word"""
        if not text or not isinstance(text, str):
            return False
            
        # Clean and normalize text
        cleaned = re.sub(r'[^\w\s]', '', text.strip())
        words = cleaned.split()
        
        # Must be exactly one word, and reasonably length
        if len(words) == 1 and 2 <= len(words[0]) <= 50:
            # Should contain alphabetic characters
            return bool(re.search(r'[a-zA-Z]', words[0]))
        return False
    
    def extract_single_word(self, text: str) -> Optional[str]:
        """Extract and clean a single word from text"""
        if not self.is_single_word(text):
            return None
            
        cleaned = re.sub(r'[^\w]', '', text.strip()).lower()
        return cleaned if cleaned else None
    
    @lru_cache(maxsize=500)
    def lookup_word(self, word: str, language: str = 'en') -> List[DictionaryDefinition]:
        """
        Main lookup function - tries multiple sources
        Returns list of definitions for the word
        """
        if not word or not isinstance(word, str):
            return []
            
        word = word.strip().lower()
        cache_key = f"{word}_{language}"
        
        # Check cache first
        if cache_key in self.cache:
            logger.debug(f"📋 Dictionary cache hit for '{word}'")
            return self.cache[cache_key]
        
        definitions = []
        
        try:
            # 1. Try online Free Dictionary API (primary source for English)
            if language == 'en':
                definitions = self._lookup_free_dictionary_api(word)
                if definitions:
                    logger.info(f"✅ Found {len(definitions)} definitions from Free Dictionary API")
            
            # 2. Try WordNet (offline fallback)
            if not definitions and self.wordnet_available:
                definitions = self._lookup_wordnet(word, language)
                if definitions:
                    logger.info(f"✅ Found {len(definitions)} definitions from WordNet")
            
            # 3. Try basic word pattern matching (last resort)
            if not definitions:
                definitions = self._lookup_basic_patterns(word, language)
                if definitions:
                    logger.info(f"✅ Found basic definition for '{word}'")
                    
        except Exception as e:
            logger.error(f"❌ Dictionary lookup failed for '{word}': {e}")
        
        # Cache the result (even if empty)
        self.cache[cache_key] = definitions
        return definitions
    
    def _lookup_free_dictionary_api(self, word: str) -> List[DictionaryDefinition]:
        """Lookup word using Free Dictionary API"""
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            response = requests.get(url, timeout=self.api_timeout)
            
            if response.status_code == 200:
                data = response.json()
                definitions = []
                
                for entry in data:
                    word_text = entry.get('word', word)
                    phonetic = self._extract_phonetic(entry.get('phonetics', []))
                    
                    for meaning in entry.get('meanings', []):
                        part_of_speech = meaning.get('partOfSpeech', '')
                        
                        for definition_data in meaning.get('definitions', []):
                            definition_text = definition_data.get('definition', '')
                            example = definition_data.get('example', '')
                            
                            if definition_text:
                                def_obj = DictionaryDefinition(
                                    word=word_text,
                                    part_of_speech=part_of_speech,
                                    definition=definition_text,
                                    example=example,
                                    pronunciation=phonetic,
                                    language='en'
                                )
                                def_obj.source = "Free Dictionary API"
                                definitions.append(def_obj)
                
                return definitions[:5]  # Limit to 5 definitions
                
        except requests.RequestException as e:
            logger.warning(f"⚠️ Free Dictionary API request failed: {e}")
        except Exception as e:
            logger.error(f"❌ Error parsing Free Dictionary API response: {e}")
        
        return []
    
    def _extract_phonetic(self, phonetics: List[Dict]) -> str:
        """Extract pronunciation from phonetics data"""
        for phonetic in phonetics:
            if phonetic.get('text'):
                return phonetic['text']
        return ""
    
    def _lookup_wordnet(self, word: str, language: str = 'en') -> List[DictionaryDefinition]:
        """Lookup word using NLTK WordNet"""
        if not self.wordnet_available:
            return []
        
        try:
            synsets = self.wordnet.synsets(word)
            definitions = []
            
            for synset in synsets[:5]:  # Limit to 5 synsets
                # Get definition
                definition_text = synset.definition()
                
                # Get part of speech
                pos_map = {
                    'n': 'noun',
                    'v': 'verb', 
                    'a': 'adjective',
                    's': 'adjective',  # satellite adjective
                    'r': 'adverb'
                }
                part_of_speech = pos_map.get(synset.pos(), synset.pos())
                
                # Get example if available
                examples = synset.examples()
                example = examples[0] if examples else ""
                
                def_obj = DictionaryDefinition(
                    word=word,
                    part_of_speech=part_of_speech,
                    definition=definition_text,
                    example=example,
                    language=language
                )
                def_obj.source = "WordNet"
                definitions.append(def_obj)
            
            return definitions
            
        except Exception as e:
            logger.error(f"❌ WordNet lookup failed: {e}")
            return []
    
    def _lookup_basic_patterns(self, word: str, language: str = 'en') -> List[DictionaryDefinition]:
        """Basic pattern matching for common words"""
        basic_words = {
            'hello': 'A greeting used to begin a conversation or to answer the telephone',
            'world': 'The earth and all the people and things on it',
            'computer': 'An electronic device that can store and process data',
            'book': 'A set of printed pages fastened together inside a cover',
            'water': 'A clear liquid that has no color, taste, or smell',
            'house': 'A building where people live',
            'car': 'A vehicle with four wheels and an engine',
            'phone': 'A device used for talking to someone in another place',
            'love': 'A strong feeling of affection',
            'time': 'The indefinite continued progress of existence',
        }
        
        if word.lower() in basic_words:
            def_obj = DictionaryDefinition(
                word=word,
                part_of_speech='noun',
                definition=basic_words[word.lower()],
                language=language
            )
            def_obj.source = "Basic Dictionary"
            return [def_obj]
        
        return []
    
    def clear_cache(self):
        """Clear the definition cache"""
        self.cache.clear()
        logger.info("🗑️ Dictionary cache cleared")

# Global service instance
_dictionary_service = None

def get_dictionary_service() -> DictionaryService:
    """Get or create dictionary service instance"""
    global _dictionary_service
    if _dictionary_service is None:
        _dictionary_service = DictionaryService()
        logger.info("✅ Dictionary service initialized")
    return _dictionary_service

def lookup_word_definition(text: str, language: str = 'en') -> Tuple[bool, List[Dict]]:
    """
    Convenient function to lookup word definition
    
    Args:
        text: The text to check and lookup
        language: Language code (en, zh, ms)
    
    Returns:
        Tuple of (is_single_word, definitions_list)
    """
    service = get_dictionary_service()
    
    if not service.is_single_word(text):
        return False, []
    
    word = service.extract_single_word(text)
    if not word:
        return False, []
    
    definitions = service.lookup_word(word, language)
    return True, [d.to_dict() for d in definitions]
