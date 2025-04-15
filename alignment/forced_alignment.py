import torch
import torchaudio
import os
import uroman
from tqdm import tqdm
import nltk
nltk.data.path.append("/app/nltk_data")
from nltk.corpus import stopwords
from Levenshtein import distance as edit_distance
from Levenshtein import ratio as string_similarity
from num2words import num2words
#See for more details: https://pytorch.org/audio/stable/generated/torchaudio.pipelines.MMS_FA.html
from torchaudio.pipelines import MMS_FA as bundle # Get pretrained multi-language model
import numpy as np
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString

'''
ForceAlignment - stores functions used to align text to audio
'''
class ForcedAlignment:
    confidence_match_threshold = 0.80

    #skip attempt to align chapter if smaller than this
    smallest_permitted_chapter_word_count = 50
    
    #split chapters that contain more words than this
    max_chunk_word_count = 3000
    
    # Reference Material November 11, 2024 - https://pytorch.org/audio/main/tutorials/forced_alignment_tutorial.html
    #                                      - https://pytorch.org/audio/stable/tutorials/forced_alignment_for_multilingual_data_tutorial.html
    #                    January  20, 2025 - https://pytorch.org/audio/stable/tutorials/speech_recognition_pipeline_tutorial.html

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu" ) # use GPU if available
    model = bundle.get_model(with_star=False).to(device)             # use pretrained model from MMS_FA
    model = bundle.get_model(with_star=False).to(device)             # use pretrained model from MMS_FA
    tokenizer = bundle.get_tokenizer()
    aligner   = bundle.get_aligner()
    labels    = bundle.get_labels(star=None)
    model_sample_rate = bundle.sample_rate
    stopwords = set(stopwords.words("english"))
    
    def resample_waveform(waveform :torch.tensor, old_sample_rate :int, chunk_size = 16000):
        '''
        resample_waveform - resamples the waveform to match the model bundle waveform and deletes old waveform and uses chunking to make it more memory efficient
        Args:
            waveform - waveform tensor to resample and delete
            old_sample_rate - existing sample rate of the waveform 
            chunk_size - size of each chunk used to resample the waveform
        Return:
            the resampled waveform tensor 
        '''
        new_waveform_chunks = []
        print("Resampling audio")
        number_of_chunks = waveform.shape[1]//chunk_size + 1
        for chunk_index in tqdm(range(number_of_chunks)):
            new_waveform_chunk = waveform[:,chunk_index*chunk_size:(chunk_index+1)*chunk_size]
            new_waveform_chunks.append(torchaudio.functional.resample(new_waveform_chunk,old_sample_rate,ForcedAlignment.model_sample_rate))
        del waveform
        return torch.cat(new_waveform_chunks, dim=1) 
    
    def get_emissions_from_audio(audio_file_path, use_cache = True):
        '''
        get_emissions_from_audio - takes in an file path for audio, processes the audio with an ML model
            and turns it to a result the aligner can process and caches the results. It also returns the waveform size
        Args:
            audio_file_path - string containing the filepath to the audiofile
            use_cache - if true, reads and writes to ".emissions" file in preprocessing directory 
        Returns:
            returns tuple of emissions from the model that the aligner can use along with the audiowaveform and a waveform size
            i.e. emissions, waveform_size
        '''
        if use_cache:
            preprocessing_audio_file_path_prefix, _ = os.path.splitext(audio_file_path)
            emissions_save_file = preprocessing_audio_file_path_prefix + "_emissions.cache"
            waveform_size_save_file = preprocessing_audio_file_path_prefix + "_waveformsize.cache"
            preprocessing_audio_file_path_prefix, _ = os.path.splitext(audio_file_path)
            emissions_save_file = preprocessing_audio_file_path_prefix + "_emissions.cache"
            waveform_size_save_file = preprocessing_audio_file_path_prefix + "_waveformsize.cache"
            if os.path.exists(emissions_save_file) and not os.path.exists(waveform_size_save_file):
                waveform, sample_rate = torchaudio.load(audio_file_path) # has ffmpeg and Sox system calls built-in
                waveform = waveform.to(ForcedAlignment.device)
                if sample_rate != ForcedAlignment.model_sample_rate:
                    waveform = ForcedAlignment.resample_waveform(waveform,sample_rate)
        
                torch.save(waveform.size(1),waveform_size_save_file)

            if os.path.exists(emissions_save_file):
                return torch.load(emissions_save_file,weights_only=False).to(ForcedAlignment.device), torch.load(waveform_size_save_file,weights_only=False)
        
        #used for chunking audio. Constants given should be roughly 2 minutes of audio at a time with a 20 second context overlap.  
        context_size = 480128 # 2 minutes?
        context_overlap = 80021 # 20 seconds?
        assert(context_overlap<context_size)
        
        waveform, sample_rate = torchaudio.load(audio_file_path)  # has ffmpeg and Sox system calls built-in
        waveform = waveform.to(ForcedAlignment.device)
        if sample_rate != ForcedAlignment.model_sample_rate:
            waveform = ForcedAlignment.resample_waveform(waveform,sample_rate)
        
        with torch.inference_mode(): # Use model with promise of not training it (for performance reasons)
            emissions = []
            first_pass = True
            print("Processing audiofile")
            for waveform_index in tqdm(range(0,waveform.size(1),int(context_size))):
                start_of_waveform = int(waveform_index - ( context_overlap if not first_pass else 0))
                end_of_waveform = int(waveform_index + context_size + context_overlap)
                waveform_to_process = waveform[:, start_of_waveform : end_of_waveform]
                emissions_to_process , _ = ForcedAlignment.model(waveform_to_process)
                waveform_to_emisison_coefficent = emissions_to_process.size(1)/waveform_to_process.size(1)
                emission_start = (int(waveform_to_emisison_coefficent*context_overlap) if not first_pass else 0)
                emission_end = emission_start + int(waveform_to_emisison_coefficent*context_size)
                trimmed_emissions = emissions_to_process[:,emission_start:emission_end]
                emissions.append(trimmed_emissions)
                if first_pass:
                    first_pass = False
            
            emissions  = torch.cat(emissions,dim=1)
            
            if use_cache:
                torch.save(emissions,emissions_save_file)
                torch.save(waveform.size(1),waveform_size_save_file)
            return emissions, waveform.size(1)

    def remove_chapter_headers(cfi_and_words: list) -> list:
        '''
        remove_chapter_headers - takes in list of cfi word pairings removes repeated text from
            the beginning of each chapter
        Args:
            cfi_and_words - A list of tuples of strings of cfi and word
        Returns:
            returns A list of tuples of a cfi string and word string
        '''
        how_many_words_to_check = 20
        word_counter = {}
        old_chapter_marker = None
        words_checked = 0
        chapters_counted =0
        word_tracker = {}
        for cfi, word in cfi_and_words:
            current_chapter_marker = ForcedAlignment.chapter_marker_from_cfi(cfi)
            if old_chapter_marker != current_chapter_marker:
                words_checked = 0
                old_chapter_marker = current_chapter_marker
                chapters_counted+=1
                word_tracker = {}
            
            if words_checked <= how_many_words_to_check:
                if word.lower() not in ForcedAlignment.stopwords:
                    if word not in word_tracker:
                        if word in word_counter:
                            word_counter[word]+=1
                        else:
                            word_counter[word]=1
                        word_tracker[word] = 1
        
        #Remove all words before some word that occurs this many times across per chapter 
        delete_preceding_text_if_exceeds = 2*len(cfi_and_words)//3
        clean_if_more_chapters_than = 4
        words_checked = 0
        new_cfi_and_words = []
        header_candidate = []
        old_chapter_marker = None

        for cfi, word in cfi_and_words:
            current_chapter_marker = ForcedAlignment.chapter_marker_from_cfi(cfi)
            if old_chapter_marker != current_chapter_marker:
                old_chapter_marker = current_chapter_marker
                words_checked = 0
            
            words_checked += 1
            if words_checked == how_many_words_to_check:
                new_cfi_and_words += header_candidate
                header_candidate = []
            if words_checked < how_many_words_to_check:
                if word.lower() in word_counter and word_counter[word.lower()]>delete_preceding_text_if_exceeds and clean_if_more_chapters_than < chapters_counted:
                    header_candidate = []
                else:
                    header_candidate.append((cfi, word))
            else:
                new_cfi_and_words.append((cfi, word))
        
        #for the edge case where the last chapter is less than 20 words.
        new_cfi_and_words += header_candidate
        
        return new_cfi_and_words

    #TODO: Fix "replace_numbers_with_text". Sometimes returns decimal.conversionsytax exceptions
    def preprocess_transcript(cfi_word_pairs: list, replace_numbers_with_text = False) -> list:
        '''
        preprocess_transcript - takes in a list of cfis and words and returns the 
            list of cfis with words that the forced alignemnt model can recognize (latin alphabet).
            removed text that is known to not be part of the audiobook. 
        Args:
            cfi_word_pairs - list of cfi and words
        Returns:
            List of cfi and preprocessed words
        '''
        preprocessed_cfi_word_pairs = []
        uroman_text_processor = uroman.Uroman()
        for cfi, word in tqdm(cfi_word_pairs):
            word = uroman_text_processor.romanize_string(word)
            if replace_numbers_with_text:
                digits = []
                new_word = []
                digit_mode = False
                for char in word:
                    if not digit_mode:
                        if char.isdigit():
                            digit_mode=True
                        else:
                            new_word.append(char)

                    if digit_mode:
                        if char.isdigit() or char ==".":
                            digits.append(char)
                        else:
                            number_string = "".join(digits)
                            if number_string[-1]==".":
                                number_string = number_string[:-1]
                                new_word.append(num2words(number_string))
                                new_word.append(".")
                            else:
                                new_word.append(num2words(number_string))
                            digits.clear()
                            digit_mode = False
                            new_word.append(char)    
                word = "".join(new_word)
                
            word = word.lower()
            #replace right single quotation mark with apostrophe
            word = word.replace("’","'")
            #replace left single quotation mark with apostrophe
            word = word.replace("‘","'")
            #replace right double quotation mark with two apostrophes
            word = word.replace("”","''")
            #replace left double quotation mark with two apostrophes
            word = word.replace("“","''")

            #replace dashes with spaces since the bundle already uses dashes to represent something else
            word = word.replace("-"," ")

            word = "".join([char if char in ForcedAlignment.labels else " " for char in word])
            word_list = word.split()
            for word in word_list:
                preprocessed_cfi_word_pairs.append((cfi, word))

        return preprocessed_cfi_word_pairs

    #TODO: add a case to handle chapters that have the same start and end since these lead to false positives of chapters, which leads to the false positives failing to match and getting excluded 
    #TODO: Determine how to handle if audiobook and ebook chapters are out of order of each other.
    #TODO: add checks for out of order audio
    #TODO?: add padding to audio emissions in case edit distance trimming removes last word 
    def match_cfi_chunks_to_emissions(emissions :torch.Tensor, preprocessed_cfi_word_chunks :list, span_to_timestamp ) -> list[tuple]:
        '''
        match_cfi_chunks_to_emissions - Takes in the emisssions of an audiobook and a 
            list of cfis and words to try to match to the audiobook. It then returns a list of 
            audio emissios offsets and the associated chapter it matched to, discarding 
            any chapters that do not have a match to the audio.
        Args:
            emissions - emisssions generated from the audiobook
            preprocessed_cfi_word_chunks - list of list of cfi and words to match to the emisssions
            span_to_timestamp - function to convert a span offset into human readable time 
        Returns:
            List of tuples containing (audio emission for the transcipt, the number of seconds into the entire audiobook the chapter starts, and their associated cfi_word chunk
        '''
        
        # Take the emissions and find which letters are associated with the emission at each point slice of audio (indicies are mapped associated with specific letters)
        greedy_token_indicies = torch.flatten(torch.argmax(emissions,dim=-1))
        #find where letters are associated and skip over where there are no letters in the audio. More technically, assume emission None token is mapped to 0
        indicies_of_clean_tokens_indicies = torch.where(greedy_token_indicies)[0]
        #these are the indicies (to map to letters) of the slices of audio that have letters associated with them
        cleaned_tokens_indicies = greedy_token_indicies[indicies_of_clean_tokens_indicies]
        #These are the letters in the audio
        labeled_tokens = [ForcedAlignment.labels[index] for index in cleaned_tokens_indicies]
        
        #converting the letters into a string 
        characters_from_audio = "".join(labeled_tokens)

        #how many characters should be in the search window context of both mediums
        context_window_size = 100
        
        emissions_and_time_offsets_and_good_chapters = []
        print("Finding audiobook-ebook offsets")
        
        
        number_of_cfi_word_chunks = len(preprocessed_cfi_word_chunks)
        #this loop searches for the word chunks in the audio
        for cfi_word_chunk_index in tqdm(range(number_of_cfi_word_chunks)):
            #turns the transcript (list of words) into a single string. No spaces are present in final string because the list of words were sepearted based on white space
            characters_from_transcript = "".join([word for cfi, word in preprocessed_cfi_word_chunks[cfi_word_chunk_index] ] )
            #find the characters in the transcript that are not commas since commas are not reliably outputed by the audio module. These will also be needed to map back to the transcipt after an offset between audio and text is found.
            #TODO?: Remove possibly redudant white space checking removal
            indicies_of_valid_labels_from_transcript = [index for index in range(len(characters_from_transcript)) if characters_from_transcript[index] != "'" and characters_from_transcript[index] != " "]
            #Removing the spaces from the trasncript since spaces are not present in audio slices 
            cleaned_spaceless_transcript = "".join( [characters_from_transcript[index] for index in indicies_of_valid_labels_from_transcript])
            
            start_of_chapter_text = cleaned_spaceless_transcript[:context_window_size]
            end_of_chapter_text = cleaned_spaceless_transcript[-context_window_size:]
            
            audio_chapter_starts = ForcedAlignment.get_audiobook_offset(start_of_chapter_text,characters_from_audio)
            audio_chapter_ends = ForcedAlignment.get_audiobook_offset(end_of_chapter_text,characters_from_audio)+context_window_size
            audio_chapter_text = characters_from_audio[audio_chapter_starts:audio_chapter_ends]
            chapter_integrity = string_similarity(cleaned_spaceless_transcript,audio_chapter_text)
            if chapter_integrity > ForcedAlignment.confidence_match_threshold:
                emissions_start_index = indicies_of_clean_tokens_indicies[audio_chapter_starts]
                audio_chapter_ends = min(audio_chapter_ends,len(indicies_of_clean_tokens_indicies)-1)
                emissions_end_index = indicies_of_clean_tokens_indicies[audio_chapter_ends]
                chapter_emission =  emissions[:,emissions_start_index:emissions_end_index]
                emissions_and_time_offsets_and_good_chapters.append( (chapter_emission,span_to_timestamp(emissions_start_index),preprocessed_cfi_word_chunks[cfi_word_chunk_index]))
        
        return emissions_and_time_offsets_and_good_chapters

    
    def chunk_text(preprocessed_cfi_word_pairs):
        '''
        chunk_text - takes in a list of cfi and words and splits them up by chapters and 
            splits those chapters up smaller in case they're too large, and removes chapters that are extremely small.
        Args:
            preprocessed_cfi_word_pairs - list of cfi and word pairs 
        Returns:
            List of list of cfi and word pairs chunked by chapter and split up large chapters 
        '''
        

        cfi_text_chunks = []
        current_chunk = []
        previous_chapter_marker = ForcedAlignment.chapter_marker_from_cfi(preprocessed_cfi_word_pairs[0][0])
        #chunks into chapters
        for cfi, word in tqdm(preprocessed_cfi_word_pairs):
            current_chapter_marker = ForcedAlignment.chapter_marker_from_cfi(cfi)
            if current_chapter_marker != previous_chapter_marker:
                previous_chapter_marker = current_chapter_marker
                cfi_text_chunks.append(current_chunk)
                current_chunk = []
            current_chunk.append((cfi,word))
        cfi_text_chunks.append(current_chunk)
        
        #skip small chapters (<50 words)
        new_cfi_text_chunks = []
        for chunks in cfi_text_chunks:
            if ForcedAlignment.smallest_permitted_chapter_word_count <= len(chunks):
                new_cfi_text_chunks.append(chunks)

        cfi_text_chunks = new_cfi_text_chunks
        
        #split large chapters apart (>3000 words)
        new_cfi_text_chunks = []
        for chunk in cfi_text_chunks:
            #these calculations are to ensure each chunk recieves nearly the same number of words 
            if len(chunk) < ForcedAlignment.max_chunk_word_count:
                new_cfi_text_chunks.append(chunk)
            else:
                #Note: These commented "e.g." values are not the actual values. They are used to help demonstrate what the logic is doing.
                #e.g. 4                        = 12523               // 4000                + 1
                number_of_chunks_to_split_into = len(chunk)//ForcedAlignment.max_chunk_word_count + 1
                #e.g. 3130 =  12523     // 4
                chunk_size = len(chunk) // number_of_chunks_to_split_into

                new_chunks = [
                    #e.g. chunk[0,3130] ,chunk[3130,6260],chunk[6260,9390]
                    chunk[
                        sub_chunk_index     * chunk_size:
                        (sub_chunk_index+1) * chunk_size
                        ] 
                        for sub_chunk_index in range(number_of_chunks_to_split_into-1)
                    ]
                #e.g.             current_chunk[                               9390         ,remaining values]
                new_chunks.append(chunk[number_of_chunks_to_split_into-1* chunk_size:                ])
                new_cfi_text_chunks += new_chunks

        return new_cfi_text_chunks

    def chapter_marker_from_cfi(cfi):
        '''
        chapter_marker_from_cfi - given a cfi will return a string denoting the chapter header
        Args:
            cfi - string representing the cfi
        Returns:
            substring of the cfi that denotes the chapter
        '''
        cfi_markers = cfi.split("/")
        return cfi_markers[2]

    def get_audiobook_offset(characters_from_text,characters_from_audio) -> int:
        '''
        get_audiobook_offset - Given a snippet of text and a large selection of noisy text, returns
        how far into the large selection of text the snippet of text starts, using
            fuzzy matching.
        Args:
            characters_from_text - snippet of text to be looked for
            characters_from_audio - a large string that is being search through
        Returns:
            Integer representing the offset of how far into the characters_from_audio the characters_from_text is found
        '''
        context_size = len(characters_from_text)
        distances = [edit_distance(characters_from_text,characters_from_audio[offset:offset+context_size]) for offset in range(len(characters_from_audio)-context_size)]
        offset = int(np.argmin(distances))
        offset = int(np.argmin(distances))
        return offset
    
    def gen_VTT_by_CFIs(audio_file_path : str, cfi_word_pairs : list):
        '''
        gen_VTT_by_CFIs - creates a VTT text given an audio file and list of cfi word pairs broken up into smaller processiable chunks,
        preferably by chapter or where the chapter was too large.
        Args:
            audio_file_path - the path to the audio file
            cfi word pairs - list of list of cfi word pairs that has been broken down into chunks. e.g. Each chunk is a chapter.
        Returns:
            tuple of 
                (float representing average confidence across all words in transcript,
                text to be written to a vtt file)
        '''

        emissions, waveform_size = ForcedAlignment.get_emissions_from_audio(audio_file_path)
        #Get emissions from each channel putting forth the highest confidence from each channel. If someone speaks in the left earm and then someone speaks in the right, we want the confidence from both to be processed and on the same channel.
        emissions = torch.max(emissions, dim=0,keepdim=True)[0]
        waveform_emission_ratio = waveform_size/emissions.size(1)  #Used to convert emission frame counts to timestamps
        span_to_timestamp = lambda span: (waveform_emission_ratio*span)/ForcedAlignment.model_sample_rate
        cfi_word_pairs = ForcedAlignment.remove_chapter_headers(cfi_word_pairs)
        print("Preprocessing text")
        preprocessed_cfi_word_pairs = ForcedAlignment.preprocess_transcript(cfi_word_pairs)
        print("chunking text")
        preprocessed_cfi_word_chunks = ForcedAlignment.chunk_text(preprocessed_cfi_word_pairs)
        print("matching text to emissions")
        audiobook_emissions_by_chapter_and_chunks_of_cfi_word_parings = ForcedAlignment.match_cfi_chunks_to_emissions(emissions, preprocessed_cfi_word_chunks,span_to_timestamp)
        print("Aligning audiobook and ebook")
        results = []
        for index in tqdm(range(len(audiobook_emissions_by_chapter_and_chunks_of_cfi_word_parings))):
            try:
                emission, time_offset, cfi_word_chunk = audiobook_emissions_by_chapter_and_chunks_of_cfi_word_parings[index]
                results.append((ForcedAlignment.align_cfi_word_chunk_and_emissions(cfi_word_chunk,emission,span_to_timestamp),time_offset))
            except Exception as e:
                print("Alignment Exception:",e)
                
        processed_results = []
        for chapter_index in range(len(results)):
            try:
                scores = [tuple[3] for tuple in results[chapter_index][0]]
                average_score = sum(scores)/len(scores)
                if average_score < ForcedAlignment.confidence_match_threshold:
                    continue

                time_offset = results[chapter_index][1]
                for tuple in results[chapter_index][0]:
                    cfi, word = tuple[0] #from cfi word list
                    seconds_start = float(tuple[1] + time_offset)
                    seconds_end   = float(tuple[2] + time_offset)
                    score = tuple[3]
                    processed_results.append((cfi,word,seconds_start,seconds_end,score))
                time_offset += seconds_start
            except Exception as e:
                print("vtt generation error:",e)
        try:
            average_confidence,vtt_text, json_text = ForcedAlignment.gen_VTT_txt(processed_results)
        except Exception as e:
            print("vtt generation error:",e)
            average_confidence = 0
            vtt_text = ""
        return average_confidence, vtt_text, json_text
    
    def align_cfi_word_chunk_and_emissions(cfi_word_chunk, emissions, span_to_timestamp):
        ''' 
        align_cfi_word_chunk_and_emissions - takes in list of cfi and words and emissions and returns a list of tuples containing the alignment of the text to the emissions.
        Args:
            cfi_word_chunk - list of cfi and words to be aligned to the audio
            emissions - emissions representation of the audio
            span_to_timestamp - function to map emissions offset to human readable time
        Returns:
            List of tuples containing (efi_word pairing tuple,
                            time start,
                            time stop,
                            confidence score)
        '''
        words = [word for cfi, word in cfi_word_chunk]
        token_spans = ForcedAlignment.aligner(emissions[0],ForcedAlignment.tokenizer(words)) 
        assert len(token_spans) == len(cfi_word_chunk)
        #TODO?: check condition of where there are no results length of span is zero
        # span is a list of TokenSpans, where each token in the span recieves a confidence score from the model.
        average_token_score_per_span = lambda span : sum([token.score for token in span])/len(span)

        return [(efi_word,span_to_timestamp(span[0].start),span_to_timestamp(span[-1].end),average_token_score_per_span(span) )  for efi_word,span in zip(cfi_word_chunk,token_spans)]


    def format_time(seconds)->str:
        '''
        format_time - takes in seconds and returns VTT compliant hours:minutes:seconds.milliseconds formatting
        Args:
            seconds - float value in seconds
        Returns:
            string representation seconds in VTT compliant format    
        '''
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        milliseconds = int(round((secs - int(secs)) * 1000))
        return f"{hours:02d}:{minutes:02d}:{int(secs):02d}.{milliseconds:03d}"

    def write_string_to_file(text: str, out_vtt_file_path):
        '''
        write_string_t_file - creates a file given a text and a write file location. Is a wrapper that writes text to a given file path 
        Args:
            vtt_text - text to be written to the vtt file
            out_vtt_file_path - the path to write the VTT file to
        '''

        with open(out_vtt_file_path, 'w') as f_out:
            f_out.write(text)

    def gen_VTT_txt(results):
        '''
        gen_VTT_txt - creates a VTT file given alignment data, and a corrisponding json mapping
        Args:
            results - results from alignment already done that need a VTT. 
        Returns:
            Tuple of float representing average confidence across all words in transcript, vtt text, and json text
        '''
        #list[(cfi,word_1,seconds_start,seconds_end,score))]
        vtt_text_list =[]
        json_text_list = []
        vtt_text_list.append('WEBVTT\n\n')
        for result in results:
            cfi = result[0]
            word = result[1]
            start_time = result[2]
            end_time = result[3]
            formatted_start = ForcedAlignment.format_time(start_time)
            formatted_end = ForcedAlignment.format_time(end_time)
            vtt_text_list.append(f"NOTE {word}\n\n")
            vtt_text_list.append(f"{formatted_start} --> {formatted_end}\n")
            vtt_text_list.append(f"{cfi}\n\n")
            json_text_list.append(f'"{cfi}" : {start_time}')
        if len(results) != 0:
            average_confidence = sum([result[4] for result in results])/len(results)
        else:
            average_confidence = 0
        
        json_text = "{\n\t"+",\n\t".join(json_text_list) + "\n}"

        vtt_text = "".join(vtt_text_list)
        return average_confidence, vtt_text, json_text

    def load_spine_html(epub_path):
        """
        Return a list of (spine_index, item_id, html_string) for each item in the spine.
        """
        book = epub.read_epub(epub_path)
        spine = book.spine  # e.g. [("chap01", {}), ("chap02", {}), ...]

        results = []
        for idx, (idref, _) in enumerate(spine):
            item = book.get_item_with_id(idref)
            if not item:
                continue
            html_content = item.content  # bytes
            html_text = html_content.decode("utf-8", errors="ignore")
            results.append((idx, idref, html_text))
        return results


    def build_word_cfis_for_spine_item(spine_index, item_id, html_str, ignore_classes_or_ids=None):
        """
        Parse a single spine item and return a list of (full_cfi, word).

        Example of full_cfi:
        epubcfi(/6/24[html1]!/4/8/13:57)
        """

        soup = BeautifulSoup(html_str, "html.parser")

        # Remove <script> and <style> tags entirely
        for tag in soup.find_all(["script", "style"]):
            tag.decompose()

        # Convert ignore_classes_or_ids to a set if needed (for faster membership checks)
        if ignore_classes_or_ids is None:
            ignore_classes_or_ids = set()
        elif not isinstance(ignore_classes_or_ids, (list, set)):
            ignore_classes_or_ids = {ignore_classes_or_ids}
        else:
            ignore_classes_or_ids = set(ignore_classes_or_ids)

        # Identify the <html> element or fallback to the entire soup
        html_el = soup.find("html") or soup

        # epub.js seems to count <html> as step "/2"
        if html_el.has_attr("id"):
            root_step = f"2[{html_el['id']}]"
        else:
            root_step = "2"

        # This will hold the final list of (partial_cfi, word) we first build,
        # which we then transform into full CFIs.
        word_level_cfis = []

        def add_word_range(cfi_path, start_offset, word):
            """
            Build a partial range CFI of the form:
                /4/2[pgepubid00003]/14,/1:510,/1:516

            - cfi_path is what we track from the DOM traversal (e.g. '/4/2[pgepubid00003]/14/1')
            - We split off the last step (the text node step) and replace it with offset references
            """
            # Separate the container path from the text-node step
            container_path, _, text_step = cfi_path.rpartition('/')

            # If container_path starts with "/2", remove it so the partial doc path lines up with epub.js (where <body> => /4).
            if container_path.startswith("/2"):
                container_path = container_path[2:]  # remove leading "/2"

            # Construct the partial range
            start_cfi = f"{container_path},/{text_step}:{start_offset}"
            end_cfi   = f",/{text_step}:{start_offset + len(word)}"
            partial_range = f"{start_cfi}{end_cfi}"

            word_level_cfis.append((partial_range, word))

        def split_text_into_words(cfi_path, text_content):
            """
            Split text_content into words, produce range CFIs for each.
            """
            current_search_pos = 0
            raw_words = text_content.split()
            for w in raw_words:
                start_index = text_content.find(w, current_search_pos)
                if start_index == -1:
                    continue
                add_word_range(cfi_path, start_index, w)
                current_search_pos = start_index + len(w)

        def text_node_step_name(i):
            """
            epub.js uses odd steps for text nodes: 1,3,5,...
            """
            return str((i * 2) + 1)

        def traverse_dom(node, parent_path):
            """
            Recursively walk the DOM, assigning steps to elements (even) and text nodes (odd).
            """
            if isinstance(node, NavigableString):
                text_content = node.strip()
                if text_content:
                    cfi_path = "/".join(parent_path)
                    # Insert a slash in front so cfi_path is "/4/...
                    split_text_into_words(f"/{cfi_path}", text_content)
            else:
                if not node.name:
                    return  

                # Skip <head> so <body> becomes step /4
                if node.name == "head":
                    return

                child_element_count = 0
                text_node_count = 0

                for child in node.children:
                    if isinstance(child, NavigableString):
                        # text node => odd step
                        step_name = text_node_step_name(text_node_count)
                        text_node_count += 1
                        new_path = parent_path + [step_name]
                        traverse_dom(child, new_path)
                    else:
                        # element => even step
                        child_element_count += 1
                        even_step = child_element_count * 2
                        if child.has_attr("id"):
                            step_str = f"{even_step}[{child['id']}]"
                        else:
                            step_str = str(even_step)
                        new_path = parent_path + [step_str]
                        traverse_dom(child, new_path)

        # Traverse the DOM to build partial CFIs (the part after the `!`)
        traverse_dom(html_el, [root_step])

        # prepend the spine-level path to convert partial CFIs into full CFIs
        # epubcfi(/6/ {2*(spine_index+1)} [item_id]! <partial_cfi>)
        spine_step = 2 * (spine_index + 1)  # e.g. 2 => first spine item, 4 => second, etc.
        doc_path = f"/6/{spine_step}[{item_id}]"

        full_word_level_cfis = []
        for partial_cfi, word in word_level_cfis:
            full_cfi = f"epubcfi({doc_path}!{partial_cfi})"
            full_word_level_cfis.append((full_cfi, word))

        return full_word_level_cfis
