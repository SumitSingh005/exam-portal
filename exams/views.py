import random
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Avg, Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.decorators import student_required, teacher_required

from .models import Exam, PortalSettings, Question, Result, ResultAnswer

EXAM_SESSION_KEYS = ['question_ids', 'q_index', 'answers', 'current_exam_id', 'option_orders', 'exam_ready', 'anti_cheating']


def clear_exam_session(request):
    for key in EXAM_SESSION_KEYS:
        request.session.pop(key, None)


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


def parse_exam_datetime(value):
    parsed = parse_datetime(value)
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def parse_float_input(value, default=None):
    try:
        if value in (None, ''):
            raise ValueError
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int_input(value, default=None):
    try:
        if value in (None, ''):
            raise ValueError
        return int(value)
    except (TypeError, ValueError):
        return default


def build_question_options(question, option_order):
    return [
        {
            'value': option_number,
            'label': getattr(question, f'option{option_number}'),
            'id': f'option{index}',
        }
        for index, option_number in enumerate(option_order, start=1)
    ]


def validate_question_input(question_type, question_text, option_values, correct_option, written_answer):
    question_text = (question_text or '').strip()
    written_answer = (written_answer or '').strip()
    clean_options = [(value or '').strip() for value in option_values]

    if not question_text:
        return None, "Question text is required."

    if question_type == 'written':
        return {
            'question_type': 'written',
            'question_text': question_text,
            'option1': '',
            'option2': '',
            'option3': '',
            'option4': '',
            'correct_option': None,
            'written_answer': written_answer,
        }, None

    if any(not option for option in clean_options):
        return None, "All four options are required for MCQ questions."

    parsed_correct_option = parse_int_input(correct_option)
    if parsed_correct_option not in (1, 2, 3, 4):
        return None, "Please choose a valid correct option."

    return {
        'question_type': 'mcq',
        'question_text': question_text,
        'option1': clean_options[0],
        'option2': clean_options[1],
        'option3': clean_options[2],
        'option4': clean_options[3],
        'correct_option': parsed_correct_option,
        'written_answer': '',
    }, None


def normalize_written_answer(value):
    return " ".join((value or "").strip().lower().split())


def build_result_summary(result):
    return {
        'score': round(result.score, 2),
        'total_questions': result.total_questions,
        'max_marks': round(result.max_marks, 2),
        'correct_marks': result.exam.correct_marks,
        'wrong_marks': result.exam.wrong_marks,
        'percentage': round(result.percentage, 2),
        'passed': result.passed,
        'review_pending': result.review_pending,
        'violation_count': result.violation_count,
        'tab_switch_count': result.tab_switch_count,
        'fullscreen_exit_count': result.fullscreen_exit_count,
        'copy_paste_count': result.copy_paste_count,
        'webcam_warning_count': result.webcam_warning_count,
        'auto_submitted': result.auto_submitted,
    }


def build_result_status_label(result):
    if result.review_pending:
        return 'Pending Review'
    if result.passed:
        return 'Pass'
    return 'Fail'


def default_anti_cheating_state():
    return {
        'tab_switch_count': 0,
        'fullscreen_exit_count': 0,
        'copy_paste_count': 0,
        'webcam_warning_count': 0,
        'auto_submitted': False,
        'notes': '',
    }


def get_anti_cheating_state(request):
    state = request.session.get('anti_cheating') or default_anti_cheating_state()
    merged = default_anti_cheating_state()
    merged.update(state)
    return merged


def update_anti_cheating_state(request):
    state = get_anti_cheating_state(request)

    if request.method == 'POST':
        for field in ('tab_switch_count', 'fullscreen_exit_count', 'copy_paste_count', 'webcam_warning_count'):
            try:
                state[field] = max(int(request.POST.get(field, state[field]) or 0), 0)
            except (TypeError, ValueError):
                state[field] = state[field]

        state['auto_submitted'] = request.POST.get('auto_submitted') == '1' or state['auto_submitted']
        notes = request.POST.get('anti_cheating_notes', '').strip()
        if notes:
            state['notes'] = notes

    request.session['anti_cheating'] = state
    return state


def get_attempt_counts(exam, user):
    used_attempts = Result.objects.filter(student=user, exam=exam).count()
    remaining_attempts = None if exam.max_attempts == 0 else max(exam.max_attempts - used_attempts, 0)
    return used_attempts, remaining_attempts


def validate_exam_availability(exam):
    if not exam.is_published:
        return "This exam is not published."
    if not exam.start_time or not exam.end_time:
        return "This exam schedule is not set yet."

    now = timezone.now()
    if now < exam.start_time:
        return "This exam has not started yet."
    if now > exam.end_time:
        return "This exam has already ended."
    return None


def recalculate_result(result):
    answers = result.answers.select_related('question')
    score = sum(answer.awarded_marks for answer in answers)
    max_marks = result.total_questions * result.exam.correct_marks
    review_pending = answers.filter(question__question_type='written', reviewed=False).exists()
    percentage = round((score / max_marks) * 100, 2) if max_marks else 0

    result.score = round(score, 2)
    result.percentage = percentage
    result.review_pending = review_pending
    result.passed = False if review_pending else percentage >= result.exam.pass_percentage
    result.save(update_fields=['score', 'percentage', 'review_pending', 'passed'])
    return result


@login_required
@teacher_required
def create_exam(request):
    portal_settings = PortalSettings.get_solo()
    if request.method == 'POST':
        title = request.POST.get('title')
        duration = parse_int_input(request.POST.get('duration'))
        pass_percentage = parse_float_input(
            request.POST.get('pass_percentage'),
            portal_settings.default_pass_percentage,
        )
        correct_marks = parse_float_input(request.POST.get('correct_marks'), 4)
        wrong_marks = parse_float_input(request.POST.get('wrong_marks'), -1)
        max_attempts = parse_int_input(request.POST.get('max_attempts'), 1)
        start_time = parse_exam_datetime(request.POST.get('start_time'))
        end_time = parse_exam_datetime(request.POST.get('end_time'))

        if not title or duration is None or pass_percentage is None or correct_marks is None or wrong_marks is None or max_attempts is None:
            messages.error(request, "Please enter valid exam details in all required fields.")
            return render(request, 'exams/create_exam.html', {'portal_settings': portal_settings})

        if not start_time or not end_time:
            messages.error(request, "Please provide valid start and end time.")
            return render(request, 'exams/create_exam.html', {'portal_settings': portal_settings})

        if end_time <= start_time:
            messages.error(request, "End time must be later than start time.")
            return render(request, 'exams/create_exam.html', {'portal_settings': portal_settings})

        Exam.objects.create(
            title=title,
            duration=duration,
            created_by=request.user,
            start_time=start_time,
            end_time=end_time,
            pass_percentage=pass_percentage,
            correct_marks=correct_marks,
            wrong_marks=wrong_marks,
            max_attempts=max(max_attempts, 0),
            instructions=request.POST.get('instructions', '').strip(),
        )
        student_emails = list(
            request.user.__class__.objects.filter(is_student=True)
            .exclude(email='')
            .values_list('email', flat=True)
        )
        send_notification_email(
            f"New Exam Created: {title}",
            (
                f"A new exam '{title}' has been created.\n"
                f"Start: {start_time}\n"
                f"End: {end_time}\n"
                f"Marking: +{correct_marks} / {wrong_marks}"
            ),
            [request.user.email] + student_emails,
        )
        messages.success(request, "Exam created successfully.")
        return redirect('dashboard')

    return render(request, 'exams/create_exam.html', {'portal_settings': portal_settings})


@login_required
@teacher_required
def add_question(request):
    exams = Exam.objects.filter(created_by=request.user)
    selected_exam_id = request.session.get('selected_exam')
    questions = None

    if selected_exam_id and not exams.filter(id=selected_exam_id).exists():
        request.session.pop('selected_exam', None)
        selected_exam_id = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if 'select_exam' in request.POST:
            exam_id = request.POST.get('exam')
            if exams.filter(id=exam_id).exists():
                request.session['selected_exam'] = exam_id
            else:
                messages.error(request, "You can only add questions to your own exams.")
            return redirect('add_question')

        if selected_exam_id and exams.filter(id=selected_exam_id).exists():
            question_type = request.POST.get('question_type', 'mcq')
            question_data, validation_error = validate_question_input(
                question_type=question_type,
                question_text=request.POST.get('question'),
                option_values=[
                    request.POST.get('option1', ''),
                    request.POST.get('option2', ''),
                    request.POST.get('option3', ''),
                    request.POST.get('option4', ''),
                ],
                correct_option=request.POST.get('correct'),
                written_answer=request.POST.get('written_answer', ''),
            )
            if validation_error:
                messages.error(request, validation_error)
                return redirect('add_question')

            Question.objects.create(
                exam_id=selected_exam_id,
                **question_data,
            )

            if action == "add":
                messages.success(request, "Question added.")
                return redirect('add_question')

            if action == "finish":
                request.session.pop('selected_exam', None)
                messages.success(request, "All questions added.")
                return redirect('dashboard')

    if selected_exam_id:
        questions = Question.objects.filter(exam_id=selected_exam_id).order_by('-id')

    return render(request, 'exams/add_question.html', {
        'exams': exams,
        'selected_exam': selected_exam_id,
        'questions': questions,
    })


@login_required
def exam_list(request):
    exams = list(Exam.objects.all().order_by('start_time', 'title'))
    if request.user.is_authenticated and getattr(request.user, 'is_student', False):
        for exam in exams:
            used_attempts, remaining_attempts = get_attempt_counts(exam, request.user)
            exam.used_attempts = used_attempts
            exam.remaining_attempts = remaining_attempts
    return render(request, 'exams/exam_list.html', {'exams': exams})


@login_required
@student_required
def exam_instructions(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    error_message = validate_exam_availability(exam)
    if error_message:
        messages.error(request, error_message)
        return redirect('exam_list')

    used_attempts, remaining_attempts = get_attempt_counts(exam, request.user)
    if remaining_attempts == 0:
        latest_result = Result.objects.filter(student=request.user, exam=exam).order_by('-submitted_at').first()
        return render(request, 'exams/already_attempted.html', {
            'exam': exam,
            'result': latest_result,
            'used_attempts': used_attempts,
            'max_attempts': exam.max_attempts,
        })

    if request.method == 'POST':
        clear_exam_session(request)
        request.session['exam_ready'] = exam.id
        return redirect('take_exam', exam_id=exam.id)

    return render(request, 'exams/exam_instructions.html', {
        'exam': exam,
        'used_attempts': used_attempts,
        'remaining_attempts': remaining_attempts,
    })


@login_required
def leaderboard(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    leaderboard_rows = list(
        Result.objects.filter(exam=exam, review_pending=False)
        .select_related('student')
        .order_by('-percentage', '-score', 'submitted_at')
    )

    current_user_rank = None
    for index, row in enumerate(leaderboard_rows, start=1):
        row.rank = index
        if row.student_id == request.user.id and current_user_rank is None:
            current_user_rank = index

    return render(request, 'exams/leaderboard.html', {
        'exam': exam,
        'leaderboard_rows': leaderboard_rows[:10],
        'current_user_rank': current_user_rank,
        'total_attempts': len(leaderboard_rows),
    })


@login_required
@student_required
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    error_message = validate_exam_availability(exam)
    if error_message:
        messages.error(request, error_message)
        return redirect('exam_list')

    used_attempts, remaining_attempts = get_attempt_counts(exam, request.user)
    latest_result = Result.objects.filter(student=request.user, exam=exam).order_by('-submitted_at').first()
    if remaining_attempts == 0:
        return render(request, 'exams/already_attempted.html', {
            'exam': exam,
            'result': latest_result,
            'used_attempts': used_attempts,
            'max_attempts': exam.max_attempts,
        })

    if request.session.get('exam_ready') != exam.id:
        return redirect('exam_instructions', exam_id=exam.id)

    if (
        'question_ids' not in request.session
        or request.session.get('current_exam_id') != exam.id
    ):
        clear_exam_session(request)
        request.session['exam_ready'] = exam.id
        request.session['anti_cheating'] = default_anti_cheating_state()
        questions = list(Question.objects.filter(exam=exam))

        if not questions:
            return render(request, 'exams/result.html', {
                'exam': exam,
                'summary': {
                    'score': 0,
                    'total_questions': 0,
                'max_marks': 0,
                'correct_marks': exam.correct_marks,
                'wrong_marks': exam.wrong_marks,
                'percentage': 0,
                'passed': False,
                'review_pending': False,
            },
            'analytics': None,
        })

        random.shuffle(questions)
        request.session['question_ids'] = [q.id for q in questions]
        request.session['q_index'] = 0
        request.session['answers'] = {}
        request.session['current_exam_id'] = exam.id
        request.session['option_orders'] = {
            str(q.id): random.sample([1, 2, 3, 4], 4)
            for q in questions if q.question_type == 'mcq'
        }

    question_ids = request.session.get('question_ids')
    q_index = request.session.get('q_index', 0)
    answers = request.session.get('answers', {})
    option_orders = request.session.get('option_orders', {})
    anti_cheating = update_anti_cheating_state(request)

    if q_index >= len(question_ids):
        answer_rows = []
        review_pending = False
        question_map = Question.objects.in_bulk(question_ids)

        for qid, ans in answers.items():
            q = question_map.get(parse_int_input(qid))
            if q is None:
                continue
            if q.question_type == 'written':
                written_response = str(ans).strip()
                selected_option = None
                is_correct = False
                awarded_marks = 0
                reviewed = False
                review_pending = True
            else:
                selected_option = parse_int_input(ans)
                if selected_option not in (1, 2, 3, 4):
                    selected_option = None
                written_response = ''
                is_correct = selected_option == q.correct_option
                awarded_marks = exam.correct_marks if is_correct else (exam.wrong_marks if selected_option else 0)
                reviewed = True
            answer_rows.append((q, selected_option, written_response, is_correct, awarded_marks, reviewed))

        answered_question_ids = {str(qid) for qid in answers.keys()}
        for qid in question_ids:
            if str(qid) in answered_question_ids:
                continue

            q = question_map.get(qid)
            if q is None:
                continue
            if q.question_type == 'written':
                answer_rows.append((q, None, '', False, 0, False))
                review_pending = True
            else:
                answer_rows.append((q, None, '', False, 0, True))

        total_questions = len(question_ids)
        score = round(sum(row[4] for row in answer_rows), 2)
        max_marks = total_questions * exam.correct_marks
        percentage = round((score / max_marks) * 100, 2) if max_marks else 0
        passed = False if review_pending else percentage >= exam.pass_percentage

        result = Result.objects.create(
            student=request.user,
            exam=exam,
            score=score,
            total_questions=total_questions,
            percentage=percentage,
            passed=passed,
            review_pending=review_pending,
            violation_count=(
                anti_cheating['tab_switch_count']
                + anti_cheating['fullscreen_exit_count']
                + anti_cheating['copy_paste_count']
                + anti_cheating['webcam_warning_count']
            ),
            tab_switch_count=anti_cheating['tab_switch_count'],
            fullscreen_exit_count=anti_cheating['fullscreen_exit_count'],
            copy_paste_count=anti_cheating['copy_paste_count'],
            webcam_warning_count=anti_cheating['webcam_warning_count'],
            auto_submitted=anti_cheating['auto_submitted'],
            anti_cheating_notes=anti_cheating['notes'],
        )

        ResultAnswer.objects.bulk_create([
            ResultAnswer(
                result=result,
                question=question,
                selected_option=selected_option,
                written_answer=written_answer,
                is_correct=is_correct,
                awarded_marks=awarded_marks,
                reviewed=reviewed,
            )
            for question, selected_option, written_answer, is_correct, awarded_marks, reviewed in answer_rows
        ])

        exam_results = Result.objects.filter(exam=exam, review_pending=False)
        question_performance = ResultAnswer.objects.filter(
            result__exam=exam
        ).filter(
            Q(question__question_type='mcq') | Q(reviewed=True)
        ).values(
            'question__question_text'
        ).annotate(
            attempts=Count('id'),
            correct_count=Count('id', filter=Q(is_correct=True)),
        ).order_by('question__question_text')

        clear_exam_session(request)
        send_notification_email(
            f"Result Published: {exam.title}",
            (
                f"Hello {request.user.username},\n\n"
                f"Your result for '{exam.title}' is ready.\n"
                f"Score: {round(score, 2)}/{round(max_marks, 2)}\n"
                f"Percentage: {percentage}%\n"
                f"Status: {'Pending Review' if review_pending else ('Pass' if passed else 'Fail')}"
            ),
            [request.user.email],
        )
        return render(request, 'exams/result.html', {
            'exam': exam,
            'summary': build_result_summary(result),
            'analytics': {
                'average_marks': round(exam_results.aggregate(avg=Avg('score'))['avg'] or 0, 2),
                'top_score': exam_results.aggregate(top=Max('score'))['top'] or 0,
                'topper': exam_results.select_related('student').order_by('-score', '-percentage', 'submitted_at').first(),
                'question_performance': [
                    {
                        'question_text': item['question__question_text'],
                        'attempts': item['attempts'],
                        'correct_count': item['correct_count'],
                        'accuracy': round((item['correct_count'] / item['attempts']) * 100, 2) if item['attempts'] else 0,
                    }
                    for item in question_performance
                ],
            },
        })

    current_q = Question.objects.get(id=question_ids[q_index])
    current_saved_answer = answers.get(str(current_q.id), '')
    if current_q.question_type == 'mcq':
        current_option_order = option_orders.get(str(current_q.id), [1, 2, 3, 4])
        question_options = build_question_options(current_q, current_option_order)
    else:
        question_options = []

    if request.method == 'POST':
        if anti_cheating['auto_submitted']:
            request.session['q_index'] = len(question_ids)
            return redirect('take_exam', exam_id=exam.id)

        selected = request.POST.get('answer') if current_q.question_type == 'mcq' else request.POST.get('written_answer')
        if not selected or not str(selected).strip():
            return render(request, 'exams/take_exam.html', {
                'exam': exam,
                'question': current_q,
                'question_options': question_options,
                'q_index': q_index + 1,
                'total': len(question_ids),
                'error': "Select an option.",
                'anti_cheating': anti_cheating,
                'current_saved_answer': current_saved_answer,
            })

        answers[str(current_q.id)] = selected
        request.session['answers'] = answers
        request.session['q_index'] = q_index + 1
        return redirect('take_exam', exam_id=exam.id)

    return render(request, 'exams/take_exam.html', {
        'exam': exam,
        'question': current_q,
        'question_options': question_options,
        'q_index': q_index + 1,
        'total': len(question_ids),
        'anti_cheating': anti_cheating,
        'current_saved_answer': current_saved_answer,
    })


@login_required
@student_required
def result_history(request):
    results = Result.objects.filter(student=request.user).select_related('exam')
    return render(request, 'exams/result_history.html', {'results': results})


@login_required
@teacher_required
def teacher_exam_list(request):
    exams = Exam.objects.filter(created_by=request.user)
    return render(request, 'exams/teacher_exam_list.html', {'exams': exams})


@login_required
@teacher_required
def teacher_exam_report(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    results = list(
        Result.objects.filter(exam=exam)
        .select_related('student')
        .order_by('-percentage', '-score', 'submitted_at')
    )

    student_count = len({result.student_id for result in results})
    highest_score = max((result.score for result in results), default=0)
    lowest_score = min((result.score for result in results), default=0)
    average_marks = round(sum(result.score for result in results) / len(results), 2) if results else 0
    average_percentage = round(sum(result.percentage for result in results) / len(results), 2) if results else 0

    weak_questions = list(
        ResultAnswer.objects.filter(result__exam=exam)
        .filter(Q(question__question_type='mcq') | Q(reviewed=True))
        .values('question__id', 'question__question_text')
        .annotate(
            attempts=Count('id'),
            correct_count=Count('id', filter=Q(is_correct=True)),
        )
        .order_by('question__id')
    )

    weak_questions = [
        {
            'question_text': item['question__question_text'],
            'attempts': item['attempts'],
            'correct_count': item['correct_count'],
            'accuracy': round((item['correct_count'] / item['attempts']) * 100, 2) if item['attempts'] else 0,
        }
        for item in weak_questions
    ]
    weak_questions.sort(key=lambda item: item['accuracy'])

    return render(request, 'exams/teacher_exam_report.html', {
        'exam': exam,
        'results': results,
        'student_count': student_count,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'average_marks': average_marks,
        'average_percentage': average_percentage,
        'weak_questions': weak_questions[:5],
        'written_questions_count': Question.objects.filter(exam=exam, question_type='written').count(),
    })


@login_required
@teacher_required
def review_result(request, result_id):
    result = get_object_or_404(
        Result.objects.select_related('student', 'exam'),
        id=result_id,
        exam__created_by=request.user,
    )
    written_answers = list(
        result.answers.filter(question__question_type='written').select_related('question').order_by('question_id')
    )

    if not written_answers:
        messages.info(request, "This result has no written answers to review.")
        return redirect('teacher_exam_report', exam_id=result.exam.id)

    if request.method == 'POST':
        for answer in written_answers:
            marks_value = request.POST.get(f'marks_{answer.id}', '0')
            feedback_value = request.POST.get(f'feedback_{answer.id}', '').strip()
            try:
                awarded_marks = float(marks_value)
            except (TypeError, ValueError):
                awarded_marks = 0

            if awarded_marks < 0:
                awarded_marks = 0
            if awarded_marks > result.exam.correct_marks:
                awarded_marks = result.exam.correct_marks

            answer.awarded_marks = awarded_marks
            answer.feedback = feedback_value
            answer.reviewed = True
            answer.is_correct = awarded_marks == result.exam.correct_marks
            answer.save(update_fields=['awarded_marks', 'feedback', 'reviewed', 'is_correct'])

        recalculate_result(result)
        messages.success(request, "Manual review saved successfully.")
        return redirect('teacher_exam_report', exam_id=result.exam.id)

    return render(request, 'exams/review_result.html', {
        'result': result,
        'written_answers': written_answers,
    })


@login_required
@teacher_required
def export_results(request, exam_id, file_format):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    results = list(
        Result.objects.filter(exam=exam)
        .select_related('student')
        .order_by('-percentage', '-score', 'submitted_at')
    )

    rows = [
        [
            'Student Username',
            'Student Email',
            'Score',
            'Max Marks',
            'Percentage',
            'Status',
            'Submitted At',
        ]
    ]
    rows.extend([
        [
            result.student.username,
            result.student.email,
            result.score,
            round(result.total_questions * exam.correct_marks, 2),
            result.percentage,
            build_result_status_label(result),
            result.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
        ]
        for result in results
    ])

    safe_title = exam.title.replace(' ', '_')
    if file_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{safe_title}_results.csv"'
        writer = csv.writer(response)
        writer.writerows(rows)
        return response

    if file_format == 'excel':
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="{safe_title}_results.xls"'
        writer = csv.writer(response, delimiter='\t')
        writer.writerows(rows)
        return response

    messages.error(request, "Unsupported export format.")
    return redirect('teacher_exam_report', exam_id=exam.id)


@login_required
@teacher_required
def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)

    if request.method == 'POST':
        duration = parse_int_input(request.POST.get('duration'))
        start_time = parse_exam_datetime(request.POST.get('start_time'))
        end_time = parse_exam_datetime(request.POST.get('end_time'))
        pass_percentage = parse_float_input(request.POST.get('pass_percentage'), exam.pass_percentage)
        correct_marks = parse_float_input(request.POST.get('correct_marks'), exam.correct_marks)
        wrong_marks = parse_float_input(request.POST.get('wrong_marks'), exam.wrong_marks)
        max_attempts = parse_int_input(request.POST.get('max_attempts'), exam.max_attempts)

        if not request.POST.get('title') or duration is None or pass_percentage is None or correct_marks is None or wrong_marks is None or max_attempts is None:
            messages.error(request, "Please enter valid exam details in all required fields.")
            return render(request, 'exams/edit_exam.html', {'exam': exam})

        if not start_time or not end_time:
            messages.error(request, "Please provide valid start and end time.")
            return render(request, 'exams/edit_exam.html', {'exam': exam})

        if end_time <= start_time:
            messages.error(request, "End time must be later than start time.")
            return render(request, 'exams/edit_exam.html', {'exam': exam})

        exam.title = request.POST.get('title')
        exam.duration = duration
        exam.start_time = start_time
        exam.end_time = end_time
        exam.pass_percentage = pass_percentage
        exam.correct_marks = correct_marks
        exam.wrong_marks = wrong_marks
        exam.max_attempts = max(max_attempts, 0)
        exam.instructions = request.POST.get('instructions', '').strip()
        exam.save()
        messages.success(request, "Exam updated successfully.")
        return redirect('teacher_exam_list')

    return render(request, 'exams/edit_exam.html', {'exam': exam})


@login_required
@teacher_required
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    if request.method == 'POST':
        exam.delete()
    return redirect('teacher_exam_list')


@login_required
@teacher_required
def manage_questions(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    questions = Question.objects.filter(exam=exam)
    return render(request, 'exams/manage_questions.html', {
        'exam': exam,
        'questions': questions,
    })


@login_required
@teacher_required
def edit_question(request, q_id):
    q = get_object_or_404(Question, id=q_id, exam__created_by=request.user)
    if request.method == 'POST':
        question_data, validation_error = validate_question_input(
            question_type=request.POST.get('question_type', q.question_type),
            question_text=request.POST.get('question'),
            option_values=[
                request.POST.get('option1', ''),
                request.POST.get('option2', ''),
                request.POST.get('option3', ''),
                request.POST.get('option4', ''),
            ],
            correct_option=request.POST.get('correct'),
            written_answer=request.POST.get('written_answer', ''),
        )
        if validation_error:
            messages.error(request, validation_error)
            return redirect('manage_questions', exam_id=q.exam.id)

        q.question_type = question_data['question_type']
        q.question_text = question_data['question_text']
        q.option1 = question_data['option1']
        q.option2 = question_data['option2']
        q.option3 = question_data['option3']
        q.option4 = question_data['option4']
        q.correct_option = question_data['correct_option']
        q.written_answer = question_data['written_answer']
        q.save()
        messages.success(request, "Question updated successfully.")
    return redirect('manage_questions', exam_id=q.exam.id)


@login_required
@teacher_required
def delete_question(request, q_id):
    q = get_object_or_404(Question, id=q_id, exam__created_by=request.user)
    exam_id = q.exam.id
    if request.method == 'POST':
        q.delete()
    return redirect('manage_questions', exam_id=exam_id)
