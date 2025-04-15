import threading
import time
import random
from forced_alignment import ForcedAlignment
from persistqueue import Queue
from Levenshtein import distance as edit_distance
import os
#these two imports have been moved down into file_conversion_worker() to prevent circular imports
#from library.controller import identify_file_type
#from library.controller import upload_and_save_book
from tqdm import tqdm
from wispar import settings
import subprocess
from django.core.files import File
use_align = settings.USE_ALIGN
from wispar.settings import MEDIA_ROOT
import numpy as np
job_queue = Queue(path=MEDIA_ROOT+"/job queue",tempdir =MEDIA_ROOT+"/job queue")

server_crashes_until_skip_task = 5

def start_worker():
    '''start_worker - starts a worker and watchdog threads'''
    threads = set()
    thread_set_lock = threading.Lock()
    job_queue_worker_thread = threading.Thread(target=job_queue_worker, name="job_queue_worker",daemon=True)
    threads.add(job_queue_worker_thread)
    file_conversion_worker_thread = threading.Thread(target=file_conversion_worker, name="file_conversion_worker",daemon=True)
    threads.add(file_conversion_worker_thread)
    watchdog_thread1 = threading.Thread(target=watchdog, args=(threads,thread_set_lock), name="watchdog",daemon=True)
    threads.add(watchdog_thread1)
    watchdog_thread2 = threading.Thread(target=watchdog, args=(threads,thread_set_lock), name="watchdog",daemon=True)
    threads.add(watchdog_thread2)
    for thread in threads:
        thread.start()

def job_queue_worker():
    '''job_queue_worker - executes all functions added to the job queue'''
    print("job queue worker started")
    task_failed_counter_directory = MEDIA_ROOT+"/crash_per_current_task_counter.npy"
    if os.path.exists(task_failed_counter_directory):
        server_restart_count = np.load(task_failed_counter_directory) 
    else:
        server_restart_count = 0
    server_restart_count+=1
    print(f"Server restarts during current task counter: {server_restart_count}")
    while True:
        if job_queue.empty():
            server_restart_count = 0 
        np.save(task_failed_counter_directory,server_restart_count)
        try:
            job, *args = job_queue.get()
            if server_restart_count<server_crashes_until_skip_task:
                result = job(*args)
                if result != None:
                    print(f"Worker {job}({args}) returned {result}. Results will not be handled")
            else:
                print(f"Server restarted more than {server_crashes_until_skip_task} times. Skipping {job}({args})")
        except Exception as e:
            print("Job Queue Worker Thread Exception:", e)
        finally:
            job_queue.task_done()
            server_restart_count=0

def get_ffmpeg_supported_inputs() -> set:
    """get_ffmpeg_supported_inputs - returns a set file extentions that ffmpeg accepts as inputs
        Returns:
            A set of strings. E.g. {".mp3",".m4a",".mov"}
    """
    ffmpeg_supported_demuxer_output = subprocess.run(
        ["ffmpeg",           # application being invoked
         "-hide_banner",     # Removes copy right disclaimer from output
         "-demuxers"         # Getting the formats that ffmpeg supports as inputs
        ],
        capture_output=True, # Output the results of the command here instead of to stdout (the server console)
        text=True            # Output is a string instead of binary output.
    ).stdout                 # store only the output of the subprocess
    #Example output
    """
     File formats:
     D. = Demuxing supported
     .E = Muxing supported
     --
     D  3dostr          3DO STR
     D  alias_pix       Alias/Wavefront PIX image
     D  amrnb           raw AMR-NB
     D  amrwb           raw AMR-WB
     D  anm             Deluxe Paint Animation
     D  aptx_hd         raw aptX HD
     D  aqtitle         AQTitle subtitles
     D  argo_asf        Argonaut Games ASF
     D  bethsoftvid     Bethesda Softworks VID
     D  bfi             Brute Force & Ignorance
     D  h263            raw H.263
     D  jpegxl_pipe     piped jpegxl sequence
     D  matroska,webm   Matroska / WebM
     D  mov,mp4,m4a,3gp,3g2,mj2 QuickTime / MOV
     D  mp3             MP2/3 (MPEG audio layer 2/3)
     D  mpc             Musepack"""
    lines = ffmpeg_supported_demuxer_output.splitlines()
    supported_demuxers = []
    for line in lines:
        line = line.strip()
        if line[0] != "D": # skip lines "File formats:", ".E = Muxing supported", and "--"
            continue
        elif line[1] != ".": #skip line " D. = Demuxing supported"
            supported_demuxers.extend(line.split()[1].split(",")) # take the entries in the second column, split them up by comma and add them to the list
    supported_input_extentions = set()
    print("Parsing ffmpeg for supported file formats")
    for demuxer in tqdm(supported_demuxers):
        ffmpeg_demuxer_details = subprocess.run(
            ["ffmpeg",                  # application being invoked
             "-hide_banner",            # Removes copy right disclaimer from output
             "-h", f"demuxer={demuxer}" # Requests additional data for the given demuxer  
            ],
            capture_output=True,        # Output the results of the command here instead of to stdout (the server console)
            text=True                   # Output is a string instead of binary output.
        ).stdout                        # store only the output of the subprocess

        #example output
        """Demuxer mov,mp4,m4a,3gp,3g2,mj2 [QuickTime / MOV]:
        Common extensions: mov,mp4,m4a,3gp,3g2,mj2,psp,m4b,ism,ismv,isma,f4v,avif.
    mov,mp4,m4a,3gp,3g2,mj2 AVOptions:
    -use_absolute_path <boolean>    .D.V....... allow using absolute path when opening alias, this is a possible security issue (default false)"""    
        
        for line in ffmpeg_demuxer_details.splitlines():
            line = line.strip()
            if line.startswith("Common extensions: "):
                line = line.removeprefix("Common extensions: ")
                extentions = line.split(",")
                extentions[-1] = extentions[-1][:-1] #remove the trailing "." e.g. "f4v,avif."
                for extention in extentions:
                    supported_input_extentions.add("."+extention) # prefix every extention with a "." because file_ext from  file_root, file_ext = os.path.splitext(dir_entry)  outputs extentions with "." such as ".mp3"

    return supported_input_extentions

def file_conversion_worker():
    '''file_conversion_worker - periodically looks through the uploaded media to see if there's unsupported media. If there is, it converts it to supported media and deletes the old copy'''
    from library.controller import identify_file_type
    from library.controller import upload_and_save_book
    from library.views import lock
    print("file conversion worker started")
    possible_image_extentions_for_covers = {".jpg", ".jpeg", ".jpe", ".jif", ".jfif", ".jfi", ".gif",".png", ".jp2", ".j2k", ".jpf", ".jpm", ".jpg2", ".j2c", ".jpc", ".jpx", ".mj2", ".webp", ".heif", ".heifs", ".heic", ".heics", ".avci", ".avcs",".hif", ".avif", ".jxl", ".tif", ".tiff", ".bmp", ".dip", ".pbm", ".pgm", ".ppm", ".pnm", "bpg", ".svg", ".svgz"}
    other_extentions = {"", ".cache", ".json", ".vtt", ".old", ".m4b", ".epub",".npy"}
    exclude_extention_from_search = other_extentions.union(possible_image_extentions_for_covers)
    valid_nonepub_ebook_extensions = {".azw", ".azw3", ".azw4", ".cbz", ".cbr", ".cb7", ".cbc", ".chm", ".djvu", ".docx", ".fb2", ".fbz", ".html", ".htmlz", ".kepub", ".lit", ".lrf", ".mobi", ".odt", ".pdf", ".prc", ".pdb", ".pml", ".rb", ".rtf", ".snb", ".tcr", ".txt", ".txtz"}
    valid_nonm4b_audiobook_extensions = get_ffmpeg_supported_inputs()
    been_checked = set()
    while True:
        time.sleep(5)
        try:
            directory = MEDIA_ROOT
            #chose random strings because it's highly unlikely a user would name their media this.
            temp_epub = directory+"/MW0VqNhRHVMMTp7RCvYtbgugfegimQUIoqZlLKr0DONOTNAMEYOURMEDIATHISORITWILLBEDELETED.epub"
            temp_m4b = directory+"/MW0VqNhRHVMMTp7RCvYtbgugfegimQUIoqZlLKr0DONOTNAMEYOURMEDIATHISORITWILLBEDELETED.m4b"
            if os.path.exists(temp_epub):
                os.remove(temp_epub)
            if os.path.exists(temp_m4b):
                os.remove(temp_m4b)

            for dir_entry in os.listdir(directory):
                old_file_root, old_file_ext = os.path.splitext(dir_entry)
                if old_file_ext.lower() not in exclude_extention_from_search:
                    if dir_entry not in been_checked:
                        been_checked.add(dir_entry)
                        old_path = "/".join([directory,dir_entry])
                        with open(old_path,"rb") as old_file_binary:
                            file_type = identify_file_type(File(old_file_binary))
                        if file_type != "audiobook" and file_type != "ebook":
                            if old_file_ext in valid_nonepub_ebook_extensions:
                                new_path = temp_epub
                                
                                subprocess.run(
                                    ["ebook-convert", old_path, new_path]
                                )
                            elif old_file_ext in valid_nonm4b_audiobook_extensions:
                                new_path = temp_m4b   
                                subprocess.run(
                                    ["ffmpeg",      # programm to run
                                     "-y",          # Yes to all prompts (yes to overwriting existing data in case the m4b by that name already exists)
                                    "-v","quiet",   # minimize output to reduce 
                                    "-i",old_path,  # input file
                                    "-c:a", "aac",  # using aac audio codec across all audio streams (should be just 1 stream because 1 file)  
                                    "-b:a", "64k",  # encode the bitrate to 64kbps (CD quality is 1.411 kbps). 
                                    "-vn",          # discard video if the file input is a video
                                    "-ar", "44.1k", # sets sample rate to 44.1 kHz. Won't use the same sample rate the alignment model is expecting because users will be hearing this and they probably don't want to hear 16 kHz quality.
                                    "-f","mp4",     # encode the output using the mp4 container. M4B audiobooks are structurally the same as an audio only mp4.
                                    new_path]       # 
                                )
                            else:
                                continue #skip entry if cannot be converted
                            
                            if os.path.exists(new_path):
                                with open(new_path,"rb") as new_file_binary:
                                    _, new_file_ext = os.path.splitext(new_path)
                                    new_file = File(file=new_file_binary,name = old_file_root+new_file_ext) #sets the name to be the old file root and the new file extention. E.g. "Alice_in_wonderland.epub"
                                    lock.acquire()
                                    try:
                                        upload_and_save_book(new_file)
                                    except Exception as e:
                                        print("file conversion upload error", e)
                                    finally:
                                        lock.release()
                                print(f"succesfully converted {old_file_root+old_file_ext} to {old_file_root+new_file_ext}")
                                os.remove(old_path)
                                os.remove(new_path) #deletes the temporary file made for the sake of the conversion
                            been_checked.remove(dir_entry) # no longer in directory so can be removed from check list
                        else:
                            print(f"Failed to convert {old_file_root+old_file_ext} to {old_file_root+new_file_ext}")
        except Exception as e:
            print("File Conversion Worker Thread Exception:",e)

def watchdog(threads,thread_set_lock):
    '''watchdog - restarts threads that die unexpectedly
        Args:
            threads - a set containing the threads to be restarted
            thread_set_lock - a semaphore to prevent multiple watchdogs from accessing the threads set at the same time
    '''
    print("watchdog started")
    while True:
        time.sleep(random.randint(5,15))
        thread_set_lock.acquire()
        dead_threads = []
        for thread in threads:
            if not thread.is_alive():
                print(f"{thread.getName()} has died!")
                dead_threads.append(thread)
        
        for dead_thread in dead_threads:
            threads.remove(dead_thread)
            if dead_thread.getName()=="watchdog":
                print("a watchdog starts a watchdog")
                new_watchdog_thread = threading.Thread(target=watchdog, args=(threads,thread_set_lock), name="watchdog",daemon=True)
                threads.add(new_watchdog_thread)
                new_watchdog_thread.start()
            elif dead_thread.getName()=="job_queue_worker":
                print("a watchdog starts a job queue worker")
                job_queue_worker_thread = threading.Thread(target=job_queue_worker, name="job_queue_worker",daemon=True)
                threads.add(job_queue_worker_thread)
                job_queue_worker_thread.start()
            elif dead_thread.getName()=="file_conversion_worker":
                print("a watchdog starts a file conversion worker")
                file_conversion_worker_thread = threading.Thread(target=file_conversion_worker, name="file_conversion_worker",daemon=True)
                threads.add(file_conversion_worker_thread)
                file_conversion_worker_thread.start()
        thread_set_lock.release()

def add_job_to_queue(function, args):
    '''
    add_job_to_queue - Adds a job to the job queue
        Args:
            function - function to be added to the job queue
            args - parameters to be passed into the function  
    '''
    job_queue.put((function,*args))

def cache_audiobook(book_path):
    '''
    cache_audiobook - caches emissions an audiobook for forced alignment processes
        Args:
            book_path - Path to the audiobook to be processes
    '''
    ForcedAlignment.get_emissions_from_audio(book_path)

def attempt_merge(saved_book, models_books_objects, default_storage, django_max):
    """
    attempt_merge - takes in a newly uploaded book and tries to match it with other books in library for forced alignment
    Args:
        saved_book : book object that was just uploaded
    """
    difference_tolerance = settings.EDIT_DISTANCE
    book_values_from_db = models_books_objects.exclude(bookId=1).values_list('bookId', 'title', 'author', 'medium', 'filefield')
    mediums_calculated = []
    lowest_diff = None
    closest_id = 0

    for bookId, title, author, medium, filefield in book_values_from_db:
        diff = calculate_difference(saved_book.title,title,saved_book.author, author)
        # switch choice if a better match is found and is within tolerance
        if diff <= difference_tolerance:
            ebook_audiobook_pairing = saved_book.medium == "ebook" and medium == "audiobook"
            audiobook_ebook_pairing = saved_book.medium == "audiobook" and medium == "ebook"
            #skip cases where the media are the same type or one of the media is an invalid type
            if not (ebook_audiobook_pairing or audiobook_ebook_pairing):
                print(f"skipping {saved_book.title}({saved_book.medium}) and {title}({medium}). ")
                continue
            else:# (saved_book.medium == "ebook" and medium == "audiobook") or (saved_book.medium == "audiobook" and medium == "ebook")
                print(f"attempting matches for {saved_book.title}({saved_book.medium}) and {title}({medium})")
                if ebook_audiobook_pairing:
                    ebook_path = default_storage.path(saved_book.filefield.name)
                    audiobook_path = default_storage.path(filefield)
                elif audiobook_ebook_pairing:
                    ebook_path = default_storage.path(filefield)
                    audiobook_path = default_storage.path(saved_book.filefield.name)
                #TODO: Figure out how to skip alignment when a vtt exists (prevents double alignment attempts when media is uploaded seperately e.g. (audiobook1 audiobook2), (ebook2). Such a grouping will make book2 have 2 alignment attempts). Keeping this code causes books to have the same bookID but have 0 in the linked_medium section
                #print("audiobook_path",audiobook_path)
                #vtt_path = get_vtt_path(audiobook_path)
                #print("vtt_path",vtt_path)
                #try:
                #    if os.path.exists(vtt_path):
                #        print(f"VTT already Made. Skipping {saved_book.title}({saved_book.medium}) and {title}({medium}). ")
                #        continue
                #except:
                #    ...

                spine_items = ForcedAlignment.load_spine_html(ebook_path)
                all_cfi_word_pairs = []
                print("generating cfis")
                for idx, item_id, html_str in spine_items:
                    pairs = ForcedAlignment.build_word_cfis_for_spine_item(
                        spine_index=idx,
                        item_id=item_id,
                        html_str=html_str,
                        ignore_classes_or_ids=["pg-footer", "pg-header", "pg-header-heading", "pg-title-no-subtitle", "pg-machine-header"]
                    )
                    all_cfi_word_pairs.extend(pairs)

                if not settings.USE_ALIGN:
                    if lowest_diff is None:
                        lowest_diff = diff
                        closest_id = bookId
                    elif diff < lowest_diff:
                        lowest_diff = diff
                        closest_id = bookId
                    
                elif settings.USE_ALIGN:
                    spine_items = ForcedAlignment.load_spine_html(ebook_path)
                    all_cfi_word_pairs = []
                    print("generating cfis")
                    for idx, item_id, html_str in spine_items:
                        pairs = ForcedAlignment.build_word_cfis_for_spine_item(
                            spine_index=idx,
                            item_id=item_id,
                            html_str=html_str,
                            ignore_classes_or_ids=["pg-footer", "pg-header", "pg-header-heading", "pg-title-no-subtitle", "pg-machine-header"]
                        )
                        all_cfi_word_pairs.extend(pairs)

                    confidence_score, vtt_text, json_text = ForcedAlignment.gen_VTT_by_CFIs(audiobook_path,all_cfi_word_pairs)
                    mediums_calculated.append((bookId, title, author, medium, filefield, confidence_score, vtt_text, json_text))
                    
    if not settings.USE_ALIGN:
        if lowest_diff is not None:
            link_books(saved_book, closest_id, models_books_objects)
        return

    confidence_match_threshold = ForcedAlignment.confidence_match_threshold
    medium_calculated_index = 0
    match_found = False
    best_guess = (None,float("-inf"))
    for medium in mediums_calculated:
        confidence_score = medium[5]
        
        #if book found was deleted during alignment, don't merge with it
        candidate_path = default_storage.path(medium[4])  
        if not os.path.exists(candidate_path):
            continue

        if confidence_match_threshold < confidence_score:
            match_found = True
            if best_guess[1] < confidence_score:
                best_guess = (medium_calculated_index,confidence_score)
        else:
            medium_calculated_index += 1
    if saved_book.linked_medium:
        unlink_book(saved_book.bookId, models_books_objects, django_max)

    if match_found:
        new_book_id = mediums_calculated[best_guess[0]][0]
        vtt = mediums_calculated[best_guess[0]][6]
        json = mediums_calculated[best_guess[0]][7]
        
        #If book being aligned gets deleted during alignment, don't merge.
        if not os.path.exists(default_storage.path(saved_book.filefield.name)):
            return
        
        # This assumes there is NOT duplicate text or audio versions, we will need more robust parsing if/when we allow that
        if saved_book.medium == "audiobook":
            current_medium_file_path = default_storage.path(saved_book.filefield.name)
            vtt_save_file_path = get_vtt_path(current_medium_file_path)
            json_save_file_path = get_json_path(current_medium_file_path)
        elif mediums_calculated[best_guess[0]][3] == "audiobook":
            new_medium_file_path = default_storage.path(mediums_calculated[best_guess[0]][4])
            vtt_save_file_path = get_vtt_path(new_medium_file_path)
            json_save_file_path = get_json_path(new_medium_file_path)
        else:
            print("This edge case should never be encountered since at least one of the media would need to be an audiobook")
            return

        ForcedAlignment.write_string_to_file(vtt,vtt_save_file_path)
        ForcedAlignment.write_string_to_file(json,json_save_file_path)
        
        link_books(saved_book, new_book_id, models_books_objects)
    else:
        if saved_book.linked_medium:

            unlink_book(saved_book.bookId, models_books_objects, django_max)

def get_vtt_path(audiobook_path):
    """
    get_vtt_path : takes in the audiobook path and returns the vtt path
    Args:
        audiobook_path : path to audiobook
    Returns:
        string with the path to the vtt
    """
    file_root, file_ext = os.path.splitext(audiobook_path)
    return str(file_root) + ".vtt"

def get_json_path(audiobook_path):
    """
    get_json_path : takes in the audiobook path and returns the json path
    Args:
        audiobook_path : path to audiobook
    Returns:
        string with the path to the json
    """
    file_root, file_ext = os.path.splitext(audiobook_path)
    return str(file_root) + ".json"

def calculate_difference(title1 :str, title2: str, author1:str, author2:str)->int:
    """
    calculate_difference - Takes in a pair of titles and authors for a given media (ebook, audiobook) and returns the sum of 
    the Levenshtein edit distance for a normalized string representation of the title and, if given, the author. 
    Args:
        title1: title of the media
        title2: title of the media to compare (can be Unknown)
        author1: author of the media
        author2: author of the media to compare (can be Unknown)
    Returns:
        int ID that is the added edit distance between parameters 
    """
    # set to lowercase and remove any characters from string that are not in alphabet of accepted characters
    normalize = lambda strin : "".join([ (char if char.isalpha() else "")  for char in strin.lower()])
    total_diff = 0
    total_diff += edit_distance(normalize(title1),normalize(title2))
    
    if author1 and author2 and author1 != "Unknown" and author2 != "Unknown":
        total_diff += edit_distance(normalize(author1),normalize(author2))

    return total_diff

def link_books(saved_book, new_book_id, models_books_objects):
    """
    link_books - Takes in a save_book and links it to an existing book_id
    Args:
        saved_book: book to be linked to new_book_id
        new_book_id: book_id of existing medium to link the saved_book to
    """
    saved_book.bookId = new_book_id
    saved_book.linked_medium=True
    saved_book.save()
    mediums_updated = models_books_objects.filter(bookId=new_book_id).update(linked_medium=True)
    if mediums_updated != 2:
        print(f"Unexpected case when linking books. Encountered {mediums_updated} instead of 2. New book_id is {new_book_id}")
def unlink_book(book_id, models_books_objects, django_max):
    """
    unlink_book - Takes in a book_id and unlinks all mediums associated with given book_id
    Args:
        book_id: book_id of mediums to be unlinked
    """
    #Mark all books with book_id unlinked
    num_of_fields_updated = models_books_objects.filter(bookId=book_id).update(linked_medium=False)
    if num_of_fields_updated != 2:
        print(f"Unexpected case when unlinking books. Encountered {num_of_fields_updated} instead of 2. Old book_id is {book_id}")
    
    #Renumber the newly unlinked mediums, leaving only one element with the original book_id 
    keep_id = True
    book_values_from_db = models_books_objects.filter(bookId=book_id).values_list('id', 'medium', 'filefield')
    for element_id , medium, filefield in book_values_from_db:
        if medium == "audiobook":
            file_root, file_ext = os.path.splitext(filefield)
            vtt_save_file = str(file_root) + ".vtt"
            json_save_file = str(file_root) + ".json"
            try:
                os.remove(vtt_save_file)
            except FileNotFoundError:
                #no vtt to remove. Can happen when when books with identical name and author fail to align 
                pass
            try:
                os.remove(json_save_file)
            except FileNotFoundError:
                #no json to remove. Can happen when when books with identical name and author fail to align 
                pass
        if keep_id:
            keep_id = False
            continue
        else:
            highest_bookid = models_books_objects.aggregate(django_max('bookId'))['bookId__max']
            models_books_objects.filter(id=element_id).update(bookId=highest_bookid)