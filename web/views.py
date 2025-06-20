from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from .models import StudentAccount, TeacherAccount


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
        elif user_type == 'teacher':
            TeacherAccount.objects.create(user=user, school_name=school_name)
        else:
            user.delete()
            return JsonResponse({'status': 'error', 'message': 'Invalid account type.'}, status=400)
        
        login(request, user)
        
        return JsonResponse({'status': 'success', 'message': 'Account created successfully!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def delete_account_view(request):
    if request.method == 'POST':
        request.user.delete()
        logout(request)
        return redirect('index')
    return redirect('index')