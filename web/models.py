from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

# Create your models here.

class StudentAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school_name = models.CharField(max_length=100)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    def __str__(self):
        return f'Student: {self.user.username}'

class TeacherAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school_name = models.CharField(max_length=100)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    def __str__(self):
        return f'Teacher: {self.user.username}'

class Class(models.Model):
    name = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=100)
    teachers = models.ManyToManyField(TeacherAccount, blank=True, related_name='classes')
    students = models.ManyToManyField(StudentAccount, blank=True, related_name='classes')

    def __str__(self):
        teacher_names = ', '.join([t.user.username for t in self.teachers.all()])
        return f'Class: {self.name} (Teachers: {teacher_names})'

# This custom model replaces allauth's SocialAccount to avoid an SQLite issue
# on Windows where the JSON1 extension is not available. We are replacing
# the JSONField with a TextField.
class CustomSocialAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    provider = models.CharField(
        verbose_name="provider",
        max_length=200,
    )
    uid = models.CharField(
        verbose_name="uid",
        max_length=getattr(settings, "ALLAUTH_SOCIALACCOUNT_UID_MAX_LENGTH", 191),
    )
    last_login = models.DateTimeField(verbose_name="last login", auto_now=True)
    date_joined = models.DateTimeField(verbose_name="date joined", auto_now_add=True)
    extra_data = models.TextField(verbose_name="extra data", default="{}")

    class Meta:
        unique_together = ("provider", "uid")
        verbose_name = "social account"
        verbose_name_plural = "social accounts"
        abstract = False

    def __str__(self):
        return str(self.user)

class Note(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='notes')
    teacher = models.ForeignKey(TeacherAccount, on_delete=models.CASCADE, related_name='notes', blank=True, null=True)
    uploaded_by_student = models.ForeignKey(StudentAccount, on_delete=models.CASCADE, related_name='notes', blank=True, null=True)
    file = models.FileField(upload_to='notes/', blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        uploader = self.teacher.user.username if self.teacher else (self.uploaded_by_student.user.username if self.uploaded_by_student else 'Unknown')
        return f'Note for {self.class_obj.name} by {uploader} ({self.uploaded_at})'

class HiddenNote(models.Model):
    """Track which users have hidden which notes (for 'Delete for Me' functionality)"""
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='hidden_by')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['note', 'user']  # Prevent duplicate hiding

    def __str__(self):
        return f'{self.user.username} hidden {self.note.name}'

class AttendanceRequest(models.Model):
    """Model to track when students request attendance"""
    student = models.ForeignKey(StudentAccount, on_delete=models.CASCADE, related_name='attendance_requests')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendance_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)  # Whether teacher has responded
    REQUESTED_STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
    ]
    requested_status = models.CharField(max_length=10, choices=REQUESTED_STATUS_CHOICES, default='present')
    
    class Meta:
        # Prevent multiple pending requests from same student in same class
        unique_together = ['student', 'class_obj', 'is_processed']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'class_obj'],
                condition=models.Q(is_processed=False),
                name='unique_pending_attendance_request'
            )
        ]

    def __str__(self):
        return f'Attendance request from {self.student.user.username} for {self.class_obj.name}'

class Attendance(models.Model):
    """Model to track actual attendance records"""
    ATTENDANCE_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
    ]
    
    student = models.ForeignKey(StudentAccount, on_delete=models.CASCADE, related_name='attendances')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendances')
    teacher = models.ForeignKey(TeacherAccount, on_delete=models.CASCADE, related_name='marked_attendances')
    status = models.CharField(max_length=10, choices=ATTENDANCE_CHOICES)
    marked_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)  # Date of attendance
    
    class Meta:
        # Prevent multiple attendance records for same student on same date in same class
        unique_together = ['student', 'class_obj', 'date']

    def __str__(self):
        return f'{self.student.user.username} - {self.status} in {self.class_obj.name} on {self.date}'

class Reminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    remind_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.text} at {self.remind_at}"
