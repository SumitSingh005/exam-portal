from functools import wraps
from django.http import HttpResponseForbidden

def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_student:
            return HttpResponseForbidden("Only students allowed")
        return view_func(request, *args, **kwargs)
    return wrapper


def teacher_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_teacher:
            return HttpResponseForbidden("Only teachers allowed")
        return view_func(request, *args, **kwargs)
    return wrapper
