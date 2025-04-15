document.addEventListener("DOMContentLoaded", function () {
    let iframe = document.getElementById('iframe_downloader');
    let gutenberg = document.getElementById('gutenberg');
    let librivox = document.getElementById('librivox');

    let buttons = document.getElementsByClassName('srcbutton');

    gutenberg.addEventListener('click', () => changeSrc('gutenberg'));
    librivox.addEventListener('click', () => changeSrc('librivox'));


    function changeSrc(city){

        for(var i = 0; i < buttons.length; i++){
            buttons[i].className = buttons[i].className.replace(" active", "");
        }

        switch(city){
            case 'gutenberg':
                iframe.title = 'Project Gutenberg';
                iframe.src = 'https://www.gutenberg.org/browse/scores/top';
                gutenberg.className += " active";
                break;
            case 'librivox':
                iframe.title = 'LibriVox';
                iframe.src = 'https://librivox.org/search?primary_key=0&search_category=title&search_page=1&search_form=get_results&search_order=catalog_date';
                librivox.className += " active";
                break;
        }
    }
    
});