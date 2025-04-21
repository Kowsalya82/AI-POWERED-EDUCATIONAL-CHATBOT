from django.contrib import admin
from django.urls import path
from chatbot import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('chat/',views.chat,name='chat'),
    path('home/', views.home, name='home'),
    path('chat/', views.chat, name='chat'), # Combined chat & history page
    path('link/', views.fetch_links_view, name='fetch_links'),
    path('logout/', views.logout_view, name='logout'),
    path('videos/', views.pdfs_view, name='videos'),
    path('get_history/', views.get_history, name='get_history'),
    path('pdf_summary/', views.pdf_summary_view, name='pdf_summary'),
    path('pdfs/', views.pdfs_view, name='pdfs_view'),  # Handles upload & delete
    path('history/', views.get_history, name='get_history'),  # Fetch history
    path('export-history/', views.save_history_to_excel, name='export_history'),  # Export to Excel

    path('save-history/', views.save_history_to_excel, name='save_history'), #changed the name to match the views function.
    path('save-upload/', views.save_uploads_metadata_to_db, name='save_upload'), #changed the name to match the views function.

    path('', views.pdfs_view, name='pdfs_view'),
    path('download-pdf/<str:filename>/', views.force_download, name='force_download'),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
