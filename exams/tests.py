from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .context_processors import portal_settings
from .models import Exam, PortalSettings, Question, Result, ResultAnswer

User = get_user_model()

class PortalSettingsTests(TestCase):
    def test_get_solo_creates_default_settings_row(self):
        settings_obj = PortalSettings.get_solo()

        self.assertEqual(settings_obj.pk, 1)
        self.assertEqual(settings_obj.site_name, 'Exam Portal')
        self.assertEqual(settings_obj.default_pass_percentage, 40.0)

    def test_get_solo_returns_in_memory_default_when_database_is_unavailable(self):
        with patch.object(PortalSettings.objects, 'get_or_create', side_effect=OperationalError):
            settings_obj = PortalSettings.get_solo()

        self.assertEqual(settings_obj.pk, 1)
        self.assertEqual(settings_obj.site_name, 'Exam Portal')
        self.assertEqual(settings_obj.certificate_title, 'Certificate of Achievement')
        self.assertEqual(settings_obj.default_pass_percentage, 40.0)

    def test_context_processor_exposes_portal_settings_values(self):
        settings_obj = PortalSettings.get_solo()
        settings_obj.site_name = 'My Exam Hub'
        settings_obj.support_email = 'support@example.com'
        settings_obj.save()

        context = portal_settings(request=None)

        self.assertEqual(context['site_name'], 'My Exam Hub')
        self.assertEqual(context['support_email'], 'support@example.com')
        self.assertEqual(context['portal_settings'].pk, 1)


class ExamWorkflowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher_flow',
            email='teacher_flow@example.com',
            password='testpass123',
        )
        self.teacher.is_teacher = True
        self.teacher.save()

        self.student = User.objects.create_user(
            username='student_flow',
            email='student_flow@example.com',
            password='testpass123',
        )
        self.student.is_student = True
        self.student.save()

        self.other_student = User.objects.create_user(
            username='student_other',
            email='student_other@example.com',
            password='testpass123',
        )
        self.other_student.is_student = True
        self.other_student.save()

        self.admin_user = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
        )

    def create_active_exam(self, **overrides):
        data = {
            'title': 'Workflow Exam',
            'duration': 30,
            'created_by': self.teacher,
            'start_time': timezone.now() - timezone.timedelta(hours=1),
            'end_time': timezone.now() + timezone.timedelta(hours=1),
            'pass_percentage': 40.0,
            'correct_marks': 4.0,
            'wrong_marks': -1.0,
            'max_attempts': 1,
            'is_published': True,
        }
        data.update(overrides)
        return Exam.objects.create(**data)

    def start_exam_session(self, exam):
        session = self.client.session
        session['exam_ready'] = exam.id
        session.save()

    def test_exam_instructions_blocks_when_attempt_limit_is_reached(self):
        exam = self.create_active_exam(max_attempts=1)
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=4,
            total_questions=1,
            percentage=100,
            passed=True,
        )

        self.client.login(username='student_flow', password='testpass123')
        response = self.client.get(reverse('exam_instructions', args=[exam.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You have already attempted this exam')

    def test_exam_instructions_allows_unlimited_attempts_even_after_previous_result(self):
        exam = self.create_active_exam(max_attempts=0)
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=4,
            total_questions=1,
            percentage=100,
            passed=True,
        )

        self.client.login(username='student_flow', password='testpass123')
        response = self.client.get(reverse('exam_instructions', args=[exam.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unlimited attempts')

    def test_exam_instructions_carries_webcam_warning_to_attempt(self):
        exam = self.create_active_exam()
        Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='2 + 2 = ?',
            option1='3',
            option2='4',
            option3='5',
            option4='6',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        response = self.client.post(
            reverse('exam_instructions', args=[exam.id]),
            {'webcam_warning_count': '1'},
        )

        self.assertRedirects(response, reverse('take_exam', args=[exam.id]))
        response = self.client.get(reverse('take_exam', args=[exam.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['anti_cheating']['webcam_warning_count'], 1)
        self.assertIn('Webcam permission denied', self.client.session['anti_cheating']['notes'])

    def test_take_exam_creates_result_with_negative_marking(self):
        exam = self.create_active_exam(correct_marks=4.0, wrong_marks=-1.0)
        question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='2 + 2 = ?',
            option1='3',
            option2='4',
            option3='5',
            option4='6',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        self.start_exam_session(exam)

        self.client.get(reverse('take_exam', args=[exam.id]))
        response = self.client.post(reverse('take_exam', args=[exam.id]), {'answer': '1'}, follow=True)

        result = Result.objects.get(student=self.student, exam=exam)
        answer = ResultAnswer.objects.get(result=result, question=question)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(result.score, -1.0)
        self.assertEqual(result.percentage, -25.0)
        self.assertFalse(result.passed)
        self.assertFalse(result.review_pending)
        self.assertFalse(answer.is_correct)
        self.assertEqual(answer.awarded_marks, -1.0)
        self.assertTrue(answer.reviewed)

    def test_written_submission_stays_pending_until_manual_review(self):
        exam = self.create_active_exam(correct_marks=5.0, pass_percentage=50.0)
        question = Question.objects.create(
            exam=exam,
            question_type='written',
            question_text='Explain Python.',
            written_answer='A programming language.',
        )

        self.client.login(username='student_flow', password='testpass123')
        self.start_exam_session(exam)

        self.client.get(reverse('take_exam', args=[exam.id]))
        self.client.post(
            reverse('take_exam', args=[exam.id]),
            {'written_answer': 'It is used for web and AI.'},
            follow=True,
        )

        result = Result.objects.get(student=self.student, exam=exam)
        answer = ResultAnswer.objects.get(result=result, question=question)

        self.assertTrue(result.review_pending)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0)
        self.assertFalse(answer.reviewed)
        self.assertEqual(answer.awarded_marks, 0)
        self.assertEqual(answer.written_answer, 'It is used for web and AI.')

    def test_teacher_review_updates_result_score_and_pass_status(self):
        exam = self.create_active_exam(correct_marks=5.0, pass_percentage=50.0)
        question = Question.objects.create(
            exam=exam,
            question_type='written',
            question_text='Explain Python.',
            written_answer='A programming language.',
        )
        result = Result.objects.create(
            student=self.student,
            exam=exam,
            score=0,
            total_questions=1,
            percentage=0,
            passed=False,
            review_pending=True,
        )
        answer = ResultAnswer.objects.create(
            result=result,
            question=question,
            written_answer='It is used for automation.',
            awarded_marks=0,
            reviewed=False,
            is_correct=False,
        )

        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.post(
            reverse('review_result', args=[result.id]),
            {
                f'marks_{answer.id}': '5',
                f'feedback_{answer.id}': 'Good explanation',
            },
            follow=True,
        )

        result.refresh_from_db()
        answer.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(result.review_pending)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 5.0)
        self.assertEqual(result.percentage, 100.0)
        self.assertTrue(answer.reviewed)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.feedback, 'Good explanation')

    def test_leaderboard_excludes_pending_review_results(self):
        exam = self.create_active_exam()
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=8,
            total_questions=2,
            percentage=100,
            passed=True,
            review_pending=False,
        )
        Result.objects.create(
            student=self.other_student,
            exam=exam,
            score=0,
            total_questions=2,
            percentage=0,
            passed=False,
            review_pending=True,
        )

        self.client.login(username='student_flow', password='testpass123')
        response = self.client.get(reverse('leaderboard', args=[exam.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'student_flow')
        self.assertNotContains(response, 'student_other')
        self.assertContains(response, 'Total Attempts: 1')

    def test_teacher_report_shows_pending_review_action(self):
        exam = self.create_active_exam()
        Question.objects.create(
            exam=exam,
            question_type='written',
            question_text='Explain Python.',
            written_answer='A programming language.',
        )
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=0,
            total_questions=1,
            percentage=0,
            passed=False,
            review_pending=True,
        )

        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.get(reverse('teacher_exam_report', args=[exam.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pending Review')
        self.assertContains(response, 'Review')
        self.assertContains(response, 'Written Questions')

    def test_admin_can_publish_selected_exams(self):
        exam = self.create_active_exam(is_published=False)

        self.client.login(username='adminuser', password='adminpass123')
        response = self.client.post(
            reverse('admin:exams_exam_changelist'),
            {
                'action': 'publish_selected_exams',
                '_selected_action': [str(exam.id)],
            },
            follow=True,
        )

        exam.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(exam.is_published)
        self.assertContains(response, 'published successfully')

    def test_admin_can_mark_selected_results_as_reviewed(self):
        exam = self.create_active_exam(correct_marks=5.0, pass_percentage=50.0)
        question = Question.objects.create(
            exam=exam,
            question_type='written',
            question_text='Explain Python.',
            written_answer='A programming language.',
        )
        result = Result.objects.create(
            student=self.student,
            exam=exam,
            score=0,
            total_questions=1,
            percentage=0,
            passed=False,
            review_pending=True,
        )
        answer = ResultAnswer.objects.create(
            result=result,
            question=question,
            written_answer='It is useful.',
            awarded_marks=5,
            reviewed=False,
            is_correct=False,
        )

        self.client.login(username='adminuser', password='adminpass123')
        response = self.client.post(
            reverse('admin:exams_result_changelist'),
            {
                'action': 'mark_selected_results_as_reviewed',
                '_selected_action': [str(result.id)],
            },
            follow=True,
        )

        result.refresh_from_db()
        answer.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(result.review_pending)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 5.0)
        self.assertEqual(result.percentage, 100.0)
        self.assertTrue(answer.reviewed)
        self.assertTrue(answer.is_correct)

    def test_admin_dashboard_shows_summary_and_quick_links(self):
        exam = self.create_active_exam(is_published=True)
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=0,
            total_questions=1,
            percentage=0,
            passed=False,
            review_pending=True,
        )

        self.client.login(username='adminuser', password='adminpass123')
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Summary')
        self.assertContains(response, 'Review Pending Results')
        self.assertContains(response, 'Open Exams')
        self.assertContains(response, 'Manage Students')
        self.assertContains(response, 'Portal Settings')

    def test_teacher_can_export_results_as_csv(self):
        exam = self.create_active_exam()
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=8,
            total_questions=2,
            percentage=100,
            passed=True,
            review_pending=False,
        )

        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.get(reverse('export_results', args=[exam.id, 'csv']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('Student Username,Student Email,Score,Max Marks,Percentage,Status,Submitted At', response.content.decode())
        self.assertIn('student_flow,student_flow@example.com,8.0,8.0,100.0,Pass', response.content.decode())

    def test_teacher_can_export_results_as_excel_friendly_file(self):
        exam = self.create_active_exam()
        Result.objects.create(
            student=self.student,
            exam=exam,
            score=0,
            total_questions=1,
            percentage=0,
            passed=False,
            review_pending=True,
        )

        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.get(reverse('export_results', args=[exam.id, 'excel']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.ms-excel')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('Student Username\tStudent Email\tScore\tMax Marks\tPercentage\tStatus\tSubmitted At', response.content.decode())
        self.assertIn('student_flow\tstudent_flow@example.com\t0.0\t4.0\t0.0\tPending Review', response.content.decode())

    def test_take_exam_persists_anti_cheating_counts_on_result(self):
        exam = self.create_active_exam(correct_marks=4.0, wrong_marks=-1.0)
        Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='2 + 2 = ?',
            option1='3',
            option2='4',
            option3='5',
            option4='6',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        self.start_exam_session(exam)
        self.client.get(reverse('take_exam', args=[exam.id]))
        self.client.post(
            reverse('take_exam', args=[exam.id]),
            {
                'answer': '2',
                'tab_switch_count': '2',
                'fullscreen_exit_count': '1',
                'copy_paste_count': '3',
                'webcam_warning_count': '1',
                'anti_cheating_notes': 'Tab switch detected | Webcam permission warning',
            },
            follow=True,
        )

        result = Result.objects.get(student=self.student, exam=exam)

        self.assertEqual(result.tab_switch_count, 2)
        self.assertEqual(result.fullscreen_exit_count, 1)
        self.assertEqual(result.copy_paste_count, 3)
        self.assertEqual(result.webcam_warning_count, 1)
        self.assertEqual(result.violation_count, 7)
        self.assertFalse(result.auto_submitted)
        self.assertIn('Webcam permission warning', result.anti_cheating_notes)

    def test_take_exam_auto_submit_records_result(self):
        exam = self.create_active_exam(correct_marks=4.0, wrong_marks=-1.0)
        Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='Capital of France?',
            option1='Berlin',
            option2='Madrid',
            option3='Paris',
            option4='Rome',
            correct_option=3,
        )

        self.client.login(username='student_flow', password='testpass123')
        self.start_exam_session(exam)
        self.client.get(reverse('take_exam', args=[exam.id]))
        response = self.client.post(
            reverse('take_exam', args=[exam.id]),
            {
                'tab_switch_count': '3',
                'fullscreen_exit_count': '1',
                'copy_paste_count': '1',
                'webcam_warning_count': '0',
                'auto_submitted': '1',
                'anti_cheating_notes': 'Auto submitted after too many violations',
            },
            follow=True,
        )

        result = Result.objects.get(student=self.student, exam=exam)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(result.auto_submitted)
        self.assertEqual(result.violation_count, 5)
        self.assertEqual(result.total_questions, 1)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.answers.count(), 1)
        self.assertIsNone(result.answers.first().selected_option)

    def test_create_exam_rejects_invalid_numeric_input_gracefully(self):
        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.post(
            reverse('create_exam'),
            {
                'title': 'Broken Exam',
                'duration': 'abc',
                'pass_percentage': 'forty',
                'correct_marks': 'four',
                'wrong_marks': '-1',
                'max_attempts': '1',
                'instructions': 'Read carefully.',
                'start_time': (timezone.now() + timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
                'end_time': (timezone.now() + timezone.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter valid exam details')
        self.assertFalse(Exam.objects.filter(title='Broken Exam').exists())

    def test_add_question_rejects_incomplete_mcq(self):
        exam = self.create_active_exam()
        self.client.login(username='teacher_flow', password='testpass123')
        session = self.client.session
        session['selected_exam'] = exam.id
        session.save()

        response = self.client.post(
            reverse('add_question'),
            {
                'question_type': 'mcq',
                'question': 'Which option is correct?',
                'option1': 'A',
                'option2': '',
                'option3': 'C',
                'option4': 'D',
                'correct': '1',
                'action': 'add',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All four options are required')
        self.assertEqual(Question.objects.filter(exam=exam).count(), 0)

    def test_add_question_ajax_returns_created_question(self):
        exam = self.create_active_exam()
        self.client.login(username='teacher_flow', password='testpass123')
        session = self.client.session
        session['selected_exam'] = exam.id
        session.save()

        response = self.client.post(
            reverse('add_question'),
            {
                'question_type': 'mcq',
                'question': 'Which option is correct?',
                'option1': 'A',
                'option2': 'B',
                'option3': 'C',
                'option4': 'D',
                'correct': '1',
                'action': 'add',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['question']['text'], 'Which option is correct?')
        self.assertEqual(Question.objects.filter(exam=exam).count(), 1)

    def test_finish_add_question_without_filled_form_clears_selected_exam(self):
        exam = self.create_active_exam()
        self.client.login(username='teacher_flow', password='testpass123')
        session = self.client.session
        session['selected_exam'] = exam.id
        session.save()

        response = self.client.post(
            reverse('add_question'),
            {'action': 'finish'},
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.assertNotIn('selected_exam', self.client.session)

    def test_edit_question_rejects_empty_question_text(self):
        exam = self.create_active_exam()
        question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='Original',
            option1='A',
            option2='B',
            option3='C',
            option4='D',
            correct_option=1,
        )

        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.post(
            reverse('edit_question', args=[question.id]),
            {
                'question_type': 'mcq',
                'question': '',
                'option1': 'A',
                'option2': 'B',
                'option3': 'C',
                'option4': 'D',
                'correct': '1',
            },
            follow=True,
        )

        question.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Question text is required')
        self.assertEqual(question.question_text, 'Original')

    def test_take_exam_restores_current_saved_answer_from_session(self):
        exam = self.create_active_exam()
        question = Question.objects.create(
            exam=exam,
            question_type='written',
            question_text='Describe Django.',
            written_answer='A Python web framework.',
        )

        self.client.login(username='student_flow', password='testpass123')
        session = self.client.session
        session['exam_ready'] = exam.id
        session['current_exam_id'] = exam.id
        session['question_ids'] = [question.id]
        session['q_index'] = 0
        session['answers'] = {str(question.id): 'Draft answer restored'}
        session['option_orders'] = {}
        session['anti_cheating'] = {
            'tab_switch_count': 0,
            'fullscreen_exit_count': 0,
            'copy_paste_count': 0,
            'webcam_warning_count': 0,
            'auto_submitted': False,
            'notes': '',
        }
        session.save()

        response = self.client.get(reverse('take_exam', args=[exam.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Draft answer restored')

    def test_take_exam_ajax_next_returns_next_question_without_redirect(self):
        exam = self.create_active_exam()
        first_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='First?',
            option1='A',
            option2='B',
            option3='C',
            option4='D',
            correct_option=1,
        )
        second_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='Second?',
            option1='W',
            option2='X',
            option3='Y',
            option4='Z',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        session = self.client.session
        session['exam_ready'] = exam.id
        session['current_exam_id'] = exam.id
        session['question_ids'] = [first_question.id, second_question.id]
        session['q_index'] = 0
        session['answers'] = {}
        session['option_orders'] = {
            str(first_question.id): [1, 2, 3, 4],
            str(second_question.id): [1, 2, 3, 4],
        }
        session['anti_cheating'] = {
            'tab_switch_count': 0,
            'fullscreen_exit_count': 0,
            'copy_paste_count': 0,
            'webcam_warning_count': 0,
            'auto_submitted': False,
            'notes': '',
        }
        session.save()

        response = self.client.post(
            reverse('take_exam', args=[exam.id]),
            {'answer': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['question']['text'], 'Second?')
        self.assertEqual(response.json()['q_index'], 2)
        self.assertTrue(response.json()['is_final'])
        self.assertEqual(self.client.session['q_index'], 1)
        self.assertEqual(self.client.session['answers'][str(first_question.id)], '1')

    def test_take_exam_mark_for_review_allows_blank_answer(self):
        exam = self.create_active_exam()
        first_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='First?',
            option1='A',
            option2='B',
            option3='C',
            option4='D',
            correct_option=1,
        )
        second_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='Second?',
            option1='W',
            option2='X',
            option3='Y',
            option4='Z',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        session = self.client.session
        session['exam_ready'] = exam.id
        session['current_exam_id'] = exam.id
        session['question_ids'] = [first_question.id, second_question.id]
        session['q_index'] = 0
        session['answers'] = {}
        session['marked_question_ids'] = []
        session['option_orders'] = {
            str(first_question.id): [1, 2, 3, 4],
            str(second_question.id): [1, 2, 3, 4],
        }
        session['anti_cheating'] = {
            'tab_switch_count': 0,
            'fullscreen_exit_count': 0,
            'copy_paste_count': 0,
            'webcam_warning_count': 0,
            'auto_submitted': False,
            'notes': '',
        }
        session.save()

        response = self.client.post(
            reverse('take_exam', args=[exam.id]),
            {'action': 'mark_review'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['question']['text'], 'Second?')
        self.assertEqual(self.client.session['q_index'], 1)
        self.assertEqual(self.client.session['answers'], {})
        self.assertIn(str(first_question.id), self.client.session['marked_question_ids'])

    def test_take_exam_ajax_previous_returns_saved_answer(self):
        exam = self.create_active_exam()
        first_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='First?',
            option1='A',
            option2='B',
            option3='C',
            option4='D',
            correct_option=1,
        )
        second_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='Second?',
            option1='W',
            option2='X',
            option3='Y',
            option4='Z',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        session = self.client.session
        session['exam_ready'] = exam.id
        session['current_exam_id'] = exam.id
        session['question_ids'] = [first_question.id, second_question.id]
        session['q_index'] = 1
        session['answers'] = {str(first_question.id): '1'}
        session['marked_question_ids'] = []
        session['option_orders'] = {
            str(first_question.id): [1, 2, 3, 4],
            str(second_question.id): [1, 2, 3, 4],
        }
        session['anti_cheating'] = {
            'tab_switch_count': 0,
            'fullscreen_exit_count': 0,
            'copy_paste_count': 0,
            'webcam_warning_count': 0,
            'auto_submitted': False,
            'notes': '',
        }
        session.save()

        response = self.client.post(
            reverse('take_exam', args=[exam.id]),
            {'action': 'previous'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['question']['text'], 'First?')
        self.assertEqual(response.json()['question']['saved_answer'], '1')
        self.assertTrue(response.json()['is_first'])
        self.assertEqual(self.client.session['q_index'], 0)

    def test_take_exam_clear_response_removes_saved_answer_and_mark(self):
        exam = self.create_active_exam()
        question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='First?',
            option1='A',
            option2='B',
            option3='C',
            option4='D',
            correct_option=1,
        )

        self.client.login(username='student_flow', password='testpass123')
        session = self.client.session
        session['exam_ready'] = exam.id
        session['current_exam_id'] = exam.id
        session['question_ids'] = [question.id]
        session['q_index'] = 0
        session['answers'] = {str(question.id): '1'}
        session['marked_question_ids'] = [str(question.id)]
        session['option_orders'] = {str(question.id): [1, 2, 3, 4]}
        session['anti_cheating'] = {
            'tab_switch_count': 0,
            'fullscreen_exit_count': 0,
            'copy_paste_count': 0,
            'webcam_warning_count': 0,
            'auto_submitted': False,
            'notes': '',
        }
        session.save()

        response = self.client.post(
            reverse('take_exam', args=[exam.id]),
            {'action': 'clear_response'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['question']['saved_answer'], '')
        self.assertFalse(response.json()['question']['marked_for_review'])
        self.assertEqual(response.json()['answered_count'], 0)
        self.assertEqual(response.json()['marked_count'], 0)
        self.assertEqual(self.client.session['answers'], {})
        self.assertEqual(self.client.session['marked_question_ids'], [])

    def test_take_exam_ajax_next_handles_deleted_following_question(self):
        exam = self.create_active_exam()
        first_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='First?',
            option1='A',
            option2='B',
            option3='C',
            option4='D',
            correct_option=1,
        )
        second_question = Question.objects.create(
            exam=exam,
            question_type='mcq',
            question_text='Second?',
            option1='W',
            option2='X',
            option3='Y',
            option4='Z',
            correct_option=2,
        )

        self.client.login(username='student_flow', password='testpass123')
        session = self.client.session
        session['exam_ready'] = exam.id
        session['current_exam_id'] = exam.id
        session['question_ids'] = [first_question.id, second_question.id]
        session['q_index'] = 0
        session['answers'] = {}
        session['marked_question_ids'] = []
        session['option_orders'] = {
            str(first_question.id): [1, 2, 3, 4],
            str(second_question.id): [1, 2, 3, 4],
        }
        session['anti_cheating'] = {
            'tab_switch_count': 0,
            'fullscreen_exit_count': 0,
            'copy_paste_count': 0,
            'webcam_warning_count': 0,
            'auto_submitted': False,
            'notes': '',
        }
        session.save()

        second_question.delete()

        response = self.client.post(
            reverse('take_exam', args=[exam.id]),
            {'answer': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'complete')
        self.assertEqual(response.json()['redirect_url'], reverse('take_exam', args=[exam.id]))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_student_signup_sends_welcome_email(self):
        response = self.client.post(
            reverse('student_signup'),
            {
                'username': 'newstudent',
                'student_id': 'STU2001',
                'email': 'newstudent@example.com',
                'password1': 'strongpass123',
                'password2': 'strongpass123',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Welcome to Exam Portal')
        self.assertIn('newstudent', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['newstudent@example.com'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_create_exam_sends_notification_email_to_teacher_and_students(self):
        self.client.login(username='teacher_flow', password='testpass123')
        response = self.client.post(
            reverse('create_exam'),
            {
                'title': 'Email Exam',
                'duration': '30',
                'pass_percentage': '40',
                'correct_marks': '4',
                'wrong_marks': '-1',
                'max_attempts': '1',
                'instructions': 'Read carefully.',
                'start_time': (timezone.now() + timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
                'end_time': (timezone.now() + timezone.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'New Exam Created: Email Exam')
        self.assertIn("A new exam 'Email Exam' has been created.", mail.outbox[0].body)
        self.assertIn('teacher_flow@example.com', mail.outbox[0].to)
        self.assertIn('student_flow@example.com', mail.outbox[0].to)
        self.assertIn('student_other@example.com', mail.outbox[0].to)
