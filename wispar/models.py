from django.db import models
from django.contrib.auth.models import User, Group
from django.core.files.storage import default_storage
import os
from wispar.settings import MEDIA_ROOT

class WisparUser(models.Model):
    # fields
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    # meta options to make sure the table name is "users"
    class Meta:
        db_table = 'users'
        app_label = 'wispar'

class PersonalSettings(models.Model):
    # fields
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    theme = models.CharField(max_length=255)
    recently_read_visible = models.BooleanField(default=True)
    recently_added_visible = models.BooleanField(default=True)
    recent_release_visible = models.BooleanField(default=True)
    library_visible = models.BooleanField(default=True)
    curved_radius = models.BooleanField(default=True) 
    ui_font = models.CharField(max_length=255, default='Roboto Slab')
    custom_epub_default = models.BooleanField(default=False)
    row_order = models.CharField(max_length=255, default='recently_read,recently_added,recent_release,library')
    class Meta:
        db_table = 'personalsettings'
        app_label = 'wispar'
    
class Book(models.Model):
    # fields
    bookId = models.IntegerField(null=False, blank=False)
    title = models.CharField(max_length=511)
    author = models.CharField(max_length=255, null=True, blank=True)  # optional field
    medium = models.CharField(
        max_length=10, 
        choices=[('Audiobook', 'Audiobook'), ('Ebook', 'Ebook')]
    )
    linked_medium = models.BooleanField()
    isbn = models.CharField(max_length=50)
    publication_date = models.CharField(null=True, blank=True, max_length=50)
    language = models.CharField(max_length=255, null=True, blank=True)
    filefield = models.FileField(null = True, max_length=511)

    # meta options to ensure table name and constraint
    class Meta:
        db_table = 'books'

    def __str__(self):
        return f"{self.title} by {self.author} as an {self.medium}"
    
    def delete(self, *args, **kwargs):
        # Delete the associated file before deleting the instance
        if self.filefield:
            # Ensure the file path is correct and exists
            file_path = self.filefield.path
            if os.path.isfile(file_path):
                os.remove(file_path)
            cached_cover_file_path = default_storage.path(f'{self.bookId}-cover.jpg')
            if os.path.isfile(cached_cover_file_path):
                os.remove(cached_cover_file_path)
            if self.medium == 'ebook' or self.linked_medium:
                locations_filepath =default_storage.path(f'locations/{self.bookId}_locations.json')
                if os.path.isfile(locations_filepath):
                    os.remove(locations_filepath)
        TitleLocation.objects.filter(book_id=self.bookId).delete()
        super(Book, self).delete(*args, **kwargs)

class TitleLocation(models.Model):
    # Timestamp
    audio_location = models.FloatField(null=True)
    # CFI string eg. "book.epub#epubcfi(/6/4[chap01ref]!/4[body01]/10[para05]/3:10)"
    # https://idpf.org/epub/linking/cfi/
    text_location = models.CharField(max_length=255, null=True)
    location_text_snippet = models.CharField(max_length=255, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book_id = models.IntegerField(null=False, blank=False, default=1)
    progress_percentage = models.IntegerField(null=True)
    last_read_at = models.DateTimeField(auto_now=True)
    bookmark_type = models.CharField(
        max_length=18,
                choices=[('bookmark', 'cfi'), ('highlight', 'cfi'), ('last_read_position', 'last_read_position')]
    )
    time_remaining = models.IntegerField(null=False, default=-1)

    class Meta:
        db_table = 'bookmarks'


class RegistrationToggle(models.Model):
    users_can_register = models.BooleanField(null=False, default=True)

    def toggle(self, user):
        if user.is_superuser:
            self.users_can_register = not self.users_can_register
        else:
            return "You don't have permission to toggle registrations."
        
    class Meta:
        db_table = 'registration_toggle'

class ContentRestrictions(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        db_table = 'content_restrictions'


class TempFile(models.Model):
    existingPath = models.CharField(unique=True, max_length=511)
    name = models.CharField(max_length=511)
    eof = models.BooleanField()

    def delete(self, *args, **kwargs):
        # Delete the associated file before deleting the instance
        if os.path.isfile(MEDIA_ROOT + '/temp/' + self.existingPath):
            # Ensure the file path is correct and exists
            os.remove(MEDIA_ROOT + '/temp/' + self.existingPath)
        super(TempFile, self).delete(*args, **kwargs)