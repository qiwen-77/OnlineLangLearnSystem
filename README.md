# Language Learning Hub

A comprehensive Django web application for language learning powered by OCR (Optical Character Recognition) and TTS (Text-to-Speech) technology. This platform provides user authentication, personalized learning experiences, and progress tracking for effective language learning.

## 🎯 Features

### 👤 User Management
- **User Registration & Authentication**: Secure user accounts with email verification
- **Personal Profiles**: Customizable learning preferences and target languages
- **Password Reset**: Email-based password recovery system
- **Progress Tracking**: Detailed learning statistics and achievements

### 🧠 AI-Powered Learning
- **Smart OCR**: Extract text from handwritten or printed images using TrOCR technology
- **Natural TTS**: Convert text to speech with multiple voice options
- **Multi-language Support**: Learn various languages with native pronunciation
- **Difficulty Levels**: Adaptive content based on user proficiency

### 📊 Learning Management
- **Personal Dashboard**: Overview of learning progress and recent activities
- **Session History**: Track all learning sessions with detailed metadata
- **Favorites**: Save and organize preferred learning materials
- **Statistics**: Comprehensive analytics on learning patterns and progress

## 🛠️ Current Status

**✅ Completed:**
- Full-featured Django web application with PostgreSQL support
- User authentication system (registration, login, logout, password reset)
- Personal user dashboards with learning statistics
- Enhanced database models for user profiles and learning history
- Responsive Bootstrap UI with modern design
- Session management and progress tracking
- Administrative interface for content management
- Security features (CSRF protection, user permissions)
- Multi-language support infrastructure

**⏳ Pending (After Model Training):**
- OCR pipeline integration (TrOCR model)
- TTS pipeline integration (TTS model)
- Audio generation and processing
- Advanced learning analytics
- Vocabulary management features

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

4. **Set up PostgreSQL (Optional):**
   - Install PostgreSQL on your system
   - Create a database named `language_learning_db`
   - Set environment variables or update `settings.py`:
     ```bash
     export DB_NAME=language_learning_db
     export DB_USER=postgres
     export DB_PASSWORD=your_password
     export DB_HOST=localhost
     export DB_PORT=5432
     ```
   - The app will fallback to SQLite if PostgreSQL is not available

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
- **Upload**: `http://127.0.0.1:8000/upload/` - Image upload for OCR
- **Text to Speech**: `http://127.0.0.1:8000/text-to-speech/` - Direct text input
- **Session History**: `http://127.0.0.1:8000/sessions/` - View learning history
- **Profile**: `http://127.0.0.1:8000/auth/profile/` - User profile management

### Admin URLs
- **Admin Panel**: `http://127.0.0.1:8000/admin/` - Django admin interface

## 📁 Project Structure

```
OnlineLangLearnSystem/
├── language_app/          # Main Django project
│   ├── settings.py       # Project settings
│   ├── urls.py          # Main URL configuration
│   └── ...
├── ocr_tts_app/          # Main application
│   ├── models.py        # Database models
│   ├── views.py         # View functions
│   ├── forms.py         # Form definitions
│   ├── urls.py          # App URL patterns
│   └── templates/       # HTML templates
├── src/                  # OCR & TTS pipelines (to be integrated)
│   ├── ocr_pipeline.py  # TrOCR implementation
│   └── tts/
│       └── tts_pipeline.py  # TTS implementation
├── static/               # CSS, JS, images
├── media/                # User uploads and generated files
│   ├── images/          # Uploaded images
│   └── audio/           # Generated audio files
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Configuration

### Settings
Key configuration options in `language_app/settings.py`:

- **Media Files**: Configured for file uploads and audio generation
- **Static Files**: Bootstrap and custom CSS/JS
- **Database**: SQLite (default) - easily changeable for production
- **File Upload Limits**: 10MB max file size

### Model Integration (After Training)
To integrate your trained models:

1. **OCR Integration**:
   - Uncomment OCR imports in `ocr_tts_app/views.py`
   - Update `src/ocr_pipeline.py` with your trained TrOCR model
   - Uncomment OCR processing methods

2. **TTS Integration**:
   - Uncomment TTS imports in `ocr_tts_app/views.py`
   - Update `src/tts/tts_pipeline.py` with your trained TTS model
   - Uncomment TTS processing methods

## 🎨 User Interface

The application features a modern, responsive design with:

- **Bootstrap 5**: Professional styling and components
- **Interactive Forms**: Image preview, character counters
- **Status Indicators**: Real-time processing status
- **Audio Players**: Built-in HTML5 audio controls
- **Responsive Design**: Works on desktop and mobile devices

## 🔄 Workflow

1. **Image Upload**: Users upload images containing text
2. **OCR Processing**: Extract text using TrOCR model (pending integration)
3. **TTS Processing**: Convert text to speech audio (pending integration)
4. **Results Display**: Show extracted text and audio player
5. **History Tracking**: Save and display processing sessions

## 🧪 Testing

Currently available for testing:
- Web interface functionality
- File upload handling
- Database operations
- Template rendering
- URL routing

After model integration:
- OCR accuracy testing
- TTS quality evaluation
- End-to-end workflow testing

## 📊 Database Schema

### OCRTTSSession Model
- `session_id`: Unique identifier (UUID)
- `uploaded_image`: Image file field
- `extracted_text`: OCR results
- `audio_file_path`: Generated audio file
- `ocr_status`: Processing status (pending/processing/completed/failed)
- `tts_status`: Processing status (pending/processing/completed/failed)
- `processing_time_*`: Performance metrics
- `created_at/updated_at`: Timestamps

## 🚀 Production Deployment

For production deployment, consider:

1. **Environment Variables**: Use environment variables for sensitive settings
2. **Database**: Switch to PostgreSQL or MySQL
3. **Static Files**: Use WhiteNoise or CDN for static file serving
4. **Media Files**: Use cloud storage (AWS S3, etc.)
5. **Web Server**: Deploy with Gunicorn + Nginx
6. **Security**: Update `ALLOWED_HOSTS`, use HTTPS, etc.

## 🤝 Contributing

This project is ready for model integration. To contribute:

1. Complete OCR model training
2. Complete TTS model training
3. Integrate models using the prepared pipeline structure
4. Test the complete workflow
5. Optimize performance and user experience

## 📝 License

This project is part of a Final Year Project (FYP) for academic purposes.

---

**Ready for Model Integration** 🎯

The Django application is fully set up and ready for your trained OCR and TTS models to be integrated!
