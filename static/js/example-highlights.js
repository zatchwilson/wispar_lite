// https://futurepress.github.io/epub.js/examples/highlights.html
    // Load the opf
    var book = ePub("https://s3.amazonaws.com/moby-dick/OPS/package.opf");

    var rendition = book.renderTo("viewer", {
      width: "100%",
      height: 600,
      ignoreClass: 'annotator-hl',
      manager: "continuous"
    });

    var displayed = rendition.display(6);

    // Navigation loaded
    book.loaded.navigation.then(function(toc){
      // console.log(toc);
    });

    var next = document.getElementById("next");
    next.addEventListener("click", function(){
      rendition.next();
    }, false);

    var prev = document.getElementById("prev");
    prev.addEventListener("click", function(){
      rendition.prev();
    }, false);

    var keyListener = function(e){

      // Left Key
      if ((e.keyCode || e.which) == 37) {
        rendition.prev();
      }

      // Right Key
      if ((e.keyCode || e.which) == 39) {
        rendition.next();
      }

    };

    rendition.on("keyup", keyListener);
    document.addEventListener("keyup", keyListener, false);

    rendition.on("relocated", function(location){
      // console.log(location);
    });


    // Apply a class to selected text
    rendition.on("selected", function(cfiRange, contents) {
      rendition.annotations.highlight(cfiRange, {}, (e) => {
        console.log("highlight clicked", e.target);
      });
      contents.window.getSelection().removeAllRanges();

    });

    this.rendition.themes.default({
      '::selection': {
        'background': 'rgba(255,255,0, 0.3)'
      },
      '.epubjs-hl' : {
        'fill': 'yellow', 'fill-opacity': '0.3', 'mix-blend-mode': 'multiply'
      }
    });

    // Illustration of how to get text from a saved cfiRange
    var highlights = [];

    rendition.on("selected", function(cfiRange) {

      book.getRange(cfiRange).then(function (range) {
        var text;

        if (range) {
          text = range.toString();

          remove.onclick = function () {
            rendition.annotations.remove(cfiRange);
            return false;
          };

          highlights.appendChild(text);
        }

      })

    });

  