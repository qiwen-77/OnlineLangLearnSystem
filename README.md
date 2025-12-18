# Online Language Learning System

A comprehensive Django web application for language learning powered by **OCR (Optical Character Recognition)**, **TTS (Text-to-Speech)**, **Translation**, and **Dictionary Lookup** technology. This platform provides multilingual support (English, Chinese, Malay), user authentication, personalized learning experiences, and comprehensive progress tracking for effective language learning.

## 🎯 Features

### 👤 User Management
- **User Registration & Authentication**: Secure user accounts with email verification
- **Personal Profiles**: Customizable learning preferences and target languages
- **Password Reset**: Email-based password recovery system
- **Progress Tracking**: Detailed learning statistics and achievements

### 🧠 AI-Powered Learning
- **Smart OCR**: Extract text from handwritten or printed images using custom-trained TrOCR models
- **High-Quality TTS**: Convert text to speech with SpeechT5 + HiFi-GAN vocoder
- **Voice Options**: Male/female voice selection with CMU Arctic speaker embeddings
- **Multilingual Translation**: English ↔ Chinese ↔ Malay using M2M100 model
- **Dictionary Lookup**: Automatic word definitions with Free Dictionary API + NLTK WordNet fallback
- **AI Tutor (RAG)**: Ask natural-language questions about extracted text and get contextual explanations using embeddings, FAISS vector search, and a local LLM
- **Audio Quality**: Fixed 0.5x speed for optimal clarity and volume enhancement
### 🧠 AI-Powered Learning
- **Smart OCR**: Extract text from handwritten or printed images using custom-trained TrOCR models
- **High-Quality TTS**: Convert text to speech with SpeechT5 + HiFi-GAN vocoder
- **Voice Options**: Male/female voice selection with CMU Arctic speaker embeddings
- **Multilingual Translation**: English ↔ Chinese ↔ Malay using M2M100 model
- **Dictionary Lookup**: Automatic word definitions with Free Dictionary API + NLTK WordNet fallback
- **AI Tutor (RAG)**: Ask natural-language questions about extracted text and get contextual explanations using embeddings, FAISS vector search, and a local LLM
- **Audio Quality**: Fixed 0.5x speed for optimal clarity and volume enhancement

### 📊 Learning Management
- **Personal Dashboard**: Overview of learning progress and recent activities
- **Session History**: Track all learning sessions with detailed metadata
- **Export Learning Notes**: Generate comprehensive .txt files with OCR text, definitions, and translations
- **Statistics**: Comprehensive analytics on learning patterns and progress
- **Single Word Detection**: Automatic dictionary lookup for individual words

## 🛠️ Current Status

**✅ Fully Completed:**
- **Complete Django web application** with SQLite database
- **User authentication system** (registration, login, logout, password reset)
- **OCR Pipeline Integration** - Custom TrOCR models with automatic fallback
- **TTS Pipeline Integration** - SpeechT5 + HiFi-GAN with voice options
- **Translation Service** - M2M100 multilingual translation
- **Dictionary Lookup** - Online API + offline NLTK WordNet fallback
- **Export Learning Notes** - Comprehensive .txt file generation
- **Personal user dashboards** with learning statistics
- **Enhanced database models** for user profiles and learning history
- **Responsive Bootstrap UI** with modern design and custom confirmations
- **Session management** and progress tracking
- **Administrative interface** for content management
- **Security features** (CSRF protection, user permissions)
- **Multilingual support** (English, Chinese, Malay)
- **Audio file management** and playback controls
- **Copy to clipboard** functionality for text and definitions
- **Error handling** and fallback mechanisms

**🎯 System Ready for Production Use!**

## 📦 Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Setup Instructions

1. **Clone or navigate to the project directory:**
   ```bash
   cd OnlineLangLearnSystem
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database Setup:**
   - The application uses **SQLite** by default (no additional setup required)
   - Database file will be created automatically as `db.sqlite3`
   - For production, you can easily switch to PostgreSQL or MySQL by updating `settings.py`

5. **Run database migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a superuser:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

8. **Access the application:**
   Open your web browser and go to: `http://127.0.0.1:8000/`

## 🌐 Application URLs

### Public URLs
- **Home**: `http://127.0.0.1:8000/` - Landing page with platform information
- **Register**: `http://127.0.0.1:8000/auth/register/` - User registration
- **Login**: `http://127.0.0.1:8000/auth/login/` - User login

### Authenticated User URLs
- **Dashboard**: `http://127.0.0.1:8000/dashboard/` - Personal learning dashboard
- **Upload**: `http://127.0.0.1:8000/upload/` - Image upload for OCR processing
- **Text to Speech**: `http://127.0.0.1:8000/text-to-speech/` - Direct text input with voice options
- **Translation**: `http://127.0.0.1:8000/translate/` - Dedicated translation interface
- **Session History**: `http://127.0.0.1:8000/sessions/` - View learning history and statistics
- **Profile**: `http://127.0.0.1:8000/auth/profile/` - User profile management

### Admin URLs
- **Admin Panel**: `http://127.0.0.1:8000/admin/` - Django admin interface

## 📁 Project Structure

```
OnlineLangLearnSystem/
├── language_app/          # Main Django project
│   ├── settings.py       # Project settings (SQLite database)
│   ├── urls.py          # Main URL configuration
│   └── ...
├── accounts/             # User authentication app
│   ├── models.py        # User and UserProfile models
│   ├── views.py         # Registration, login, profile views
│   ├── forms.py         # Custom forms with validation
│   └── signals.py       # Auto-create UserProfile on registration
├── ocr_tts_app/          # Main application
│   ├── models.py        # LearningHistory, Statistics models
│   ├── views.py         # OCR, TTS, translation, export views
│   ├── urls.py          # App URL patterns
│   └── templates/       # HTML templates with Bootstrap 5
├── src/                  # Core AI services
│   └── ocr_pipeline.py  # TrOCR model loading and text extraction
├── services/             # External service integrations
│   ├── tts_service.py   # SpeechT5 TTS with voice options
│   ├── translation_service.py  # M2M100 translation pipeline
│   └── dictionary_service.py   # Dictionary lookup with caching
├── static/               # CSS, JS, images
├── media/                # User uploads and generated files
│   ├── uploads/         # Uploaded images
│   └── tts/             # Generated audio files
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Configuration

### Settings
Key configuration options in `language_app/settings.py`:

- **Database**: SQLite (default) - automatically creates `db.sqlite3`
- **Media Files**: Configured for file uploads and audio generation
- **Static Files**: Bootstrap 5 and custom CSS/JS
- **File Upload Limits**: 10MB max file size
- **Supported Languages**: English, Chinese, Malay
- **Default Target Language**: English

### AI Model Integration
The system includes fully integrated AI models:

1. **OCR Pipeline** (`src/ocr_pipeline.py`):
   - Custom TrOCR models: `trocr_iiit5k_word/`, `my_ocr_model/`
   - Automatic fallback to Microsoft TrOCR
   - Numeric output detection and retry mechanism

2. **TTS Service** (`services/tts_service.py`):
   - SpeechT5 + HiFi-GAN vocoder
   - CMU Arctic speaker embeddings for voice variety
   - Fixed 0.5x speed for optimal clarity

3. **Translation Service** (`services/translation_service.py`):
   - M2M100 multilingual model
   - English ↔ Chinese ↔ Malay support

4. **Dictionary Service** (`services/dictionary_service.py`):
   - Free Dictionary API (online)
   - NLTK WordNet (offline fallback)
   - LRU caching for performance

## 🎨 User Interface

The application features a modern, responsive design with:

- **Bootstrap 5**: Professional styling and components
- **Interactive Forms**: Image preview, character counters, voice selection
- **Status Indicators**: Real-time processing status with progress bars
- **Audio Players**: Built-in HTML5 audio controls with play/pause
- **Custom Modals**: Confirmation dialogs for important actions
- **Copy to Clipboard**: One-click copying of text and definitions
- **Export Functionality**: Download learning notes as .txt files
- **Responsive Design**: Works on desktop and mobile devices

## 🔄 Complete Learning Workflow

1. **Image Upload**: Users upload images containing text (PNG, JPG, JPEG)
2. **OCR Processing**: Extract text using custom TrOCR models with automatic fallback
3. **Dictionary Lookup**: If single word detected, automatically fetch definitions
4. **TTS Processing**: Convert text to speech with high-quality audio generation
5. **Translation**: Optional translation to other supported languages
6. **Results Display**: Show extracted text, definitions, audio player, and translations
7. **Export Learning Notes**: Generate comprehensive .txt files for offline study
8. **History Tracking**: Save and display all processing sessions with statistics

## 🧪 Testing

**Fully Tested and Working:**
- ✅ Web interface functionality
- ✅ File upload handling and validation
- ✅ Database operations (SQLite)
- ✅ Template rendering and responsive design
- ✅ URL routing and navigation
- ✅ OCR accuracy with custom models
- ✅ TTS quality with SpeechT5 + HiFi-GAN
- ✅ Translation accuracy (English ↔ Chinese ↔ Malay)
- ✅ Dictionary lookup functionality
- ✅ Export learning notes feature
- ✅ End-to-end workflow testing
- ✅ Error handling and fallback mechanisms

## 📊 Database Schema

### LearningHistory Model
- `session_id`: Unique identifier (UUID)
- `user`: Foreign key to User model
- `uploaded_image`: Image file field
- `extracted_text`: OCR results
- `audio_url`: Generated audio file URL
- `audio_filename`: Audio file name
- `word_count`: Number of words extracted
- `is_single_word`: Boolean flag for dictionary lookup
- `word_definitions`: JSON field for dictionary results
- `dictionary_status`: Dictionary lookup status
- `ocr_status`: Processing status (pending/processing/completed/failed)
- `tts_status`: Processing status (pending/processing/completed/failed)
- `processing_time_ocr`: OCR processing time
- `processing_time_tts`: TTS processing time
- `created_at/updated_at`: Timestamps

### UserProfile Model
- `user`: One-to-one relationship with User
- `target_language`: User's target language preference
- `voice_preference`: TTS voice preference (male/female)
- `created_at/updated_at`: Timestamps

## 🚀 Production Deployment

For production deployment, consider:

1. **Environment Variables**: Use environment variables for sensitive settings
2. **Database**: Switch to PostgreSQL or MySQL for better performance
3. **Static Files**: Use WhiteNoise or CDN for static file serving
4. **Media Files**: Use cloud storage (AWS S3, etc.) for uploaded images and audio
5. **Web Server**: Deploy with Gunicorn + Nginx
6. **Security**: Update `ALLOWED_HOSTS`, use HTTPS, etc.
7. **Model Caching**: Implement Redis for AI model caching
8. **Load Balancing**: For high-traffic scenarios

## 🤝 Contributing

This project is **fully functional and ready for use**. To contribute:

1. **Feature Enhancements**: Add new language support or improve existing features
2. **UI/UX Improvements**: Enhance the user interface and experience
3. **Performance Optimization**: Improve model loading and processing speed
4. **Testing**: Add comprehensive test coverage
5. **Documentation**: Improve code documentation and user guides

## 📝 License

This project is part of a Final Year Project (FYP) for academic purposes.

---

## 🎉 **System Complete and Ready for Use!** 

The Online Language Learning System is **fully functional** with all AI models integrated and tested. Users can:

- ✅ Upload images and extract text using custom TrOCR models
- ✅ Generate high-quality speech using SpeechT5 + HiFi-GAN
- ✅ Translate text between English, Chinese, and Malay
- ✅ Look up word definitions automatically
- ✅ Export comprehensive learning notes
- ✅ Track learning progress and statistics

**Start learning languages today!** 🚀
