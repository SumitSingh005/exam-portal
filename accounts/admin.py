from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'role_label',
        'is_staff',
        'is_active',
        'date_joined',
    )
    list_filter = ('is_student', 'is_teacher', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Portal Roles', {'fields': ('is_student', 'is_teacher')}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Portal Roles', {'fields': ('is_student', 'is_teacher')}),
    )

    @admin.display(description='Role')
    def role_label(self, obj):
        if obj.is_superuser:
            return 'Admin'
        if obj.is_teacher:
            return 'Teacher'
        if obj.is_student:
            return 'Student'
        return 'User'
