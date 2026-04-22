from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from exams.models import Exam

User = get_user_model()


class StudentDashboardTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student1',
            email='student@example.com',
            password='testpass123',
        )
        self.student.is_student = True
        self.student.save()

        self.teacher = User.objects.create_user(
            username='teacher1',
            email='teacher@example.com',
            password='testpass123',
        )
        self.teacher.is_teacher = True
        self.teacher.save()

    def test_student_dashboard_renders_successfully_with_exam_list(self):
        Exam.objects.create(
            title='Sample Exam',
            duration=30,
            created_by=self.teacher,
            pass_percentage=40,
            correct_marks=4,
            wrong_marks=-1,
        )

        self.client.login(username='student1', password='testpass123')
        response = self.client.get(reverse('student_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Dashboard')
        self.assertContains(response, 'Sample Exam')

    def test_student_profile_renders_successfully(self):
        self.client.login(username='student1', password='testpass123')
        response = self.client.get(reverse('student_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Profile')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_flow_sends_email(self):
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'student@example.com'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Password reset for', mail.outbox[0].subject)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_password_reset_done_page_explains_console_backend_in_development(self):
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'student@example.com'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'console email backend')
        self.assertContains(response, 'python manage.py runserver')

    def test_student_signup_rejects_duplicate_email(self):
        response = self.client.post(
            reverse('student_signup'),
            {
                'username': 'student2',
                'email': 'student@example.com',
                'password1': 'testpass123',
                'password2': 'testpass123',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email already exists')

    def test_teacher_signup_rejects_weak_password(self):
        response = self.client.post(
            reverse('teacher_signup'),
            {
                'username': 'teacher2',
                'email': 'teacher2@example.com',
                'password1': '123',
                'password2': '123',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'too short')
