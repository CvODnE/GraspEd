from django.contrib import admin
from .models import StudentAccount, TeacherAccount

@admin.register(StudentAccount)
class StudentAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'school_name')

@admin.register(TeacherAccount)
class TeacherAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'school_name')
