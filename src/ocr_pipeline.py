"""
OCR Pipeline using TrOCR model for text recognition from images
"""
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Import dictionary service
try:
    # Add services to path
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    services_path = project_root / 'services'
    if str(services_path) not in sys.path:
        sys.path.append(str(services_path))
    
    from dictionary_service import lookup_word_definition
    DICTIONARY_AVAILABLE = True
    logger.info("✅ Dictionary service imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Dictionary service not available: {e}")
    DICTIONARY_AVAILABLE = False
    def lookup_word_definition(text, language='en'):
        return False, []

class OCRPipeline:
    def __init__(self, checkpoint_path=None, model_name="microsoft/trocr-base-printed", local_model_dir: str | None = None):
        """
        Initialize TrOCR pipeline with proper text decoding
        Args:
            checkpoint_path: Path to trained model checkpoint (e.g., 'best_checkpoint.pt')
            model_name: HuggingFace model identifier for TrOCR (fallback if no local model)
            local_model_dir: Path to local model directory with HuggingFace artifacts
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.fallback_model_name = "microsoft/trocr-base-printed"
        logger.info(f"🔧 OCR Pipeline initializing on device: {self.device}")
        
        try:
            # Track model source for fallback decisions
            self.model_source = "unknown"
            self.is_local_model = False
            
            # 1) Prefer a local directory with full HF artifacts (trocr_iiit5k_word)
            if local_model_dir and os.path.isdir(local_model_dir):
                logger.info(f"📂 Loading local OCR model from directory: {local_model_dir}")
                try:
                    self.processor = TrOCRProcessor.from_pretrained(local_model_dir)
                    # Use VisionEncoderDecoderModel for TrOCR architecture
                    self.model = VisionEncoderDecoderModel.from_pretrained(local_model_dir)
                    self.model.to(self.device)
                    self.model.eval()
                    self.is_local_model = True
                    self.model_source = "local"
                    logger.info("✅ Local model loaded with VisionEncoderDecoderModel")
                except Exception as local_err:
                    logger.error(f"❌ Failed to load local model: {local_err}")
                    logger.info("🔄 Falling back to pretrained model...")
                    self._load_fallback_model()
            # 2) Else try a provided checkpoint_path for fine-tuned weights
            elif checkpoint_path and os.path.exists(checkpoint_path):
                logger.info(f"📂 Loading custom trained model from: {checkpoint_path}")
                try:
                    self._load_trained_model(checkpoint_path, model_name)
                    self.model_source = "checkpoint"
                except Exception as checkpoint_err:
                    logger.error(f"❌ Failed to load checkpoint: {checkpoint_err}")
                    logger.info("🔄 Falling back to pretrained model...")
                    self._load_fallback_model()
            else:
                # 3) Load pretrained model
                self._load_pretrained_model(model_name)

            logger.info(f"✅ TrOCR model loaded successfully (source={self.model_source})")
        except Exception as e:
            logger.error(f"❌ Failed to load TrOCR model: {e}")
            raise
    
    def _load_pretrained_model(self, model_name):
        """Load pretrained model with proper configuration"""
        logger.info(f"📥 Loading pretrained model: {model_name}")
        self.processor = TrOCRProcessor.from_pretrained(model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        self.model_source = "pretrained"
        self.is_local_model = False
    
    def _load_fallback_model(self):
        """Load fallback model when primary model fails"""
        logger.info(f"📥 Loading fallback model: {self.fallback_model_name}")
        self.processor = TrOCRProcessor.from_pretrained(self.fallback_model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(self.fallback_model_name)
        self.model.to(self.device)
        self.model.eval()
        self.model_source = "fallback"
        self.is_local_model = False
    
    def _load_trained_model(self, checkpoint_path, base_model_name):
        """Load trained model from checkpoint"""
        try:
            # Load the processor (tokenizer) from the base model
            self.processor = TrOCRProcessor.from_pretrained(base_model_name)
            
            # Load the base model architecture with VisionEncoderDecoderModel
            self.model = VisionEncoderDecoderModel.from_pretrained(base_model_name)
            
            # Load the trained weights
            logger.info(f"🔄 Loading checkpoint weights from {checkpoint_path}")
            try:
                # Try loading with weights_only=True first (secure)
                checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=True)
            except Exception as secure_err:
                logger.warning(f"⚠️ Secure loading failed: {secure_err}")
                logger.info("🔄 Attempting fallback loading method...")
                try:
                    # Fallback to weights_only=False (less secure but may work for custom checkpoints)
                    checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
                    logger.info("✅ Fallback loading successful")
                except Exception as fallback_err:
                    logger.error(f"❌ Fallback loading also failed: {fallback_err}")
                    raise fallback_err
            
            # Debug checkpoint contents
            if isinstance(checkpoint, dict):
                logger.info(f"📋 Checkpoint keys: {list(checkpoint.keys())}")
            
            # Handle different checkpoint formats
            state_dict = None
            if 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
                logger.info("✅ Found model_state_dict in checkpoint")
            elif 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
                logger.info("✅ Found state_dict in checkpoint")
            elif 'model' in checkpoint:
                state_dict = checkpoint['model']
                logger.info("✅ Found model in checkpoint")
            else:
                # Assume the checkpoint is the state dict itself
                state_dict = checkpoint
                logger.info("✅ Using checkpoint as state_dict directly")
            
            # Load the state dict with error handling
            try:
                # Try strict loading first
                self.model.load_state_dict(state_dict, strict=True)
                logger.info("✅ Loaded state dict with strict=True")
            except Exception as strict_err:
                logger.warning(f"⚠️ Strict loading failed: {strict_err}")
                try:
                    # Try non-strict loading
                    missing_keys, unexpected_keys = self.model.load_state_dict(state_dict, strict=False)
                    if missing_keys:
                        logger.warning(f"⚠️ Missing keys: {missing_keys}")
                    if unexpected_keys:
                        logger.warning(f"⚠️ Unexpected keys: {unexpected_keys}")
                    logger.info("✅ Loaded state dict with strict=False")
                except Exception as non_strict_err:
                    logger.error(f"❌ Non-strict loading also failed: {non_strict_err}")
                    raise non_strict_err
            
            self.model.to(self.device)
            self.model.eval()
            
            logger.info(f"🎯 Custom trained TrOCR model loaded successfully from {checkpoint_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load trained model: {e}")
            logger.info("🔄 Falling back to pretrained model...")
            # Fallback to pretrained model
            self.processor = TrOCRProcessor.from_pretrained(base_model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(base_model_name)
            self.model.to(self.device)
            self.model.eval()
    
    def _is_numeric_output(self, text):
        """Check if output appears to be numeric tokens/IDs instead of decoded text"""
        if not text or len(text.strip()) == 0:
            return False
        
        # Count different character types
        alpha_count = sum(ch.isalpha() for ch in text)
        digit_count = sum(ch.isdigit() for ch in text)
        space_count = sum(ch.isspace() for ch in text)
        punct_count = sum(ch in '.,!?;:-' for ch in text)
        total_chars = len(text)
        
        # Calculate ratios
        alpha_ratio = alpha_count / max(total_chars, 1)
        digit_ratio = digit_count / max(total_chars, 1)
        
        # Patterns that suggest numeric output rather than text
        has_many_decimals = text.count('.') > 3
        has_scientific_notation = 'e-' in text.lower() or 'e+' in text.lower()
        mostly_numbers_and_spaces = (digit_count + space_count + text.count('.')) / max(total_chars, 1) > 0.8
        very_low_alpha = alpha_ratio < 0.1
        high_digit_ratio = digit_ratio > 0.6
        
        is_numeric = (very_low_alpha and high_digit_ratio) or has_many_decimals or has_scientific_notation or mostly_numbers_and_spaces
        
        logger.info(f"🔎 Text analysis: alpha={alpha_ratio:.2f}, digit={digit_ratio:.2f}, numeric_patterns={is_numeric}")
        return is_numeric
    
    def extract_text(self, image_path, language='en', include_dictionary=True):
        """
        Extract text from image using TrOCR with proper decoding and fallback
        Args:
            image_path: Path to image file or PIL Image object
            language: Language code for dictionary lookup (en, zh, ms)
            include_dictionary: Whether to perform dictionary lookup for single words
        Returns:
            dict: {
                'text': str - Extracted decoded text,
                'is_single_word': bool - Whether text is a single word,
                'word_definitions': list - Dictionary definitions if single word,
                'dictionary_status': str - Status of dictionary lookup
            }
        """
        try:
            logger.info(f"🔍 Starting OCR processing for image...")
            
            # Handle both file paths and PIL Image objects
            if isinstance(image_path, str):
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"Image file not found: {image_path}")
                image = Image.open(image_path).convert('RGB')
                logger.info(f"📷 Loaded image from path: {image_path}")
            else:
                image = image_path.convert('RGB')
                logger.info("📷 Using provided PIL Image object")
            
            # Validate image
            if image.size[0] == 0 or image.size[1] == 0:
                raise ValueError("Invalid image: zero dimensions")
            
            logger.info(f"🖼️ Image size: {image.size}")
            
            # Process image
            logger.info("🔄 Processing image through TrOCR processor...")
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)
            
            # Generate text with improved parameters
            logger.info(f"🧠 Generating text with TrOCR model (source={self.model_source})...")
            with torch.no_grad():
                generated_ids = self.model.generate(
                    pixel_values, 
                    max_length=512,
                    num_beams=4,  # Beam search for better quality
                    early_stopping=True,
                    pad_token_id=self.processor.tokenizer.pad_token_id,
                    eos_token_id=self.processor.tokenizer.eos_token_id
                )
            
            # CRITICAL: Ensure proper text decoding (not token IDs)
            logger.info("📝 Decoding generated tokens to text...")
            logger.info(f"🔍 Generated IDs shape: {generated_ids.shape}")
            logger.info(f"🔍 Generated IDs sample: {generated_ids[0][:10].tolist()}")
            
            try:
                decoded_texts = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
                generated_text = decoded_texts[0].strip() if decoded_texts else ""
                logger.info(f"📝 Decoded text length: {len(generated_text)}")
                logger.info(f"📝 Raw decoded text: '{generated_text}'")
            except Exception as decode_err:
                logger.error(f"❌ Decoding failed: {decode_err}")
                # Try alternative decoding approach
                try:
                    logger.info("🔄 Trying alternative decoding...")
                    decoded_texts = self.processor.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
                    generated_text = decoded_texts[0].strip() if decoded_texts else ""
                    logger.info(f"📝 Alternative decode successful: '{generated_text}'")
                except Exception as alt_decode_err:
                    logger.error(f"❌ Alternative decoding also failed: {alt_decode_err}")
                    return "Text decoding failed. Please try with a different image."
            
            if not generated_text:
                logger.warning("⚠️ OCR returned empty text")
                return "No text detected in the image."
            
            # VERIFICATION: Analyze the output for debugging
            alpha_count = sum(ch.isalpha() for ch in generated_text)
            digit_count = sum(ch.isdigit() for ch in generated_text)
            space_count = sum(ch.isspace() for ch in generated_text)
            punct_count = sum(ch in '.,!?;:-()[]{}' for ch in generated_text)
            total_chars = len(generated_text)
            
            logger.info("=" * 60)
            logger.info("🔍 TEXT VERIFICATION ANALYSIS:")
            logger.info(f"📊 Total characters: {total_chars}")
            logger.info(f"🔤 Alphabetic chars: {alpha_count} ({alpha_count/max(total_chars,1)*100:.1f}%)")
            logger.info(f"🔢 Numeric chars: {digit_count} ({digit_count/max(total_chars,1)*100:.1f}%)")
            logger.info(f"⬜ Spaces: {space_count} ({space_count/max(total_chars,1)*100:.1f}%)")
            logger.info(f"🔣 Punctuation: {punct_count} ({punct_count/max(total_chars,1)*100:.1f}%)")
            logger.info(f"📝 FULL TEXT OUTPUT: '{generated_text}'")
            
            if alpha_count > 0:
                logger.info("✅ SUCCESS: Text contains alphabetic characters - this looks like real text!")
            else:
                logger.warning("⚠️ WARNING: No alphabetic characters found - output may be numeric data")
            
            logger.info("=" * 60)

            # Prepare result dictionary
            result = {
                'text': generated_text,
                'is_single_word': False,
                'word_definitions': [],
                'dictionary_status': 'pending'
            }
            
            # Perform dictionary lookup for single words
            if include_dictionary and DICTIONARY_AVAILABLE and generated_text:
                logger.info("📖 Checking if text is a single word for dictionary lookup...")
                try:
                    is_single_word, definitions = lookup_word_definition(generated_text, language)
                    result['is_single_word'] = is_single_word
                    result['word_definitions'] = definitions
                    
                    if is_single_word:
                        if definitions:
                            result['dictionary_status'] = 'completed'
                            logger.info(f"📚 Found {len(definitions)} dictionary definitions for '{generated_text}'")
                            # Log first definition for debugging
                            if definitions:
                                first_def = definitions[0]
                                logger.info(f"📖 First definition: {first_def.get('definition', '')[:100]}...")
                        else:
                            result['dictionary_status'] = 'completed'
                            logger.info(f"📖 No dictionary definitions found for '{generated_text}'")
                    else:
                        result['dictionary_status'] = 'skipped'
                        logger.info("📖 Text is not a single word, skipping dictionary lookup")
                        
                except Exception as dict_err:
                    logger.error(f"❌ Dictionary lookup failed: {dict_err}")
                    result['dictionary_status'] = 'failed'
            else:
                result['dictionary_status'] = 'disabled'
                if not include_dictionary:
                    logger.info("📖 Dictionary lookup disabled")
                elif not DICTIONARY_AVAILABLE:
                    logger.warning("📖 Dictionary service not available")

            logger.info(f"✅ OCR completed successfully. Extracted {len(generated_text)} characters")
            return result
            
        except Exception as e:
            logger.error(f"❌ OCR processing failed: {e}")
            # Return error result in consistent format
            error_result = {
                'text': '',
                'is_single_word': False,
                'word_definitions': [],
                'dictionary_status': 'failed',
                'error': str(e)
            }
            
            # Provide more specific error messages
            if "CUDA" in str(e):
                error_result['error'] = f"GPU processing failed: {str(e)}. Try using CPU instead."
            elif "PIL" in str(e) or "Image" in str(e):
                error_result['error'] = f"Image processing failed: {str(e)}. Please check if the image file is valid."
            elif "tokenizer" in str(e).lower():
                error_result['error'] = f"Text processing failed: {str(e)}. Model may not be properly loaded."
            
            raise Exception(error_result['error'])

# Global OCR pipeline instance
_ocr_pipeline = None

def get_ocr_pipeline(checkpoint_path="best_checkpoint.pt"):
    """
    Get or create OCR pipeline instance with model caching
    Args:
        checkpoint_path: Path to trained model checkpoint
    Returns:
        OCRPipeline: Cached OCR pipeline instance
    """
    global _ocr_pipeline
    if _ocr_pipeline is None:
        try:
            # Environment toggles
            disable_local = os.getenv("OCR_DISABLE_LOCAL", "0").lower() in {"1", "true", "yes"}
            override_local_dir = os.getenv("OCR_LOCAL_MODEL_DIR", "").strip() or None
            
            # Detect local model directories in priority order
            project_root = Path(__file__).parent.parent
            resolved_local_dir = None if disable_local else override_local_dir
            
            if not disable_local and not resolved_local_dir:
                # 1) Check for trocr_iiit5k_word (new model)
                trocr_iiit5k_dir = project_root / "trocr_iiit5k_word"
                if trocr_iiit5k_dir.exists() and trocr_iiit5k_dir.is_dir():
                    # Validate it's a proper model directory
                    expected_files = [
                        trocr_iiit5k_dir / "config.json",
                        trocr_iiit5k_dir / "tokenizer.json",
                    ]
                    if all(p.exists() for p in expected_files):
                        resolved_local_dir = str(trocr_iiit5k_dir)
                        logger.info(f"🎯 Using trocr_iiit5k_word model directory: {resolved_local_dir}")
                    else:
                        logger.warning("⚠️ trocr_iiit5k_word directory found but missing expected files")
                
                # 2) Fallback to my_ocr_model if trocr_iiit5k_word not found
                if not resolved_local_dir:
                    local_model_dir = project_root / "my_ocr_model"
                    if local_model_dir.exists() and local_model_dir.is_dir():
                        expected_files = [
                            local_model_dir / "config.json",
                            local_model_dir / "tokenizer.json",
                        ]
                        if all(p.exists() for p in expected_files):
                            resolved_local_dir = str(local_model_dir)
                            logger.info(f"🎯 Using my_ocr_model directory: {resolved_local_dir}")
                        else:
                            logger.warning("⚠️ my_ocr_model directory found but missing expected files; skipping")

            # Try to find checkpoint in project root if no local dir
            resolved_checkpoint_path = None
            if not resolved_local_dir and checkpoint_path and not os.path.isabs(checkpoint_path):
                candidate = project_root / checkpoint_path
                if candidate.exists():
                    resolved_checkpoint_path = str(candidate)
                    logger.info(f"🎯 Found checkpoint at: {resolved_checkpoint_path}")
                else:
                    logger.warning(f"⚠️ Checkpoint not found at: {candidate}")

            _ocr_pipeline = OCRPipeline(
                checkpoint_path=resolved_checkpoint_path,
                local_model_dir=resolved_local_dir,
            )
            logger.info("✅ OCR pipeline cached successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OCR pipeline: {e}")
            raise
    
    return _ocr_pipeline

def clear_ocr_cache():
    """Clear the cached OCR pipeline (useful for testing or memory management)"""
    global _ocr_pipeline
    if _ocr_pipeline is not None:
        logger.info("🗑️ Clearing OCR pipeline cache")
        _ocr_pipeline = None
