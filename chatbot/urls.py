from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot_view, name='chatbot_view'),
    path('new/', views.new_chat, name='chatbot_new_chat'),
    path('delete-all/', views.delete_all_chats, name='chatbot_delete_all'),
    path('sessions/', views.list_sessions, name='chatbot_sessions'),
    path('session/<int:session_id>/', views.get_session, name='chatbot_get_session'),
    path('session/<int:session_id>/rename/', views.rename_session, name='chatbot_rename_session'),
    path('session/<int:session_id>/delete/', views.delete_session, name='chatbot_delete_session'),
    path('session/<int:session_id>/export/txt/', views.export_chat, {'format': 'txt'}, name='chatbot_export_txt'),
    path('session/<int:session_id>/export/md/', views.export_chat, {'format': 'md'}, name='chatbot_export_md'),
    path('regenerate/', views.regenerate_response, name='chatbot_regenerate'),
    path('feedback/', views.submit_feedback, name='chatbot_feedback'),
]
