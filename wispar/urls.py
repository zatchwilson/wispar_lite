from library import views
"""
URL configuration for wispar project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.urls import re_path as url

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index),
    path('login/', views.login_form),
    path("profile/login/", views.login_form),
    path("profile/logout/", views.logout_form),
    path("profile/register/", views.register),
    path("profile/register/toggle/", views.toggle_registrations),
    path("player/<int:book_id>/", views.player),
    path("library/", views.library),
    path("personal/", views.personal),
    path("personal/theme", views.theme),
    path("personal/homepage", views.homepage),
    path("personal/radius", views.radius),
    path("personal/uifont", views.ui_font),
    path("users/", views.users),
    path("content/", views.content),
    path('books/cover/<int:bookId>', views.show_cover),
    path('books/cover/<int:bookId>/options', views.get_covers),
    path('books/ebooks/<str:filename>/', views.serve_epub),
    path('books/audiobooks/<str:filename>/', views.serve_audiobook),
    path('books/vtt/<str:filename>/', views.serve_vtt),
    path('books/json/<str:filename>/', views.serve_cfi_json),
    path('books/progress/<int:book_id>/', views.update_last_read_progress),
    path('books/bookmarks/<int:book_id>/', views.new_bookmark),
    path('books/locations/<int:book_id>/', views.save_locations_json),
    path('library/search/', views.search_library),
    url('', include('pwa.urls')),  # You MUST use an empty string as the URL prefix,
    path("personal/epubDefault", views.custom_epub_default),
    path('define/<str:word>', views.define, name='define'),
    path('downloader/', views.download_books),
    path('books/delete-bookmark/<int:book_id>/', views.delete_bookmark),
    path('audio/<path:filename>/', views.stream_audio, name='stream_audio'),
]
