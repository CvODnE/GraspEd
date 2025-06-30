from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from .models import StudentAccount, TeacherAccount, Class, Note, AttendanceRequest, Attendance
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
    return render(request, "student_dashboard.html", {"profile_photo_url": profile_photo_url})

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
        note = Note.objects.create(class_obj=class_obj, teacher=teacher_account, text=note_text)
        if note_file:
            note.file.save(note_file.name, note_file)
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
    notes = class_obj.notes.order_by('-created_at')
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
    return render(request, 'students_notes.html')

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
                
                # Get notes for this class
                notes = class_obj.notes.order_by('-created_at')
                for note in notes:
                    all_notes.append({
                        'id': note.id,
                        'teacher': note.teacher.user.username,
                        'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
                        'text': note.text,
                        'file_url': note.file.url if note.file else None,
                        'file_name': note.file.name.split('/')[-1] if note.file else None,
                        'class_name': class_obj.name,  # Include class name for display
                    })
            
            # Sort all notes by created_at descending
            all_notes.sort(key=lambda x: x['created_at'], reverse=True)
            
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
            joined_classes = teacher_account.class_set.all()
            
            all_notes = []
            for class_obj in joined_classes:
                # Get notes for this class
                notes = class_obj.notes.order_by('-created_at')
                for note in notes:
                    all_notes.append({
                        'id': note.id,
                        'teacher': note.teacher.user.username,
                        'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
                        'text': note.text,
                        'file_url': note.file.url if note.file else None,
                        'file_name': note.file.name.split('/')[-1] if note.file else None,
                        'class_name': class_obj.name,  # Include class name for display
                    })
            
            # Sort all notes by created_at descending
            all_notes.sort(key=lambda x: x['created_at'], reverse=True)
            
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
    """Student requests attendance for their joined class"""
    if request.method == 'POST':
        try:
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
            
            # Create attendance request
            attendance_request = AttendanceRequest.objects.create(
                student=student_account,
                class_obj=class_obj
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Attendance request sent to teachers of {class_obj.name}.'
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
    """Teacher marks a student as present or absent"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            request_id = data.get('request_id')
            status = data.get('status')  # 'present' or 'absent'
            
            # Validate status
            if status not in ['present', 'absent']:
                return JsonResponse({'status': 'error', 'message': 'Invalid status. Must be present or absent.'}, status=400)
            
            # Check if user has a teacher account
            try:
                teacher_account = TeacherAccount.objects.get(user=request.user)
            except TeacherAccount.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Teacher account not found.'}, status=400)
            
            # Get the attendance request
            try:
                attendance_request = AttendanceRequest.objects.get(id=request_id)
            except AttendanceRequest.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Attendance request not found.'}, status=400)
            
            # Check if teacher teaches this class
            if not teacher_account.classes.filter(id=attendance_request.class_obj.id).exists():
                return JsonResponse({'status': 'error', 'message': 'You do not teach this class.'}, status=400)
            
            # Check if request is already processed
            if attendance_request.is_processed:
                return JsonResponse({'status': 'error', 'message': 'This attendance request has already been processed.'}, status=400)
            
            # Check if attendance already marked for today
            today = date.today()
            existing_attendance = Attendance.objects.filter(
                student=attendance_request.student,
                class_obj=attendance_request.class_obj,
                date=today
            ).first()
            
            if existing_attendance:
                return JsonResponse({'status': 'error', 'message': 'Attendance already marked for this student today.'}, status=400)
            
            # Create attendance record
            attendance = Attendance.objects.create(
                student=attendance_request.student,
                class_obj=attendance_request.class_obj,
                teacher=teacher_account,
                status=status
            )
            
            # Mark request as processed
            attendance_request.is_processed = True
            attendance_request.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Marked {attendance_request.student.user.username} as {status}.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
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