from django.contrib.auth.models import User, Group, AnonymousUser
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme, http_date
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest, HttpResponse, Http404, JsonResponse, StreamingHttpResponse, FileResponse
from django.views.decorators.http import require_GET
from .forms import UploadFileForm
from wispar import models
from wispar.settings import MEDIA_ROOT
from library.controller import cache_online_cover_locally, upload_and_save_book, delete_book, update_theme, get_cover, get_cover_options, \
      update_or_create_last_read_bookmark, update_homescreen, get_books_with_progress_percentage, convert_last_read_at_to_hours, check_user_permissions, \
      get_groups_and_group_permissions, create_new_perms_role, delete_perms_role, edit_perms_role, edit_user_roles, get_users_and_groups, \
      can_access_content_page, can_access_permissions_page, determine_row_order, delete_user, can_access_book
from django.contrib.auth.decorators import login_required
from ebooklib import epub
from django.core.files.storage import default_storage
from mutagen.mp4 import MP4
import requests
from io import BytesIO
from PIL import Image
import os
import json
from math import floor
from django.core.exceptions import PermissionDenied
from threading import Lock

lock = Lock()

# Create your views here.
@login_required
def index(request):

    user = request.user

    books = get_books_with_progress_percentage(user)
    convert_last_read_at_to_hours(books)
 
    # Get the most recent reads (keeping original added order)
    recently_read = books[:100]
    # Reverse the order of recently added books (Show last added first)
    recently_added = books.order_by('-id')[:100]

    convert_last_read_at_to_hours(recently_added)  

    recent_release = books.order_by('-publication_date')[:100]
    convert_last_read_at_to_hours(recent_release)


    context = {
        'library': books,
        'library_visible' : False,
        'title': 'Wisparr',
        'ui_font': determine_font(request.user),
        'user_perms': check_user_permissions(user),
        'rounded_corners': determine_corners(user),
        'row_one' : None,
        'row_two' : None,
        'row_three' : None,
        'row_one_title' : "",
        'row_two_title' : "",
        'row_three_title' : "",
        'row_one_visible' : False,
        'row_two_visible' : False,
        'row_three_visible' : False,
        'row_order' : "",
    }
    
    context = determine_row_order(context, user, recently_read, recently_added, recent_release)
    return render(request, 'index.html', context)

@login_required
def radius(request):
    corner_style = request.POST.get('radius')
        # Retrieve or create the PersonalSettings instance for the user
    user_settings, created = models.PersonalSettings.objects.get_or_create(user=request.user)

    #print(f'corner style: {corner_style}')
    if corner_style == 'square':
        # Update the visibility settings
        user_settings.curved_radius = False
        # Save the changes to the database
        user_settings.save()
        #print('Square Corners!')
    else:
        # Update the visibility settings
        user_settings.curved_radius = True
        # Save the changes to the database
        user_settings.save()
        #print('Rounded Corners')

    return HttpResponse("Changed radius!", status=200) 

def determine_corners(user):
    user_settings = None
    try:
        user_settings = models.PersonalSettings.objects.get_or_create(user=user)
        return user_settings[0].curved_radius
    except Exception as e:
        # Log error but still return the template
        print(f'Error fetching user settings: {str(e)}')
        # Set default values if there's an error
        return True

def determine_epub_default(user):
    user_settings = None
    try:
        user_settings = models.PersonalSettings.objects.get_or_create(user=user)
        return user_settings[0].custom_epub_default
    except Exception as e:
        # Log error but still return the template
        print(f'Error fetching user settings: {str(e)}')
        # Set default values if there's an error
        return False

@login_required
def get_covers(request, bookId):
    return get_cover_options(bookId)

@login_required
def show_cover(request, bookId):
    return get_cover(bookId)

@login_required
def library(request):

    books = get_books_with_progress_percentage(request.user)
    convert_last_read_at_to_hours(books)
    context ={
        'library': books,
        'title': 'Library - Wisparr',
        'ui_font': determine_font(request.user),
        'user_perms': check_user_permissions(request.user),
        'rounded_corners': determine_corners(request.user),
    }
    return render(request, 'library.html', context)


@login_required
def personal(request):
    themes = ["Modern Light", "Modern Dark", "Classic Light", "Classic Dark", "Urban Fog", "Emerald Canopy", "Ocean Depths", "Twilight Bloom", "Paperwhite", 
              "Void Luminescence", "Frosted Horizon", "Sunset Marina", "Skyline Mist", "Velvet Dusk", "Meadow Breeze", "Golden Ember", "Seafoam Serenity", 
              "Desert Mirage", "Golden Harvest", "Stormy Harbor", "Charcoal Ember", "Sunlit Blush", "Autumn Fog"]
    context = {
        "themes": themes,
        'library': None,
        'library_visible' : False,
        'title': 'Profile - Wisparr',
        'ui_font': determine_font(request.user),
        'user_perms': check_user_permissions(request.user),
        'rounded_corners': determine_corners(request.user),
        'custom_epub_default': determine_epub_default(request.user),
        'row_one' : None,
        'row_two' : None,
        'row_three' : None,
        'row_one_title' : "",
        'row_two_title' : "",
        'row_three_title' : "",
        'row_one_visible' : False,
        'row_two_visible' : False,
        'row_three_visible' : False,
        'row_order' : "",
    }
    
    context = determine_row_order(context, request.user, 'recently_read', 'recently_added', 'recent_release')

    context['row_one'] = context['row_order'].split(',')[0]
    context['row_two'] = context['row_order'].split(',')[1]
    context['row_three'] = context['row_order'].split(',')[2]
    return render(request, 'personal.html', context)

@login_required
def homepage(request):
    user = request.user
    if request.method == "POST":
        print('Updating Homepage')
        if request.POST.get('row_order'):
            row_order = request.POST.get('row_order')
        else:
            print('what the fuck')
        recently_read_row = request.POST.get('recently_read')
        recently_added_row = request.POST.get('recently_added')
        recent_release_row = request.POST.get('recent_release')
        library_visible = request.POST.get('library')
        
        if recently_read_row == 'on':
            recently_read_row = True
        else:
            recently_read_row = False

        if recently_added_row == 'on':
            recently_added_row = True
        else:
            recently_added_row = False
        
        if recent_release_row == 'on':
            recent_release_row = True
        else:
            recent_release_row = False
        
        if library_visible == 'on':
            library_visible = True
        else:
            library_visible = False
        print(row_order)
        update_homescreen(recently_read_row, recently_added_row, recent_release_row, library_visible, row_order, user)
    return HttpResponse("Changed Homescreen!", status=200) 
        


@login_required
@user_passes_test(can_access_permissions_page, login_url="/", redirect_field_name=None)
def users(request):
    context = {}
    all_users = get_users_and_groups()

    groups_and_permissions = get_groups_and_group_permissions()

    context ={
        'title': 'User Settings',
        'ui_font': determine_font(request.user),
        'user_perms': check_user_permissions(request.user),
        'users': all_users,
        'groups_list': [group for group in groups_and_permissions],
        'groups_dict_json': json.dumps(groups_and_permissions),
        'registrations_are_active': models.RegistrationToggle.objects.get_or_create(id=1)[0].users_can_register
    }
    if (request.method == "GET"):
        return render(request, 'users.html', context)
    elif (request.method == "POST"):
        request_dict = request.POST
        try:
            if('new-role-button' in request_dict):
                create_new_perms_role(request_dict)
            elif('delete-button' in request_dict):
                delete_perms_role(request_dict)
            elif('edit-role-button' in request_dict):
                edit_perms_role(request_dict)
            elif('change-roles-button' in request_dict):
                edit_user_roles(request_dict)
            elif('delete-user-button' in request_dict):
                err_str = delete_user(request.user, request_dict)
                if err_str:
                    context['error_message'] = err_str
                    return render(request, 'users.html', context)
            return redirect('/users/')
        except Exception as e:
            print(e)
            if 'Duplicate entry' in str(e):
                context["error_message"] = "A group with that name already exists, please try a different name."
            else:
                context["error_message"] = str(e)
            return render(request, 'users.html', context)

@login_required
@user_passes_test(can_access_content_page, login_url="/", redirect_field_name=None)
def content(request):

    books = get_books_with_progress_percentage(request.user)
    convert_last_read_at_to_hours(books)

    context ={
        'title': 'Content Settings',
        'library': books,
        'ui_font': determine_font(request.user),
        'user_perms': check_user_permissions(request.user),
        'rounded_corners': determine_corners(request.user),
    }

    if request.user.is_superuser:
        groups = Group.objects.all()
        for group in groups:
            group.banned_books = [restriction['book'] for restriction in models.ContentRestrictions.objects.filter(group_id=group.id).values("book")]
        
        context['groups'] = groups

    if request.method == "POST":
        try:
            res = handle_file_upload(request)
            return res
        except Exception as e:
            print(e)
            context["error_message"] = str(e)
            return render(request, 'content.html', context)
    elif request.method == "DELETE":
        print('Trying to delete...')
        try:
            data = json.loads(request.body)
            bookId = data.get('bookId')
            
            book_was_deleted = delete_book(bookId)

            if book_was_deleted:
                print('Success! Book deleted')
            else:
                print('Book Failed to delete!')
        except Exception as e:
            print(e)
            context["error_message"] = e
            return render(request, 'content.html', context)
    # Update Title Metadata
    elif request.method == 'PUT':
        print('Updating metadata...')
        data = json.loads(request.body)
        title = data.get('title')
        bookId = data.get('bookId')
        cover_url = data.get(f'selectedImage-{bookId}')
        cache_online_cover_locally(cover_url, bookId)
        books_to_update = models.Book.objects.filter(bookId=bookId)
        for title in books_to_update:
            if data['title']:
                title.title = data['title']
            if data['author']:
                title.author = data['author']
            if data['isbn']:
                title.isbn = data['isbn']
            if data['pub-date']:
                title.publication_date = data["pub-date"]
            if data['language']:
                title.language = data['language']  
            title.save()
            if request.user.is_superuser:
                for group in Group.objects.all():
                    if f'{group.name}-toggle' not in data:
                        models.ContentRestrictions.objects.get_or_create(book=title, group=group)
                    else:
                        existing_restrictions = models.ContentRestrictions.objects.filter(book=title, group=group)
                        if len(existing_restrictions) > 0:
                            existing_restrictions[0].delete()

    return render(request, 'content.html', context)

@login_required
def player(request, book_id):
    # Initialize variables
    curr_ebook = None
    curr_audiobook = None
    last_place_read = None
    past_bookmarks = None

    if not can_access_book(request.user, book_id) and not request.user.is_superuser:
        raise Http404
    
    # Retrieve the ebook
    curr_ebook = models.Book.objects.filter(bookId=book_id, medium='ebook').first()
    if not curr_ebook:
        print(f"No ebook found with bookId={book_id}")

    # Retrieve the audiobook
    curr_audiobook = models.Book.objects.filter(bookId=book_id, medium='audiobook').first()
    if not curr_audiobook:
        print(f"No audiobook found with bookId={book_id}")
    context = {}

    if not curr_audiobook and not curr_ebook:
        raise Http404
    # Retrieve the last place read
    last_place_read = models.TitleLocation.objects.filter(book_id=book_id, user=request.user, bookmark_type='last_read_position').first()
    if not last_place_read:
        print("No previous last place read found.")

    # Retrieve the bookmarks
    past_bookmarks = models.TitleLocation.objects.filter(book_id=book_id, user=request.user)
    print(len(past_bookmarks))
    if not past_bookmarks:
        print("No previous bookmarks.")

    # Check if both curr_ebook and curr_audiobook are retrieved
    if curr_ebook and curr_audiobook:
        audio_filepath = curr_audiobook.filefield.name
        vtt_filepath = audio_filepath.split('.')
        # Remove file extension
        vtt_filepath = ''.join(vtt_filepath[:len(vtt_filepath) - 1])
        vtt_filepath = vtt_filepath + '.vtt'
        print(f'VTT Filepath: {vtt_filepath}')
        context = {
            'vtt': vtt_filepath,
            'audiobook': curr_audiobook.filefield,
            'title': curr_ebook.title,
            'medium': curr_ebook.medium,
            'book_filepath': curr_ebook.filefield.name,
            'book_id': book_id,
            'audio_location': str(last_place_read.audio_location) if last_place_read else None, 
            #convert time to string otherwise javascript butchers it and converts 00:00:00 to midnight
            'ebook_location': last_place_read.text_location if last_place_read else None,
            'ui_font': determine_font(request.user),
            'user_perms': check_user_permissions(request.user),
            'rounded_corners': determine_corners(request.user),
            'custom_epub_default': determine_epub_default(request.user),
            'bookmarks': past_bookmarks,
            'progress_percentage': last_place_read.progress_percentage if last_place_read else None,
            'last_read_at': str(last_place_read.last_read_at) if last_place_read else None,
            'time_remaining': last_place_read.time_remaining if last_place_read else None,
        }
        return render(request, 'player.html', context)
    else:
        # Handle the case where one or both mediums are not found
        if curr_ebook:
            context = {
                'audiobook': None,
                'title': curr_ebook.title,
                'medium': curr_ebook.medium,
                'book_filepath': curr_ebook.filefield.name,
                'book_id': book_id,
                'audio_location': str(last_place_read.audio_location) if last_place_read else None, #convert time to string otherwise javascript butchers it
                'ebook_location': last_place_read.text_location if last_place_read else None,
                'ui_font': determine_font(request.user),
                'rounded_corners': determine_corners(request.user),
                'user_perms': check_user_permissions(request.user),
                'custom_epub_default': determine_epub_default(request.user),
                'bookmarks': past_bookmarks,
                'progress_percentage': last_place_read.progress_percentage if last_place_read else None,
                'last_read_at': str(last_place_read.last_read_at) if last_place_read else None,
                'time_remaining': last_place_read.time_remaining if last_place_read else None,
            }
            return render(request, 'player.html', context)
        if curr_audiobook:
            books = get_books_with_progress_percentage(request.user)
            convert_last_read_at_to_hours(books)

            context = {
                'audiobook': curr_audiobook.filefield,
                'title': curr_audiobook.title,
                'medium': curr_audiobook.medium,
                'book_filepath': None,
                'book_id': book_id,
                'audio_location': str(last_place_read.audio_location) if last_place_read else None, #convert time to string otherwise javascript butchers it
                'ebook_location': last_place_read.text_location if last_place_read else None,
                'ui_font': determine_font(request.user),
                'rounded_corners': determine_corners(request.user),
                'user_perms': check_user_permissions(request.user),
                'custom_epub_default': determine_epub_default(request.user),
                'bookmarks': past_bookmarks,
                'library': books,
                'progress_percentage': last_place_read.progress_percentage if last_place_read else None,
                'last_read_at': str(last_place_read.last_read_at) if last_place_read else None,
                'time_remaining': last_place_read.time_remaining if last_place_read else None,
            }
        missing_media = []
        if not curr_ebook:
            missing_media.append('ebook')
            context['book_filepath'] = None
        if not curr_audiobook:
            missing_media.append('audiobook')
            context['audiobook'] = None
        missing_media_str = ' and '.join(missing_media)
        return render(request, 'player.html', context)
        #return HttpResponseNotFound(f"The requested {missing_media_str} could not be found.")

@login_required
def theme(request):
    context = {
            'title': 'Personal Settings'
    }
    
    if request.method == "POST":
        try:
            # Reads from post request to change user's preferred theme
            theme = request.POST.get("wispar_theme","")
            update_theme(theme, request.user)
            return render(request, 'personal.html', context)
            
        except Exception as e:
            context["error_message"] = e
            return render(request, 'content.html', context)

def ui_font(request):
    context = {
            'title': 'Personal Settings'
    }
    
    if request.method == "POST":
        user_settings, created = models.PersonalSettings.objects.get_or_create(user=request.user)
        try:
            # Reads from post request to change user's preferred font
            font = request.POST.get("interface-font-select","")
            # Change Font
            print(font)
            user_settings.ui_font = font
            # Save the changes to the database
            user_settings.save()
            print(user_settings.ui_font)
            return render(request, 'personal.html', context)
            
        except Exception as e:
            context["error_message"] = e
            return render(request, 'content.html', context)
        
def determine_font(user):
    user_settings = None
    try:
        user_settings, created = models.PersonalSettings.objects.get_or_create(user=user)
        print(f'Saved User font is: {user_settings.ui_font}')
        return user_settings.ui_font
    except Exception as e:
        # Log error but still return the template
        print(f'Error fetching user settings: {str(e)}')
        # Set default values if there's an error
        return 'Roboto slab'

def login_form(request):
    login_error = ""
    next_url = request.GET.get('next', '/')
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            if url_has_allowed_host_and_scheme(request.POST.get('next'), None):
                return redirect(request.POST.get('next'))
            else:
                return redirect("/profile/")
        else:
            print("Cant verify User!")
            login_error = "Username and password do not match"
    context = {
        "title": 'Login - Wisparr',
        "next": next_url,
        "login_error": login_error,
        "registrations_are_active": models.RegistrationToggle.objects.get_or_create(id=1)[0].users_can_register
    }
    return render(request, "login.html", context)

def register(request):
    registrations_are_active = models.RegistrationToggle.objects.get_or_create(id=1)[0].users_can_register

    if not registrations_are_active:
        raise Http404
    
    register_error = ""

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            new_user = User.objects.create_user(username,password=password)
            basic_reader_group = Group.objects.get_or_create(name="Basic Reader")[0]
            basic_reader_group.user_set.add(new_user)
            return redirect("/login/")
        except Exception as e:
            print(f"Error creating user: {e}")
            if 'Duplicate entry' in str(e):
                register_error = "That username is already taken, please pick a different username and try again."
            else:
                register_error = e
    context = {
        "title": 'Register - Wisparr',
        "register_error": register_error
    }
    return render(request, "register.html", context)

def logout_form(request):
    logout(request)
    return redirect("/profile/login/")

@login_required
def serve_epub(request, filename): 
    # Construct the file path 
    file_path = os.path.join(MEDIA_ROOT, filename)
    if not os.path.exists(file_path): 
        return HttpResponse("File not found", status=404) 
    
    # Open the file in binary mode and return it as a response 
    with open(file_path, 'rb') as epub_file: 
        response = HttpResponse(epub_file.read(), content_type='application/epub+zip') 
        response['Content-Disposition'] = f'inline; filename="{filename}"' 
        return response

@login_required
@require_GET
def serve_audiobook(request, filename):
    file_path = os.path.join(MEDIA_ROOT, filename)
    if not os.path.exists(file_path):
        return HttpResponse("File not found", status=404)

    response = StreamingHttpResponse(open(file_path, 'rb'), content_type='audio/mpeg')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['Accept-Ranges'] = 'bytes' # Inform client that range requests are supported

    return response

@login_required
def serve_vtt(request, filename): 
    # Construct the file path 
    file_path = os.path.join(MEDIA_ROOT, filename)
    if not os.path.exists(file_path): 
        return HttpResponse("File not found", status=404) 
    
    # Open the file in binary mode and return it as a response 
    with open(file_path, 'rb') as vtt_file: 
        response = HttpResponse(vtt_file.read(), content_type='text/vtt') 
        response['Content-Disposition'] = f'inline; filename="{filename}"' 
        return response
    
@login_required
def update_last_read_progress(request, book_id):
    user = request.user

    try:
        bookmark_data = request.POST.dict()
        bookmark_data['user'] = user
        bookmark_data['book_id'] = book_id

        if update_or_create_last_read_bookmark(bookmark_data):
            return HttpResponse(status=200)
        else:
            return HttpResponse(status=500)
    except Exception as e:
        print("failed to save last position: ", e)
        return HttpResponse(status=500)

@login_required
def new_bookmark(request, book_id):
    user = request.user

    try:
        bookmark_data = request.POST.dict()
        bookmark_data['user'] = user
        bookmark_data['book_id'] = book_id

        new_last_read_bookmark = models.TitleLocation(
        audio_location = bookmark_data['audio_location'],
        text_location = bookmark_data['text_location'],
        location_text_snippet = bookmark_data['location_text_snippet'],
        user = bookmark_data['user'],
        book_id= bookmark_data['book_id'],
        bookmark_type = bookmark_data['bookmark_type'],
        progress_percentage = int(float(bookmark_data['progress_percentage']))
        )
        new_last_read_bookmark.save()

        return HttpResponse(status=200)
    except Exception as e:
        print("failed to save last position: ", e)
        return HttpResponse(status=500)

@login_required
def delete_bookmark(request, book_id):
    user = request.user
    try:
        bookmark_data = request.POST.dict()
        # Try to get the bookmark for the current user with the given book_id.
        bookmark = models.TitleLocation.objects.get(user=user, book_id=book_id, bookmark_type=bookmark_data['bookmark_type'], text_location=bookmark_data['text_location'])
        bookmark.delete()
        return HttpResponse(status=200)
    except models.TitleLocation.DoesNotExist:
        # Return 404 if no such bookmark exists.
        return HttpResponse(status=404)
    except Exception as e:
        print("Failed to remove bookmark:", e)
        return HttpResponse(status=500)


@login_required
def save_locations_json(request, book_id):
    locations_directory_filepath = os.path.join(MEDIA_ROOT, 'locations')
    if request.method == 'GET':
        filename = f"{book_id}_locations.json"
        file_path = os.path.join(locations_directory_filepath, filename)
        if not os.path.exists(file_path): 
            return HttpResponse("Locations need to be generated", status=204) 
    # Open the file in binary mode and return it as a response 
        with open(file_path, 'rb') as locations_file: 
            response = HttpResponse(locations_file.read(), content_type='text/json')
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
    if request.method == 'POST':
        try:
            locations = json.loads(request.body)
            os.makedirs(locations_directory_filepath, exist_ok=True)
            file_path = os.path.join(locations_directory_filepath, f"{book_id}_locations.json")
            with open(file_path, 'w') as json_file:
                json.dump(locations, json_file) 
            return HttpResponse(status=200)
        except Exception as e:
            print("failed to save locations json: ", e)
            return HttpResponse(status=500)
        

@login_required
def search_library(request):
    search_string = request.POST.get('search_input')
    found_books = get_books_with_progress_percentage(request.user, search_string)
    convert_last_read_at_to_hours(found_books)
    context = {
        'library': found_books,
        'is_search_query': True,
        'user_perms': check_user_permissions(request.user),
        'ui_font': determine_font(request.user),
    }

    return render(request, 'search_results.html', context)

@login_required
def add_user_group(request):
    context = {}
    try:
        if request.method == "POST":
            create_new_perms_role(request.POST)
            return redirect('/users/')
    except Exception as e:
        print(e)
        context["error_message"] = str(e)
        return render(request, 'users.html', context)
    
def custom_epub_default(request):
    custom_epub_default = request.POST.get('custom-epub-default')
    print(custom_epub_default)
    # Retrieve or create the PersonalSettings instance for the user
    user_settings, created = models.PersonalSettings.objects.get_or_create(user=request.user)

    if custom_epub_default == 'on':
        user_settings.custom_epub_default = True
        # Save the changes to the database
        user_settings.save()
    else:
        user_settings.custom_epub_default = False
        user_settings.save()

    return HttpResponse("Changed ePub Default!", status=200) 

@login_required
def define(request, word): 
    # Construct the file path 
    file_path = os.path.join(MEDIA_ROOT, 'dictionary.json')
    if not os.path.exists(file_path): 
        return HttpResponse("File not found", status=404) 
    
    # Step 1: Open the JSON file
    with open(file_path, 'r', encoding='utf-8') as file:
        # Step 2: Convert the JSON content to a dictionary
        data = json.load(file)
    if word.strip().upper() in data:
        # Step 3: View the loaded data
        return HttpResponse(data[word.strip().upper()], status=200) 
    else:    
        return HttpResponse("Word not found", status=404) 
 
@login_required
def toggle_registrations(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    registration_toggle = models.RegistrationToggle.objects.get_or_create(id=1)[0]
    err_str = registration_toggle.toggle(request.user)
    if err_str:
        return HttpResponse(err_str, status=500)
    else:
        registration_toggle.save()
        return HttpResponse(status=200)


def handle_file_upload(request):
    file = request.FILES['file'].read()
    fileName = request.POST['filename']
    existingPath = request.POST['existingPath']
    end = request.POST['end']
    nextSlice = request.POST['nextSlice']

    # Return invaild response if any part of the file is invalid
    if file=="" or fileName=="" or existingPath=="" or end=="" or nextSlice=="":
        res = JsonResponse({'data':'Invalid Request'})
        return res
    else:
        # If the file upload has not begun, begin to write new file
        if existingPath == 'null':
            path = MEDIA_ROOT + '/temp/' + fileName
            with open(path, 'wb+') as destination:
                destination.write(file)
            # If old temp exists, delete it from temp folder/models.
            try:
                old = models.TempFile.objects.get(existingPath=fileName)
                old.delete()
            except:
                pass

            TempFile = models.TempFile()
            TempFile.existingPath = fileName
            TempFile.eof = end
            TempFile.name = fileName
            TempFile.save()
            
            # If the first chunk was the only chunk, open the file and upload it, before deleting the temporary location
            if int(end):
                res = JsonResponse({'data': 'Uploaded Successfully', 'existingPath': fileName})
                path = MEDIA_ROOT + '/temp/' + TempFile.existingPath
                try:
                    lock.acquire()
                    with open(path, 'rb') as uploaded_book_file:
                        upload_and_save_book(uploaded_book_file)
                except Exception as e:
                    print(e)
                finally:
                    lock.release()
                    TempFile.delete()
            else:
                res = JsonResponse({'existingPath': fileName})
            return res
        else:
            # If the file is in progress being uploaded, continue upload
            path = MEDIA_ROOT + '/temp/' + existingPath
            model_id = models.TempFile.objects.get(existingPath=existingPath)
            if model_id.name == fileName:
                if not model_id.eof:
                    with open(path, 'ab+') as destination:
                        destination.write(file)
                    if int(end):
                        model_id.eof = int(end)
                        model_id.save()
                        res = JsonResponse({'data':'Uploaded Successfully','existingPath':model_id.existingPath})
                        lock.acquire()
                        try:
                            with open(path, 'rb') as uploaded_book_file:
                                upload_and_save_book(uploaded_book_file)
                        except Exception as e:
                            print(e)                                
                        finally:
                            lock.release()
                            model_id.delete()
                        
                    else:
                        # Continue upload
                        res = JsonResponse({'existingPath':model_id.existingPath})    
                    return res
                else:
                    res = JsonResponse({'data':'EOF found. Invalid request'})
                    return res
            else:
                res = JsonResponse({'data':'No such file exists in the existingPath'})

@login_required
@user_passes_test(can_access_content_page, login_url="/", redirect_field_name=None)
def download_books(request):
    context = {
        'user_perms': check_user_permissions(request.user),
    }
    return render(request, "downloader.html", context)

@login_required
def serve_cfi_json(request, filename): 
    # Construct the file path 
    file_path = os.path.join(MEDIA_ROOT, filename)
    if not os.path.exists(file_path): 
        return HttpResponse("File not found", status=404) 
    
    # Open the file in binary mode and return it as a response 
    with open(file_path, 'rb') as json_file: 
        response = HttpResponse(json_file.read(), content_type='application/json') 
        response['Content-Disposition'] = f'inline; filename="{filename}"' 
        return response



def stream_audio(request, filename):
    print(filename)
    path = filename

    if not os.path.exists(path):
        return HttpResponse(status=404)

    file_size = os.path.getsize(path)
    content_type = 'audio/m4b'  # or 'audio/mp4' depending on the browser

    range_header = request.headers.get('Range', '')
    if range_header:
        start, end = range_header.strip().split('=')[1].split('-')
        start = int(start)
        end = int(end) if end else file_size - 1
        length = end - start + 1

        with open(path, 'rb') as f:
            f.seek(start)
            data = f.read(length)

        response = HttpResponse(data, status=206, content_type=content_type)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = str(length)
    else:
        response = FileResponse(open(path, 'rb'), content_type=content_type)
        response['Content-Length'] = str(file_size)

    response['Accept-Ranges'] = 'bytes'
    response['Last-Modified'] = http_date(os.path.getmtime(path))
    return response