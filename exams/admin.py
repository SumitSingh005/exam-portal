from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from accounts.models import User

from .models import Exam, PortalSettings, Question, Result, ResultAnswer
from .views import recalculate_result


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ('question_type', 'question_text', 'correct_option')
    show_change_link = True


class ResultInline(admin.TabularInline):
    model = Result
    extra = 0
    fields = ('student', 'score', 'percentage', 'result_status_badge', 'submitted_at')
    readonly_fields = ('student', 'score', 'percentage', 'result_status_badge', 'submitted_at')
    show_change_link = True
    can_delete = False

    @admin.display(description='Status')
    def result_status_badge(self, obj):
        if obj.review_pending:
            return status_badge('Pending Review', '#f59e0b')
        if obj.passed:
            return status_badge('Pass', '#16a34a')
        return status_badge('Fail', '#dc2626')


class ResultAnswerInline(admin.TabularInline):
    model = ResultAnswer
    extra = 0
    fields = (
        'question',
        'selected_option',
        'written_answer',
        'awarded_marks',
        'is_correct',
        'reviewed',
        'feedback',
    )
    readonly_fields = ('question', 'selected_option', 'written_answer', 'is_correct')


def status_badge(label, color):
    return format_html(
        '<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
        'background:{};color:white;font-weight:600;font-size:12px;">{}</span>',
        color,
        label,
    )


def build_admin_dashboard_summary():
    portal_settings = PortalSettings.get_solo()
    total_students = User.objects.filter(is_student=True).count()
    total_teachers = User.objects.filter(is_teacher=True).count()
    total_exams = Exam.objects.count()
    published_exams = Exam.objects.filter(is_published=True).count()
    pending_reviews = Result.objects.filter(review_pending=True).count()
    total_results = Result.objects.count()

    return {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_exams': total_exams,
        'published_exams': published_exams,
        'pending_reviews': pending_reviews,
        'total_results': total_results,
        'site_name': portal_settings.site_name,
        'support_email': portal_settings.support_email,
        'certificate_title': portal_settings.certificate_title,
        'default_pass_percentage': portal_settings.default_pass_percentage,
        'quick_links': [
            {
                'label': 'Portal Settings',
                'url': reverse('admin:exams_portalsettings_change', args=[1]),
            },
            {
                'label': 'Review Pending Results',
                'url': f"{reverse('admin:exams_result_changelist')}?review_pending__exact=1",
            },
            {
                'label': 'Open Exams',
                'url': f"{reverse('admin:exams_exam_changelist')}?is_published__exact=1",
            },
            {
                'label': 'Manage Students',
                'url': f"{reverse('admin:accounts_user_changelist')}?is_student__exact=1",
            },
            {
                'label': 'Manage Teachers',
                'url': f"{reverse('admin:accounts_user_changelist')}?is_teacher__exact=1",
            },
            {
                'label': 'All Results',
                'url': reverse('admin:exams_result_changelist'),
            },
        ],
    }


@admin.register(PortalSettings)
class PortalSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'support_email', 'certificate_title', 'default_pass_percentage')

    def has_add_permission(self, request):
        return not PortalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'created_by',
        'duration',
        'attempt_limit_label',
        'question_count',
        'result_count',
        'publish_status_badge',
        'start_time',
        'end_time',
    )
    list_filter = ('is_published', 'start_time', 'end_time', 'created_by')
    search_fields = ('title', 'created_by__username', 'created_by__email')
    autocomplete_fields = ('created_by',)
    inlines = [QuestionInline, ResultInline]
    actions = ('publish_selected_exams', 'unpublish_selected_exams')

    @admin.action(description='Publish selected exams')
    def publish_selected_exams(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f'{updated} exam(s) published successfully.')

    @admin.action(description='Unpublish selected exams')
    def unpublish_selected_exams(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} exam(s) unpublished successfully.')

    @admin.display(description='Attempts')
    def attempt_limit_label(self, obj):
        return 'Unlimited' if obj.has_unlimited_attempts else obj.max_attempts

    @admin.display(description='Published')
    def publish_status_badge(self, obj):
        if obj.is_published:
            return status_badge('Published', '#2563eb')
        return status_badge('Unpublished', '#6b7280')

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.question_set.count()

    @admin.display(description='Results')
    def result_count(self, obj):
        return obj.result_set.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_question', 'exam', 'question_type', 'correct_option')
    list_filter = ('question_type', 'exam')
    search_fields = ('question_text', 'exam__title')
    autocomplete_fields = ('exam',)

    @admin.display(description='Question')
    def short_question(self, obj):
        text = obj.question_text.strip()
        return text[:80] + ('...' if len(text) > 80 else '')


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'exam',
        'score',
        'percentage',
        'result_status_badge',
        'submitted_at',
    )
    list_filter = ('passed', 'review_pending', 'submitted_at', 'exam')
    search_fields = ('student__username', 'student__email', 'exam__title')
    autocomplete_fields = ('student', 'exam')
    inlines = [ResultAnswerInline]
    actions = ('mark_selected_results_as_reviewed',)

    @admin.action(description='Mark selected results as reviewed')
    def mark_selected_results_as_reviewed(self, request, queryset):
        updated = 0
        skipped = 0

        for result in queryset:
            unreviewed_answers = result.answers.filter(question__question_type='written', reviewed=False)
            if not unreviewed_answers.exists():
                recalculate_result(result)
                updated += 1
                continue

            for answer in unreviewed_answers:
                answer.reviewed = True
                answer.is_correct = answer.awarded_marks == result.exam.correct_marks
                answer.save(update_fields=['reviewed', 'is_correct'])

            recalculate_result(result)
            updated += 1

        if updated:
            self.message_user(request, f'{updated} result(s) marked as reviewed and recalculated.')
        if skipped:
            self.message_user(request, f'{skipped} result(s) were skipped.', level='warning')

    @admin.display(description='Status')
    def result_status_badge(self, obj):
        if obj.review_pending:
            return status_badge('Pending Review', '#f59e0b')
        if obj.passed:
            return status_badge('Pass', '#16a34a')
        return status_badge('Fail', '#dc2626')


@admin.register(ResultAnswer)
class ResultAnswerAdmin(admin.ModelAdmin):
    list_display = (
        'result',
        'question',
        'selected_option',
        'awarded_marks',
        'is_correct',
        'reviewed',
    )
    list_filter = ('reviewed', 'is_correct', 'question__question_type')
    search_fields = (
        'result__student__username',
        'result__exam__title',
        'question__question_text',
        'written_answer',
    )
    autocomplete_fields = ('result', 'question')
    actions = ('mark_selected_answers_as_reviewed',)

    @admin.action(description='Mark selected answers as reviewed')
    def mark_selected_answers_as_reviewed(self, request, queryset):
        updated = 0
        touched_results = set()

        for answer in queryset.select_related('result', 'question', 'result__exam'):
            answer.reviewed = True
            answer.is_correct = answer.awarded_marks == answer.result.exam.correct_marks
            answer.save(update_fields=['reviewed', 'is_correct'])
            touched_results.add(answer.result_id)
            updated += 1

        for result in Result.objects.filter(id__in=touched_results):
            recalculate_result(result)

        self.message_user(request, f'{updated} answer(s) marked as reviewed.')


_original_admin_index = admin.site.index
admin.site.index_template = 'admin/custom_index.html'
admin.site.site_header = 'Exam Portal Admin'
admin.site.site_title = 'Exam Portal Admin'
admin.site.index_title = 'Management Dashboard'


def custom_admin_index(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context['dashboard_summary'] = build_admin_dashboard_summary()
    return _original_admin_index(request, extra_context=extra_context)


admin.site.index = custom_admin_index
