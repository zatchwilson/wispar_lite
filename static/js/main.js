var sidebarHidden = 'no';

// Wait for the DOM to load
document.addEventListener("DOMContentLoaded", function () {
    // Set theme from local storage on page load
    const currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;
    try {
        if (currentTheme) {
            document.documentElement.setAttribute('data-theme', currentTheme);
        }
    }
    catch (e) {
        console.log(e);
    }

    let uiFont = document.getElementById('ui-font').content;
    if (uiFont) {
        document.documentElement.style.setProperty('--default-font', uiFont);
    }

    var rounded_corners = document.getElementsByName('rounded_corners')[0].content
    if (rounded_corners) {
        if (rounded_corners === 'True') {
            document.documentElement.style.setProperty('--optional-radius', '1rem');
        }
        else {
            document.documentElement.style.setProperty('--optional-radius', '0rem');
        }
    }

});



// Define breakpoints (adjust as needed)
const PHONE_MAX = 600;
const TABLET_MAX = 1024;

const sidebar = document.getElementById("sidebar");
const toggleButton = document.getElementById("toggleSidebar");

// Helper: determine device type by window width
function getDeviceType() {
    const width = window.innerWidth;
    if (width < PHONE_MAX) {
        return "phone";
    } else if (width < TABLET_MAX) {
        return "tablet";
    } else {
        return "desktop";
    }
}

// Set the sidebar state by applying a CSS class
// and saving the state in localStorage.
function setSidebarState(state) {
    // Remove any previous state classes
    sidebar.classList.remove("sidebar-hidden", "sidebar-collapsed", "sidebar-expanded");
    if (state === "hidden") {
        sidebar.classList.add("sidebar-hidden");
    } else if (state === "collapsed") {
        sidebar.classList.add("sidebar-collapsed");
    } else if (state === "expanded") {
        sidebar.classList.add("sidebar-expanded");
    }
    localStorage.setItem("sidebarState", state);
}

// Return the default state based on the device type.
function getDefaultState(deviceType) {
    if (deviceType === "phone") return "hidden";
    if (deviceType === "tablet") return "collapsed";
    if (deviceType === "desktop") return "expanded";
}

// Toggle between states depending on device type.
function toggleState() {
    const deviceType = getDeviceType();
    // Get current state from localStorage or use default if not set.
    let currentState = localStorage.getItem("sidebarState") || getDefaultState(deviceType);

    if (deviceType === "phone") {
        // For phones: toggle between hidden and collapsed.
        if (currentState === "hidden") {
            setSidebarState("collapsed");
        } else {
            setSidebarState("hidden");
        }
    } else {
        // For tablets and desktops: toggle between collapsed and expanded.
        if (currentState === "collapsed") {
            setSidebarState("expanded");
        } else {
            setSidebarState("collapsed");
        }
    }
}

// On document ready, set initial state.
document.addEventListener("DOMContentLoaded", function () {
    const deviceType = getDeviceType();
    let savedState = localStorage.getItem("sidebarState");
    if (deviceType === "phone") {
        savedState = "hidden"
    } else
    if (!savedState || savedState === "hidden") {
        // Use default state based on device if none saved.
        savedState = getDefaultState(deviceType);
        localStorage.setItem("sidebarState", savedState);
    }
    setSidebarState(savedState);
});

// Attach toggle function to the button.
toggleButton.addEventListener("click", toggleState);

// Handles the 'sticky' scrolling of the header, sidebar, and TOC
const header = document.querySelector('header');
const toc = document.querySelector('#toc')
var lastScrollY = 0;
let scheduled = false;

window.addEventListener('scroll', () => {
  if (!scheduled) {
    requestAnimationFrame(() => {
      
        //console.log('last scrollY: ' + lastScrollY)
        let currentScrollY = window.scrollY;
        //console.log('current scrollY: ' + currentScrollY)
        if (currentScrollY > lastScrollY + 100) {
            // Scrolling down
            //console.log("Down: " + scrollY)
            lastScrollY = currentScrollY;
            //console.log("setting last scroll to: " + lastScrollY);
            if (header) {
                header.style.top = '-3.5rem';
            }
            if (sidebar) {
                sidebar.style.top = '-.25rem';
            }
            if (toc) {
                toc.style.top = '0rem';
            }
        } else if (currentScrollY < lastScrollY - 100) {
            // Scrolling up
            //console.log("Up: " + scrollY)
            lastScrollY = currentScrollY;
            if (header) {
                header.style.top = '0';
            }
            if (sidebar) {
                if (getDeviceType() === 'phone') {
                    sidebar.style.top = '3rem';
                } else {
                    sidebar.style.top = '1rem';
                }
            }
            if (toc) {
                toc.style.top = '3rem';
            }
        }
        scheduled = false;
    });
    scheduled = true;
  }
});