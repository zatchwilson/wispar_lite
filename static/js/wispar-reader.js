// Based off sample code from: https://futurepress.github.io/epub.js/examples/spreads.html

var params = URLSearchParams && new URLSearchParams(document.location.search.substring(1));
var url = params && params.get("url") && decodeURIComponent(params.get("url"));
var currentSectionIndex = (params && params.get("loc")) ? params.get("loc") : undefined;

var medium = document.getElementsByName('medium')[0].content;
var audioLocationSeconds = document.getElementsByName('audio_location')[0].content;
var ebookLocationCFI = document.getElementsByName('ebook_location')[0].content;
var bookId = document.getElementsByName('book_id')[0].content;
var epubFilepath = document.getElementsByName('bookFilepath')[0].content;
var audioFilepath = document.getElementsByName('audioFilepath')[0].content;
var epubURL = '/books/ebooks/' + epubFilepath;
var rendition = undefined;
var audioDuration = undefined;
var currentEOP = undefined;
var cuesProcessed = false;
const loadingOverlay = document.getElementById("loading-overlay");
const settingsOverlay = document.getElementById("settings-overlay")
var custom_epub_default = document.getElementsByName('custom-epub-default')[0].content;
var last_read_at = document.getElementsByName('last_read_at')[0].content;
var progress_percentage = document.getElementsByName('progress_percentage')[0].content;
var time_remaining = document.getElementsByName("time_remaining")[0].content;
const time_remaining_p_tag = document.getElementById("time_remaining")
let ebook_loaded = false;
const textSeachBar = document.getElementById("text-search-bar");
const textSearchBtn = document.getElementById("search-button");
const resultsModal = document.getElementById("search-results");
const searchOverlay = document.getElementById("search-overlay");
const bookmarkAndAnnotations = document.getElementById('bookmarks');
const trackElement = document.getElementById('textTrack');
const deleteAnnotationBtn = document.getElementById("delete-annotation");
var currentPageIsBookmark = false;

if (time_remaining && time_remaining != "-1" && time_remaining != "None") {
    format_time_remaining(time_remaining)
}

if (epubFilepath !== "None") {
    var book = ePub(epubURL);
    ebook_loaded = true;
}

if (ebook_loaded) {
    // Render book to veiwer div
    rendition = book.renderTo("viewer", {
        width: "100%",
        height: "100%",
        spread: "always",
    });

    const currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;

    rendition.themes.register("/static/fonts.css");

    const fontSize = document.getElementById("font-size");
    let fontValue = document.getElementById("font-value");

    fontSize.addEventListener("input", function () {
        let value = Math.trunc(fontSize.value) + '%';
        rendition.themes.fontSize(value);
        fontValue.value = Math.trunc(fontSize.value);
    });

    fontValue.addEventListener("input", function () {
        rendition.themes.fontSize(Math.trunc(fontValue.value) + '%')
        fontSize.value = Math.trunc(fontValue.value);
        //console.log(fontSize.value);
        //console.log(fontValue.value);
    });

    let fontSelect = document.getElementById('font-fam');
    if (fontSelect) {
        fontSelect.addEventListener('change', function () {
            rendition.themes.font(fontSelect.value);
            //console.log(fontSize.value);
            //console.log(fontValue.value);
        
        });    
    }

    let leading = document.getElementById('leading');
    if (leading) {
        leading.addEventListener('change', function () {
            rendition.themes.override("line-height", leading.value);
            //console.log(leading.value);
        });    
    }

    let settingsBtn = document.getElementById("settingsBtn");
    let modal = document.getElementById("modal");

    settingsBtn.addEventListener("click", function (params) {
        settingsOverlay.style.display = 'block';
        modal.style.display = 'block';
    });

    settingsOverlay.addEventListener('click', closeModal);
    document.getElementById("donewsettings").addEventListener('click', closeModal);

    function closeModal() {
    settingsOverlay.style.display = 'none';
    modal.style.display = 'none'; 
    searchOverlay.style.display = 'none';
    resultsModal.style.display = 'none';
    resultsModal.innerHTML = '';
    }

    // When the book is ready, define navigation gui and buttons
    book.ready.then(() => {
        fetchOrGenerateLocations(bookId);
        next.addEventListener("click", function (e) {
            book.package.metadata.direction === "rtl" ? rendition.prev() : rendition.next();
            e.preventDefault();
        }, false);

        prev.addEventListener("click", function (e) {
            book.package.metadata.direction === "rtl" ? rendition.next() : rendition.prev();
            e.preventDefault();
        }, false);

        var keyListener = function (e) {
            // Left Key
            if ((e.keyCode || e.which) == 37) {
                book.package.metadata.direction === "rtl" ? rendition.next() : rendition.prev();
            }
            // Right Key
            if ((e.keyCode || e.which) == 39) {
                book.package.metadata.direction === "rtl" ? rendition.prev() : rendition.next();
            }
        };

        rendition.on("keyup", keyListener);
        document.addEventListener("keyup", keyListener, false);
    })

    function removeBookmarksOnPage() {
        let bkmrkToDelete = []
        Array.from(document.getElementById('bookmarks').options).forEach(function (annotation) {
            var cfi = annotation.value;
            let epub_location = new ePub.CFI();
            if (cfi && cfi !== "Bookmarks") {
                // Check if the option text starts with "B-"
                if (annotation.textContent.trim().indexOf("B-") === 0) {
                    let after_page_start = epub_location.compare(cfi, rendition ? rendition.currentLocation().start.cfi : null);
                    let before_page_end = epub_location.compare(rendition ? rendition.currentLocation().end.cfi : null, cfi);
                    if (after_page_start && before_page_end) {
                        console.log("No bkmrk on page");
                    } else {
                        bkmrkToDelete.push(annotation)
                    }
                }
            }
        });
        const bookmarkList= document.getElementById('bookmarks');
        bkmrkToDelete.forEach(function (bookmark) {
            for (var i = 0; i < bookmarkList.length; i++) {
                if (bookmarkList.options[i].value == bookmark.value) {
                    if (bookmarkList.options[i].textContent.trim().indexOf("B-") === 0) {
                        rendition.annotations.remove(bookmarkList.options[i].value, "bookmark");
                        removeTitleLocation("bookmark", bookmarkList.options[i].value)
                    }
                    bookmarkList.remove(i);
                }
            }
        });
        return;
    }    

    // Hide Next/Prev if at beggining or end
    rendition.on("relocated", function (location) {
        console.log('RELOCATED');
        var toc = document.getElementById("toc");
        toc.selectedIndex = 0;
        updateEndOfPage(location);
        var next = book.package.metadata.direction === "rtl" ? document.getElementById("prev") : document.getElementById("next");
        var prev = book.package.metadata.direction === "rtl" ? document.getElementById("next") : document.getElementById("prev");

        if (location.atEnd) {
            next.style.visibility = "hidden";
        } else {
            next.style.visibility = "visible";
        }

        if (location.atStart) {
            prev.style.visibility = "hidden";
        } else {
            prev.style.visibility = "visible";
        }

        currentPageIsBookmark = false;
        // Is Bookmark after page start, but before end?
        Array.from(document.getElementById('bookmarks').options).forEach(function (annotation) {
            var cfi = annotation.value;
            let epub_location = new ePub.CFI();
            if (cfi && cfi !== "Bookmarks") {
                // Check if the option text starts with "H-"
                if (annotation.textContent.trim().indexOf("B-") === 0) {
                    //console.log("Beggining of Page: ", rendition ? rendition.currentLocation().start.cfi : null);
                    //console.log("Bookmark         : ", cfi);
                    //console.log("End of Page      : ", rendition ? rendition.currentLocation().end.cfi : null)
                    let after_page_start = epub_location.compare(cfi, rendition ? rendition.currentLocation().start.cfi : null);
                    let before_page_end = epub_location.compare(rendition ? rendition.currentLocation().end.cfi : null, cfi);
                    if (after_page_start && before_page_end) {
                        //console.log("No bkmrk on page");
                    } else {
                        currentPageIsBookmark = true;
                        
                    }
                }
            }
        })

        if (currentPageIsBookmark) {
            pageIsBookmarked();
            deleteAnnotationBtn.disabled = false;
        } else {
            pageIsNotBookmarked();
        }
    });
    rendition.themes.register("Classic-Light", "/static/injected.css");
    rendition.themes.register("Modern-Light", "/static/injected.css");
    rendition.themes.register("Modern-Dark", "/static/injected.css");
    rendition.themes.register("Classic-Dark", "/static/injected.css");
    rendition.themes.register("Urban-Fog", "/static/injected.css");
    rendition.themes.register("Paperwhite", "/static/injected.css");
    rendition.themes.register("Void-Luminescence", "/static/injected.css");
    rendition.themes.register("Ocean-Depths", "/static/injected.css");
    rendition.themes.register("Emerald-Canopy", "/static/injected.css");
    rendition.themes.register("Twilight-Bloom", "/static/injected.css");
    rendition.themes.register("Frosted-Horizon", "/static/injected.css");
    rendition.themes.register("Sunset-Marina", "/static/injected.css");
    rendition.themes.register("Skyline-Mist", "/static/injected.css");
    rendition.themes.register("Velvet-Dusk", "/static/injected.css");
    rendition.themes.register("Meadow-Breeze", "/static/injected.css");
    rendition.themes.register("Golden-Ember", "/static/injected.css");
    rendition.themes.register("Seafoam-Serenity", "/static/injected.css");
    rendition.themes.register("Desert-Mirage", "/static/injected.css");
    rendition.themes.register("Golden-Harvest", "/static/injected.css");
    rendition.themes.register("Stormy-Harbor", "/static/injected.css");
    rendition.themes.register("Charcoal-Ember", "/static/injected.css");
    rendition.themes.register("Sunlit-Blush", "/static/injected.css");
    rendition.themes.register("Autumn-Fog", "/static/injected.css");
        
    rendition.display(ebookLocationCFI != 'None' ? ebookLocationCFI : undefined).then((section) => {
        if (custom_epub_default) {
            if (custom_epub_default === 'True') {
                rendition.themes.select(currentTheme.replace(' ', '-'));
            }
        }
        rendition.themes.fontSize("100%");
    })
    

    textSearchBtn.addEventListener("click", function (e) {
        e.preventDefault();
        searchOverlay.style.display = "block";
        doSearch(textSeachBar.value).then(results => {
            if (results.length === 0) {
                const p = document.createElement('p');
                p.textContent = "No Results Found 😞";
                resultsModal.appendChild(p);
            }
            results.forEach(result => {
                // Create an anchor element
                const link = document.createElement('a');
                link.href = "#"; // Prevent default link navigation
                link.textContent = result.excerpt;
          
                link.addEventListener('click', (event) => {
                  event.preventDefault(); // Prevent page jump
                  rendition.display(result.cfi);
                  closeModal();
                });
          
                // Append the link to the results div
                resultsModal.appendChild(link);
          
                // Line break for spacing
                resultsModal.appendChild(document.createElement('br'));
                resultsModal.appendChild(document.createElement('br'));
            });
            resultsModal.style.display = "block";
        })
    })
    function doSearch(q) {
        return Promise.all(
            book.spine.spineItems.map(item => item.load(book.load.bind(book)).then(item.find.bind(item, q)).finally(item.unload.bind(item)))
        ).then(results => Promise.resolve([].concat.apply([], results)));
    };

    const bookmarkButton = document.getElementById("bookmark-page");
    var notBookmarked = document.getElementById("not-bookmarked");
    var isBookmarked = document.getElementById('is-bookmarked');

    function pageIsBookmarked() {
        // Bookmarked
        isBookmarked.style.display = "block";
        notBookmarked.style.display = "none";
    }

    function pageIsNotBookmarked() {
        // Bookmarked
        notBookmarked.style.display = "block";
        isBookmarked.style.display = "none";
        removeBookmarksOnPage();
    }

    bookmarkButton.addEventListener("click", function () {
        if (isBookmarked.style.display !== "block") {
            // Bookmarked
            pageIsBookmarked();
            bookmark(("" + rendition ? Math.floor(rendition.currentLocation().start.percentage * 100) + "%" : null), rendition ? rendition.currentLocation().start.cfi : null)
        } else {// Not Bookmarked
            pageIsNotBookmarked();
            deleteAnnotationBtn.disabled = true;
        }
    });

    var isFullscreen = false;
    var fullscreen = document.getElementById("fullscreen");
    // Attach event listener to the button
    if (fullscreen) {
        fullscreen.addEventListener("click", toggleFullscreen);
        fullscreen.style.display = "flex";
    }

    var navigation = document.getElementById("navigation");
    var readerRow = document.getElementById("reader-row");
    var view = document.getElementById("viewer");
    var sidebar = document.getElementById("sidebar");
    let toggleButton = document.getElementById("toggleSidebar");

    document.addEventListener("fullscreenchange", function () {
        if (document.fullscreenElement) {
            readerRow.style.maxWidth = "100vw";
            navigation.style.display = "none";
            sidebar.style.display = "none";
            view.style.maxWidth = "75vw";
            toggleButton.style.opacity = 0;
            isFullscreen = true;
        } else {
            readerRow.style.paddingBottom = "0rem";
            readerRow.style.maxWidth = "100%";
            readerRow.style.width = "unset";
            navigation.style.display = "flex";
            sidebar.style.display = "flex";
            view.style.maxWidth = "75vw";
            toggleButton.style.opacity = 1;
            isFullscreen = false;
        }
    });

    function toggleFullscreen () {
        if (isFullscreen) {
            document.exitFullscreen();
        } else {
            document.documentElement.requestFullscreen();
        }
        rendition.resize();
    }

    function updateEndOfPage(location) {
        currentEOP = location.end.cfi;
        console.log('New EOP: ' + currentEOP.toString());
    }

    // One the navigation is loaded, make TOC
    book.loaded.navigation.then(function (toc) {
        var $select = document.getElementById("toc");
        var docfrag = document.createDocumentFragment();

        let selectHeader = document.createElement("option");
        selectHeader.textContent = "Table Of Contents";

        docfrag.appendChild(selectHeader);

        toc.forEach(function (chapter) {
            var option = document.createElement("option");
            option.textContent = chapter.label;
            option.setAttribute("ref", chapter.href);

            docfrag.appendChild(option);
        });

        $select.appendChild(docfrag);

        $select.onchange = function () {
            var index = $select.selectedIndex;
            var url = $select.options[index].getAttribute("ref");
            if (url) {
                rendition.display(url);
            }
            return false;
        };

        var userAnnotations = document.getElementById('bookmarks');
        // Annotations
        Array.from(userAnnotations.options).forEach(function (annotation) {
            var cfi = annotation.value;

            if (cfi && cfi !== "Bookmarks") {
                // Check if the option text starts with "H-"
                if (annotation.textContent.trim().indexOf("H-") === 0) {
                    rendition.annotations.highlight(cfi, {}, function (e) {
                        //console.log("Re-highlighted", e.target);
                    });
                }
            }
        });
    });

    deleteAnnotationBtn.addEventListener('click', function (e) {
        console.log("[",bookmarkAndAnnotations.value,"] ", currentPageIsBookmark)
        if (bookmarkAndAnnotations.value === "Bookmarks" && !currentPageIsBookmark) {
            return;
        }
        removeBookmarksOnPage();
        for (var i = 0; i < bookmarkAndAnnotations.length; i++) {
            if (bookmarkAndAnnotations.options[i].value == bookmarkAndAnnotations.value && bookmarkAndAnnotations.value !== "Bookmarks") {
                if (bookmarkAndAnnotations.options[i].textContent.trim().indexOf("H-") === 0) {
                    rendition.annotations.remove(bookmarkAndAnnotations.options[i].value, "highlight");
                    removeTitleLocation("highlight", bookmarkAndAnnotations.options[i].value)
                } else {
                    rendition.annotations.remove(bookmarkAndAnnotations.options[i].value, "bookmark");
                    if (bookmarkAndAnnotations.options[i].textContent.trim().indexOf("B-") === 0) {
                        removeTitleLocation("bookmark", bookmarkAndAnnotations.options[i].value)
                    }
                    
                }
                bookmarkAndAnnotations.remove(i);
                notBookmarked.style.display = "block";
                isBookmarked.style.display = "none";
            }
        }
        bookmarkAndAnnotations.value = bookmarkAndAnnotations.options[0].value;
        deleteAnnotationBtn.disabled = true;
    });
    
    bookmarkAndAnnotations.onchange = function () {
        console.log('lol');
        if (bookmarkAndAnnotations.value === "Bookmarks") {
            deleteAnnotationBtn.disabled = true;    
        } else {
            deleteAnnotationBtn.disabled = false;
        }
    };

    // Reference to the popup element
    const popup = document.getElementById('textPopup');
    const defineBtn = document.getElementById('defineBtn');
    const wikiBtn = document.getElementById('wikiBtn');
    const highlightBtn = document.getElementById('highlightBtn');
    const bookmarkBtn = document.getElementById('bookmarkBtn');

    // Update the button actions based on the current selected text.
    function updateButtons(selectedText, cfiRange) {
        defineBtn.onclick = () => queryDictionary(selectedText);
        wikiBtn.onclick = () => searchWikipedia(selectedText);
        highlightBtn.onclick = () => saveHighlight(selectedText, cfiRange);
        bookmarkBtn.onclick = () => bookmark(selectedText, cfiRange);
    }

    // Display the popup at the given coordinates.
    function showPopup(x, y, selectedText, cfiRange) {
        console.log(selectedText, " : ", cfiRange);
        updateButtons(selectedText, cfiRange);
        popup.style.left = x + 'px';
        popup.style.top = y + 'px';
        popup.style.display = 'block';
    }

    // Hide the popup.
    function hidePopup() {
        popup.style.display = 'none';
        document.getElementById("definition").style.display = 'none';
    }

    rendition.on("selected", function (cfiRange, contents, e) {
        setTimeout(() => {
            // Get the Selection object from the iframe's window
            const selection = contents.window.getSelection();

            const getRect = (target, frame) => {
                const rect = target.getBoundingClientRect()
                const viewElementRect =
                    frame ? frame.getBoundingClientRect() : { left: 0, top: 0 }
                const left = rect.left + viewElementRect.left
                const right = rect.right + viewElementRect.left
                const top = rect.top + viewElementRect.top
                const bottom = rect.bottom + viewElementRect.top
                return { left, right, top, bottom }
            }

            // If there is a valid selection
            if (selection && selection.rangeCount > 0) {
                const selectedText = selection.toString();

                const range = selection.getRangeAt(0)
                const { left, right, top, bottom } = getRect(range, contents.document.defaultView.frameElement)
                console.log(left, right, top, bottom);

                showPopup(left, bottom, selectedText, cfiRange);
            }
        }, 10);
        contents.document.addEventListener('mousedown', function () {
            hidePopup();
        });
    });

    function saveHighlight(selectedText, cfiRange) {
        // This does the epub.js built in highlighting
        rendition.annotations.highlight(cfiRange, {}, function (e) {
            //console.log("highlight clicked", e.target);
        });

        // Get the selected text and add it as a highlight option
        book.getRange(cfiRange).then(function (range) {
            if (range) {
                var text = range.toString();
                var displayText = "H- " + text.slice(0, 20);
                var option = document.createElement('option');
                option.textContent = displayText;
                option.value = cfiRange;
                // Append the option to the bookmarks dropdown
                document.getElementById('bookmarks').appendChild(option);
                saveTitleLocation('highlight', cfiRange, displayText);
            }
        });
    }

    // Function to call the dictionary API for the selected word.
    function queryDictionary(word) {
        // Construct the URL to the Django endpoint
        const url = '/define/' + encodeURIComponent(word);
        fetch(url)
            .then(response => {
                // Check if the request was successful
                if (!response.ok) {
                    document.getElementById("definition").innerHTML = "Word not found";
                    document.getElementById("definition").style.display = 'block';
                }
                return response.text(); // Parse the response as text
            })
            .then(definition => {
                console.log("Definition:", definition);
                // Place the definition into an element on your page
                document.getElementById("definition").innerHTML = definition;
                document.getElementById("definition").style.display = 'block';
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById("definition").innerHTML = "Error: " + error.message;
                document.getElementById("definition").style.display = 'block';
            });
    }

    // Function to open a Wikipedia search for the selected word.
    function searchWikipedia(word) {
        const url = 'https://en.wikipedia.org/wiki/Special:Search?search=' + encodeURIComponent(word);
        window.open(url, '_blank');
    }

    document.addEventListener('click', function (e) {
        if (!popup.contains(e.target)) {
            hidePopup();
        }
    });

    if (rendition != undefined) {
        rendition.hooks.content.register(function (contents) {
            // Adapted from example here: https://github.com/futurepress/epub.js/wiki/Tips-and-Tricks-%28v0.3%29
            const el = contents.document.documentElement;
            if (el) {
                //Enable swipe gesture to flip a page
                let start;
                let end;

                el.addEventListener('touchstart', (event) => {
                    start = event.changedTouches[0];
                    //console.log('Touch Event Start');
                });

                el.addEventListener('touchend', (event) => {
                    //console.log('Touch Event End');
                    end = event.changedTouches[0];
                    const bound = el.getBoundingClientRect();
                    const hr = (end.screenX - start.screenX) / bound.width;
                    const vr = Math.abs((end.screenY - start.screenY) / bound.height);
                    //console.log(`hr: ${hr}/.005, vr: ${vr}/.03`);
                    if (hr > 0.005 && vr > .005) return rendition.prev();
                    if (hr < -0.005 && vr > .005) return rendition.next();
                });
            }
        });
    }

    function bookmark(selectedText, cfiRange) {
        // Get the selected text and add it as a bookmark option
        book.getRange(cfiRange).then(function (range) {
            if (range) {
                var displayText = "B- " + selectedText.slice(0, 20);
                var option = document.createElement('option');
                option.textContent = displayText;
                option.value = cfiRange;
                // Append the option to the bookmarks dropdown
                document.getElementById('bookmarks').appendChild(option);
                saveTitleLocation('bookmark', cfiRange, displayText);
            }
        });
        hidePopup();
    }

    // When a bookmark is selected, jump to that location
    document.getElementById('bookmarks').addEventListener("change", function (e) {
        var selectEl = e.target;
        var selectedOption = selectEl.options[selectEl.selectedIndex];
        var cfi = selectedOption.value;
        if (cfi && cfi !== "Bookmarks") {
            rendition.display(cfi).then(function () {
                console.log(selectedOption.textContent);
            });
        }
    });

    // Helper function to send bookmark/highlight data to the backend (TitleLocation model)
    function saveTitleLocation(bookmark_type, cfiRange, displayText) {
        var data = new FormData();
        data.append('csrfmiddlewaretoken', getCSRFToken());
        data.append('text_location', cfiRange);
        data.append('location_text_snippet', displayText)
        data.append('bookmark_type', bookmark_type);
        // Include dummy values for these fields if needed
        data.append('audio_location', 0);
        data.append('progress_percentage', 0);
        var bookId = document.getElementsByName('book_id')[0].content;
        navigator.sendBeacon(`/books/bookmarks/${bookId}/`, data);
    }

    function removeTitleLocation(bookmark_type, cfiRange) {
        var data = new FormData();
        data.append('csrfmiddlewaretoken', getCSRFToken());
        data.append('text_location', cfiRange);
        data.append('bookmark_type', bookmark_type);
        var bookId = document.getElementsByName('book_id')[0].content;
        navigator.sendBeacon(`/books/delete-bookmark/${bookId}/`, data);
    }
    
} else {
    var poster = document.getElementById("player-bar-poster");
    poster.style.transform = "translate(0,0)"
}

window.addEventListener("unload", unloadBook);
async function unloadBook() {
    try {
        if (rendition) {
            await rendition.destroy(); // Detach and clean up the rendition
            console.log("Rendition destroyed.");
        }
        if (book) {
            await book.destroy(); // Clean up the book instance
            console.log("Book destroyed.");
        }

        // Clear the container
        const container = document.getElementById("viewer");
        if (container) {
            container.innerHTML = "";
            console.log("Viewer container cleared.");
        }
    } catch (error) {
        console.error("Error while unloading the book:", error);
    }
}

document.addEventListener("visibilitychange", () => {

    if (document.visibilityState === "hidden") {
        calculate_time_remaining()
        update_last_read_position();
    }
});

// Fallback handler – in case visibilitychange isn’t supported or doesn’t fire
window.addEventListener("pagehide", () => {
    calculate_time_remaining()
    update_last_read_position();
});

// Audio Playback
const audio = document.getElementById("audio-player");
var track = undefined;
if (audio) {
    if (ebook_loaded) {
        overlay.style.display = 'block';
    }
    // This triggers loading the VTT file, hidden tells the audio element we won't be displaying the subs in the audio element.
    if (trackElement) {
        trackElement.track.mode = "hidden";
    }
    audio.onloadedmetadata = function () {
        audioDuration = audio.duration;

        var play = document.getElementById("play");
        var pause = document.getElementById("pause");
        var playing = false;

        let resumeTimeStamp = 0;
        const savedTimeStr = localStorage.getItem(bookId);
        if (savedTimeStr !== null) {
            const localTime = parseFloat(savedTimeStr);
            const serverTime = parseFloat(audioLocationSeconds !== "None" ? audioLocationSeconds : 0);

            if (!isNaN(serverTime)) {
                if (localTime > serverTime) {
                    console.log('Local progress is ahead of server progress.');
                    resumeTimeStamp = localTime;
                } else if (localTime < serverTime) {
                    console.log('Server progress is ahead the local progress.');
                    localStorage.setItem(bookId, serverTime);
                    resumeTimeStamp = serverTime;
                } else {
                    console.log('Local and server progress are in sync.');
                    resumeTimeStamp = serverTime;
                }
            } else {
                console.log('Server progress not available.');
            }
        } else {
            console.log('No saved progress found in localStorage.');
            resumeTimeStamp = parseFloat(audioLocationSeconds !== "None" ? audioLocationSeconds : 0);
        }

        audio.currentTime = resumeTimeStamp;
        console.log(resumeTimeStamp);

        play.addEventListener("click", function (e) {
            play.style.display = "none";
            pause.style.display = "block";
            playing = true;
            playAudio();
            e.preventDefault();
        }, false);

        pause.addEventListener("click", function (e) {
            pauseAudio();
            pause.style.display = "none";
            play.style.display = "block";
            playing = false;
            if (sleepTimerRunning) {
                showToast("Ending Sleep Timer");
                clearPreviousTimer();
                sleepTimerRunning = false;
            }
            e.preventDefault();
        }, false);

        function playAudio() {
            audio.play();
        }

        function pauseAudio() {
            audio.pause();
        }

        // Fast Forward and Rewind functionality
        const rewindButton = document.getElementById("rewind");
        const fastForwardButton = document.getElementById("fastforward");

        rewindButton.addEventListener("click", function (e) {
            // Move back 10 seconds, but not below 0.
            if (audio.readyState >= 1) {
                audio.currentTime = Math.max(0, audio.currentTime - 10);
            }
            else 
            {
                audio.addEventListener('loadedmetadata', () =>
                {
                    let newTime = audio.currentTime - 10;
                    newTime = Math.max(0, newTime);
                    audio.currentTime = newTime;
                }, {once: true});
            }
            e.preventDefault();
        });

        fastForwardButton.addEventListener("click", function (e) {
            // Move forward 30 seconds, but not past the audio duration.
            
            if (audio.readyState >= 1) {
                audio.currentTime = Math.min(audio.duration, audio.currentTime + 30);
            }
            else 
            {
                audio.addEventListener('loadedmetadata', () =>
                {
                    let newTime = audio.currentTime + 30;
                    newTime = Math.min(audio.duration, newTime);
                    audio.currentTime = newTime;
                }, {once: true});
            }
            
            e.preventDefault();
        });


        const volumeControl = document.getElementById("volumeControl");
        const volumeValue = document.getElementById("volumeValue");
        volumeControl.addEventListener("input", function () {
            audio.volume = parseFloat(volumeControl.value);
            volumeValue.textContent = Math.trunc(volumeControl.value * 100) + '%';
        });

        const speedControl = document.getElementById("speedControl");
        const speedValue = document.getElementById("speedValue");
        speedControl.addEventListener("input", function () {
            audio.playbackRate = parseFloat(speedControl.value);
            speedValue.textContent = speedControl.value + 'x';
        });

        var collapseAudio = document.getElementById("collapse");
        var expandAudio = document.getElementById("expand");
        var audioPlayer = document.getElementById("audioplayer");
        var sleepTimer = document.getElementById("sleep-timer-ui");
        var playerBar = document.getElementById("player-bar")
        var controlRow = document.getElementById("control-row");
        var progressContainer = document.getElementById('progress-container');

        function collapse() {
            audioPlayer.style.display = "none";
            sleepTimer.style.display = "none";
            collapseAudio.style.display = "none";
            expandAudio.style.display = "block";
            controlRow.style.backgroundColor = "transparent"
            progressContainer.style.display = "none"
            poster.style.display = "none"
        }

        function expand() {
            audioPlayer.style.display = "flex";
            sleepTimer.style.display = "flex";
            expandAudio.style.display = "none";
            collapseAudio.style.display = "block";
            controlRow.style.backgroundColor = "rgba(var(--background-color), 0.75)"
            progressContainer.style.display = "block"
            poster.style.display = "block"
        }

        collapseAudio.addEventListener("click", collapse);

        expandAudio.addEventListener("click", expand);


        // Sleep Timer

        const sleepTimerInput = document.getElementById('sleep-timer-duration');
        const timerValue = document.getElementById('timer-value');
        const startTimerButton = document.getElementById('sleep-timer');
        const toast = document.getElementById('toast');

        let timer;
        let fadeInterval;

        sleepTimerInput.addEventListener('input', () => {
            timerValue.textContent = sleepTimerInput.value;
        });

        var sleepTimerRunning = false;
        // Start timer when button is clicked
        startTimerButton.addEventListener('click', () => {
            sleepTimerRunning = true;
            if (playing) {
                const minutes = parseInt(sleepTimerInput.value, 10);
                const milliseconds = minutes * 60 * 1000;

                clearPreviousTimer();

                showToast(`Sleep timer started for ${minutes} minutes.`);
                console.log("starting timer");

                timer = setTimeout(() => {
                    console.log("Timer is up, fading...");
                    sleepTimerRunning = false;
                    fadeOutAudio();
                }, milliseconds);
            }
            else {
                showToast("Resume Playback to Start Timer");
            }
        });

        function clearPreviousTimer() {
            clearInterval(timer);
            clearInterval(fadeInterval);
        }

        function fadeOutAudio() {
            const fadeDuration = 5000; // Fade out over 5 seconds
            const fadeSteps = 50; // Number of steps in the fade-out
            const fadeStepTime = fadeDuration / fadeSteps;
            const initialVolume = audio.volume;
            const volumeStep = initialVolume / fadeSteps;

            fadeInterval = setInterval(() => {
                if (audio.volume > 0) {
                    audio.volume = Math.max(0, audio.volume - volumeStep);
                } else {
                    // Stop playback and clear fade interval when volume reaches 0
                    pauseAudio();
                    clearInterval(fadeInterval);
                    audio.volume = initialVolume; // Reset volume for future
                }
            }, fadeStepTime);
        }

        // Progress bar elements
        const progressBar = document.getElementById('progress-bar');
        const currentTimeDisplay = document.getElementById('current-time');
        const durationDisplay = document.getElementById('duration');

        // Initialize time display when metadata is loaded
        if (audio.readyState > 0) {
            durationDisplay.textContent = formatTime(audio.duration);
            currentTimeDisplay.textContent = formatTime(audio.currentTime);
        } else {
            // Listen for the 'load' event on the track element
            console.log("Audio Load Event")
            audio.addEventListener('load', () => {
                durationDisplay.textContent = formatTime(audio.duration);
                currentTimeDisplay.textContent = formatTime(audio.currentTime);
            });
        }

        // Update time display and progress bar
        audio.addEventListener('timeupdate', updateProgress);
        audio.addEventListener('loadedmetadata', () => {
            durationDisplay.textContent = formatTime(audio.duration);
        });

        // Handle progress bar clicks
        progressContainer.addEventListener('click', (e) => {
            const rect = progressContainer.getBoundingClientRect();
            const clickX = e.clientX - rect.left; // X position of the click relative to the progress bar
            const progressBarWidth = rect.width; // Total width of the progress bar
            //console.log("seeking to: " + formatTime(clickX / progressBarWidth * audio.duration) + ", " + (clickX / progressBarWidth) * 100 + "%");
            const seekTime = clickX / progressBarWidth * audio.duration; // Calculate the seek time

            //console.log(formatTime(audio.currentTime))
            // Ensure the seek time is within valid bounds
            audio.currentTime = seekTime;//Math.max(0, Math.min(seekTime, audio.duration));
            //console.log(formatTime(audio.currentTime))
        });

        // Update progress bar and time displays
        function updateProgress() {
            const progress = (audio.currentTime / audio.duration) * 100;
            progressBar.style.width = `${progress}%`;
            currentTimeDisplay.textContent = formatTime(audio.currentTime);
        }

        function showToast(message) {
            toast.textContent = message;
            toast.classList.add('show');
            toast.classList.remove('hidden');

            setTimeout(() => {
                toast.classList.remove('show');
                toast.classList.add('hidden');
            }, 3000);
        }
    }
    if (ebook_loaded) {
        rendition.hooks.render.register(function (view) {
            console.log("hook");
            if (rendition && !cuesProcessed) {
                console.log("Rendition loaded, awaiting audio/vtt");
                // Check if the track is already loaded
                if (trackElement.readyState === 2) { // 2 = LOADED
                    console.log("Track Already Loaded!");
                    processCues(trackElement.track, rendition);
                    overlay.style.display = 'none';
                } else if (trackElement.readyState === 3) {
                    overlay.style.display = 'none';
                    console.log("VTT failed to load...");
                } else {
                    // Listen for the 'load' event on the track element
                    trackElement.addEventListener('load', () => {
                        console.log("waiting for the track...");
                        processCues(trackElement.track, rendition);
                        overlay.style.display = 'none';
                    });
                }
            } else {
                console.warn("Annotations module not available yet.");
            }
        });
    }
}

function processCues(track, rendition) {
    if (track && rendition) {
        console.log('vtt track Ready');

        var cues = track.cues;
        //console.log("Number of Cues: ", cues.length);

        var old_word_highlights = [];
        var last_chap = undefined;
        track.addEventListener('cuechange', () => {
            console.log('New Cue: ');
            old_word_highlights.forEach(cfiRange => {
                // Remove prev highlighted CFIs
                //console.log("Removing: ", cfiRange);
                rendition.annotations.remove(cfiRange, "highlight");
            });
            // To account for rapid DOM updating keep a log of the last several and ensure they have been removed
            if (old_word_highlights.length > 10) {
                old_word_highlights = [];
            }
            const activeCue = track.activeCues[0];
            if (activeCue) {
                //let cur_cfi_prefix = (rendition.currentLocation().start.cfi).split('!')[0];
                //console.log("Prefix: ", cur_cfi_prefix);
                //const h_range = cur_cfi_prefix + "!" + activeCue.text + ")";
                const h_range = activeCue.text;
                var EpubCFI = new ePub.CFI();

                let curr_chap = h_range.split('/')[2];

                // End of Chapter
                console.log("Last chap: ", last_chap, "current chap: ", curr_chap);
                if (last_chap && (last_chap !== curr_chap)) {
                    console.log('Next Chapter!');
                    rendition.display(h_range);
                }

                last_chap = curr_chap;

                // Turn Page
                if (EpubCFI.compare(currentEOP, h_range) !== 1) {
                    console.log('TURN PAGE!');
                    book.package.metadata.direction === "rtl" ? rendition.prev() : rendition.next();
                }

                if (h_range) {
                    //console.log(EpubCFI.isCfiString(h_range), ": ", h_range);
                    if (rendition) {
                        rendition.annotations.highlight(h_range, {}, (e) => { /*  */ });
                    }
                    old_word_highlights.push(h_range);
                }
            }
        });
    }
    console.log('Done Proccessing Cues...');
    cuesProcessed = true;
    // if (rendition) {
    //     updateEndOfPage(rendition ? rendition.currentLocation().start.cfi : null);
    // }
}

// loop to update user progress every 5 minutes in the database
const updateInterval = 300000
setTimeout(function () {
    setInterval(calculate_time_remaining, updateInterval)
    setInterval(update_last_read_position, updateInterval)

}, updateInterval)

function CfiFromTimestamp(textTrack, currentTime) {
    const cues = textTrack.cues;
    if (!cues || cues.length === 0) return null;

    let left = 0;
    let right = cues.length - 1;
    
    // Binary search to find the first cue with startTime > currentTime
    while (left <= right) {
      const mid = Math.floor((left + right) / 2);
      if (cues[mid].startTime <= currentTime) {
        left = mid + 1;
      } else {
        right = mid - 1;
      }
    }
    console.log(left < cues.length ? cues[left].text : null);
    // left now points to the next cue or cues.length if none exists
    return left < cues.length ? cues[left].text : null;
}

function updateAudioTimestampFromTextLocation(epubLoc, mapping) {
    let EpubCFI = new ePub.CFI();
    const keys = Object.keys(mapping);
    
    // Binary search for the first CFI that comes after the current text location.
    let left = 0;
    let right = keys.length - 1;
    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        if (EpubCFI.compare(keys[mid], epubLoc) <= 0) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    // 'left' points to the next CFI or is at the end.
    const selectedKey = left < keys.length ? keys[left] : keys[keys.length - 1];
    const newTimestamp = mapping[selectedKey];
    
    // Update the audio element's currentTime.
    console.log(`Updated audio time to ${newTimestamp} seconds, based on text location ${selectedKey}`);
    return newTimestamp;
}

async function fetchAudioMapping(filename) {
    const url = `/books/json/${filename}/`;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const mapping = await response.json();
        return mapping;
    } catch (error) {
        console.error("Error fetching audio mapping:", error);
        return null;
    }
}

async function update_last_read_position() {
    let EpubCFI = new ePub.CFI();
    const last_read_data = new FormData();
    last_read_data.append('csrfmiddlewaretoken', getCSRFToken());
    let timestamp = audio ? audio.currentTime : null;
    let epubLoc = rendition ? rendition.currentLocation().start.cfi : null;
    let audioTimestampToCFI = undefined;

    if (audio) {
        // Is audiostamp ahead of text?
        audioTimestampToCFI = CfiFromTimestamp(trackElement.track, timestamp);
        console.log("Comparing epub: ", epubLoc, ", to audio: ", audioTimestampToCFI.split(',')[0] + audioTimestampToCFI.split(',')[1] + ')');
        audioTimestampToCFI = audioTimestampToCFI.split(',')[0] + audioTimestampToCFI.split(',')[1] + ')';
        console.log(EpubCFI.compare(EpubCFI.parse(epubLoc), EpubCFI.parse(audioTimestampToCFI)));
        if (EpubCFI.compare(epubLoc, audioTimestampToCFI) === -1) {
            console.log("audio is ahead of text!");
            // If so, update text location to match
            epubLoc = audioTimestampToCFI;
        } else 
        // If not, then if the text location is ahead
        if (EpubCFI.compare(epubLoc, audioTimestampToCFI) === 1) {
            console.log("Text is ahead of audio!");
            // Update audio location to match
            const mapping = await fetchAudioMapping(audioFilepath.split('.m4b')[0] + '.json');
            timestamp = updateAudioTimestampFromTextLocation(epubLoc, mapping);
        }
        last_read_data.append('audio_location', timestamp);
    } else {
        last_read_data.append('audio_location', '0');
    }
    last_read_data.append('text_location', epubLoc);

    var curr_progress_percentage = get_percentage_progress(audio, rendition);
    last_read_data.append('progress_percentage', curr_progress_percentage);
    last_read_data.append('time_remaining', isFinite(time_remaining) ? time_remaining : -1)

    //send http request to update database
    navigator.sendBeacon(`/books/progress/${document.getElementsByName('book_id')[0].content}/`, last_read_data);
    last_read_at = Date.now()
    progress_percentage = curr_progress_percentage
}


async function calculate_time_remaining(){
    var last_read_at_milliseconds = undefined
    if (typeof(last_read_at) == "number") {
        last_read_at_milliseconds = last_read_at
    } else if (last_read_at != "None") {
        last_read_at_milliseconds = Date.parse(last_read_at)
    } else {
        last_read_at_milliseconds = Date.now() - (updateInterval * 1000)
    }
    var curr_time = Date.now()
    var curr_percentage = get_percentage_progress(audio, rendition)
    var remaining_percentage = 100 - curr_percentage

    if (time_remaining == -1 || time_remaining == 'None') { //calc time remaining for the first time
        var curr_rate = curr_percentage / ((curr_time - last_read_at_milliseconds) / 1000)
        time_remaining = Number(remaining_percentage / curr_rate)

    } else {
        var curr_rate = (curr_percentage - progress_percentage) / ((curr_time - last_read_at_milliseconds) / 1000)
        var curr_time_remaining = Number(remaining_percentage / curr_rate)
        time_remaining = isFinite(curr_time_remaining) ? curr_time_remaining : time_remaining
    }

    format_time_remaining(time_remaining)
}


function format_time_remaining(time_remaining) {
    if (time_remaining > 3600){
        var hours_remaining = (time_remaining / 3600).toFixed(1)
        time_remaining_p_tag.innerHTML = `~${hours_remaining} hours remaining in this book`
    } else if (time_remaining > 300) {
        var minutes_remaining = (time_remaining / 60).toFixed(1)
        time_remaining_p_tag.innerHTML = `~${minutes_remaining} minutes remaining in this book`
    } else {
        time_remaining_p_tag.innerHTML = `Less than 5 minutes remaining in this book`
    }
}


function getCSRFToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, "csrftoken".length + 1) === ("csrftoken" + '=')) {
                cookieValue = decodeURIComponent(cookie.substring("csrftoken".length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function get_percentage_progress(audio_player, rendition) {
    // Calculate audio progress
    let audio_progress = 0
    if (audio_player) {
        const total_length = audioDuration ? audioDuration : 1
        const current_time = audio_player.currentTime ? audio_player.currentTime : 0
        audio_progress = Number(current_time / total_length * 100)
    }

    let epub_progress = 0
    if (rendition) {
        epub_progress = book.locations.percentageFromCfi(rendition.currentLocation().start.cfi) * 100
    }

    const total_progress = Math.max(epub_progress, audio_progress)
    return total_progress

}

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secondsRemaining = Math.floor(seconds % 60);

    // Format to always show two digits for minutes and seconds
    const formattedMinutes = minutes < 10 ? '0' + minutes : minutes;
    const formattedSeconds = secondsRemaining < 10 ? '0' + secondsRemaining : secondsRemaining;

    return `${hours}:${formattedMinutes}:${formattedSeconds}`;

}

async function fetchOrGenerateLocations(bookId) {
    var locations = undefined
    // Make the GET request
    fetch(`/books/locations/${bookId}/`, {
        method: 'GET',  // Specify the request method as GET
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            } else if (response.status == 204) {
                return
            } else if (response.status == 200) {
                return response.json();  // Parse the JSON response
            }

        })
        .then(data => {
            locations = data
            if (locations) {
                book.locations.load(locations)
            } else {
                book.locations.generate(1600).then(locations => {
                    fetch(`/books/locations/${bookId}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCSRFToken(),
                        },
                        body: book.locations.save() // Convert the data to JSON
                    }).then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not oaky')
                        }
                    })
                })
            }
        })
        .catch(error => {
            console.error('Error fetching or sending locations:', error);
        });

}

// Function to save the current audio time to localStorage
function saveAudioProgress() {
    if (audio) {
        const currentTime = audio.currentTime;
        localStorage.setItem(bookId, currentTime);
        //console.log(`Saved progress for ${bookId}: ${currentTime}`);
    }
}

// Save progress every 5 seconds (adjust as needed)
setInterval(saveAudioProgress, 5000);