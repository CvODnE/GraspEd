from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from .models import StudentAccount, TeacherAccount, Class, Note, AttendanceRequest, Attendance, HiddenNote
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import os
import uuid
from datetime import date
import requests
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import cohere
from dotenv import load_dotenv
from django.views.decorators.http import require_POST
from langchain_community.llms import Cohere
from langchain_community.utilities.serpapi import SerpAPIWrapper
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
import re
from django.utils import timezone
from dateutil import parser as date_parser
from .models import Reminder
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

# Load environment variables from .env
load_dotenv()

cohere_api_key = os.getenv("COHERE_API_KEY")
serpapi_api_key = os.getenv("SERPAPI_API_KEY")
llm = Cohere(cohere_api_key=cohere_api_key)
search = SerpAPIWrapper(serpapi_api_key=serpapi_api_key)

search_tool = Tool(
    name="Web Search",
    func=search.run,
    description="Searches the web for up-to-date information about any topic."
)

agent = initialize_agent(
    tools=[search_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=False,
    handle_parsing_errors=True
)

# Global variable to store the local chatbot instance
local_chatbot = None

def get_local_chatbot():
    """Get or create local chatbot instance"""
    global local_chatbot
    if local_chatbot is None:
        try:
            from local_chatbot import LocalChatbot
            print("🤖 Initializing local chatbot...")
            local_chatbot = LocalChatbot("microsoft/DialoGPT-small")
            if local_chatbot.is_loaded:
                print("✅ Local chatbot initialized successfully!")
            else:
                print("❌ Local chatbot failed to initialize")
                local_chatbot = None
        except Exception as e:
            print(f"❌ Error initializing local chatbot: {e}")
            local_chatbot = None
    return local_chatbot

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
        
        from django.contrib.auth.backends import ModelBackend
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        return JsonResponse({'status': 'success', 'redirect_url': redirect_url})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

def login_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            from django.contrib.auth.backends import ModelBackend
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
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
    profile_photo_url = None
    try:
        profile_photo_url = request.user.studentaccount.profile_photo.url
    except Exception:
        profile_photo_url = None
    # Get reminders for the logged-in student
    reminders = Reminder.objects.filter(user=request.user).order_by('remind_at')
    return render(request, "student_dashboard.html", {"profile_photo_url": profile_photo_url, "reminders": reminders})

@login_required
def teacher_dashboard_view(request):
    teacher_profile_photo = None
    try:
        teacher_account = TeacherAccount.objects.get(user=request.user)
        teacher_profile_photo = teacher_account.profile_photo.url if teacher_account.profile_photo else None
    except TeacherAccount.DoesNotExist:
        teacher_profile_photo = None
    return render(request, "teacher_dashboard.html", {
        'teacher_profile_photo': teacher_profile_photo,
        'active_page': 'dashboard',
    })

@login_required
def create_class_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            class_name = data.get('class_name')
            password = data.get('password')
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found. Please log in as a teacher.'}, status=400)
            # Check if class name already exists
            if Class.objects.filter(name=class_name).exists():
                return JsonResponse({'status': 'error', 'message': 'Class name already exists. Please choose a different name.'}, status=400)
            # Create the new class
            new_class = Class.objects.create(name=class_name, password=password)
            new_class.teachers.add(teacher_account)
            return JsonResponse({'status': 'success', 'message': 'Class created successfully.'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_teacher_classes_view(request):
    """Get all classes joined by the teacher"""
    if request.method == 'GET':
        try:
            teacher_account = TeacherAccount.objects.get(user=request.user)
            classes = Class.objects.filter(teachers=teacher_account)
            classes_data = []
            for class_obj in classes:
                classes_data.append({
                    'name': class_obj.name,
                    'password': class_obj.password,
                    'student_count': class_obj.students.count(),
                    'created_at': class_obj.id,  # Using ID as a simple timestamp for now
                })
            return JsonResponse({'status': 'success', 'classes': classes_data})
        except TeacherAccount.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def join_class_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            class_name = data.get('class_name')
            password = data.get('password')
            
            # Check if user has a student account
            try:
                student_account = StudentAccount.objects.get(user=request.user)
            except StudentAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Student account not found. Please log in as a student.'}, status=400)
            
            # Check if class exists with correct password
            try:
                class_obj = Class.objects.get(name=class_name, password=password)
            except Class.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Invalid class name or password. Please check with your teacher.'}, status=400)
            
            # Add student to class
            class_obj.students.add(student_account)
            return JsonResponse({'status': 'success', 'message': 'Joined class successfully.'})
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_student_classes_view(request):
    """Get all classes joined by the student"""
    if request.method == 'GET':
        try:
            student_account = StudentAccount.objects.get(user=request.user)
            classes = student_account.classes.all()
            
            classes_data = []
            for class_obj in classes:
                teachers = [t.user.username for t in class_obj.teachers.all()]
                classes_data.append({
                    'name': class_obj.name,
                    'teacher': teachers[0] if teachers else '',
                    'student_count': class_obj.students.count(),
                    'joined_at': class_obj.id,  # Using ID as a simple timestamp for now
                })
            
            return JsonResponse({'status': 'success', 'classes': classes_data})
        except StudentAccount.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student account not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
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
    # Logout from Django auth
    logout(request)
    
    # Clear any session data
    request.session.flush()
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'redirect_url': '/'})
    
    # Redirect to home page for regular requests
    return redirect('/')

@login_required
def user_type_selection_view(request):
    """Show user type selection page after Google login"""
    # Check if user already has an account type
    if StudentAccount.objects.filter(user=request.user).exists():
        return redirect('student_dashboard')
    elif TeacherAccount.objects.filter(user=request.user).exists():
        return redirect('teacher_dashboard')
    
    return render(request, 'user_type_selection.html')

@login_required
def set_user_type_view(request):
    """Set user type and redirect to appropriate dashboard"""
    if request.method == 'POST':
        data = json.loads(request.body)
        user_type = data.get('user_type')
        school_name = data.get('school_name', 'Unknown School')
        
        if user_type == 'student':
            StudentAccount.objects.create(user=request.user, school_name=school_name)
            return JsonResponse({'status': 'success', 'redirect_url': '/student/dashboard/'})
        elif user_type == 'teacher':
            TeacherAccount.objects.create(user=request.user, school_name=school_name)
            return JsonResponse({'status': 'success', 'redirect_url': '/teacher/dashboard/'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid user type'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

# New: Teacher join class view
@login_required
def teacher_join_class_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            class_name = data.get('class_name')
            password = data.get('password')
            # Get or create TeacherAccount for the user
            teacher_account, _ = TeacherAccount.objects.get_or_create(user=request.user, defaults={'school_name': 'Unknown'})
            # Check if class exists with correct password
            try:
                class_obj = Class.objects.get(name=class_name, password=password)
            except Class.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Invalid class name or password. Please check with your admin.'}, status=400)
            # Add teacher to class
            class_obj.teachers.add(teacher_account)
            return JsonResponse({'status': 'success', 'message': 'Joined class successfully.'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def teacher_upload_note_view(request):
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        note_text = request.POST.get('note_text', '')
        note_file = request.FILES.get('note_file')
        try:
            teacher_account, _ = TeacherAccount.objects.get_or_create(user=request.user, defaults={'school_name': 'Unknown'})
            class_obj = Class.objects.get(name=class_name, teachers=teacher_account)
        except Class.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'You have not joined this class or class does not exist.'}, status=400)
        if not note_file and not note_text:
            return JsonResponse({'status': 'error', 'message': 'Please provide a file or type a note.'}, status=400)
        # Set name for text-only notes
        note_name = None
        if note_file:
            note_name = note_file.name
        elif note_text:
            note_name = note_text[:40] + ("..." if len(note_text) > 40 else "")
        else:
            note_name = "Text Note"
        note = Note.objects.create(class_obj=class_obj, teacher=teacher_account, text=note_text, name=note_name)
        if note_file:
            note.file.save(note_file.name, note_file)
        # --- Automated Reminders for Students ---
        from .models import Reminder
        from django.utils import timezone
        reminder_text = f"A new note '{note_name}' was uploaded to your class '{class_obj.name}'."
        remind_at = timezone.now()
        for student in class_obj.students.all():
            Reminder.objects.create(user=student.user, text=reminder_text, remind_at=remind_at)
        # --- End Automated Reminders ---
        return JsonResponse({'status': 'success', 'message': 'Note uploaded successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_class_notes_view(request):
    class_name = request.GET.get('class_name')
    if not class_name:
        return JsonResponse({'status': 'error', 'message': 'Class name is required.'}, status=400)
    
    try:
        class_obj = Class.objects.get(name=class_name)
    except Class.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Class not found.'}, status=404)
    
    # Enhanced security check: verify user is a member of the class
    is_member = False
    
    # Check if user is a student in the class
    try:
        student_account = StudentAccount.objects.get(user=request.user)
        if class_obj.students.filter(pk=student_account.pk).exists():
            is_member = True
    except StudentAccount.DoesNotExist:
        pass
    
    # Check if user is a teacher in the class
    try:
        teacher_account = TeacherAccount.objects.get(user=request.user)
        if class_obj.teachers.filter(pk=teacher_account.pk).exists():
            is_member = True
    except TeacherAccount.DoesNotExist:
        pass
    
    if not is_member:
        return JsonResponse({'status': 'error', 'message': 'You are not a member of this class.'}, status=403)
    
    # Get notes for the class
    notes = class_obj.notes.order_by('-uploaded_at')
    notes_data = []
    for note in notes:
        notes_data.append({
            'id': note.id,
            'teacher': note.teacher.user.username,
            'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            'text': note.text,
            'file_url': note.file.url if note.file else None,
            'file_name': note.file.name.split('/')[-1] if note.file else None,
        })
    return JsonResponse({'status': 'success', 'notes': notes_data})

@login_required
def student_notes_page_view(request):
    profile_photo_url = None
    try:
        profile_photo_url = request.user.studentaccount.profile_photo.url
    except Exception:
        profile_photo_url = None
    return render(request, 'student_notes.html', {"profile_photo_url": profile_photo_url})

@login_required
def get_student_notes_view(request):
    """Get all notes for all classes the student has joined"""
    if request.method == 'GET':
        try:
            # Verify user is a student
            student_account = StudentAccount.objects.get(user=request.user)
            
            # Get all classes the student has joined
            joined_classes = student_account.classes.all()
            
            # STRICT SECURITY CHECK: ensure student has actually joined classes
            if not joined_classes.exists():
                return JsonResponse({'status': 'success', 'notes': [], 'message': 'No classes joined'})
            
            all_notes = []
            for class_obj in joined_classes:
                # Double-check that student is still a member of this class
                if not class_obj.students.filter(pk=student_account.pk).exists():
                    continue  # Skip if student is no longer a member
                
                # Get notes for this class (both teacher and student notes), excluding hidden notes
                notes = class_obj.notes.order_by('-uploaded_at')
                for note in notes:
                    # Skip if this note is hidden by the current user
                    try:
                        if HiddenNote.objects.filter(note=note, user=request.user).exists():
                            continue
                    except Exception as hidden_error:
                        # Continue processing even if hidden note check fails
                        pass
                    
                    # Determine uploader type and name
                    uploader_type = 'teacher' if note.teacher else 'student'
                    uploader_name = ''
                    if note.teacher:
                        uploader_name = note.teacher.user.username
                    elif note.uploaded_by_student:
                        uploader_name = note.uploaded_by_student.user.username
                    
                    # Check if current user uploaded this note
                    is_own_note = False
                    if uploader_type == 'teacher' and note.teacher and note.teacher.user == request.user:
                        is_own_note = True
                    elif uploader_type == 'student' and note.uploaded_by_student and note.uploaded_by_student.user == request.user:
                        is_own_note = True
                    
                    all_notes.append({
                        'id': note.id,
                        'teacher': uploader_name,  # Keep for backward compatibility
                        'uploader_type': uploader_type,
                        'uploader_name': uploader_name,
                        'is_own_note': is_own_note,  # New field to indicate if current user uploaded this note
                        'uploaded_at': note.uploaded_at.strftime('%Y-%m-%d %H:%M') if note.uploaded_at else '',
                        'name': note.name or '',
                        'text': note.text,
                        'file_url': note.file.url if note.file else None,
                        'file_name': note.file.name.split('/')[-1] if note.file else None,
                        'class_name': class_obj.name,  # Include class name for display
                    })
            
            # Sort all notes by uploaded_at descending
            all_notes.sort(key=lambda x: x['uploaded_at'], reverse=True)
            
            return JsonResponse({'status': 'success', 'notes': all_notes, 'joined_classes_count': joined_classes.count()})
            
        except StudentAccount.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student account not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_teacher_notes_view(request):
    """Get all notes for all classes the teacher has joined"""
    if request.method == 'GET':
        try:
            # Verify user is a teacher
            teacher_account = TeacherAccount.objects.get(user=request.user)
            
            # Get all classes the teacher has joined
            joined_classes = teacher_account.classes.all()
            
            all_notes = []
            for class_obj in joined_classes:
                # Get notes for this class (both teacher and student notes), excluding hidden notes
                notes = class_obj.notes.order_by('-uploaded_at')
                for note in notes:
                    # Skip if this note is hidden by the current user
                    try:
                        if HiddenNote.objects.filter(note=note, user=request.user).exists():
                            continue
                    except Exception as hidden_error:
                        # Continue processing even if hidden note check fails
                        pass
                    
                    # Determine uploader type and name
                    uploader_type = 'teacher' if note.teacher else 'student'
                    uploader_name = ''
                    if note.teacher:
                        uploader_name = note.teacher.user.username
                    elif note.uploaded_by_student:
                        uploader_name = note.uploaded_by_student.user.username
                    
                    # Check if current user uploaded this note
                    is_own_note = False
                    if uploader_type == 'teacher' and note.teacher and note.teacher.user == request.user:
                        is_own_note = True
                    elif uploader_type == 'student' and note.uploaded_by_student and note.uploaded_by_student.user == request.user:
                        is_own_note = True
                    
                    all_notes.append({
                        'id': note.id,
                        'teacher': uploader_name,  # Keep for backward compatibility
                        'uploader_type': uploader_type,
                        'uploader_name': uploader_name,
                        'is_own_note': is_own_note,  # New field to indicate if current user uploaded this note
                        'uploaded_at': note.uploaded_at.strftime('%Y-%m-%d %H:%M') if note.uploaded_at else '',
                        'name': note.name or '',
                        'text': note.text,
                        'file_url': note.file.url if note.file else None,
                        'file_name': note.file.name.split('/')[-1] if note.file else None,
                        'class_name': class_obj.name,  # Include class name for display
                    })
            
            # Sort all notes by uploaded_at descending
            all_notes.sort(key=lambda x: x['uploaded_at'], reverse=True)
            
            return JsonResponse({'status': 'success', 'notes': all_notes})
            
        except TeacherAccount.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def debug_student_status_view(request):
    """Debug endpoint to check student's current status"""
    if request.method == 'GET':
        try:
            # Check if user is a student
            try:
                student_account = StudentAccount.objects.get(user=request.user)
            except StudentAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Not a student account'}, status=400)
            
            # Get all classes the student is associated with
            joined_classes = student_account.classes.all()
            
            # Get all classes in the system
            all_classes = Class.objects.all()
            
            debug_info = {
                'student_username': request.user.username,
                'student_account_id': student_account.id,
                'joined_classes_count': joined_classes.count(),
                'joined_classes': [{'name': c.name, 'id': c.id} for c in joined_classes],
                'total_classes_in_system': all_classes.count(),
                'all_classes': [{'name': c.name, 'id': c.id, 'students_count': c.students.count()} for c in all_classes],
            }
            
            return JsonResponse({'status': 'success', 'debug_info': debug_info})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def clear_student_relationships_view(request):
    """Clear all student-class relationships for debugging"""
    if request.method == 'POST':
        try:
            # Check if user is a student
            try:
                student_account = StudentAccount.objects.get(user=request.user)
            except StudentAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Not a student account'}, status=400)
            
            # Clear all relationships
            student_account.classes.clear()
            
            return JsonResponse({'status': 'success', 'message': 'All class relationships cleared. You will need to rejoin classes.'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def upload_profile_photo_view(request):
    """Upload profile photo for student account"""
    if request.method == 'POST':
        try:
            # Check if user has a student account
            try:
                student_account = StudentAccount.objects.get(user=request.user)
            except StudentAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Student account not found.'}, status=400)
            
            # Check if file was uploaded
            if 'profile_photo' not in request.FILES:
                return JsonResponse({'status': 'error', 'message': 'No file uploaded.'}, status=400)
            
            uploaded_file = request.FILES['profile_photo']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if uploaded_file.content_type not in allowed_types:
                return JsonResponse({'status': 'error', 'message': 'Invalid file type. Please upload an image (JPEG, PNG, or GIF).'}, status=400)
            
            # Validate file size (max 5MB)
            if uploaded_file.size > 5 * 1024 * 1024:
                return JsonResponse({'status': 'error', 'message': 'File too large. Please upload an image smaller than 5MB.'}, status=400)
            
            # Create media directory if it doesn't exist
            media_dir = os.path.join(settings.MEDIA_ROOT, 'profile_photos')
            os.makedirs(media_dir, exist_ok=True)
            
            # Save the file with a unique name
            file_extension = os.path.splitext(uploaded_file.name)[1]
            unique_filename = f"{request.user.username}_{uuid.uuid4().hex}{file_extension}"
            file_path = f'profile_photos/{unique_filename}'
            
            saved_path = default_storage.save(file_path, uploaded_file)
            
            # Update the student account
            student_account.profile_photo = saved_path
            student_account.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Profile photo uploaded successfully.',
                'photo_url': student_account.profile_photo.url
            })
            
        except Exception as e:
            import traceback
            print(f"Profile photo upload error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def test_upload_view(request):
    """Simple test endpoint to verify upload functionality"""
    if request.method == 'POST':
        try:
            print("Test upload endpoint called")
            print("Files received:", request.FILES)
            print("POST data received:", request.POST)
            return JsonResponse({'status': 'success', 'message': 'Test upload endpoint working'})
        except Exception as e:
            print(f"Test upload error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'GET not allowed'}, status=405)

@login_required
def student_attendance_view(request):
    try:
        student_account = StudentAccount.objects.get(user=request.user)
        joined_classes = list(student_account.classes.all())
        joined_class = joined_classes[0] if joined_classes else None
        profile_photo_url = student_account.profile_photo.url if student_account.profile_photo else None
    except StudentAccount.DoesNotExist:
        joined_class = None
        profile_photo_url = None
    return render(request, "student_attendance.html", {
        "joined_class": joined_class,
        "profile_photo_url": profile_photo_url
    })

@login_required
def leave_class_view(request):
    if request.method == 'POST':
        try:
            student_account = StudentAccount.objects.get(user=request.user)
            joined_classes = list(student_account.classes.all())
            if not joined_classes:
                return JsonResponse({'status': 'error', 'message': 'You are not in any class.'}, status=400)
            class_obj = joined_classes[0]
            class_obj.students.remove(student_account)
            return JsonResponse({'status': 'success', 'message': f'You have left {class_obj.name}.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def request_attendance_view(request):
    """Student requests attendance for their joined class (present or absent)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            requested_status = data.get('requested_status', 'present')
            # Check if user has a student account
            try:
                student_account = StudentAccount.objects.get(user=request.user)
            except StudentAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Student account not found.'}, status=400)
            # Get the student's joined class
            joined_classes = list(student_account.classes.all())
            if not joined_classes:
                return JsonResponse({'status': 'error', 'message': 'You have not joined any class yet.'}, status=400)
            class_obj = joined_classes[0]
            # Check if there's already a pending request
            existing_request = AttendanceRequest.objects.filter(
                student=student_account,
                class_obj=class_obj,
                is_processed=False
            ).first()
            if existing_request:
                return JsonResponse({'status': 'error', 'message': 'You already have a pending attendance request.'}, status=400)
            # Check if attendance already marked for today
            today = date.today()
            existing_attendance = Attendance.objects.filter(
                student=student_account,
                class_obj=class_obj,
                date=today
            ).first()
            if existing_attendance:
                return JsonResponse({'status': 'error', 'message': 'Attendance already marked for today.'}, status=400)
            # Create attendance request with requested_status
            attendance_request = AttendanceRequest.objects.create(
                student=student_account,
                class_obj=class_obj,
                requested_status=requested_status
            )
            return JsonResponse({
                'status': 'success', 
                'message': f'Attendance request ({requested_status}) sent to teachers of {class_obj.name}.'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def get_attendance_requests_view(request):
    """Get pending attendance requests for classes the teacher teaches"""
    if request.method == 'GET':
        try:
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=400)
            
            # Get all classes the teacher teaches
            teacher_classes = teacher_account.classes.all()
            
            # Get pending attendance requests for these classes
            pending_requests = AttendanceRequest.objects.filter(
                class_obj__in=teacher_classes,
                is_processed=False
            ).select_related('student__user', 'class_obj').order_by('-requested_at')
            
            requests_data = []
            for req in pending_requests:
                requests_data.append({
                    'id': req.id,
                    'student_name': req.student.user.username,
                    'class_name': req.class_obj.name,
                    'requested_at': req.requested_at.strftime('%Y-%m-%d %H:%M'),
                    'student_id': req.student.id,
                    'class_id': req.class_obj.id
                })
            
            return JsonResponse({'status': 'success', 'requests': requests_data})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def mark_attendance_view(request):
    """Teacher marks students as present or absent (batch support)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            attendance_list = data.get('attendance')
            if not isinstance(attendance_list, list):
                return JsonResponse({'status': 'error', 'message': 'Invalid data format.'}, status=400)
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=400)
            # Get the teacher's joined class
            joined_classes = list(teacher_account.classes.all())
            if not joined_classes:
                return JsonResponse({'status': 'error', 'message': 'You have not joined any class yet.'}, status=400)
            class_obj = joined_classes[0]
            today = date.today()
            results = []
            for entry in attendance_list:
                student_id = entry.get('student_id')
                status = entry.get('status')
                if status not in ['present', 'absent']:
                    results.append({'student_id': student_id, 'result': 'Invalid status'})
                    continue
                try:
                    student = StudentAccount.objects.get(id=student_id)
                except StudentAccount.DoesNotExist:
                    results.append({'student_id': student_id, 'result': 'Student not found'})
                    continue
                # Always update or create attendance for today
                attendance, created = Attendance.objects.get_or_create(
                    student=student,
                    class_obj=class_obj,
                    date=today,
                    defaults={'teacher': teacher_account, 'status': status}
                )
                if not created:
                    attendance.status = status
                    attendance.teacher = teacher_account
                    attendance.save()
                    results.append({'student_id': student_id, 'result': 'Updated to ' + status})
                else:
                    results.append({'student_id': student_id, 'result': 'Marked as ' + status})
            return JsonResponse({'status': 'success', 'message': 'Attendance saved.', 'results': results})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def teacher_upload_profile_photo_view(request):
    """Upload profile photo for teacher account"""
    if request.method == 'POST':
        try:
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=400)
            
            # Check if file was uploaded
            if 'profile_photo' not in request.FILES:
                return JsonResponse({'status': 'error', 'message': 'No file uploaded.'}, status=400)
            
            uploaded_file = request.FILES['profile_photo']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if uploaded_file.content_type not in allowed_types:
                return JsonResponse({'status': 'error', 'message': 'Invalid file type. Please upload an image (JPEG, PNG, or GIF).'}, status=400)
            
            # Validate file size (max 5MB)
            if uploaded_file.size > 5 * 1024 * 1024:
                return JsonResponse({'status': 'error', 'message': 'File too large. Please upload an image smaller than 5MB.'}, status=400)
            
            # Create media directory if it doesn't exist
            media_dir = os.path.join(settings.MEDIA_ROOT, 'profile_photos')
            os.makedirs(media_dir, exist_ok=True)
            
            # Save the file with a unique name
            file_extension = os.path.splitext(uploaded_file.name)[1]
            unique_filename = f"{request.user.username}_{uuid.uuid4().hex}{file_extension}"
            file_path = f'profile_photos/{unique_filename}'
            
            saved_path = default_storage.save(file_path, uploaded_file)
            
            # Update the teacher account
            teacher_account.profile_photo = saved_path
            teacher_account.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Profile photo uploaded successfully.',
                'photo_url': teacher_account.profile_photo.url
            })
            
        except Exception as e:
            import traceback
            print(f"Teacher profile photo upload error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def teacher_leave_class_view(request):
    """Teacher leaves a class they have joined"""
    if request.method == 'POST':
        try:
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=400)
            
            # Get the teacher's joined classes
            joined_classes = list(teacher_account.classes.all())
            if not joined_classes:
                return JsonResponse({'status': 'error', 'message': 'You are not in any class.'}, status=400)
            
            class_obj = joined_classes[0]
            class_name = class_obj.name
            
            # Remove teacher from class
            class_obj.teachers.remove(teacher_account)
            
            return JsonResponse({
                'status': 'success', 
                'message': f'You have left {class_name}.'
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def teacher_notes_page_view(request):
    """Teacher notes page view"""
    try:
        teacher_account = TeacherAccount.objects.get(user=request.user)
        teacher_profile_photo = teacher_account.profile_photo.url if teacher_account.profile_photo else None
    except TeacherAccount.DoesNotExist:
        teacher_profile_photo = None
    return render(request, 'teacher_notes.html', {
        'teacher_profile_photo': teacher_profile_photo,
        'active_page': 'notes',
    })

@login_required
def notify_absent_view(request):
    """Student notifies teacher they are absent today"""
    if request.method == 'POST':
        try:
            import json
            from datetime import date
            # Check if user has a student account
            try:
                student_account = StudentAccount.objects.get(user=request.user)
            except StudentAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Student account not found.'}, status=400)
            # Get the student's joined class
            joined_classes = list(student_account.classes.all())
            if not joined_classes:
                return JsonResponse({'status': 'error', 'message': 'You have not joined any class yet.'}, status=400)
            class_obj = joined_classes[0]
            # Get a teacher for the class (first one)
            teacher = class_obj.teachers.first()
            if not teacher:
                return JsonResponse({'status': 'error', 'message': 'No teacher found for your class.'}, status=400)
            # Check if attendance already marked for today
            today = date.today()
            existing_attendance = Attendance.objects.filter(
                student=student_account,
                class_obj=class_obj,
                date=today
            ).first()
            if existing_attendance:
                return JsonResponse({'status': 'error', 'message': 'Attendance already marked for today.'}, status=400)
            # Mark as absent
            Attendance.objects.create(
                student=student_account,
                class_obj=class_obj,
                teacher=teacher,
                status='absent'
            )
            return JsonResponse({'status': 'success', 'message': f'Your absence has been notified to the teacher of {class_obj.name}.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def teacher_attendance_view(request):
    try:
        teacher_account = TeacherAccount.objects.get(user=request.user)
        joined_classes = list(teacher_account.classes.all())
        class_obj = joined_classes[0] if joined_classes else None
        students = class_obj.students.all() if class_obj else []
    except TeacherAccount.DoesNotExist:
        class_obj = None
        students = []
    return render(request, "teacher_attendance.html", {
        "class_obj": class_obj,
        "students": students,
        "active_page": "attendance"
    })

@login_required
def get_attendance_for_today_view(request):
    """Return all attendance for the teacher's class as JSON (history)"""
    try:
        teacher_account = TeacherAccount.objects.get(user=request.user)
        joined_classes = list(teacher_account.classes.all())
        if not joined_classes:
            return JsonResponse({'status': 'error', 'message': 'No class found.'}, status=400)
        class_obj = joined_classes[0]
        records = Attendance.objects.filter(class_obj=class_obj).order_by('-date','-marked_at')
        attendance = [
            {
                'student_name': a.student.user.username,
                'status': a.status,
                'date': a.date.strftime('%Y-%m-%d'),
                'marked_at': a.marked_at.strftime('%Y-%m-%d %H:%M')
            } for a in records
        ]
        return JsonResponse({'status': 'success', 'attendance': attendance})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_pending_attendance_requests_view(request):
    """Return all pending attendance requests for the teacher's class"""
    try:
        teacher_account = TeacherAccount.objects.get(user=request.user)
        joined_classes = list(teacher_account.classes.all())
        if not joined_classes:
            return JsonResponse({'status': 'error', 'message': 'No class found.'}, status=400)
        class_obj = joined_classes[0]
        requests = AttendanceRequest.objects.filter(class_obj=class_obj, is_processed=False).select_related('student__user').order_by('requested_at')
        data = [
            {
                'id': req.id,
                'student_name': req.student.user.username,
                'requested_status': req.requested_status,
                'requested_at': req.requested_at.strftime('%Y-%m-%d %H:%M')
            } for req in requests
        ]
        return JsonResponse({'status': 'success', 'requests': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def approve_attendance_request_view(request):
    """Teacher approves a pending attendance request (present/absent)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            request_id = data.get('request_id')
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=400)
            # Get the attendance request
            try:
                attendance_request = AttendanceRequest.objects.get(id=request_id, is_processed=False)
            except AttendanceRequest.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Attendance request not found or already processed.'}, status=400)
            # Mark attendance for today
            today = date.today()
            student = attendance_request.student
            class_obj = attendance_request.class_obj
            status = attendance_request.requested_status
            # Update or create attendance
            attendance, created = Attendance.objects.get_or_create(
                student=student,
                class_obj=class_obj,
                date=today,
                defaults={'teacher': teacher_account, 'status': status}
            )
            if not created:
                attendance.status = status
                attendance.teacher = teacher_account
                attendance.save()
            attendance_request.is_processed = True
            attendance_request.save()
            # Delete any other pending requests for this student for today
            AttendanceRequest.objects.filter(
                student=student,
                class_obj=class_obj,
                is_processed=False
            ).delete()
            return JsonResponse({'status': 'success', 'message': f'Attendance marked as {status} for {student.user.username}.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def student_attendance_history_view(request):
    """Return all attendance records for the logged-in student in their class as JSON"""
    try:
        student_account = StudentAccount.objects.get(user=request.user)
        joined_classes = list(student_account.classes.all())
        if not joined_classes:
            return JsonResponse({'status': 'error', 'message': 'No class found.'}, status=400)
        class_obj = joined_classes[0]
        records = Attendance.objects.filter(student=student_account, class_obj=class_obj).order_by('-date','-marked_at')
        attendance = [
            {
                'status': a.status,
                'date': a.date.strftime('%Y-%m-%d'),
                'marked_at': a.marked_at.strftime('%Y-%m-%d %H:%M')
            } for a in records
        ]
        return JsonResponse({'status': 'success', 'attendance': attendance})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def student_upload_note_view(request):
    """Allow students to upload notes to their class (text, PDF, PNG, JPG, or both)"""
    if request.method == 'POST':
        try:
            student_account = StudentAccount.objects.get(user=request.user)
            joined_classes = list(student_account.classes.all())
            if not joined_classes:
                return JsonResponse({'status': 'error', 'message': 'You have not joined any class yet.'}, status=400)
            class_obj = joined_classes[0]
            note_text = request.POST.get('note_text', '').strip()
            note_file = request.FILES.get('note_file')
            if not note_text and not note_file:
                return JsonResponse({'status': 'error', 'message': 'Please provide a file or type a note.'}, status=400)
            saved_path = None
            file_name = None
            if note_file:
                allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
                if note_file.content_type not in allowed_types:
                    return JsonResponse({'status': 'error', 'message': 'Invalid file type. Please upload a PDF or image.'}, status=400)
                if note_file.size > 10 * 1024 * 1024:
                    return JsonResponse({'status': 'error', 'message': 'File too large. Max 10MB.'}, status=400)
                ext = note_file.name.split('.')[-1]
                filename = f"{student_account.user.username}_{class_obj.id}_{uuid.uuid4().hex}.{ext}"
                file_path = f"notes/{filename}"
                saved_path = default_storage.save(file_path, note_file)
                file_name = note_file.name
            # Set note name
            note_name = file_name or (note_text[:40] + ("..." if len(note_text) > 40 else "")) or "Text Note"
            Note.objects.create(
                class_obj=class_obj,
                uploaded_by_student=student_account,
                file=saved_path,
                name=note_name,
                text=note_text if note_text else None
            )
            return JsonResponse({'status': 'success', 'message': 'Note uploaded successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def delete_note_view(request):
    """Delete a note with proper permissions - users can only delete their own notes"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            note_id = data.get('note_id')
            delete_type = data.get('delete_type', 'delete_for_everyone')  # 'delete_for_everyone' or 'delete_for_me'
            
            if not note_id:
                return JsonResponse({'status': 'error', 'message': 'Note ID is required.'}, status=400)
            
            # Get the note
            try:
                note = Note.objects.get(id=note_id)
            except Note.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Note not found.'}, status=404)
            
            # Check if user is a student
            try:
                student_account = StudentAccount.objects.get(user=request.user)
                is_student = True
            except StudentAccount.DoesNotExist:
                is_student = False
            
            # Check if user is a teacher
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
                is_teacher = True
            except TeacherAccount.DoesNotExist:
                is_teacher = False
            
            if not is_student and not is_teacher:
                return JsonResponse({'status': 'error', 'message': 'Access denied.'}, status=403)
            
            note_name = note.name or 'Note'
            
            if delete_type == 'delete_for_everyone':
                # Check permissions - users can only delete their own notes completely
                can_delete = False
                
                if is_student:
                    # Student can only delete their own notes completely
                    if note.uploaded_by_student and note.uploaded_by_student.user == request.user:
                        can_delete = True
                
                elif is_teacher:
                    # Teacher can only delete their own notes completely
                    if note.teacher and note.teacher.user == request.user:
                        can_delete = True
                
                if not can_delete:
                    return JsonResponse({'status': 'error', 'message': 'You can only delete your own notes completely.'}, status=403)
                
                # Delete the note completely
                note.delete()
                return JsonResponse({'status': 'success', 'message': f'Note "{note_name}" deleted for everyone.'})
            
            elif delete_type == 'delete_for_me':
                # Any user can hide a note from their view
                from .models import HiddenNote
                
                # Create or get the hidden note record
                hidden_note, created = HiddenNote.objects.get_or_create(
                    note=note,
                    user=request.user
                )
                
                if created:
                    return JsonResponse({'status': 'success', 'message': f'Note "{note_name}" hidden from your view.'})
                else:
                    return JsonResponse({'status': 'success', 'message': f'Note "{note_name}" is already hidden from your view.'})
            
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid delete type.'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
@require_POST
def ai_chat(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        user = request.user if request.user.is_authenticated else None
        if not user_message:
            return JsonResponse({'error': 'No message provided.'}, status=400)

        # Simple intent detection for reminders (expanded)
        if user and any(kw in user_message.lower() for kw in ["remind me", "set a reminder", "add a reminder", "make a reminder"]):
            import re
            match = re.search(r'(remind me to|set a reminder to|add a reminder to|make a reminder to)? ?(.+?) (at|on|by|for) (.+)', user_message, re.IGNORECASE)
            if match:
                reminder_text = match.group(2).strip()
                time_str = match.group(4).strip()
                try:
                    remind_at = date_parser.parse(time_str, fuzzy=True, default=timezone.now())
                    Reminder.objects.create(user=user, text=reminder_text, remind_at=remind_at)
                    return JsonResponse({'reply': f'Reminder set: "{reminder_text}" at {remind_at.strftime("%Y-%m-%d %H:%M")}'})
                except Exception as e:
                    return JsonResponse({'reply': f'Could not parse the reminder time. Please try again. ({str(e)})'})
            else:
                return JsonResponse({'reply': 'Please specify what and when to remind you. For example: "Remind me to submit my homework at 5pm".'})

        # Otherwise, use the agent as before
        result = agent.run(user_message)
        return JsonResponse({'reply': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def delete_reminder(request, reminder_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    reminder.delete()
    return JsonResponse({'status': 'success', 'message': 'Reminder deleted.'})

@csrf_exempt
@require_POST
def edit_reminder(request, reminder_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    data = json.loads(request.body)
    new_text = data.get('text')
    new_time = data.get('remind_at')
    if new_text:
        reminder.text = new_text
    if new_time:
        try:
            reminder.remind_at = date_parser.parse(new_time, fuzzy=True, default=timezone.now())
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Invalid date/time format.'}, status=400)
    reminder.save()
    return JsonResponse({'status': 'success', 'message': 'Reminder updated.'})