from django.urls import path
from . import views
from .views import ai_chat, delete_reminder, edit_reminder


app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("community/", views.community_view, name="community"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("student/dashboard/", views.student_dashboard_view, name="student_dashboard"),
    path("student/notes/", views.student_notes_page_view, name="student_notes_page"),
    path("student/get_notes/", views.get_student_notes_view, name="get_student_notes"),
    path("student/debug/", views.debug_student_status_view, name="debug_student_status"),
    path("student/clear_relationships/", views.clear_student_relationships_view, name="clear_student_relationships"),
    path("student/upload_profile_photo/", views.upload_profile_photo_view, name="upload_profile_photo"),
    path("student/test_upload/", views.test_upload_view, name="test_upload"),
    path("student/attendance/", views.student_attendance_view, name="student_attendance"),
    path("student/request_attendance/", views.request_attendance_view, name="request_attendance"),
    path("student/leave_class/", views.leave_class_view, name="leave_class"),
    path("teacher/dashboard/", views.teacher_dashboard_view, name="teacher_dashboard"),
    path("teacher/notes/", views.teacher_notes_page_view, name="teacher_notes_page"),
    path("teacher/get_notes/", views.get_teacher_notes_view, name="get_teacher_notes"),
    path("teacher/create_class/", views.create_class_view, name="create_class"),
    path("teacher/get_classes/", views.get_teacher_classes_view, name="get_teacher_classes"),
    path("teacher/join_class/", views.teacher_join_class_view, name="teacher_join_class"),
    path("teacher/upload_note/", views.teacher_upload_note_view, name="teacher_upload_note"),
    path("teacher/delete_note/", views.delete_note_view, name="teacher_delete_note"),
    path("teacher/get_attendance_requests/", views.get_attendance_requests_view, name="get_attendance_requests"),
    path("teacher/mark_attendance/", views.mark_attendance_view, name="mark_attendance"),
    path("teacher/upload_profile_photo/", views.teacher_upload_profile_photo_view, name="teacher_upload_profile_photo"),
    path("teacher/leave_class/", views.teacher_leave_class_view, name="teacher_leave_class"),
    path("class/get_notes/", views.get_class_notes_view, name="get_class_notes"),
    path("student/join_class/", views.join_class_view, name="join_class"),
    path("student/get_classes/", views.get_student_classes_view, name="get_student_classes"),
    path("delete_account/", views.delete_account_view, name="delete_account"),
    path("logout/", views.logout_view, name="logout"),
    path("user-type-selection/", views.user_type_selection_view, name="user_type_selection"),
    path("set-user-type/", views.set_user_type_view, name="set_user_type"),
    path("student/notify_absent/", views.notify_absent_view, name="notify_absent"),
    path("teacher/attendance/", views.teacher_attendance_view, name="teacher_attendance"),
    path("teacher/get_attendance_for_today/", views.get_attendance_for_today_view, name="get_attendance_for_today"),
    path("teacher/pending_attendance_requests/", views.get_pending_attendance_requests_view, name="pending_attendance_requests"),
    path("teacher/approve_attendance_request/", views.approve_attendance_request_view, name="approve_attendance_request"),
    path("student/attendance_history/", views.student_attendance_history_view, name="student_attendance_history"),
    path("student/upload_note/", views.student_upload_note_view, name="student_upload_note"),
    path("student/delete_note/", views.delete_note_view, name="delete_note"),
    path("student/get_notes/", views.get_student_notes_view, name="student_get_notes"),
]

urlpatterns += [
    path('api/ai-chat/', ai_chat, name='ai_chat'),
    path('reminders/delete/<int:reminder_id>/', delete_reminder, name='delete_reminder'),
    path('reminders/edit/<int:reminder_id>/', edit_reminder, name='edit_reminder'),
]