"""
Text-to-Speech Pipeline for converting text to audio
"""
import torch
import torchaudio
from TTS.api import TTS
import os
import logging
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

class TTSPipeline:
    def __init__(self, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
        """
        Initialize TTS pipeline
        Args:
            model_name: TTS model identifier
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        try:
            self.tts = TTS(model_name=model_name, progress_bar=False)
            if torch.cuda.is_available():
                self.tts.to(self.device)
            logger.info(f"TTS model loaded successfully: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            # Fallback to a simpler model
            try:
                self.tts = TTS(model_name="tts_models/en/ljspeech/glow-tts", progress_bar=False)
                if torch.cuda.is_available():
                    self.tts.to(self.device)
                logger.info("Loaded fallback TTS model: glow-tts")
            except Exception as e2:
                logger.error(f"Failed to load fallback TTS model: {e2}")
                raise Exception(f"Could not load any TTS model: {str(e2)}")
    
    def text_to_speech(self, text, output_path=None, speaker=None):
        """
        Convert text to speech and save as WAV file
        Args:
            text: Text to convert to speech
            output_path: Path to save audio file (optional)
            speaker: Speaker voice (if supported by model)
        Returns:
            str: Path to generated audio file
        """
        try:
            if not text or not text.strip():
                raise ValueError("Text cannot be empty")
            
            # Generate unique filename if not provided
            if output_path is None:
                filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
                output_path = os.path.join("media", "audio", filename)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Generate speech
            logger.info(f"Generating speech for text: {text[:50]}...")
            
            if speaker and hasattr(self.tts, 'speakers') and self.tts.speakers:
                # Use specific speaker if available
                self.tts.tts_to_file(text=text, file_path=output_path, speaker=speaker)
            else:
                # Use default speaker
                self.tts.tts_to_file(text=text, file_path=output_path)
            
            logger.info(f"Audio saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"TTS processing failed: {e}")
            raise Exception(f"Failed to generate speech: {str(e)}")
    
    def get_available_speakers(self):
        """Get list of available speakers"""
        try:
            if hasattr(self.tts, 'speakers') and self.tts.speakers:
                return self.tts.speakers
            return []
        except:
            return []

# Global TTS pipeline instance
_tts_pipeline = None

def get_tts_pipeline():
    """Get or create TTS pipeline instance"""
    global _tts_pipeline
    if _tts_pipeline is None:
        _tts_pipeline = TTSPipeline()
    return _tts_pipeline
