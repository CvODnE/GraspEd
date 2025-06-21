from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from .models import StudentAccount, TeacherAccount, Class


def index(request):
    return render(request, "index.html")

def signup_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        school_name = data.get('school_name')
        user_type = data.get('user_type')

        if User.objects.filter(username=username).exists():
            return JsonResponse({'status': 'error', 'message': 'Username already exists.'}, status=400)

        user = User.objects.create_user(username=username, password=password)
        if user_type == 'student':
            StudentAccount.objects.create(user=user, school_name=school_name)
            redirect_url = '/student/dashboard/'
        elif user_type == 'teacher':
            TeacherAccount.objects.create(user=user, school_name=school_name)
            redirect_url = '/teacher/dashboard/'
        else:
            user.delete()
            return JsonResponse({'status': 'error', 'message': 'Invalid account type.'}, status=400)
        
        login(request, user)
        
        return JsonResponse({'status': 'success', 'redirect_url': redirect_url})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

def login_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            redirect_url = ''
            if StudentAccount.objects.filter(user=user).exists():
                redirect_url = '/student/dashboard/'
            elif TeacherAccount.objects.filter(user=user).exists():
                redirect_url = '/teacher/dashboard/'
            else:
                # This case should ideally not happen if data is consistent
                return JsonResponse({'status': 'error', 'message': 'User account type not determined.'}, status=400)
            
            return JsonResponse({'status': 'success', 'redirect_url': redirect_url})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid username or password.'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def student_dashboard_view(request):
    return render(request, "student_dashboard.html")

@login_required
def teacher_dashboard_view(request):
    return render(request, "teacher_dashboard.html")

@login_required
def create_class_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        class_name = data.get('class_name')
        password = data.get('password')
        teacher_account = TeacherAccount.objects.get(user=request.user)
        if Class.objects.filter(name=class_name).exists():
            return JsonResponse({'status': 'error', 'message': 'Class name already exists.'}, status=400)
        new_class = Class.objects.create(name=class_name, password=password, teacher=teacher_account)
        return JsonResponse({'status': 'success', 'message': 'Class created successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def join_class_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        class_name = data.get('class_name')
        password = data.get('password')
        student_account = StudentAccount.objects.get(user=request.user)
        try:
            class_obj = Class.objects.get(name=class_name, password=password)
        except Class.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Invalid class name or password.'}, status=400)
        class_obj.students.add(student_account)
        return JsonResponse({'status': 'success', 'message': 'Joined class successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def delete_account_view(request):
    if request.method == 'POST':
        request.user.delete()
        logout(request)
        return redirect('index')
    return redirect('index')

@login_required
def logout_view(request):
    logout(request)
    return redirect('index')