document.addEventListener("DOMContentLoaded", function () {
    let rowOne = document.getElementById('row_one');
    let rowTwo = document.getElementById('row_two');
    let rowThree = document.getElementById('row_three');
    var libraryVisible = document.getElementById('library-visible').content;
    let square = document.getElementById('square');
    let round = document.getElementById('round');
    let fontSelect = document.getElementById('interface-font-select')
    let customEpubDefault = document.getElementById('custom-epub-default');

    const rows = [
        { id: rowOne.name, title: rowOne.title, visible: rowOne.content },
        { id: rowTwo.name, title: rowTwo.title, visible: rowTwo.content },
        { id: rowThree.name, title: rowThree.title, visible: rowThree.content },
    ];

    console.log(rows);
    const listContainer = document.getElementById("home-row-order");

    // Create draggable row elements
    rows.forEach(row => {
        const li = document.createElement("li");
        li.setAttribute("draggable", "true");
        li.classList.add("draggable-row");

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.id = row.id;
        checkbox.name = row.id;
        checkbox.checked = (row.visible === "True");
        console.log(checkbox.checked);
        checkbox.addEventListener('click', () => updateUserSetting("home-screen"));

        const label = document.createElement("label");
        label.setAttribute("for", row.id);
        label.textContent = `Show ${row.title} Row`;

        li.appendChild(checkbox);
        li.appendChild(label);
        li.addEventListener('dragover', (event) => dragOver(event));
        li.addEventListener('dragstart', (event) => dragStart(event));
        li.addEventListener('dragend', (event) => dragEnd(event));
        listContainer.appendChild(li);
    });

    // Create the library visible element (non-draggable)
    const liLibrary = document.createElement("li");
    liLibrary.setAttribute("id", "library-list-element");

    const checkboxLibrary = document.createElement("input");
    checkboxLibrary.type = "checkbox";
    checkboxLibrary.id = "library";
    checkboxLibrary.name = "library";
    checkboxLibrary.checked = (libraryVisible === "True");
    checkboxLibrary.addEventListener('click', () => updateUserSetting("home-screen"));

    const labelLibrary = document.createElement("label");
    labelLibrary.setAttribute("for", "library");
    labelLibrary.setAttribute("id", "library-id");
    labelLibrary.textContent = "Show Library On Homepage";

    liLibrary.appendChild(checkboxLibrary);
    liLibrary.appendChild(labelLibrary);
    listContainer.appendChild(liLibrary);

    document.querySelectorAll('input[name="wispar_theme"]').forEach(radio => {
        radio.addEventListener('click', () => toggleTheme(radio.value));
    });
    var theme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;
    if (theme) {
        document.getElementById(theme + '_theme').checked = true;
    } else {
        document.getElementById('Modern Light_theme').checked = true;
    }

    fontSelect.value = document.getElementById('ui-font').content;

    // Home Screen Settings
    if (fontSelect) {
        fontSelect.addEventListener('change', () => updateFont(fontSelect.value));    
    }
    customEpubDefault.addEventListener('click', () => updateUserSetting("custom-epub"));

    var rounded_corners = document.getElementsByName('rounded_corners')[0].content
    if (rounded_corners === 'True') {
        round.checked = true;
    } else {
        square.checked = true;
    }
    square.addEventListener('click', () => updateUI('square'));
    round.addEventListener('click', () => updateUI('round'));


    function updateOrder() {
        const orderContainer = document.getElementById('home-row-order');
        const rows = orderContainer.querySelectorAll('li');

        // Assume each <li> contains an <label> whose id is unique (like "recently-added")
        const order = Array.from(rows).map(li => {
            const input = li.querySelector('input');
            return input ? input.id : '';
        });

        let hiddenInput = document.getElementById('row_order');
        // Set the value to the comma-separated order
        console.log(`New Row Order: ${order.join(',')}`);
        hiddenInput.value = order.join(',');
        updateUserSetting('home-screen');
    }


    function updateFont(font) {
        document.documentElement.style.setProperty('--default-font', font);
        updateUserSetting("uiFont");
    }
    
    
    function updateUserSetting(setting_element) {
        console.log('Updating Setting!');
        const form = document.getElementById(setting_element);
        const formData = new FormData(form);
        //console.log('Updating User Settings: ', formData);
        fetchThis(form.action, "POST", formData);
    }
    
    function updateUI(style) {
        if (style === 'round') {
            document.documentElement.style.setProperty('--optional-radius', '1rem');
        }
        else {
            document.documentElement.style.setProperty('--optional-radius', '0rem');
        }
        const form = document.getElementById("radius");
        const formData = new FormData(form);
        fetchThis(form.action, "POST", formData)
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
    
    let selected = null
    function dragOver(e) {
        e.preventDefault();
        // Get the closest parent li with the class "draggable-row"
        const target = e.target.closest('.draggable-row');
        // If there's no target or the target is the dragged element, do nothing.
        if (!target || target === selected) return;
        
        if (isBefore(selected, target)) {
          target.parentNode.insertBefore(selected, target);
        } else {
          target.parentNode.insertBefore(selected, target.nextSibling);
        }
      }
      
    
    function dragEnd() {
        selected = null;
        updateOrder();
    }
    
    function dragStart(e) {
        console.log('DRAG Start EVENT');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', null);
        selected = e.target;
    }
    
    function isBefore(el1, el2) {
        let cur;
        if (el2.parentNode === el1.parentNode) {
            for (cur = el1.previousSibling; cur; cur = cur.previousSibling) {
                if (cur === el2) return true;
            }
        }
        return false;
    }
    

});

export function toggleTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}