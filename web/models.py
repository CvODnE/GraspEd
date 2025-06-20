from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class StudentAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school_name = models.CharField(max_length=100)

    def __str__(self):
        return f'Student: {self.user.username}'

class TeacherAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school_name = models.CharField(max_length=100)

    def __str__(self):
        return f'Teacher: {self.user.username}'
