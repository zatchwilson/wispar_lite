from django.test import TestCase
from library.controller import *
from alignment.forced_alignment_worker import *
import subprocess
# Create your tests here.
valid_isbn_10 = [
    "0-306-40615-2",
    "0-7432-7356-7",
    "3-598-21500-2",
    "0-395-19395-8",
    "0-13-110362-8",
    "1-56619-909-3",
    "0-670-82162-4",
    "1-4028-9462-7",
]

valid_isbn_13 = [
    "978-3-16-148410-0",
    "978-0-545-01022-1",
    "978-1-4028-9462-6",
    "978-0-06-112008-4",
    "978-1-86197-876-9",
    "978-0-201-53082-7",
    "978-0-12-374856-0"
]

invalid_isbn_10 = [
    "1-86197-876-9",
    "0-306-40615-3",
    "1-86197-876-8",
    "0-7432-7356-9",
    "3-598-21500-1",
    "0-395-19395-9",
    "0-13-110362-9",
    "1-56619-909-2",
    "0-670-82162-5",
    "1-4028-9462-9",
    "0-14-200067-8",
    "0-14-200067-7"
]

invalid_isbn_13 = [
    "978-1-4493-9310-0",
    "978-0-521-85033-7",
    "978-0-7432-7356-0",
    "978-3-16-148410-1",
    "978-0-545-01022-2",
    "978-1-4028-9462-7",
    "978-0-06-112008-5",
    "978-0-7432-7356-1",
    "978-0-521-85033-8",
    "978-1-86197-876-8",
    "978-0-201-53082-8",
    "978-0-12-374856-1",
    "978-1-4493-9310-1"
]
class UtilsTestCase(TestCase):
    def testing_isbns(self):
        print(f'Testing Valid ISBN-10...')
        all_correct = True
        for isbn in valid_isbn_10:
            if not validate_isbn(isbn):
                all_correct = False
        self.assertTrue(all_correct)
        print(f'Testing Valid ISBN-13...')
        all_correct = True
        for isbn in valid_isbn_13:
            if not validate_isbn(isbn):
                all_correct = False
        self.assertTrue(all_correct)
        print(f'Testing Invalid ISBN-10...')
        all_incorrect = True
        for isbn in invalid_isbn_10:
            if validate_isbn(isbn):
                all_correct = False
        self.assertTrue(all_incorrect)
        print(f'Testing Invalid ISBN-13...')
        all_incorrect = True
        for isbn in invalid_isbn_13:
            if validate_isbn(isbn):
                all_correct = False
        self.assertTrue(all_incorrect)

class FileConversionTests(TestCase):
    def testing_ffmpeg(self):
        '''testing_ffmpeg- ensures ffmpeg has the correct codecs to translate from mp3 to m4b'''
        
        print("testing parsing ffmpeg outputs and codec availability to input mp3")
        set_of_supported_file_extentions = get_ffmpeg_supported_inputs()
        self.assertTrue(".mp3" in set_of_supported_file_extentions)
        
        print("testing codec availability to output m4b")
        ffmpeg_muxer_details = subprocess.run(
            ["ffmpeg",          # application being invoked
             "-hide_banner",    # Removes copy right disclaimer from output
             "-muxers",         # Requests list of muxers  
            "|", "grep", "mp4"  # Returns the lines in the list that only contain mp4 
            ],
            capture_output=True,# Output the results of the command here instead of to stdout (the server console)
            text=True           # Output is a string instead of binary output.
        ).stdout                # store only the output of the subprocess
        
        self.assertTrue("mp4" in ffmpeg_muxer_details) # mp4 should exist in the output of the command