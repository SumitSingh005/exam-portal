# Exam Portal

Exam Portal is a Django-based online examination system for students and teachers.  
Teachers can create exams, add questions, manage schedules, apply negative marking, and view reports.  
Students can register, attempt exams, view results, check leaderboards, and track performance from their profile page.

## Features

- Student and teacher authentication
- Exam creation and scheduling
- Question management
- Randomized question order
- Randomized answer options
- Negative marking support
- Pass/fail analytics
- Leaderboards
- Student profile and progress tracking
- Teacher reports
- Email notification support

## Tech Stack

- Python
- Django
- SQLite
- Bootstrap
- Chart.js

## Project Structure

```text
exam_portal/
├── accounts/
├── exams/
├── exam_portal/
├── static/
├── templates/
├── manage.py
├── .env.example
└── README.md
```

## Setup Steps

### 1. Clone or open the project

Make sure you are inside the project folder:

```powershell
cd exam_portal
```

### 2. Create virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Django

```powershell
pip install django
```

If you later add more dependencies, install them too.

### 4. Run migrations

```powershell
python manage.py makemigrations
python manage.py migrate
```

### 5. Create superuser

```powershell
python manage.py createsuperuser
```

### 6. Start development server

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Email Environment Variables

The project supports email notifications for:

- student registration
- teacher registration
- exam creation
- result publishing

Use the variables from `.env.example`.

Example PowerShell setup:

```powershell
$env:EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST="smtp.gmail.com"
$env:EMAIL_PORT="587"
$env:EMAIL_USE_TLS="True"
$env:EMAIL_HOST_USER="yourgmail@gmail.com"
$env:EMAIL_HOST_PASSWORD="your_16_char_app_password"
$env:DEFAULT_FROM_EMAIL="yourgmail@gmail.com"
python manage.py runserver
```

If you do not set these, the project falls back to Django's console email backend. In that mode, password reset emails are generated, but they are printed in the terminal instead of being sent to a real inbox.

## Roles

### Student

- register and login
- view available exams
- attempt exams
- view results
- view leaderboard
- view profile and performance history

### Teacher

- register and login
- create exams
- set exam schedule
- configure pass percentage
- configure negative marking
- add and manage questions
- view reports
- view analytics

## Main Features Added

### Exam Scheduling

Teachers can set:

- start date and time
- end date and time

Students can only attempt exams during the active time window.

### Auto Result Analytics

- pass/fail status
- percentage
- topper
- average marks
- question-wise performance

### Negative Marking

Teachers can define:

- marks for correct answers
- marks for wrong answers

### Leaderboards

Students can see top scorers for each exam.

### Student Profile

Students can view:

- exam history
- average marks
- percentage trend
- improvement over time

### Teacher Reports

Teachers can see:

- who attempted the exam
- highest score
- lowest score
- weak questions
- number of students per exam

### Randomization

- question order is shuffled
- answer options are shuffled

## Database Note

This project uses SQLite, but on Windows the active database is configured to live outside the OneDrive project folder by default.

Default database path:

```text
C:\Users\<YourUser>\AppData\Local\ExamPortal\db.sqlite3
```

This avoids the `sqlite3.OperationalError: disk I/O error` problem that can happen when SQLite files are stored inside OneDrive-synced folders.

If you want to use a different SQLite file, set:

```powershell
$env:SQLITE_NAME="C:\path\to\your\db.sqlite3"
```

## Useful Commands

### Run server

```powershell
python manage.py runserver
```

### Make migrations

```powershell
python manage.py makemigrations
```

### Apply migrations

```powershell
python manage.py migrate
```

### Create admin user

```powershell
python manage.py createsuperuser
```

## Future Improvements

- Export results to CSV
- Certificate generation
- Webcam or proctoring support
- Subjective questions
- SMS or WhatsApp notifications
- HTML email templates for notifications

## Author

Built as an online exam management project using Django.
