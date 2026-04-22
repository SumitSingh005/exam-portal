from django.conf import settings


def auth_environment(request):
    return {
        'uses_console_email_backend': settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend',
    }
