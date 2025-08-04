from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from .models import StudentAccount, TeacherAccount, Class, Note, CustomSocialAccount, AttendanceRequest, Attendance

# Try to import allauth models if available
try:
    from allauth.socialaccount.models import SocialApplication
    HAS_SOCIAL_APPLICATION = True
except ImportError:
    HAS_SOCIAL_APPLICATION = False

@admin.register(StudentAccount)
class StudentAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'school_name', 'user_email', 'user_date_joined')
    list_filter = ('school_name', 'user__date_joined')
    search_fields = ('user__username', 'user__email', 'school_name')
    readonly_fields = ('user',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def user_date_joined(self, obj):
        return obj.user.date_joined
    user_date_joined.short_description = 'Date Joined'

@admin.register(TeacherAccount)
class TeacherAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'school_name', 'user_email', 'user_date_joined')
    list_filter = ('school_name', 'user__date_joined')
    search_fields = ('user__username', 'user__email', 'school_name')
    readonly_fields = ('user',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def user_date_joined(self, obj):
        return obj.user.date_joined
    user_date_joined.short_description = 'Date Joined'

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher_list', 'student_count', 'created_at', 'password', 'notes_count')
    list_filter = ('teachers', 'students', 'teachers__school_name')
    search_fields = ('name', 'teachers__user__username', 'students__user__username')
    filter_horizontal = ('teachers', 'students')
    list_per_page = 20
    
    def teacher_list(self, obj):
        return ", ".join([t.user.username for t in obj.teachers.all()])
    teacher_list.short_description = 'Teachers'
    
    def student_count(self, obj):
        return obj.students.count()
    student_count.short_description = 'Students'
    student_count.admin_order_field = 'students__count'
    
    def created_at(self, obj):
        return obj.id  # Using ID as a simple timestamp
    created_at.short_description = 'Created'
    
    def notes_count(self, obj):
        return obj.notes.count()
    notes_count.short_description = 'Notes'
    notes_count.admin_order_field = 'notes__count'

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('class_obj', 'teacher', 'uploaded_by_student', 'file', 'text', 'uploaded_at')
    list_filter = ('class_obj', 'teacher', 'uploaded_by_student', 'uploaded_at')
    search_fields = ('class_obj__name', 'teacher__user__username', 'uploaded_by_student__user__username')
    readonly_fields = ('uploaded_at',)
    date_hierarchy = 'uploaded_at'
    list_per_page = 25
    
    def class_name(self, obj):
        return obj.class_obj.name
    class_name.short_description = 'Class'
    class_name.admin_order_field = 'class_obj__name'
    
    def teacher_name(self, obj):
        return obj.teacher.user.username
    teacher_name.short_description = 'Teacher'
    teacher_name.admin_order_field = 'teacher__user__username'
    
    def has_file(self, obj):
        return bool(obj.file)
    has_file.boolean = True
    has_file.short_description = 'Has File'
    
    def has_text(self, obj):
        return bool(obj.text)
    has_text.boolean = True
    has_text.short_description = 'Has Text'
    
    def file_size(self, obj):
        if obj.file:
            try:
                size = obj.file.size
                if size < 1024:
                    return f"{size} B"
                elif size < 1024 * 1024:
                    return f"{size // 1024} KB"
                else:
                    return f"{size // (1024 * 1024)} MB"
            except:
                return "Unknown"
        return "-"
    file_size.short_description = 'File Size'

@admin.register(CustomSocialAccount)
class CustomSocialAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'uid', 'last_login', 'date_joined')
    list_filter = ('provider', 'last_login', 'date_joined')
    search_fields = ('user__username', 'user__email', 'provider', 'uid')
    readonly_fields = ('last_login', 'date_joined')
    date_hierarchy = 'date_joined'

# Register allauth models
if HAS_SOCIAL_APPLICATION:
    @admin.register(SocialApplication)
    class SocialApplicationAdmin(admin.ModelAdmin):
        list_display = ('name', 'provider', 'client_id')
        list_filter = ('provider',)
        search_fields = ('name', 'provider')

# Unregister the default User admin and register our custom one
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    readonly_fields = ('date_joined', 'last_login')

@admin.register(AttendanceRequest)
class AttendanceRequestAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'class_name', 'requested_at', 'is_processed', 'status')
    list_filter = ('is_processed', 'requested_at', 'class_obj', 'class_obj__teachers')
    search_fields = ('student__user__username', 'class_obj__name')
    readonly_fields = ('requested_at',)
    date_hierarchy = 'requested_at'
    list_per_page = 25
    
    def student_name(self, obj):
        return obj.student.user.username
    student_name.short_description = 'Student'
    student_name.admin_order_field = 'student__user__username'
    
    def class_name(self, obj):
        return obj.class_obj.name
    class_name.short_description = 'Class'
    class_name.admin_order_field = 'class_obj__name'
    
    def status(self, obj):
        if obj.is_processed:
            return "Processed"
        return "Pending"
    status.short_description = 'Status'

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'class_name', 'teacher_name', 'status', 'date', 'marked_at')
    list_filter = ('status', 'date', 'marked_at', 'class_obj', 'teacher')
    search_fields = ('student__user__username', 'class_obj__name', 'teacher__user__username')
    readonly_fields = ('marked_at',)
    date_hierarchy = 'date'
    list_per_page = 25
    
    def student_name(self, obj):
        return obj.student.user.username
    student_name.short_description = 'Student'
    student_name.admin_order_field = 'student__user__username'
    
    def class_name(self, obj):
        return obj.class_obj.name
    class_name.short_description = 'Class'
    class_name.admin_order_field = 'class_obj__name'
    
    def teacher_name(self, obj):
        return obj.teacher.user.username
    teacher_name.short_description = 'Teacher'
    teacher_name.admin_order_field = 'teacher__user__username'
