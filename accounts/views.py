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

    return {
        'total_exams': total_exams,
        'total_questions': total_questions,
        'students_attempted': students_attempted,
        'average_marks': round(average_marks, 2),
        'average_percentage': round(average_percentage, 2),
        'topper': topper,
        'pending_reviews': pending_reviews,
        'exam_analytics': exam_analytics,
    }


def build_student_analytics(user):
    exams = list(Exam.objects.all())
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

    for exam in exams:
        used_attempts = results.filter(exam=exam).count()
        exam.used_attempts = used_attempts
        exam.remaining_attempts = None if exam.max_attempts == 0 else max(exam.max_attempts - used_attempts, 0)

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
    }


def home(request):
    return render(request, 'home.html')


def validate_signup_data(username, email, password1, password2):
    username = (username or '').strip()
    email = (email or '').strip().lower()
    password1 = password1 or ''
    password2 = password2 or ''

    if not username or not email:
        return username, email, "Username and email are required."

    if password1 != password2:
        return username, email, "Passwords do not match"

    if User.objects.filter(username__iexact=username).exists():
        return username, email, "Username already exists"

    if User.objects.filter(email__iexact=email).exists():
        return username, email, "Email already exists"

    try:
        validate_password(password1, user=User(username=username, email=email))
    except ValidationError as exc:
        return username, email, " ".join(exc.messages)

    return username, email, None


def student_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        username, email, validation_error = validate_signup_data(username, email, password1, password2)
        if validation_error:
            messages.error(request, validation_error)
            return redirect('student_signup')

        user = User.objects.create_user(username=username, email=email, password=password1)
        user.is_student = True
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
        username, email, validation_error = validate_signup_data(username, email, password1, password2)
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
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Try to get user for lockout check
        try:
            user_obj = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            user_obj = None
        
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
        user = authenticate(request, username=username, password=password)

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
                log_security_event("LOGIN_FAILED_UNKNOWN", None, client_ip, f"Unknown user: {username}")

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
