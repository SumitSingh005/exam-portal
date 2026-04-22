from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [

    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.txt',
            subject_template_name='accounts/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    

    path('student/signup/', views.student_signup, name='student_signup'),
    path('teacher/signup/', views.teacher_signup, name='teacher_signup'),
    path('register/', views.register_choice, name='register_choice'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student-profile/', views.student_profile, name='student_profile'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
]
