from math import floor
from django.core.files.storage import default_storage
from django.core.files.base import File
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Max, Min, ExpressionWrapper, Subquery, Value, DurationField, CharField, OuterRef, F, Q
from django.db.models.functions import Coalesce
from django.contrib.auth.models import Group, Permission, User
from django.utils import timezone
from mutagen.mp4 import MP4, MP4Info
from ebooklib import epub
from wispar import models, settings
from olclient.openlibrary import OpenLibrary
import requests
import os
import re
import io
from bs4 import BeautifulSoup
import magic
import zipfile
import tempfile
import shutil
from datetime import datetime
from django.contrib.contenttypes.models import ContentType

import sys
sys.path.append("alignment")
import forced_alignment_worker #type: ignore

def update_homescreen(recently_read_row, recently_added_row, recent_release_row, library_visible, row_order, user):
    # Retrieve or create the PersonalSettings instance for the user
    user_settings, created = models.PersonalSettings.objects.get_or_create(user=user)
    
    # Update the visibility settings
    user_settings.recently_read_visible = str(recently_read_row)
    user_settings.recently_added_visible = str(recently_added_row)
    user_settings.recent_release_visible = str(recent_release_row)
    user_settings.library_visible = str(library_visible)
    user_settings.row_order = row_order
    # Save the changes to the database
    user_settings.save()


def determine_row_order(context, user, recently_read, recently_added, recent_release):
    try:
        user_settings, _ = models.PersonalSettings.objects.get_or_create(user=user)
        context['library_visible'] = user_settings.library_visible

        row_order_v = user_settings.row_order or "recently_read,recently_added,recent_release,library,"
        context['row_order'] = row_order_v

        rows = row_order_v.split(',')
        # Map row types to their respective values
        content_mapping = {
            'recently_read': {
                'data': recently_read,
                'title': "Recently Read",
                'visible': user_settings.recently_read_visible
            },
            'recently_added': {
                'data': recently_added,
                'title': "Recently Added",
                'visible': user_settings.recently_added_visible
            },
            'recent_release': {
                'data': recent_release,
                'title': "Recent Releases",
                'visible': user_settings.recent_release_visible
            }
        }
        for idx, row_key in enumerate(rows[:3], start=1):
            row_config = content_mapping.get(row_key)
            if row_config:
                context[f'row_{["one", "two", "three"][idx-1]}'] = row_config['data']
                context[f'row_{["one", "two", "three"][idx-1]}_title'] = row_config['title']
                context[f'row_{["one", "two", "three"][idx-1]}_visible'] = row_config['visible']
    except Exception as e:
        print(f'Error fetching user homepage row settings: {str(e)}')
        # defaults
        context['library_visible'] = True
        context['row_one'] = recently_read
        context['row_one_title'] = "Recently Read"
        context['row_one_visible'] = True
        context['row_two'] = recently_added
        context['row_two_title'] = "Recently Added"
        context['row_two_visible'] = True
        context['row_three'] = recent_release
        context['row_three_title'] = "Recent Releases"
        context['row_three_visible'] = True
    return context

"""
Fixes missing metadata fields by identifying and handling 'Unknown' values.

Parameters:
    metadata (dict): A dictionary containing book metadata.
    
Returns:
    dict: The updated metadata dictionary.
"""
def fix_missing_metadata(metadata):
    # If local metadata is complete, return
    if update_metadata(metadata, None, None):
        #print(f'Local Metadata is complete, skipping online sources...')
        return
    all_validated = True
    try:
        #print(f'identifier is: {metadata.get('identifier')}, Sanatizing to: {sanitize_isbn(metadata.get('identifier'))}')
        metadata['identifier'] = sanitize_isbn(metadata.get('identifier'))
        # Check if we have a "valid" ISBN, If so update missing data
        # This assumes there will be a single (or no) response from the api for the provided ISBN (Which should be the case AKAIK)
        if validate_isbn(metadata["identifier"]):
            all_validated = fix_with_isbn(metadata, all_validated)
            # If there are no Unknown values, return metadata
            # TODO: It may be nice to try validating local metadata rather than take it as fact
            # - Maybe search title & author and ensure there is at least one result from api's, if not, assume bad local metadata
            if all_validated:
                return metadata
        # If there is missing metadata after attempting ISBN lookup, use title instead
        if metadata.get('title') != "Unknown":
            all_validated = fix_with_title(metadata, all_validated)
        else:
            #print(f'Invalid Title {metadata.get('title')} provided, trying with filename: {metadata['filepath'].name}')
            all_validated = fix_with_filename(metadata, all_validated)
        if all_validated:
            return metadata
        else:
            #print(f'Filename: "{metadata['filepath'].name}" does not contain title, trying solely text based search')
            all_validated = fix_with_text(metadata, all_validated)
            if all_validated:
                return metadata
            else:
                # TODO: Maybe prompt/ask the user for manual input on remaining missing items?
                return metadata 
    except Exception as e:
        print("Error while fixing metadata:", e)
        return metadata

google = True  # Assuming we want to use Google API too
ol_api = True
api_key = os.getenv("GOOGLE_BOOKS_API_KEY")

def fix_with_isbn(metadata, all_validated):
    #print(f'Using Google API: {google}, Using OL API: {ol_api}')
    
    if metadata.get('identifier') == "Unknown":
        #print("Error: ISBN is missing. Cannot proceed without an identifier.")
        return all_validated

    fetched_metadata_ol = {}
    fetched_metadata_google = {}

    # Fetch metadata from Open Library
    if ol_api:
        fetched_metadata_ol = openlibrary_api_query(metadata)
        if fetched_metadata_ol.get('title') == "Unknown":
            #print("Open Library did not return data for this ISBN.")
            fetched_metadata_ol = {}

    # Update metadata using fetched data
    all_validated = update_metadata(metadata, fetched_metadata_ol, fetched_metadata_google)
    if all_validated:
        return all_validated

    # Fetch metadata from Google Books API
    if google:
        fetched_metadata_google = google_books_api_query(f'isbn:{sanitize_isbn(metadata["identifier"])}')
        if not fetched_metadata_google.get('items'):
            #print("Google Books API did not return data for this ISBN.")
            fetched_metadata_google = {}

    # Update metadata using fetched data
    all_validated = update_metadata(metadata, fetched_metadata_ol, fetched_metadata_google)

    return all_validated

def fix_with_title(metadata, all_validated):
    #print(f'Invalid ISBN provided, trying with Title: {metadata.get("title")}...')
    
    if metadata.get("title") == "Unknown":
        print("Error: Title is missing. Cannot proceed without a title.")
        return all_validated

    # Fetch metadata from Open Library and Google Books APIs using the title
    fetched_metadata_ol = openlibrary_api_query(metadata) if ol_api else {}
    fetched_metadata_google = google_books_api_query(f'intitle:{metadata["title"]}') if google else {}

    # Update metadata using fetched data
    all_validated = update_metadata(metadata, fetched_metadata_ol, fetched_metadata_google)

    return all_validated

def fix_with_filename(metadata, all_validated):
    filepath = metadata['filepath'].name
    query = filepath.split('.')
    # Remove file extension
    query = ''.join(query[:len(query) - 1])
    suffix = is_django_generated_suffix(query)
    if suffix:
        # Remove appended Django suffix
        query = query.split('_')
        query = ' '.join(query[:len(query) - 1])
    query = query.replace("-", " ").replace("_", " ").replace(".", " ")
    metadata['title'] = query
    #print(f'Using filename-derived query: "{query}"')

    # Fetch metadata from Open Library and Google Books APIs using the filename-derived query
    fetched_metadata_ol = openlibrary_api_query(metadata) if ol_api else {}
    fetched_metadata_google = google_books_api_query(f'intitle:{query}') if google else {}

    # Update metadata using fetched data
    all_validated = update_metadata(metadata, fetched_metadata_ol, fetched_metadata_google)

    return all_validated

def fix_with_text(metadata, all_validated):
    query = sanitize_text(get_middle_sentences(metadata['filepath'], 50))
    if query == "":
        #print("Error: Could not extract text from the file.")
        return all_validated

    #print(f'Using extracted text for metadata lookup: {query}')

    # Fetch metadata from Open Library and Google Books APIs using extracted text
    #TODO: Figure this out lmao
    #fetched_metadata_ol = openlibrary_api_query(metadata) if ol_api else {}
    fetched_metadata_google = google_books_api_query(query) if google else {}

    # Update metadata using fetched data
    all_validated = update_metadata(metadata, None, fetched_metadata_google)

    return all_validated

def update_metadata(metadata, fetched_metadata_ol, fetched_metadata_google):
    all_validated = True
    for metadata_type, value in metadata.items():
        if value == "Unknown":
            new_value = "Unknown"
            if fetched_metadata_ol:
                new_value = fetched_metadata_ol.get(metadata_type, "Unknown")
            if new_value == "Unknown" and fetched_metadata_google:
                new_value = fetch_from_google_metadata(metadata_type, fetched_metadata_google)

            if new_value != "Unknown":
                metadata[metadata_type] = new_value
                #print(f'Updated {metadata_type} from API: {metadata[metadata_type]}')
            else:
                #print(f'Missing {metadata_type} and could not update from any available data sources.')
                # If we don't know the ISBN, we shouldn't pick one at 'random', the only metadata type we can ignore for completeness is id
                if metadata_type != "identifier":
                    all_validated = False
        else:
            print(f'Saving Local File Metadata: {metadata_type}: {value}')

    return all_validated

def fetch_from_google_metadata(metadata_type, google_data):
    if 'items' in google_data and google_data['items']:
        sorted_books = sorted(google_data['items'], key=prioritize, reverse=True)
        best_book_info = sorted_books[0].get('volumeInfo', {})

        if metadata_type == "title":
            return best_book_info.get('title', "Unknown")
        elif metadata_type == "author":
            authors = best_book_info.get('authors')
            return ', '.join(authors) if authors else "Unknown"
        elif metadata_type == "publication_date":
            return best_book_info.get('publishedDate', "Unknown")
        elif metadata_type == "language":
            return best_book_info.get('language', "Unknown")
    else:
        print(f'No data found in Google Books API for {metadata_type}.')
    return "Unknown"

def openlibrary_api_query(metadata):
    ol = OpenLibrary()
    lookup_isbn = metadata["identifier"]
    metadata_title = metadata["title"]
    metadata_author = metadata['author']
    
    # Initialize variables
    book_data = None
    authors = []
    
    # Try fetching book information by ISBN
    try:
        #print('Trying Open Library lookup by ISBN...')
        book_data = ol.Edition.get(isbn=lookup_isbn)
    except Exception as e:
        print(f'Error retrieving OpenLibrary data with ISBN: {e}')

    # If book_data is still None, try fetching by title
    if not book_data:
        #print(f'ISBN lookup failed for {lookup_isbn}, trying with title: {metadata_title}')
        try:
            # Search for works by title
            book_search_result = ol.Work.search(title=metadata_title)
            if book_search_result:
                print('open Library Title Match! Metadata extraction not yet working lol')
            else:
                print('No search results found for the title.')
        except Exception as e:
            print(f'Error retrieving OpenLibrary data with Title: {e}')
            
    if not book_data:
        print('Failed to retrieve book data from Open Library.')
        return metadata  # Return metadata as is if no data was found
    
    #print('Extracting data from Open Library')
    
    # Extract data from book_data
    metadata['title'] = getattr(book_data, 'title', metadata['title'])
    #print(f"Title: {metadata['title']}")
    
    # Get authors
    authors = getattr(book_data, 'authors', [])
    if authors:
        author_names = []
        for author in authors:
            try:
                # If author is an object with attributes
                if hasattr(author, 'name'):
                    author_names.append(author.name)
                # If author is a dictionary with 'key', fetch the author data
                elif isinstance(author, dict) and 'key' in author:
                    author_data = ol.get(f"{author['key']}.json")
                    author_names.append(author_data.get('name', 'Unknown'))
                else:
                    print(f'Unknown author format: {author}')
            except Exception as e:
                print(f'Error retrieving author data: {e}')
                author_names.append('Unknown')
        metadata['author'] = ', '.join(author_names) if author_names else metadata['author']
    #print(f"Author(s): {metadata['author']}")
    
    # Get publication date
    metadata['publication_date'] = getattr(book_data, 'publish_date', metadata['publication_date'])
    #print(f"Publication Date: {metadata['publication_date']}")
    
    # Get language
    languages = getattr(book_data, 'languages', [])
    if languages:
        language_codes = []
        for lang in languages:
            if isinstance(lang, dict):
                code = lang.get('key', '').split('/')[-1]
                language_codes.append(code)
            else:
                # If lang is an object, try to access its attributes
                code = getattr(lang, 'key', '').split('/')[-1]
                language_codes.append(code)
        metadata['language'] = ', '.join(language_codes) if language_codes else metadata['language']
    else:
        print('No language data found in Open Library.')
    #print(f"Language: {metadata['language']}")
    
    return metadata

def google_books_api_query(query):
    api_url = 'https://www.googleapis.com/books/v1/volumes'
    params = {
        'q': query,
        'key': api_key
    }
    try:
        #print("Trying to make request to Google Books API...")
        api_response = requests.get(api_url, params=params, timeout=10)
        #print(f'Request: {api_response.request.url} received response with status code: {api_response.status_code}')
        api_response.raise_for_status()
        return api_response.json()
    except requests.exceptions.Timeout:
        print("Request to Google Books API timed out.")
        return {}
    except requests.exceptions.HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
        return {}
    except requests.exceptions.RequestException as e:
        print("Error during API request:", e)
        return {}

def get_first_sentences(epub_path, sentence_count=2):
    #print('Opening book for chapter text...')
    try:
        book = epub.read_epub(epub_path.path)
        # Use get_items() method to get text items
        text_items = [item for item in book.get_items() if item.media_type == 'application/xhtml+xml']
        if not text_items:
            print("No text items found in the EPUB file.")
            return ''
        first_chapter = text_items[0]
        soup = BeautifulSoup(first_chapter.get_content(), 'html.parser')
        text = soup.get_text()
        sentences = text.split('.')
        return '. '.join(sentences[:sentence_count]).strip() + '.'
    except Exception as e:
        print("ERROR WITH FIRST SENTENCE")
        print(e)
        return ''

def get_middle_sentences(epub_path, sentence_count=5):
    #print('Opening book for text extraction...')
    try:
        book = epub.read_epub(epub_path.path)

        # Get the spine (reading order)
        spine = book.spine
        total_items = len(spine)
        if total_items == 0:
            print("No spine items found.")
            return ''

        # Calculate the middle index
        middle_index = total_items // 2

        # Extract from the middle item
        idref, _ = spine[middle_index]
        item = book.get_item_with_id(idref)
        if item.media_type == 'application/xhtml+xml':
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            if text:
                sentences = text.split('.')
                sentences = [s.strip() for s in sentences if s.strip()]
                if len(sentences) >= sentence_count:
                    extracted_text = '. '.join(sentences[:sentence_count]).strip()
                    return extracted_text + '.'
        print("No suitable content found in middle item.")
        return ''
    except Exception as e:
        print("ERROR WITH TEXT EXTRACTION")
        print(e)
        return ''

def is_django_generated_suffix(file_name):
    # Regex pattern to match Django's random suffix (e.g., '_gd8dsa7d9')
    pattern = r'_[a-zA-Z0-9]{7,}$'
    #base_name = file_name.rsplit('.', 1)[0]  # Remove the file extension
    return bool(re.search(pattern, file_name))

def sanitize_text(text):
    # Remove line breaks and carriage returns
    text = text.replace('\n', ' ').replace('\r', '')
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Optionally, escape quotes if necessary
    # text = text.replace('"', '\\"').replace("'", "\\'")
    return text

def identify_file_type(file):
    # Read the content of the file
    file_content = file.read()
    
    # Reset the file pointer to the beginning after reading
    file.seek(0)
    
    # Get both MIME type and file description
    mime = magic.Magic(mime=True)
    file_magic = magic.Magic()
    mime_type = mime.from_buffer(file_content)
    file_description = file_magic.from_buffer(file_content)
    
    # Initialize the string variable
    file_type = ''
    
    # Use MIME type first
    if mime_type == 'application/epub+zip' or 'EPUB document' in file_description:
        file_type = 'ebook'
    elif mime_type in ['audio/mp4', 'audio/x-m4b'] or 'ISO Media' in file_description:
        file_type = 'audiobook'
    elif mime_type == 'application/zip':
        if is_epub(file_content):
            file_type = 'ebook'
        else:
            file_type = 'Invalid ePub, or other zip file'
    else:
        file_type = f'Unknown or other file type: {mime_type} ({file_description})'
    
    return file_type

def is_epub(file_content):
    try:
        # Use BytesIO to handle the in-memory bytes as a file
        with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zf:
            return 'mimetype' in zf.namelist()
    except zipfile.BadZipFile:
        return False

"""
Upload file and save new book object:
Args:
    book_file (epub): new book to be added
Returns:
"""
def upload_and_save_book(book_file):
    file_root, file_ext = os.path.splitext(book_file.name)
    
    try:
        saved_book = models.Book.objects.get(bookId='1')
        delete_book(1)
        
    except:
        print("No book with ID 1")

    #print(f'Identifying Filetype')
    book_medium = identify_file_type(book_file)
    #print(f'filetype found: {book_medium}, is ebook: {book_medium == 'ebook'}, is audiobook: {book_medium == 'audiobook'}')
    new_book = models.Book(
        bookId = '1',
        title = "",
        author = "",
        medium = book_medium,
        linked_medium = False,
        isbn = '',
        publication_date = '1',
        language = '',
        filefield = File(book_file, name=os.path.basename(book_file.name)),
    )
    new_book.save()
    #print("Initial Save")
    saved_book = models.Book.objects.get(bookId='1')

    highest_bookid = models.Book.objects.aggregate(Max('bookId'))['bookId__max']
    #print(f'Current Highest bookId: {highest_bookid}')

    if saved_book.medium == "ebook":
        try:
            print(f'Loading Book at: {saved_book.filefield.path}')
            book_meta = epub.read_epub(saved_book.filefield.path)
            # Look in metadata for ISBN id
            isbn = "Unknown"
            identifiers = book_meta.get_metadata('DC', "identifier")
            if identifiers:
                for identifier in identifiers:
                    # Ensure identifier is not None and has at least one element
                    if identifier and identifier[0]:
                        possible_isbn = identifier[0][:14]
                        print(f'Possible ISBN: {possible_isbn}')
                        if validate_isbn(possible_isbn):
                            isbn = possible_isbn
                            break
                    else:
                        print(f'Invalid identifier format: {identifier}')

            # Extract metadata fields safely
            def get_metadata_field(metadata_list):
                if metadata_list and metadata_list[0] and metadata_list[0][0]:
                    return metadata_list[0][0]
                else:
                    return "Unknown"

            # Retrieve metadata fields
            title_meta = book_meta.get_metadata('DC', 'title')
            author_meta = book_meta.get_metadata('DC', 'creator')
            date_meta = book_meta.get_metadata('DC', 'date')
            language_meta = book_meta.get_metadata('DC', 'language')

            # Build metadata dictionary
            metadata = {
                'title': get_metadata_field(title_meta)[:200],
                'author': get_metadata_field(author_meta),
                "identifier": isbn,
                'publication_date': get_metadata_field(date_meta),
                'language': get_metadata_field(language_meta),
                'filepath': "Unknown",
            }
        except Exception as e:
            print("Failed to open ePub: ", e)
            metadata = {
                'title': "Unknown",
                'author': "Unknown",
                "identifier": "Unknown",
                'publication_date': "Unknown",
                'language': "Unknown",
                'filepath': "Unknown",
            }
    elif saved_book.medium == "audiobook":
        file_path = default_storage.path(saved_book.filefield.name)
        audio = MP4(file_path)
        
        metadata = {
            'title': audio.tags.get('\xa9nam', ['Unknown'])[0],
            'author': audio.tags.get('\xa9ART', ['Unknown'])[0],
            "identifier": audio.tags.get('----:com.apple.iTunes:ASIN', ['Unknown'])[0],
            'publication_date': audio.tags.get('\xa9day', [''])[0],
            'language': audio.tags.get('\xa9lan', ['Unknown'])[0],
            # None of below are currently saved/used by model
            'album': audio.tags.get('\xa9alb', ['Unknown'])[0],
            'genre': audio.tags.get('\xa9gen', ['Unknown'])[0],
            'description': audio.tags.get('desc', [''])[0],
            'filepath': "Unknown",
        }
    else:
        print("Unkown Medium")
        # Handle unknown mediums or other file types
        metadata = {
            'title':  "Unknown",
            'author': "Unknown",
            "identifier": "Unknown",
            'publication_date': "Unknown",
            'language': "Unknown",
            'filepath': "Unknown",
        }
    saved_book.title = metadata["title"]
    saved_book.author = metadata['author']
    saved_book.isbn = metadata["identifier"]
    saved_book.publication_date = metadata["publication_date"]
    saved_book.language = metadata['language']
    saved_book.bookId = get_book_id(saved_book)

    saved_book.save()

    # Update missing metadata
    try:
        print("Checking for unkown metadata...")
        metadata['filepath'] = saved_book.filefield
        if saved_book.medium == "ebook":
            metadata = fix_missing_metadata(metadata)
        saved_book.title = metadata["title"]
        saved_book.author = metadata['author']
        saved_book.isbn = metadata["identifier"]
        saved_book.publication_date = metadata["publication_date"]
        saved_book.language = metadata['language']
        new_book_id = get_book_id(saved_book)
        saved_book.bookId = new_book_id
        print("Corrected New Book ID: ", new_book_id)
        saved_book.save()
    except Exception as e:
        print("Exception while updating metadata: ", e)
        

    if saved_book.medium == "audiobook" and settings.USE_ALIGN:
        forced_alignment_worker.add_job_to_queue(forced_alignment_worker.cache_audiobook,(default_storage.path(saved_book.filefield.name),))

    forced_alignment_worker.add_job_to_queue(forced_alignment_worker.attempt_merge,(saved_book, models.Book.objects, default_storage, Max,))
    
"""
Returns a ID number unique to Wispar instance
- Implementation looks for exact matches
Args:
    saved_book : book object with metadata contining a valid title and author
Returns:
    int ID that is one higher than any previous ID if media doesn't already have an ID in another format, else returns format of ID 
"""
def get_book_id(saved_book):
    title_needing_id = saved_book.title.strip()
    author_of_media = saved_book.author.strip()

    #find an existing bookid with a title and author closest to the new title and author 
    book_id = None
    is_linked = False
    book_id_and_titles = models.Book.objects.exclude(bookId=1).values_list('bookId', 'title', 'author', 'medium', 'linked_medium')
    for bookId, title, author, medium ,linked in book_id_and_titles:
        #skip if book is same medium
        if medium == saved_book.medium:
            continue

        diff = forced_alignment_worker.calculate_difference(title_needing_id,title,author_of_media, author)
        #Force match on exact pairing
        if diff == 0:
            book_id = bookId
            is_linked = linked
            break

    if book_id:
        if is_linked:
            forced_alignment_worker.unlink_book(book_id, models.Book.objects, Max)
        forced_alignment_worker.link_books(saved_book, book_id, models.Book.objects)
        return book_id
    
    highest_bookid = models.Book.objects.aggregate(Max('bookId'))['bookId__max']
    return (highest_bookid) + 1


"""
Remove spaces and dashes from the ISBN.

Args:
    isbn (str): ISBN to sanitize.

Returns:
    str: ISBN without spaces or dashes.
"""
def sanitize_isbn(isbn):
    return ''.join([char for char in isbn.replace("-", "").replace(" ", "") if char.isdigit()])

"""
Validate an ISBN-10 number.

Args: isbn (str): The ISBN-10 number as a string.

Returns: bool: True if the ISBN is valid, False otherwise.
"""
def validate_isbn_10(isbn):
    isbn = isbn.upper()
    if len(isbn) != 10:
        return False

    total = 0
    for i in range(9):
        if not isbn[i].isdigit():
            return False
        digit = int(isbn[i])
        total += digit * (10 - i)

    # Handle the last character, which can be a digit or 'X'
    last_char = isbn[9]
    if last_char == 'X':
        digit = 10
    elif last_char.isdigit():
        digit = int(last_char)
    else:
        return False
    total += digit

    # ISBN-10 is valid if the total modulo 11 is zero
    is_valid = total % 11 == 0
    return is_valid

"""
Validate a 13-digit ISBN number.

Args: isbn (str): The ISBN-13 number as a string.

Returns: bool: True if the ISBN is valid, False otherwise.
"""
def validate_isbn_13(isbn):

    if len(isbn) != 13 or not isbn.isdigit():
        return False

    total = sum(
        (int(isbn[i]) if i % 2 == 0 else int(isbn[i]) * 3)
        for i in range(12)
    )
    check_digit = (10 - (total % 10)) % 10

    is_valid = check_digit == int(isbn[12])
    return is_valid

"""
Validate ISBN number based on length and character types:
- ISBN-10: 10 characters, all digits except possible 'X' as last character
- ISBN-13: 13 characters, all digits.

Args: isbn (str): ISBN to validate.

Returns: bool: True if valid, False otherwise.
"""
def validate_isbn(isbn):
    print(f'Validating ISBN: "{isbn}"')
    isbn = sanitize_isbn(isbn)

    if len(isbn) == 10:
        print('Doing ISBN-10 check digit check')
        is_valid = validate_isbn_10(isbn)
        print(f'ISBN-10: {isbn} validity is {is_valid}')
        return is_valid
    elif len(isbn) == 13 and isbn.isdigit():
        print('Doing ISBN-13 check digit check')
        is_valid = validate_isbn_13(isbn)
        print(f'ISBN-13: {isbn} validity is {is_valid}')
        return is_valid
    else:
        print("Not a 10 or 13 digit number")
    return False

def delete_book(bookId):
    try:
        book_to_delete = models.Book.objects.filter(bookId=bookId)
        for book in book_to_delete:
            print(f'Deleting {book.title}')
            book.delete()
        if len(models.Book.objects.filter(bookId=bookId)) == 0:
            return True
        else:
            return False    
    except Exception as e:
        print(e)
        return False

# Updates the user's theme
def update_theme(theme, user):
    try:
        pass
        # user.theme = theme;
        # user.save()
        
    except Exception as e:
        return False

"""
Prioritize Google Books api results by ratings or ratingsCount, first result is often "low quality" 
eg, someone selling low quality public domain ebook copy, unrelated Fan Fic/Sequels, etc.
Args:
    book (JSON book info): book information to use in prioritizing a collection
Returns:
    priority score: Having a lot of ratings is twice as important as having a high rating, having neither is 0 (lowest possible)
"""
def prioritize(book):
    volume_info = book.get('volumeInfo', {})
    # Default values for missing keys, 0
    average_rating = volume_info.get('averageRating', 0)
    ratings_count = volume_info.get('ratingsCount', 0)
    # Having a lot of ratings is twice as important as having a high rating, having neither is 0 (lowest possible)
    # Assumptions:
    #   - The  "correct" book is *most commonly* going to be the most commonly known, and thus have the most reviews
    #   - The "correct" book is *more likely* to have high user reviews (compared to knock offs/copycats/plagerism, etc.)   
    return (ratings_count * 2, average_rating)

"""
Attempts Extraction of cover image from local file, and on failure procures one online
Args:
    bookId (int): ID of the book we want a cover for
Returns:
    cover (Http Response): Cover image, or 404 if none found, or 500 server error on exception
"""
def get_cover(bookId):
    saved_book = models.Book.objects.filter(bookId=bookId).order_by('id').first()
    # Get cover saved in local file/metadata:
    #print(f'Looking  for local  cover for: {saved_book.title}')
    # First look for a jpg saved by wispar
    try:
        file_name = f'{bookId}-cover.jpg'
        # Get the file path using default_storage
        file_path = default_storage.path(file_name)
        
        # Open the file in binary mode
        with open(file_path, 'rb') as file:
            # Create an HTTP response with the image content
            response = HttpResponse(file.read(), content_type='image/png')
            response['Content-Disposition'] = f'inline; filename="{file_name}"'
            return response
    except Exception as e:
        print()
        #print(f"No locally cached image: {str(e)}")
    if saved_book.medium == "ebook":
        try:
            # Read the EPUB file
            book_meta = epub.read_epub(saved_book.filefield.path)

            # Return the cover image as an HTTP response
            cover = extract_cover(book_meta)
            if cover:
                response = HttpResponse(cover, content_type='image/png')
                response['Content-Disposition'] = 'inline; filename="cover.png"'
                #print(f'Returning cover for {saved_book.title} succesfully!')
                return response
        except Exception as e:
            print("Cover Not Found:", e)

    elif saved_book.medium == "audiobook":
        audio = MP4(saved_book.filefield)
        cover = audio.tags.get('covr')
        if cover:
            #print("cover exists!")
            cover_img = cover[0]
            # Return the cover image as an HTTP response
            response = HttpResponse(cover_img, content_type='image/png')
            response['Content-Disposition'] = f'inline; filename="cover.png"'
            return response
    # Finally:
    #print("No local cover :(")
    # Fetch cover image from Google Books API based on the isbn or title
    return  get_online_cover(saved_book)

"""
Returns the raw binary content of the cover image if found,
otherwise returns None.
"""
def extract_cover(book):
    # Method 1: <meta name="cover" content="cover-id" />
    #    This is the standard OPF-based way for some EPUBs.
    cover_meta = book.get_metadata('OPF', 'cover')
    if cover_meta:
        # cover_meta is a list of (tag, attrs) tuples.
        # e.g., [('cover', {'name': 'cover', 'content': 'cover-image'})]
        meta_attrs = cover_meta[0][1]  # Get the dict of attributes
        if 'content' in meta_attrs:
            cover_id = meta_attrs['content']
            maybe_cover_item = book.get_item_with_id(cover_id)
            if maybe_cover_item and maybe_cover_item.media_type.startswith('image'):
                #print("Cover found via <meta name='cover'> in the OPF (Method 1).")
                return maybe_cover_item.content

    # Method 2: Look for an item with ID="cover" in the manifest (some EPUBs do this).
    cover_item = book.get_item_with_id('cover')
    if cover_item and cover_item.media_type.startswith('image'):
        #print("Cover found via ID='cover' in the manifest (Method 2).")
        return cover_item.content

    # Method 3: Look for any image file that has 'cover' in its filename
    #    (covers named 'cover.jpg', 'cover.png', etc.).
    for item in book.get_items():
        if item.media_type.startswith('image'):
            filename_lower = item.file_name.lower()
            # Check if the filename has 'cover' and a valid image extension
            if 'cover' in filename_lower:
                #print(f"Cover found via a matching filename: {item.file_name} (Method 3).")
                return item.content

    # Method 4: Parse cover.xhtml to see if it references an image
    #    Some EPUBs define a dedicated XHTML page named 'cover.xhtml'.
    cover_html_items = [
        i for i in book.get_items()
        if i.file_name.endswith(('cover.xhtml', 'cover.html')) and i.media_type == 'application/xhtml+xml'
    ]
    if cover_html_items:
        for html_item in cover_html_items:
            soup = BeautifulSoup(html_item.content, 'html.parser')
            img_tag = soup.find('img')
            if img_tag and 'src' in img_tag.attrs:
                # The src might be relative (e.g. "../images/cover.jpg"), find the right item by matching the end of the path/relative path
                img_src = img_tag['src'].strip()
                # Normalize and try to find it in the manifest items
                img_src_basename = img_src.split('/')[-1]
                for item in book.get_items():
                    # Compare with or without path
                    if item.file_name.endswith(img_src_basename) and item.media_type.startswith('image'):
                        #print("Cover found by parsing cover.xhtml (Method 4).")
                        return item.content

    # If all methods fail, return None
    print("No cover image found.")
    return None

def get_cover_options(bookId):
    saved_book = models.Book.objects.filter(bookId=bookId).order_by('id').first()

    isbn = saved_book.isbn
    title = saved_book.title
    author = saved_book.author
    data = {}
    if validate_isbn(isbn):
        #print(f'ISBN: {isbn} validated, looking for cover...')
        query = f'isbn:{sanitize_isbn(isbn)}'
        data = google_books_api_query(query)
        #print(JsonResponse(data))
    if 'items' in data and data['items']:
        print('Sorting...')
        # Sort items by prioritize function (descending order)
        sorted_books = sorted(data['items'], key=prioritize, reverse=True)
        print("Returning: ", len(sorted_books), " cover options...")
        cover_urls = {'images': []}
        sorted_books[0].get('volumeInfo', {})
        for title in sorted_books:
            title_info = title.get('volumeInfo', {})
            if 'imageLinks' in title_info:
                # Use the highest resolution image available
                image_url = title_info['imageLinks'].get('extraLarge') or \
                            title_info['imageLinks'].get('large') or \
                            title_info['imageLinks'].get('medium') or \
                            title_info['imageLinks'].get('thumbnail')
                if image_url:
                    cover_urls['images'].append(image_url)
        if len(cover_urls) > 0:
            return JsonResponse(cover_urls)
    print("Looking with title for cover...")
    query = f'intitle:{title}+inauthor:{author}'
    data = google_books_api_query(query)
    if 'items' in data and data['items']:
        print('Sorting...')
        # Sort items by prioritize function (descending order)
        sorted_books = sorted(data['items'], key=prioritize, reverse=True)
        print("Returning: ", len(sorted_books), " cover options...")
        cover_urls = {'images': []}
        sorted_books[0].get('volumeInfo', {})
        for title in sorted_books:
            title_info = title.get('volumeInfo', {})
            if 'imageLinks' in title_info:
                # Use the highest resolution image available
                image_url = title_info['imageLinks'].get('extraLarge') or \
                            title_info['imageLinks'].get('large') or \
                            title_info['imageLinks'].get('medium') or \
                            title_info['imageLinks'].get('thumbnail')
                if image_url:
                    cover_urls['images'].append(image_url)
        if len(cover_urls) > 0:
            return JsonResponse(cover_urls)
    return JsonResponse({'images':[]})

"""
Search Google Books API for cover image
TODO: Add API key?
Args: saved_book (wispar book model): book information to used in searching for cover
Returns: cover (Http Response): Cover image, or 404 if none found, or 500 server error on exception
"""
def get_online_cover(saved_book):
    try:
        isbn = saved_book.isbn
        title = saved_book.title
        author = saved_book.author

        if validate_isbn(isbn):
            #print(f'ISBN: {isbn} validated, looking for cover...')
            query = f'isbn:{sanitize_isbn(isbn)}'
            data = google_books_api_query(query)
            isbn_cover_response  = select_best_cover(data, saved_book)
        
            if isbn_cover_response:
                #print(f'Found cover based on ISBN: {isbn}, returning...')
                return isbn_cover_response
            '''
            else:
                # Open Library
                cover_url = f'https://covers.openlibrary.org/b/ISBN/{isbn}-L.jpg"
                image_response = requests.get(cover_url)
                if image_response.status_code == 200:
                    response = HttpResponse(image_response.content, content_type='image/jpeg')
                    response['Content-Disposition'] = 'inline; filename="cover.jpg"'
                    print('OPEN LIBRARY')
                    return response
                else:
                    print("No ISBN  cover match,")
'''
        print("Looking with title for cover...")
        query = f'intitle:{title}+inauthor:{author}'
        data = google_books_api_query(query)
        title_cover_response  = select_best_cover(data, saved_book)
        if title_cover_response:
            #print("Found cover based on title, returning cover...")
            return title_cover_response
        
        return HttpResponse("File not found", status=404) 
    except Exception as e:
        print("Error fetching cover from Google Books API:", e)
        return HttpResponse('Error fetching cover image', status=500)

def cache_online_cover_locally(url, bookId):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            #print('Caching image...')
            # Extract the file name from the URL
            file_name = f'{bookId}-cover.jpg'
            file_path = default_storage.path(file_name)

            # Save the image
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
    except:
        print('Could not cache cover')
def cache_online_cover_in_epub(saved_book, cover_image_content):
    print('lol')
"""     # Load the EPUB file
    try:
        book = epub.read_epub(saved_book.filefield.path)
        print('book loaded')
    except:
        print('Error loading ebook for cover caching...')
    # Print items
    print("Items in the EPUB:", [item.file_name for item in book.get_items()])

    # Add the cover image
    book.set_cover(file_name='cover.jpg', content=cover_image_content)
    print('cover set')
    print("Items in the EPUB:", [item.file_name for item in book.get_items()])

    try:
        # Save back to the original file path
        # Write to a temporary file first
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
            tmp_path = tmp_file.name
        epub.write_epub(tmp_path, book)
        shutil.move(tmp_path, saved_book.filefield.path)
        print(f"Cover image updated in '{saved_book.filefield.path}'")

    except Exception as e:
        print(f'Error saving updated epub with cover: {e}') """

"""
Sorts list of potential covers based on prioritize function, returns "top" result
Args:
    data (List of 'items' containing JSON book info): potential book matches for cover
Returns:
    cover/None: Returns cover if  good match found, else, returns None
"""
def select_best_cover(data, saved_book):
    if 'items' in data and data['items']:
        # Sort items by prioritize function (descending order)
        sorted_books = sorted(data['items'], key=prioritize, reverse=True)
        print("Selecting best availible cover from: ", len(sorted_books), " options...")
        
        # Pick the best match
        best_book_info = sorted_books[0].get('volumeInfo', {})
        if 'imageLinks' in best_book_info:
            # Use the highest resolution image available
            image_url = best_book_info['imageLinks'].get('extraLarge') or \
                        best_book_info['imageLinks'].get('large') or \
                        best_book_info['imageLinks'].get('medium') or \
                        best_book_info['imageLinks'].get('thumbnail')
            if image_url:
                image_response = requests.get(image_url)
                if image_response.status_code == 200:

                    cache_online_cover_locally(image_url, saved_book.bookId)
                    response = HttpResponse(image_response.content, content_type='image/jpeg')
                    response['Content-Disposition'] = 'inline; filename="cover.jpg"'
                    return response
    return None


"""
Takes data from most recent position of current book being read, and either creates a bookmark at the last read position
if reading for the first time, or updates the existing mark.
Args:
    data: Dict containing all relevant information for bookmark
Returns:
    True if successfully updated/created, False otherwise
"""
def update_or_create_last_read_bookmark(data):
    try:
        existing_last_read_bookmark = models.TitleLocation.objects.filter(user_id=data['user'].id).filter(book_id=data['book_id']).filter(bookmark_type="last_read_position")
        progress_percent = int(float(data['progress_percentage'] or 0))
        time_remain = int(float(data['time_remaining'] or 0))
        if len(existing_last_read_bookmark) == 0:
            new_last_read_bookmark = models.TitleLocation(
                audio_location = data['audio_location'],
                text_location = data['text_location'],
                user = data['user'],
                book_id= data['book_id'],
                bookmark_type = 'last_read_position',
                progress_percentage = progress_percent,
                time_remaining = time_remain
            )
            new_last_read_bookmark.save()
            print("successfully saved")
        else:
            old_last_read_bookmark = existing_last_read_bookmark[0]
            old_last_read_bookmark.audio_location = data['audio_location']
            old_last_read_bookmark.text_location = data['text_location']
            old_last_read_bookmark.progress_percentage = progress_percent
            old_last_read_bookmark.time_remaining = time_remain
            old_last_read_bookmark.save()
        return True
    except Exception as e:
        print("Error updating or creating bookmark: ", e)
        return False
    
def get_books_with_progress_percentage(user, search_string = None):
    percentages = models.TitleLocation.objects.filter(
        book_id=OuterRef('bookId'),
        bookmark_type='last_read_position',
        user=user
    ).values('progress_percentage')[:1]

    last_read_datetimes = models.TitleLocation.objects.filter(
        book_id=OuterRef('bookId'),
        bookmark_type='last_read_position',
        user=user
    ).values('last_read_at')[:1]

    if not user.is_superuser:
        current_user_group = user.groups.all()[0]
        current_group_restrictions = models.ContentRestrictions.objects.filter(group=current_user_group).values("book").all()
        if len(current_group_restrictions) > 0:
            group_restricted_book_ids = [restriction["book"] for restriction in current_group_restrictions]
            book_ids = models.Book.objects.exclude(id__in=group_restricted_book_ids).values('bookId').annotate(min_id=Min('id')).values_list('min_id', flat=True)
        else:
            book_ids = models.Book.objects.filter().values('bookId').annotate(min_id=Min('id')).values_list('min_id', flat=True)
    else:
        # Get the minimum id for each bookId
        book_ids = models.Book.objects.filter().values('bookId').annotate(min_id=Min('id')).values_list('min_id', flat=True)

    current_time = timezone.now()

    # Retrieve Book objects with these ids
    if search_string:
        books = models.Book.objects.annotate(
            progress_percentage=Coalesce(Subquery(percentages), 0),
            last_read_hours_at = Subquery(last_read_datetimes),
            last_read_hours_ago = ExpressionWrapper(F('last_read_hours_at') - current_time, output_field=DurationField())
        ).filter(Q(title__icontains=search_string) | Q(author__icontains=search_string),
                 id__in=book_ids
                 )
    else:
        books = models.Book.objects.annotate(
            progress_percentage=Coalesce(Subquery(percentages), 0),
            last_read_hours_at = Subquery(last_read_datetimes),
            last_read_hours_ago = ExpressionWrapper(F('last_read_hours_at') - current_time, output_field=DurationField())
        ).filter(id__in=book_ids)

    return books

def convert_last_read_at_to_hours(books):
     for book in books:
        if book.last_read_hours_ago:
            book.last_read_hours_ago = book.last_read_hours_ago.total_seconds() * -1
            if book.last_read_hours_ago < 3600:
                book.last_read_hours_ago = -1 # need a non falsey value for the template to render correctly
            else:
                book.last_read_hours_ago = floor(int(book.last_read_hours_ago) / 3600)

def check_user_permissions(user):

    return_user = {
        'can_delete_books': user.has_perm('wispar.delete_book'),
        'can_add_books': user.has_perm('wispar.add_book'),
        'can_change_permission': user.has_perm('auth.change_permission'),
        'is_superuser': user.is_superuser
    }

    return return_user

def get_groups_and_group_permissions():
    groups = Group.objects.all()
    group_dict = {}
    for group in groups:
        permission_list = []
        for permission in group.permissions.all():
            permission_list.append(permission.codename)
        group_dict[group.name] = permission_list

    return group_dict


def create_new_perms_role(perms_data):
    new_group = Group(
        name=perms_data['new_group_name_input']
    )
    new_group.save()
    wispar_book_content_type = ContentType.objects.get_for_model(models.Book)
    auth_content_type = ContentType.objects.get_for_model(Permission)
    # user_content_type = ContentType.objects.get_for_model(User)
    if ('add_content_check' in perms_data):
        add_book_permission = Permission.objects.get(codename="add_book", content_type= wispar_book_content_type)
        new_group.permissions.add(add_book_permission)
    if ('remove_content_check' in perms_data):
        delete_book_permission = Permission.objects.get(codename="delete_book", content_type= wispar_book_content_type)
        new_group.permissions.add(delete_book_permission)
    if ('manage_perms_check' in perms_data):
        manage_perms_permission = Permission.objects.get(codename="change_permission", content_type= auth_content_type)
        new_group.permissions.add(manage_perms_permission)
    # if ('remove_users_check' in perms_data):
    #     remove_user_permission = Permission.objects.get(codename='delete_user', content_type=user_content_type)
    #     new_group.permissions.add(remove_user_permission)
    new_group.save()

def delete_perms_role(perms_data):
    group_to_delete = Group.objects.get(name=perms_data['select-role'])

    users_to_reassign = group_to_delete.user_set.all()
    basic_group = Group.objects.get_or_create(name="Basic Reader")[0]

    for user in users_to_reassign:
        basic_group.user_set.add(user)
    group_to_delete.delete()

def edit_perms_role(perms_data):
    group_to_edit = Group.objects.get(name=perms_data['select-role'])
    group_to_edit.permissions.clear() # delete all permissions for this group

    can_add_books ='add_content_check' in perms_data
    can_remove_books = 'remove_content_check' in perms_data
    can_manage_perms = 'manage_perms_check' in perms_data
    # can_remove_user = 'remove_users_check' in perms_data

    wispar_book_content_type = ContentType.objects.get_for_model(models.Book)
    auth_content_type = ContentType.objects.get_for_model(Permission)
    # user_content_type = ContentType.objects.get_for_model(User)

    if can_add_books:
        group_to_edit.permissions.add(Permission.objects.get(codename="add_book", content_type=wispar_book_content_type))
    if can_remove_books:
        group_to_edit.permissions.add(Permission.objects.get(codename="delete_book", content_type=wispar_book_content_type))
    if can_manage_perms:
        group_to_edit.permissions.add(Permission.objects.get(codename="change_permission", content_type=auth_content_type))
    # if can_remove_user:
    #     group_to_edit.permissions.add(Permission.objects.get(codename="delete_user", content_type=user_content_type))

    group_to_edit.save()

def get_users_and_groups():
    users_with_group = User.objects.all().annotate(
        group_name=Subquery(
            Group.objects.filter(user__id=OuterRef('pk')).values('name')[:1]
        )
    ).filter(is_superuser = 0)

    return users_with_group

def edit_user_roles(perms_data):
    users_with_group = get_users_and_groups()

    err_message = None
    for user in users_with_group:
        element_name = f'{user.username}-select-role'
        if element_name in perms_data and perms_data[element_name] != user.group_name:
            try:
                new_group = Group.objects.get(name=perms_data[element_name])
                user.groups.clear()
                new_group.user_set.add(user)
                new_group.save()
                user.save()
            except Group.DoesNotExist as e:
                err_message = "At least one of the assigned roles does not exist."
    
    if err_message:
        return err_message


def can_access_content_page(user):
    return user.has_perm('wispar.add_book') or user.has_perm('wispar.delete_book') or user.is_superuser

def can_access_permissions_page(user):
    return user.has_perm('auth.change_permission') or user.is_superuser

def delete_user(user, perms_data):
    if not user.is_superuser:
        return "You do not have permissions to delete users."
    try:
        deleted = models.User.objects.get(username=perms_data['delete-user-button']).delete()[0]
        if not deleted:
            return "An error occurred while deleting that user."
    except Exception as e:
        return f"An error occurred while deleting that user: {e}"
    
def can_access_book(user, book_id):
    if user.is_superuser:
        return True
    users_group = user.groups.all()[0]
    groups_restrictions = models.ContentRestrictions.objects.filter(group=users_group).values("book")
    restricted_book_ids = [restriction["book"] for restriction in groups_restrictions] #not book.bookId, but book.id
    possible_restricted_books = models.Book.objects.filter(bookId=book_id)

    for book in possible_restricted_books:
        if book.id in restricted_book_ids:
            return False

    return True