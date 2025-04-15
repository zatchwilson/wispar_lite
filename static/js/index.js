// Row One 
var oneN = document.getElementById('row-one-next');
oneN.onclick = function (event) {
    event.preventDefault();
    var container = document.getElementById('row-one');
    sideScroll(container, 'right', 1, 504, 10);
};

var OneP = document.getElementById('row-one-prev');
OneP.onclick = function (event) {
    event.preventDefault();
    var container = document.getElementById('row-one');
    sideScroll(container, 'left', 1, 504, 10);
};

// Row Two
var twoN = document.getElementById('row-two-next');
twoN.onclick = function (event) {
    event.preventDefault();
    var container = document.getElementById('row-two');
    sideScroll(container, 'right', 1, 504, 10);
};

var twoP = document.getElementById('row-two-prev');
twoP.onclick = function () {
    event.preventDefault(event);
    var container = document.getElementById('row-two');
    sideScroll(container, 'left', 1, 504, 10);
};

// Row Three
var threeN = document.getElementById('row-three-next');
threeN.onclick = function (event) {
    event.preventDefault();
    var container = document.getElementById('row-three');
    sideScroll(container, 'right', 1, 504, 10);
};

var threeP = document.getElementById('row-three-prev');
threeP.onclick = function (event) {
    event.preventDefault();
    var container = document.getElementById('row-three');
    sideScroll(container, 'left', 1, 504, 10);
};

function sideScroll(element, direction, speed, distance, step) {
    let scrollAmount = 0;
    var slideTimer = setInterval(function () {
        if (direction == 'left') {
            element.scrollLeft -= step;
        } else {
            element.scrollLeft += step;
        }
        scrollAmount += step;
        if (scrollAmount >= distance) {
            window.clearInterval(slideTimer);
        }
    }, speed);
}
