function makeTableSortable(table) {
    console.log('make table sortable...');
    // Select all header cells with the class "sort-column" in the table header.
    const sortableColumns = table.querySelectorAll("thead tr .sort-column");

    sortableColumns.forEach(header => {
        header.setAttribute("role", "button");
        header.setAttribute("aria-sort", "none");

        header.addEventListener("click", function () {
            const clickedHeader = this;
            // Get the index of the clicked header within its parent row.
            const parentRow = clickedHeader.parentElement;
            const children = Array.from(parentRow.children);
            const columnIndex = children.indexOf(clickedHeader);

            // Clear sorting classes and aria attributes from other columns.
            sortableColumns.forEach(col => {
                if (col !== clickedHeader) {
                    col.classList.remove("sort-asc", "sort-desc");
                    col.setAttribute("aria-sort", "none");
                }
            });

            // Toggle sorting class on the clicked header between ascending and descending.
            if (clickedHeader.classList.contains("sort-asc")) {
                clickedHeader.classList.remove("sort-asc");
                clickedHeader.classList.add("sort-desc");
                clickedHeader.setAttribute("aria-sort", "descending");
            } else {
                clickedHeader.classList.remove("sort-desc");
                clickedHeader.classList.add("sort-asc");
                clickedHeader.setAttribute("aria-sort", "ascending");
            }

            const ascending = clickedHeader.classList.contains("sort-asc");
            const descending = clickedHeader.classList.contains("sort-desc");

            // Get the table body and its rows.
            const tbody = table.querySelector("tbody");
            const rows = Array.from(tbody.querySelectorAll("tr"));

            // Sort the rows based on the text content of the targeted cell.
            rows.sort((rowA, rowB) => {
                const cellA = rowA.querySelectorAll("td")[columnIndex];
                const cellB = rowB.querySelectorAll("td")[columnIndex];
                const textA = cellA.textContent.trim();
                const textB = cellB.textContent.trim();

                return ascending
                    ? textA.localeCompare(textB)
                    : textB.localeCompare(textA);
            });

            // Append the sorted rows back to the tbody.
            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

// Apply the functionality to all tables with the "sortable" class.
document.querySelectorAll(".sortable").forEach(table => {
    makeTableSortable(table);
});

const group_selector = document.getElementById("select-role")
const delete_button = document.getElementById('delete-role-button')
const new_role_button = document.getElementById('new-role-button')
const submit_changes_button = document.getElementById('edit-role-button')
const group_dict = JSON.parse(document.getElementsByName('permissions_set')[0].content)
const add_content_check = document.getElementById('add_content_check')
const remove_content_check = document.getElementById('remove_content_check')
const manage_perms_check = document.getElementById('manage_perms_check')
// const remove_users_check = document.getElementById('remove_users_check')

group_selector.addEventListener("change", function() {

    if(group_selector.value == "createNewGroup") {
        uncheck_all()
        const group_name_inputs = document.getElementsByClassName("hidden_new_group_name_input")
        Array.from(group_name_inputs).forEach((input) => {
            input.classList.remove('hidden_new_group_name_input')
            input.classList.add('visible_new_group_name_input')
            new_role_button.classList.remove('new-role-hidden')
            new_role_button.classList.add('new-role')
            submit_changes_button.classList.add('edit-role-hidden')
            submit_changes_button.classList.remove('edit-role')
            delete_button.classList.add("delete-hidden")
            delete_button.classList.remove("delete")
        })
    } else {
        const group_name_inputs = document.getElementsByClassName("visible_new_group_name_input")
        Array.from(group_name_inputs).forEach((input) => {
            input.classList.add('hidden_new_group_name_input')
            input.classList.remove('visible_new_group_name_input')
            new_role_button.classList.remove('new-role')
            new_role_button.classList.add('new-role-hidden')
        })
    }

    if(group_selector.value == '') {
        uncheck_all()
        delete_button.classList.add("delete-hidden")
        delete_button.classList.remove("delete")
        new_role_button.classList.add("new-role-hidden")
        new_role_button.classList.remove("new-role")
        submit_changes_button.classList.add("edit-role-hidden")
        submit_changes_button.classList.remove("edit-role")
    } else if(group_selector.value != 'createNewGroup'){
        delete_button.classList.remove("delete-hidden")
        delete_button.classList.add("delete")
        submit_changes_button.classList.remove("edit-role-hidden")
        submit_changes_button.classList.add("edit-role")
        const curr_permissions_set = group_dict[group_selector.value]
        if (curr_permissions_set.includes('add_book')) {
            add_content_check.checked = true
        }

        if (curr_permissions_set.includes('delete_book')) {
            remove_content_check.checked = true
        }

        if (curr_permissions_set.includes('change_permission')) {
            manage_perms_check.checked = true
        }
    }
})

function uncheck_all() {
    add_content_check.checked = false
    remove_content_check.checked = false
    manage_perms_check.checked = false
}

const new_role_name_input = document.getElementById("new_group_name_input")
new_role_button.disabled = true
new_role_name_input.onkeyup = function() {
    const input_length = new_role_name_input.value.length
    new_role_button.disabled = (input_length < 2 || input_length > 30)
}


const registration_toggle = document.getElementById("registration_toggle")

if (registration_toggle != null) {
    const registrations_are_active = document.getElementsByName('registrations_are_active')[0].content
    const registration_toggle_form = document.getElementById("registration_toggle_form")
    
    registration_toggle.checked = registrations_are_active == "True"
    
    registration_toggle.addEventListener("click", () => {fetchThis("/profile/register/toggle/", "POST", new FormData(registration_toggle_form))})
    
}

function fetchThis(url, method, formData) {
    fetch(url, {
        method: method,
        body: formData,
        credentials: 'include',
    })
        .then(response => {
            if (response.ok) {
                console.log("Successful...");
            } else {
                console.error("Error...", response.statusText);
            }
        })
        .catch(error => {
            console.error("Error with the request:", error);
        });
}