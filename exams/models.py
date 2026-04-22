from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Exam(models.Model):
    title = models.CharField(max_length=200)
    duration = models.IntegerField(help_text="Minutes")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    pass_percentage = models.FloatField(default=40.0)
    correct_marks = models.FloatField(default=4.0)
    wrong_marks = models.FloatField(default=-1.0)
    instructions = models.TextField(blank=True)
    max_attempts = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.title

    @property
    def total_questions(self):
        return self.question_set.count()

    @property
    def max_marks(self):
        return self.total_questions * self.correct_marks

    @property
    def has_started(self):
        return bool(self.start_time and timezone.now() >= self.start_time)

    @property
    def has_ended(self):
        return bool(self.end_time and timezone.now() > self.end_time)

    @property
    def is_active(self):
        now = timezone.now()
        return bool(
            self.is_published
            and self.start_time
            and self.end_time
            and self.start_time <= now <= self.end_time
        )

    @property
    def has_unlimited_attempts(self):
        return self.max_attempts == 0


class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'MCQ'),
        ('written', 'Written'),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='mcq')
    question_text = models.TextField()
    option1 = models.CharField(max_length=200, blank=True)
    option2 = models.CharField(max_length=200, blank=True)
    option3 = models.CharField(max_length=200, blank=True)
    option4 = models.CharField(max_length=200, blank=True)
    correct_option = models.IntegerField(null=True, blank=True)
    written_answer = models.TextField(blank=True)

    def __str__(self):
        return self.question_text

    @property
    def is_written(self):
        return self.question_type == 'written'


class Result(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    score = models.FloatField()
    total_questions = models.IntegerField(default=0)
    percentage = models.FloatField(default=0)
    passed = models.BooleanField(default=False)
    review_pending = models.BooleanField(default=False)
    violation_count = models.IntegerField(default=0)
    tab_switch_count = models.IntegerField(default=0)
    fullscreen_exit_count = models.IntegerField(default=0)
    copy_paste_count = models.IntegerField(default=0)
    webcam_warning_count = models.IntegerField(default=0)
    auto_submitted = models.BooleanField(default=False)
    anti_cheating_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.exam}"

    @property
    def max_marks(self):
        return self.total_questions * self.exam.correct_marks


class ResultAnswer(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.IntegerField(null=True, blank=True)
    written_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    awarded_marks = models.FloatField(default=0)
    reviewed = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)

    def __str__(self):
        return f"{self.result_id} - Q{self.question_id}"


class PortalSettings(models.Model):
    site_name = models.CharField(max_length=200, default='Exam Portal')
    support_email = models.EmailField(blank=True)
    certificate_title = models.CharField(max_length=200, default='Certificate of Achievement')
    default_pass_percentage = models.FloatField(default=40.0)

    class Meta:
        verbose_name = 'Portal Settings'
        verbose_name_plural = 'Portal Settings'

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def build_default(cls):
        return cls(
            pk=1,
            site_name='Exam Portal',
            certificate_title='Certificate of Achievement',
            default_pass_percentage=40.0,
        )

    @classmethod
    def get_solo(cls):
        try:
            settings_obj, _ = cls.objects.get_or_create(
                pk=1,
                defaults={
                    'site_name': 'Exam Portal',
                    'certificate_title': 'Certificate of Achievement',
                    'default_pass_percentage': 40.0,
                },
            )
            return settings_obj
        except (OperationalError, ProgrammingError):
            return cls.build_default()
