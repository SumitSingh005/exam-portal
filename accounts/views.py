from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Max, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from exams.models import Exam, Question, Result, ResultAnswer

User = get_user_model()


# ========================
# SECURITY SETTINGS
# ========================
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def log_security_event(event_type, user=None, ip_address=None, details=""):
    """
    Log security-related events for audit purposes.
    """
    import os
    
    log_file = getattr(settings, 'SECURITY_LOG_FILE', os.path.join(settings.BASE_DIR, "security.log"))
    
    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    username = user.username if user else "Anonymous"
    ip = ip_address or "Unknown"
    
    log_entry = f"[{timestamp}] {event_type} | User: {username} | IP: {ip} | {details}\n"
    
    try:
        with open(log_file, "a") as f:
            f.write(log_entry)
    except Exception:
        pass  # Don't break app if logging fails


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def send_notification_email(subject, message, recipients):
    clean_recipients = [email for email in recipients if email]
    if not clean_recipients:
        return

    send_mail(
        subject,
        message,
        None,
        clean_recipients,
        fail_silently=True,
    )


def build_teacher_ai_assistant(exam_analytics, pending_reviews, average_percentage, students_attempted, total_exams):
    focus_points = []
    action_items = []

    if not total_exams:
        return {
            'status': 'Ready to Assist',
            'summary': 'Create your first exam to unlock teaching insights and performance recommendations.',
            'risk_label': 'No data yet',
            'focus_points': [
                'No exams have been created yet.',
                'Add questions with clear marking rules to start collecting analytics.',
            ],
            'action_items': [
                'Create an exam',
                'Add MCQ or written questions',
                'Publish the schedule for students',
            ],
        }

    if not students_attempted:
        return {
            'status': 'Awaiting Attempts',
            'summary': 'Your exams are ready, but student attempt data is not available yet.',
            'risk_label': 'Waiting for data',
            'focus_points': [
                f'{total_exams} exam is available for students.',
                'Analytics will improve once students submit attempts.',
            ],
            'action_items': [
                'Check that exam schedules are active',
                'Confirm exams are published',
                'Share the exam window with students',
            ],
        }

    weakest_exam = None
    busiest_exam = None
    weak_question = None

    for item in exam_analytics:
        if item['attempts'] and (weakest_exam is None or item['average_percentage'] < weakest_exam['average_percentage']):
            weakest_exam = item
        if item['attempts'] and (busiest_exam is None or item['attempts'] > busiest_exam['attempts']):
            busiest_exam = item
        for question in item.get('question_performance', []):
            if question['attempts'] and (weak_question is None or question['accuracy'] < weak_question['accuracy']):
                weak_question = question

    if average_percentage >= 75:
        status = 'Class Performing Well'
        risk_label = 'Low risk'
        summary = 'Most finalized attempts are strong. Keep monitoring weak questions and pending reviews.'
    elif average_percentage >= 50:
        status = 'Needs Light Support'
        risk_label = 'Medium risk'
        summary = 'Class performance is moderate. A short revision or clarification session can improve results.'
    else:
        status = 'Intervention Suggested'
        risk_label = 'High risk'
        summary = 'Average performance is low. Review question difficulty and provide guided revision.'

    if weakest_exam:
        focus_points.append(f'Lowest average exam: {weakest_exam["exam"].title} at {weakest_exam["average_percentage"]}%.')
        action_items.append(f'Review performance for {weakest_exam["exam"].title}')
    else:
        focus_points.append('No finalized exam averages are available yet.')

    if busiest_exam:
        focus_points.append(f'Most attempted exam: {busiest_exam["exam"].title} with {busiest_exam["attempts"]} attempts.')

    if weak_question:
        question_text = weak_question['question_text']
        if len(question_text) > 90:
            question_text = f'{question_text[:87]}...'
        focus_points.append(f'Weakest question accuracy: {weak_question["accuracy"]}% - {question_text}')
        action_items.append('Clarify or revise the weakest question')

    if pending_reviews:
        focus_points.append(f'{pending_reviews} written answer review is pending.')
        action_items.append('Complete pending written-answer reviews')

    action_items.extend([
        'Export reports for offline analysis',
        'Compare pass count with average percentage',
    ])

    return {
        'status': status,
        'summary': summary,
        'risk_label': risk_label,
        'focus_points': focus_points[:4],
        'action_items': action_items[:5],
    }


def build_teacher_analytics(user):
    exams = Exam.objects.filter(created_by=user)
    total_exams = exams.count()
    total_questions = Question.objects.filter(exam__created_by=user).count()
    result_qs = Result.objects.filter(exam__created_by=user).select_related('exam', 'student')
    finalized_results = result_qs.filter(review_pending=False)
    students_attempted = result_qs.values('student').distinct().count()
    average_marks = finalized_results.aggregate(avg=Avg('score'))['avg'] or 0
    average_percentage = finalized_results.aggregate(avg=Avg('percentage'))['avg'] or 0
    topper = finalized_results.order_by('-score', '-percentage', 'submitted_at').first()
    pending_reviews = result_qs.filter(review_pending=True).count()

    exam_analytics = []
    for exam in exams.order_by('-id')[:5]:
        exam_results = result_qs.filter(exam=exam)
        finalized_exam_results = exam_results.filter(review_pending=False)
        question_performance = ResultAnswer.objects.filter(
            result__exam=exam
        ).filter(
            Q(question__question_type='mcq') | Q(reviewed=True)
        ).values(
            'question__id',
            'question__question_text',
        ).annotate(
            attempts=Count('id'),
            correct_count=Count('id', filter=Q(is_correct=True)),
        ).order_by('question__id')

        exam_analytics.append({
            'exam': exam,
            'attempts': exam_results.count(),
            'pending_reviews': exam_results.filter(review_pending=True).count(),
            'average_marks': round(finalized_exam_results.aggregate(avg=Avg('score'))['avg'] or 0, 2),
            'average_percentage': round(finalized_exam_results.aggregate(avg=Avg('percentage'))['avg'] or 0, 2),
            'top_score': finalized_exam_results.aggregate(top=Max('score'))['top'] or 0,
            'pass_count': finalized_exam_results.filter(passed=True).count(),
            'question_performance': [
                {
                    'question_text': item['question__question_text'],
                    'attempts': item['attempts'],
                    'correct_count': item['correct_count'],
                    'accuracy': round((item['correct_count'] / item['attempts']) * 100, 2) if item['attempts'] else 0,
                }
                for item in question_performance
            ],
        })

    teacher_ai_assistant = build_teacher_ai_assistant(
        exam_analytics=exam_analytics,
        pending_reviews=pending_reviews,
        average_percentage=round(average_percentage, 2),
        students_attempted=students_attempted,
        total_exams=total_exams,
    )

    return {
        'total_exams': total_exams,
        'total_questions': total_questions,
        'students_attempted': students_attempted,
        'average_marks': round(average_marks, 2),
        'average_percentage': round(average_percentage, 2),
        'topper': topper,
        'pending_reviews': pending_reviews,
        'exam_analytics': exam_analytics,
        'teacher_ai_assistant': teacher_ai_assistant,
    }


def build_student_ai_coach(finalized_results, pending_reviews, avg_percentage, improvement, active_exam_count, upcoming_exam_count):
    recent_results = list(finalized_results.order_by('-submitted_at')[:3])
    focus_points = []
    action_items = []

    if not recent_results:
        return {
            'status': 'Getting Started',
            'summary': 'AI Study Coach will become smarter after your first submitted exam.',
            'risk_label': 'No data yet',
            'focus_points': [
                'Attempt an available exam to unlock personalized performance guidance.',
                'Read exam instructions carefully before starting.',
            ],
            'action_items': [
                'Browse available exams',
                'Check schedule and attempt limits',
            ],
        }

    latest_result = recent_results[0]
    weakest_result = min(recent_results, key=lambda result: result.percentage)

    if pending_reviews:
        focus_points.append(f'{pending_reviews} result is waiting for teacher review.')

    if improvement > 0:
        focus_points.append(f'Your recent trend is improving by {improvement}%.')
    elif improvement < 0:
        focus_points.append(f'Your recent trend dropped by {abs(improvement)}%.')
    else:
        focus_points.append('Your recent trend is stable.')

    focus_points.append(f'Lowest recent exam: {weakest_result.exam.title} at {weakest_result.percentage}%.')

    if avg_percentage >= 75:
        status = 'Strong Momentum'
        risk_label = 'Low risk'
        summary = 'You are performing well. Keep practicing consistently and protect your accuracy.'
        action_items.extend([
            'Review only the questions you missed',
            'Attempt the next live exam when ready',
        ])
    elif avg_percentage >= 50:
        status = 'Almost There'
        risk_label = 'Medium risk'
        summary = 'You are close to a strong average. A focused review before the next exam should help.'
        action_items.extend([
            f'Revise {weakest_result.exam.title}',
            'Practice speed and accuracy before the next attempt',
        ])
    else:
        status = 'Needs Focus'
        risk_label = 'High risk'
        summary = 'Focus on building accuracy first. Review mistakes before attempting another exam.'
        action_items.extend([
            f'Restudy {weakest_result.exam.title}',
            'Spend extra time on wrong answers and concepts',
        ])

    if active_exam_count:
        action_items.append('Prioritize live exams with attempts left')
    elif upcoming_exam_count:
        action_items.append('Prepare for the next scheduled exam')
    else:
        action_items.append('Use result history for revision until a new exam is published')

    return {
        'status': status,
        'summary': summary,
        'risk_label': risk_label,
        'focus_points': focus_points,
        'action_items': action_items,
        'latest_exam': latest_result.exam.title,
        'latest_percentage': round(latest_result.percentage, 2),
    }


def build_student_analytics(user):
    now = timezone.now()
    exams = list(Exam.objects.all().order_by('start_time', 'title'))
    results = Result.objects.filter(student=user).select_related('exam').order_by('-submitted_at')
    finalized_results = results.filter(review_pending=False)
    avg_score = finalized_results.aggregate(avg=Avg('score'))['avg'] or 0
    avg_percentage = finalized_results.aggregate(avg=Avg('percentage'))['avg'] or 0
    pass_count = finalized_results.filter(passed=True).count()
    pending_reviews = results.filter(review_pending=True).count()
    ordered_results = list(finalized_results.order_by('submitted_at'))
    first_percentage = ordered_results[0].percentage if ordered_results else 0
    latest_percentage = ordered_results[-1].percentage if ordered_results else 0
    improvement = round(latest_percentage - first_percentage, 2) if ordered_results else 0

    active_exam_count = 0
    upcoming_exam_count = 0
    recommended_exam = None

    for exam in exams:
        used_attempts = results.filter(exam=exam).count()
        exam.used_attempts = used_attempts
        exam.remaining_attempts = None if exam.max_attempts == 0 else max(exam.max_attempts - used_attempts, 0)
        has_attempts_left = exam.has_unlimited_attempts or exam.remaining_attempts > 0

        if exam.is_active and has_attempts_left:
            active_exam_count += 1
            if recommended_exam is None:
                recommended_exam = exam
        elif (
            exam.is_published
            and exam.start_time
            and exam.start_time > now
            and has_attempts_left
        ):
            upcoming_exam_count += 1
            if recommended_exam is None:
                recommended_exam = exam

    completion_rate = round((pass_count / finalized_results.count()) * 100, 2) if finalized_results.exists() else 0
    readiness_message = "Start with any available exam to build your performance history."
    if finalized_results.exists():
        if avg_percentage >= 75:
            readiness_message = "You are performing strongly. Keep the streak steady in your next exam."
        elif avg_percentage >= 50:
            readiness_message = "You are close to a strong average. Review recent mistakes before the next exam."
        else:
            readiness_message = "Focus on accuracy first. Review results, then attempt the next available exam."

    ai_coach = build_student_ai_coach(
        finalized_results=finalized_results,
        pending_reviews=pending_reviews,
        avg_percentage=avg_percentage,
        improvement=improvement,
        active_exam_count=active_exam_count,
        upcoming_exam_count=upcoming_exam_count,
    )

    return {
        'total_exams': len(exams),
        'attempted_exams': results.count(),
        'avg_score': round(avg_score, 2),
        'avg_percentage': round(avg_percentage, 2),
        'pass_count': pass_count,
        'pending_reviews': pending_reviews,
        'results': results[:5],
        'all_results': results,  # Chart needs all results for full history
        'exams': exams,
        'full_results': ordered_results,
        'improvement': improvement,
        'first_percentage': round(first_percentage, 2),
        'latest_percentage': round(latest_percentage, 2),
        'active_exam_count': active_exam_count,
        'upcoming_exam_count': upcoming_exam_count,
        'recommended_exam': recommended_exam,
        'completion_rate': completion_rate,
        'readiness_message': readiness_message,
        'ai_coach': ai_coach,
    }


def home(request):
    return render(request, 'home.html')


def normalize_student_id(value):
    return (value or '').strip().upper()


def validate_signup_data(username, email, password1, password2, student_id=None, require_student_id=False):
    username = (username or '').strip()
    email = (email or '').strip().lower()
    student_id = normalize_student_id(student_id)
    password1 = password1 or ''
    password2 = password2 or ''

    if not username or not email:
        return username, email, student_id, "Username and email are required."

    if require_student_id and not student_id:
        return username, email, student_id, "Student ID is required."

    if password1 != password2:
        return username, email, student_id, "Passwords do not match"

    if User.objects.filter(username__iexact=username).exists():
        return username, email, student_id, "Username already exists"

    if student_id and User.objects.filter(student_id__iexact=student_id).exists():
        return username, email, student_id, "Student ID already exists"

    if User.objects.filter(email__iexact=email).exists():
        return username, email, student_id, "Email already exists"

    try:
        validate_password(password1, user=User(username=username, email=email))
    except ValidationError as exc:
        return username, email, student_id, " ".join(exc.messages)

    return username, email, student_id, None


def get_user_by_login_identifier(identifier):
    identifier = (identifier or '').strip()
    if not identifier:
        return None

    student_id = normalize_student_id(identifier)
    return User.objects.filter(
        Q(username__iexact=identifier) | Q(student_id__iexact=student_id)
    ).first()


def student_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        student_id = request.POST.get('student_id')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        username, email, student_id, validation_error = validate_signup_data(
            username,
            email,
            password1,
            password2,
            student_id=student_id,
            require_student_id=True,
        )
        if validation_error:
            messages.error(request, validation_error)
            return redirect('student_signup')

        user = User.objects.create_user(username=username, email=email, password=password1)
        user.is_student = True
        user.student_id = student_id
        user.save()

        send_notification_email(
            "Welcome to Exam Portal",
            f"Hello {username},\n\nYour student account has been created successfully.",
            [email],
        )

        messages.success(request, "Account created successfully! Please login.")
        return redirect('login')

    return render(request, 'accounts/student_signup.html')


def teacher_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        username, email, _student_id, validation_error = validate_signup_data(username, email, password1, password2)
        if validation_error:
            messages.error(request, validation_error)
            return redirect('teacher_signup')

        user = User.objects.create_user(username=username, email=email, password=password1)
        user.is_teacher = True
        user.save()

        send_notification_email(
            "Welcome to Exam Portal",
            f"Hello {username},\n\nYour teacher account has been created successfully.",
            [email],
        )

        messages.success(request, "Account created successfully! Please login.")
        return redirect('login')

    return render(request, 'accounts/teacher_signup.html')


def user_login(request):
    if request.method == 'POST':
        login_identifier = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Try to get user for lockout check
        user_obj = get_user_by_login_identifier(login_identifier)
        
        # Check if account is locked
        if user_obj and user_obj.locked_until:
            if timezone.now() < user_obj.locked_until:
                remaining_time = (user_obj.locked_until - timezone.now()).seconds // 60
                messages.error(request, f"Account locked. Try again in {remaining_time} minutes.")
                log_security_event("LOGIN_BLOCKED_LOCKED", user_obj, client_ip, "Locked account login attempt")
                return render(request, 'accounts/login.html')
            else:
                # Lockout expired, reset attempts
                user_obj.failed_login_attempts = 0
                user_obj.locked_until = None
                user_obj.save()
        
        # Check if account is manually deactivated
        if user_obj and not user_obj.is_active_manual:
            messages.error(request, "Account has been deactivated. Contact support.")
            log_security_event("LOGIN_BLOCKED_INACTIVE", user_obj, client_ip, "Inactive account login attempt")
            return render(request, 'accounts/login.html')
        
        # Attempt authentication
        auth_username = user_obj.username if user_obj else login_identifier
        user = authenticate(request, username=auth_username, password=password)

        if user is not None:
            # Reset failed attempts on successful login
            if user_obj:
                user_obj.failed_login_attempts = 0
                user_obj.last_failed_login = None
                user_obj.locked_until = None
                user_obj.save()
            
            log_security_event("LOGIN_SUCCESS", user, client_ip, "Successful login")
            login(request, user)

            if user.is_superuser:
                return redirect('/admin/')
            if user.is_teacher:
                return redirect('teacher_dashboard')
            if user.is_student:
                return redirect('student_dashboard')
        else:
            # Failed login attempt
            if user_obj:
                user_obj.failed_login_attempts += 1
                user_obj.last_failed_login = timezone.now()
                
                if user_obj.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                    # Lock the account
                    from datetime import timedelta
                    user_obj.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    user_obj.save()
                    messages.error(request, f"Too many failed attempts. Account locked for {LOCKOUT_DURATION_MINUTES} minutes.")
                    log_security_event("LOGIN_BLOCKED_MAX_ATTEMPTS", user_obj, client_ip, f"Attempts: {user_obj.failed_login_attempts}")
                else:
                    user_obj.save()
                    remaining = MAX_LOGIN_ATTEMPTS - user_obj.failed_login_attempts
                    messages.error(request, f"Invalid username or password. {remaining} attempts remaining.")
                    log_security_event("LOGIN_FAILED", user_obj, client_ip, f"Attempts: {user_obj.failed_login_attempts}")
            else:
                messages.error(request, "Invalid username or password")
                log_security_event("LOGIN_FAILED_UNKNOWN", None, client_ip, f"Unknown user: {login_identifier}")

    return render(request, 'accounts/login.html')


def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully")
    return redirect('home')


@login_required
def dashboard(request):
    user = request.user

    if user.is_superuser:
        return redirect('/admin/')

    if user.is_teacher:
        return render(request, 'accounts/teacher_dashboard.html', build_teacher_analytics(user))

    if user.is_student:
        return render(request, 'accounts/student_dashboard.html', build_student_analytics(user))

    return redirect('/admin/')


def register_choice(request):
    return render(request, 'accounts/register_choice.html')


@login_required
def student_dashboard(request):
    if not request.user.is_student:
        return redirect('dashboard')

    return render(request, 'accounts/student_dashboard.html', build_student_analytics(request.user))


@login_required
def teacher_dashboard(request):
    if not request.user.is_teacher:
        return redirect('dashboard')

    return render(request, 'accounts/teacher_dashboard.html', build_teacher_analytics(request.user))


@login_required
def student_profile(request):
    if not request.user.is_student:
        return redirect('dashboard')

    return render(request, 'accounts/student_profile.html', build_student_analytics(request.user))
