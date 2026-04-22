from django.urls import path

from . import views

urlpatterns = [
    path('', views.exam_list, name='exam_list'),
    path('instructions/<int:exam_id>/', views.exam_instructions, name='exam_instructions'),
    path('leaderboard/<int:exam_id>/', views.leaderboard, name='leaderboard'),
    path('take/<int:exam_id>/', views.take_exam, name='take_exam'),
    path('results/', views.result_history, name='result_history'),
    path('create-exam/', views.create_exam, name='create_exam'),
    path('add-question/', views.add_question, name='add_question'),
    path('teacher-exams/', views.teacher_exam_list, name='teacher_exam_list'),
    path('teacher-report/<int:exam_id>/', views.teacher_exam_report, name='teacher_exam_report'),
    path('teacher-report/<int:exam_id>/export/<str:file_format>/', views.export_results, name='export_results'),
    path('review-result/<int:result_id>/', views.review_result, name='review_result'),
    path('edit/<int:exam_id>/', views.edit_exam, name='edit_exam'),
    path('delete/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('manage-questions/<int:exam_id>/', views.manage_questions, name='manage_questions'),
    path('edit-question/<int:q_id>/', views.edit_question, name='edit_question'),
    path('delete-question/<int:q_id>/', views.delete_question, name='delete_question'),
]
