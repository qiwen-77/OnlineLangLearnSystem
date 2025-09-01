"""
SpeechT5-Only Text-to-Speech Service for Python 3.12
Features:
- High-quality audio using SpeechT5 + HiFi-GAN vocoder only
- Male/Female voice selection with distinct speaker embeddings
- Adjustable speaking speed for language learning
- Optimized for English with fallback support for other languages
- No Coqui TTS dependencies - Python 3.12 compatible
"""
import os
import uuid
import logging
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Check for required libraries (no Coqui TTS)
TRANSFORMERS_TTS_AVAILABLE = False
DATASETS_AVAILABLE = False
LIBROSA_AVAILABLE = False

try:
    from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
    import torch
    import soundfile as sf
    TRANSFORMERS_TTS_AVAILABLE = True
    logger.info("✅ Transformers TTS (SpeechT5) is available")
except ImportError as e:
    TRANSFORMERS_TTS_AVAILABLE = False
    logger.error(f"❌ Transformers TTS not available: {e}")

try:
    from datasets import load_dataset  # type: ignore
    DATASETS_AVAILABLE = True
    logger.info("✅ Datasets library is available")
except Exception as e:
    DATASETS_AVAILABLE = False
    logger.warning(f"⚠️ datasets library not available: {e}")

try:
    import librosa
    LIBROSA_AVAILABLE = True
    logger.info("✅ librosa is available for audio processing")
except ImportError:
    logger.warning("⚠️ librosa not available - speed adjustment will be limited")

# Language mapping (SpeechT5 is primarily English, but we support multi-language input)
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'zh': 'Chinese', 
    'ms': 'Malay',
}

class SpeechT5TTSService:
    """
    SpeechT5-only TTS service optimized for Python 3.12 and language learning.
    
    Features:
    - High-quality audio using microsoft/speecht5_tts + microsoft/speecht5_hifigan
    - Distinct male/female voices with proper speaker embeddings
    - Adjustable speaking speed (0.5x to 2.0x) for language learning
    - Optimized for English with multi-language input support
    - No Coqui TTS dependencies
    """
    
    def __init__(self):
        self.media_root = Path(getattr(settings, 'MEDIA_ROOT', Path.cwd() / 'media'))
        self.output_dir = self.media_root / 'tts'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize SpeechT5 components
        if not TRANSFORMERS_TTS_AVAILABLE:
            raise RuntimeError(
                "SpeechT5 TTS not available. Please install:\n"
                "pip install transformers torch soundfile datasets librosa"
            )
        
        try:
            logger.info("🎙️ Initializing SpeechT5 TTS with HiFi-GAN vocoder...")
            
            # Load SpeechT5 models
            self.processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
            self.model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
            self.vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")
            
            # Load speaker embeddings for voice selection
            self.speaker_embeddings = {}
            self._load_speaker_embeddings()
            
            logger.info("✅ SpeechT5 TTS system initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize SpeechT5 TTS: {e}")
            raise RuntimeError(f"SpeechT5 TTS initialization failed: {str(e)}")
    
    def _load_speaker_embeddings(self):
        """Load high-quality speaker embeddings for distinct male/female voices."""
        # Try to load local embeddings first
        local_embeddings_dir = Path("speaker_embeddings")
        if local_embeddings_dir.exists():
            try:
                female_path = local_embeddings_dir / "female.pt"
                male_path = local_embeddings_dir / "male.pt"
                
                if female_path.exists() and male_path.exists():
                    self.speaker_embeddings['female'] = torch.load(female_path, map_location='cpu')
                    self.speaker_embeddings['male'] = torch.load(male_path, map_location='cpu')
                    logger.info("✅ Loaded local speaker embeddings from speaker_embeddings/")
                    return
            except Exception as e:
                logger.warning(f"Failed to load local embeddings: {e}")
        
        # Try to load from datasets
        if DATASETS_AVAILABLE:
            try:
                logger.info("📦 Loading CMU Arctic speaker embeddings for distinct voices...")
                
                # Load the dataset without trust_remote_code (deprecated)
                try:
                    ds = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
                except Exception as ds_err:
                    logger.warning(f"Dataset loading failed: {ds_err}")
                    raise ds_err
                
                # Use specific speakers for clear distinction
                available_speakers = len(ds)
                logger.info(f"Found {available_speakers} speakers in CMU Arctic dataset")
                
                if available_speakers >= 8:
                    # Use well-known speakers from CMU Arctic:
                    # Index 7 = slt (female), Index 1 = rms (male) 
                    self.speaker_embeddings['female'] = torch.tensor(ds[7]["xvector"]).unsqueeze(0)  # slt
                    self.speaker_embeddings['male'] = torch.tensor(ds[1]["xvector"]).unsqueeze(0)    # rms
                    
                    # Verify embeddings are sufficiently different
                    female_emb = self.speaker_embeddings['female']
                    male_emb = self.speaker_embeddings['male']
                    similarity = torch.cosine_similarity(female_emb, male_emb).item()
                    logger.info(f"🎭 Speaker similarity: {similarity:.3f} (lower = more distinct)")
                    
                    if similarity > 0.8:
                        logger.warning("Speakers may sound similar, using enhanced synthetic embeddings")
                        self._create_enhanced_synthetic_embeddings()
                    else:
                        logger.info("✅ Loaded distinct male/female speaker embeddings from dataset")
                        
                        # Save embeddings locally for faster future loading
                        local_embeddings_dir.mkdir(exist_ok=True)
                        torch.save(self.speaker_embeddings['female'], local_embeddings_dir / "female.pt")
                        torch.save(self.speaker_embeddings['male'], local_embeddings_dir / "male.pt")
                        logger.info("💾 Saved embeddings locally for future use")
                        
                else:
                    logger.warning("Not enough speakers in dataset, using synthetic embeddings")
                    self._create_enhanced_synthetic_embeddings()
                
            except Exception as emb_err:
                logger.warning(f"Failed to load dataset embeddings: {emb_err}")
                self._create_enhanced_synthetic_embeddings()
        else:
            logger.warning("Datasets library not available, using synthetic embeddings")
            self._create_enhanced_synthetic_embeddings()
    
    def _create_enhanced_synthetic_embeddings(self):
        """Create enhanced synthetic speaker embeddings with maximum distinction."""
        torch.manual_seed(42)  # For reproducible embeddings
        
        # Create highly distinct embeddings based on acoustic characteristics
        # Female voice characteristics: higher pitch, lighter timbre
        female_base = torch.randn(1, 512) * 0.2
        female_base[0, :256] += 0.8   # Boost higher frequency components
        female_base[0, 100:200] += 0.5  # Mid-high frequencies
        female_base[0, :50] += 0.3    # Very high frequencies
        
        # Male voice characteristics: lower pitch, deeper timbre
        male_base = torch.randn(1, 512) * 0.2  
        male_base[0, 256:] += 0.8     # Boost lower frequency components
        male_base[0, 350:450] += 0.5  # Mid-low frequencies
        male_base[0, 450:] += 0.3     # Very low frequencies
        
        # Normalize to prevent clipping
        female_base = torch.nn.functional.normalize(female_base, p=2, dim=1)
        male_base = torch.nn.functional.normalize(male_base, p=2, dim=1)
        
        self.speaker_embeddings = {
            'female': female_base,
            'male': male_base
        }
        
        # Verify distinction
        similarity = torch.cosine_similarity(female_base, male_base).item()
        logger.info(f"🎭 Synthetic embedding similarity: {similarity:.3f}")
        logger.info("✅ Created enhanced synthetic speaker embeddings with maximum distinction")
    
    def get_available_voices(self) -> Dict[str, str]:
        """Get available voice options."""
        return {
            'female': 'Female Voice (Higher pitch, clearer for learning)',
            'male': 'Male Voice (Lower pitch, authoritative)'
        }
    
    def _adjust_audio_speed(self, audio_path: str, speed: float) -> str:
        """Adjust audio speed without changing pitch."""
        if speed == 1.0:
            return audio_path  # No change needed
        
        if not LIBROSA_AVAILABLE:
            logger.warning("librosa not available - cannot adjust speed")
            return audio_path
        
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=None)
            
            # Adjust speed using time stretching (preserves pitch)
            y_stretched = librosa.effects.time_stretch(y, rate=speed)
            
            # Save adjusted audio
            speed_suffix = f"_speed{speed:.1f}".replace(".", "p")
            base_name = os.path.splitext(audio_path)[0]
            adjusted_path = f"{base_name}{speed_suffix}.wav"
            
            sf.write(adjusted_path, y_stretched, sr)
            logger.info(f"✅ Adjusted audio speed to {speed}x: {adjusted_path}")
            
            # Remove original file
            os.remove(audio_path)
            
            return adjusted_path
            
        except Exception as e:
            logger.warning(f"Failed to adjust audio speed: {e}")
            return audio_path
    
    def synthesize(self, text: str, language: str = 'en', voice: str = 'female', speed: float = 1.0) -> Tuple[str, str]:
        """
        Convert text to high-quality speech using SpeechT5 with voice and speed control.
        
        Args:
            text: Text to synthesize
            language: Language code ('en', 'zh', 'ms') - Note: SpeechT5 is optimized for English
            voice: Voice gender ('male', 'female')
            speed: Speaking speed (0.5 to 2.0, default 1.0)
            
        Returns:
            Tuple of (absolute_file_path, relative_url)
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If synthesis fails
        """
        # Validate inputs
        if not text or not text.strip():
            raise ValueError("Text must not be empty")
        
        if speed != 0.5:
            raise ValueError("Speed must be 0.5 for optimal clarity")
        
        if language.lower() not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language '{language}'. Supported: {list(SUPPORTED_LANGUAGES.keys())}")
        
        if voice.lower() not in ['male', 'female']:
            raise ValueError("Voice must be 'male' or 'female'")
        
        # Generate unique filename (speed is always 0.5x)
        filename = f"tts_{uuid.uuid4().hex[:12]}_{language}_{voice}_s0p5.wav"
        abs_path = str(self.output_dir / filename)
        
        try:
            logger.info(f"🎙️ Synthesizing with SpeechT5: '{text[:50]}...' | Lang: {language} | Voice: {voice} | Speed: 0.5x (fixed for clarity)")
            
            # Warn for non-English languages
            if language != 'en':
                logger.warning(f"⚠️ SpeechT5 is optimized for English. {language} text will be processed but may sound less natural.")
            
            # Use SpeechT5 for synthesis
            abs_path = self._synthesize_speecht5(text, voice, abs_path, speed)
            
            # Verify file was created
            if not os.path.exists(abs_path):
                raise RuntimeError("Audio file was not generated")
            
            # Get relative URL
            filename = os.path.basename(abs_path)
            rel_url = f"/media/tts/{filename}"
            
            logger.info(f"✅ SpeechT5 synthesis successful: {rel_url}")
            return abs_path, rel_url
            
        except Exception as e:
            logger.error(f"❌ SpeechT5 synthesis failed: {e}")
            # Clean up partial file
            if os.path.exists(abs_path):
                try:
                    os.remove(abs_path)
                except:
                    pass
            raise RuntimeError(f"SpeechT5 synthesis failed: {str(e)}")
    
    def _synthesize_speecht5(self, text: str, voice: str, abs_path: str, speed: float) -> str:
        """Synthesize using SpeechT5 with HiFi-GAN vocoder for maximum quality."""
        # Select speaker embedding
        speaker_emb = self.speaker_embeddings.get(voice.lower(), self.speaker_embeddings.get('female'))
        logger.info(f"🎭 Using {voice} voice with embedding shape: {speaker_emb.shape}")
        
        # Process text with SpeechT5 processor
        inputs = self.processor(text=text, return_tensors="pt")
        logger.info(f"📝 Input tokens shape: {inputs['input_ids'].shape}")
        
        # Generate speech with optimized settings for clarity
        with torch.no_grad():
            speech = self.model.generate_speech(
                inputs["input_ids"], 
                speaker_emb, 
                vocoder=self.vocoder
            )
        
        # Ensure proper tensor format
        if speech.dim() > 1:
            speech = speech.squeeze()
        
        # Convert to numpy for processing
        speech_audio = speech.numpy()
        
        # Enhance audio quality
        # 1. Normalize to prevent distortion
        max_val = np.max(np.abs(speech_audio))
        if max_val > 0:
            speech_audio = speech_audio / max_val
        
        # 2. Apply gentle volume boost for clarity
        speech_audio = speech_audio * 0.95  # Slightly below max to prevent clipping
        
        # 3. Save with high sample rate for maximum quality
        sample_rate = 22050  # SpeechT5's native rate
        sf.write(abs_path, speech_audio, samplerate=sample_rate)
        
        duration = len(speech_audio) / sample_rate
        logger.info(f"🎵 Generated high-quality {voice} voice: {duration:.1f}s @ {sample_rate}Hz")
        
        # Speed is always 0.5x, so always adjust
        abs_path = self._adjust_audio_speed(abs_path, 0.5)
        
        return abs_path
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about the SpeechT5 TTS engine."""
        return {
            'engine_type': 'speecht5',
            'model': 'microsoft/speecht5_tts',
            'vocoder': 'microsoft/speecht5_hifigan',
            'supports_speed_control': False,  # Fixed at 0.5x
            'fixed_speed': '0.5x',
            'supports_voice_selection': True,
            'max_quality': True,
            'supported_languages': list(SUPPORTED_LANGUAGES.keys()),
            'optimized_for': 'English',
            'available_voices': self.get_available_voices(),
            'python_version_compatible': '3.12+'
        }
    
    def get_supported_languages(self) -> list:
        """Get list of supported language codes."""
        return list(SUPPORTED_LANGUAGES.keys())
    
    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        return language.lower() in SUPPORTED_LANGUAGES


# Global instance for caching
_tts_instance: Optional[SpeechT5TTSService] = None

def get_tts_service() -> SpeechT5TTSService:
    """Get cached SpeechT5 TTS service instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = SpeechT5TTSService()
    return _tts_instance

def synthesize_text(text: str, language: str = 'en', voice: str = 'female', speed: float = 0.5) -> Tuple[str, str]:
    """
    Convenience function to synthesize high-quality text using SpeechT5.
    
    Args:
        text: Text to synthesize
        language: Language code ('en', 'zh', 'ms') - Note: SpeechT5 is optimized for English
        voice: Voice gender ('male', 'female')
        speed: Speaking speed (fixed at 0.5x for clarity)
        
    Returns:
        Tuple of (absolute_file_path, relative_url)
    """
    service = get_tts_service()
    return service.synthesize(text, language, voice, 0.5)