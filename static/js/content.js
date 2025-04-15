// Wait for the DOM to load
document.addEventListener("DOMContentLoaded", function () {
    // Find the form by its ID
    const form = document.getElementById("asyncForm");
    const dropContainer = document.getElementById("dropcontainer");
    var uploadText = document.getElementById('drop-title');


    var fileUploadError = "";
    var progressFiles = 0;
    var totalFiles = 0;


    // Check if the form exists
    if (form) {
        const inputsAndButtons = form.querySelectorAll("input, button");
        inputsAndButtons.forEach(function (element) {
            if (element.type === 'file') {
                // Replace the file input to clear it
                const newInput = element.cloneNode();
                newInput.value = '';
                element.parentNode.replaceChild(newInput, element);
            }
        });
        // Attach a submit event listener to the form
        form.addEventListener("submit", function (event) {
            event.preventDefault(); // Prevent the default form submission

            if(form.books.files.length == 0)
                return

            totalFiles = form.books.files.length;

            inputsAndButtons.forEach(function (element) {
                element.disabled = true;
                element.style.display = 'none';
            });

            for (const file of form.books.files){
                upload_file(0, null, file);
            }

            inputsAndButtons.forEach(function (element) {
                element.disabled = false;
            });

            dropContainer.innerHTML = "Please don't refresh until all books have finished uploading. Progress: 0/" + totalFiles.toString();

            if (fileUploadError !== "")
            {
                dropContainer.innerHTML = fileUploadError;
            }
        });
    }


    // Select all links with the class "delete-book-link"
    const bookLinks = document.querySelectorAll('.rounded-rectangle');
    const overlay = document.getElementById('overlay');
    const cancelButtons = document.querySelectorAll('.cancel');
    const deleteButtons = document.querySelectorAll('.delete')

    bookLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();

            // Get the book ID from the link ID
            const bookId = this.id;
            console.log("Book clicked:", bookId);

            openModal(bookId);
        });
    });

    overlay.addEventListener('click', function (e) {
        closeAnyModal();
    });

    function openModal(bookId) {
        let modal = document.getElementById('modal-'+bookId);
        overlay.style.display = 'block';
        modal.style.display = 'block';
        
        deleteButtons.forEach(button => {
            button.addEventListener('click', function (e) {
                modal.style.display = 'none';
                let confirmModal = document.getElementById("confirm-modal")
                confirmModal.style.display = 'block';
                let confirmed = document.getElementById("delete-confirm");
                confirmed.addEventListener("click", function (e){
                    deleteBook(bookId);
                });
                let cancel = document.getElementById('cancel-delete');
                cancel.addEventListener("click", function (e) {
                    closeAnyModal();
                });
            });
        });
        cancelButtons.forEach(cbutton => {
            cbutton.addEventListener('click', function (e) {
                closeModal(modal);
            });
        
        });

        var coverImg = document.getElementById(`edit-cover-${bookId}`);
        coverImg.addEventListener('click', function (e) {
            showCoverOptions(bookId);
        });
    }

    function showCoverOptions(bookId) {
        document.documentElement.style.setProperty('--show-hide', 'none');
        let coverImgContainer = document.getElementById(`cover-images-${bookId}`)
        coverImgContainer.style.display = 'flex';
        fetch(`/books/cover/${bookId}/options`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
        })
        .then(response => {
            if (!response.ok) {
              console.log(`Network response was not ok (status ${response.status})`);
            }
            // We expect JSON with an array of image URLs
            return response.json();
        })
        .then(data => {
            // data.images should be an array of image URLs
            console.log(data);
            const images = data.images;
            if (images.length > 0) {
                images.forEach(url => {
                    const img = new Image();
                    img.src = url;
                    img.addEventListener('click', function (e) {
                        console.log(`Clicked on: ${img.src}`)
                        const selectedImageInput = document.getElementById(`selectedImage-${bookId}`);
                        selectedImageInput.value = url;
                        let preview_img = document.getElementById(`edit-cover-${bookId}`);
                        preview_img.src = url;
                    });
                    // Append each image to the container
                    console.log('Appending img...')
                    coverImgContainer.appendChild(img);
                });   
            } else {
                console.log("No Covers Found...");
                document.documentElement.style.setProperty('--show-hide', 'block');
            }
        })
        .catch(error => {
            console.error("Error with the request:", error);
        });
      }
      

    function closeModal(modal) {
        overlay.style.display = 'none';
        modal.style.display = 'none';
    }

    
    function closeAnyModal() {
        let modals = document.querySelectorAll('.modal');
        overlay.style.display = 'none';
        modals.forEach(modal => {
            modal.style.display = 'none'; 
        });
    }

    function deleteBook(bookId) {
        // Send the book ID in the body of the DELETE request
        fetch('/content/', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({ bookId: bookId })
        })
            .then(response => {
                if (response.ok) {
                    console.log("Book deleted successfully");

                    window.location.reload();
                } else {
                    console.error("Error deleting the book:", response.statusText);
                }
            })
            .catch(error => {
                console.error("Error with the request:", error);
            });
    }
    
    // Find the form by its ID
    const metadataForms = document.querySelectorAll(".metadata-form");

    // Check if the form exists
    if (metadataForms) {
        metadataForms.forEach(form => {
            // Attach a submit event listener to the form
            form.addEventListener("submit", function (event) {
                event.preventDefault(); // Prevent the default form submission

                const formData = new FormData(form);

                // Send the form data using the Fetch API
                fetch(form.action, {
                    method: "PUT",
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify(Object.fromEntries(formData)),
                    credentials: 'include', // Include cookies if needed (e.g., for CSRF tokens)
                })
                    .then(function (data) {
                        window.location.reload();
                    })
                    .catch(function (error) {
                        form.before = "<output>Upload Failed! Please rety.</output>";
                        console.error("An error occurred:", error);
                    });
            }); 
        });
    } else {
        console.error("Metadata Form not found.");
    }
    // Sourced this from here:  nikitahl.com/custom-styled-input-type-file
    if (dropContainer) {
        const dropContainerChildren = dropContainer.querySelectorAll('*');
        const fileInput = document.getElementById("books");
        dropContainer.addEventListener("dragover", (e) => {
            // prevent default to allow drop
            e.preventDefault();
        }, false)
    
        dropContainer.addEventListener("dragenter", () => {
            dropContainer.classList.add("drag-active");
        })
    
        dropContainer.addEventListener("dragleave", () => {
            dropContainer.classList.remove("drag-active");
        })
    
        dropContainer.addEventListener("drop", (e) => {
            e.preventDefault();
            dropContainer.classList.remove("drag-active");
            fileInput.files = e.dataTransfer.files;
        })
    
        dropContainerChildren.forEach(item => {
            item.addEventListener('dragover', (e) => {
                dropContainer.classList.add("drag-active");
                e.stopPropagation()
            })
            item.addEventListener('dragenter', (e) => {
                dropContainer.classList.add("drag-active");
                e.stopPropagation()
            })
            item.addEventListener('dragleave', (e) => {
                dropContainer.classList.add("drag-active");
                e.stopPropagation()
            })
        })
    }

    //Max size of a given chunk (20MB)
    const max_length = 1024*1024*20;
    // Uploads files in chunks
    function upload_file(start, path, file) {
        var end;
        var existingPath = path;
        var formData = new FormData();
        var nextChunk = start + max_length + 1;
        var currentChunk = file.slice(start, nextChunk);
        var uploadedChunk = start + currentChunk.size;
        if (uploadedChunk >= file.size) {
            end = 1;
        } else {
            end = 0;
        }
        formData.append('file', currentChunk);
        formData.append('filename', file.name);
        formData.append('end', end);
        formData.append('existingPath', existingPath);
        formData.append('nextSlice', nextChunk);
        $.ajaxSetup({
        // make sure to send the header
            headers: {
                "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            }
        });
        $.ajax({
            url: '/content/',
            type: 'POST',
            dataType: 'json',
            cache: false,
            processData: false,
            contentType: false,
            data: formData,
            error: function (xhr) {
                fileUploadError = "Possible error uploading file. Please refresh and try again.";
            },
            success: function (res) {
                if (nextChunk < file.size) {
                    existingPath = res.existingPath;
                    upload_file(nextChunk, existingPath, file);
                }
                else
                {
                    progressFiles++;
                    dropContainer.innerHTML = "Please don't refresh until all books uploaded. Progress: " + progressFiles.toString() + "/" + totalFiles.toString();
                    if (progressFiles === totalFiles)
                    {
                        window.location.reload();
                    }

                }
            }
        })
    }
});
