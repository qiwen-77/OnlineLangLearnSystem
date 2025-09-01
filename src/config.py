"""
Configuration classes for OCR model training and inference
This file provides compatibility for loading trained checkpoints
"""

class OCRConfig:
    """Configuration class for OCR model"""
    def __init__(self, **kwargs):
        # Default configuration values
        self.model_name = kwargs.get('model_name', 'microsoft/trocr-base-printed')
        self.max_length = kwargs.get('max_length', 512)
        self.num_beams = kwargs.get('num_beams', 4)
        self.early_stopping = kwargs.get('early_stopping', True)
        
        # Add any other configuration parameters from kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        """Convert config to dictionary"""
        return {key: value for key, value in self.__dict__.items() 
                if not key.startswith('_')}
    
    @classmethod
    def from_dict(cls, config_dict):
        """Create config from dictionary"""
        return cls(**config_dict)

# Default configuration
DEFAULT_OCR_CONFIG = OCRConfig(
    model_name='microsoft/trocr-base-printed',
    max_length=512,
    num_beams=4,
    early_stopping=True
)
