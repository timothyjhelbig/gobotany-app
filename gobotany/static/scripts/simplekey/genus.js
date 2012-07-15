define([
    'bridge/jquery',
    'gobotany/sk/PhotoHelper',
    'util/sidebar',
    'util/activate_search_suggest',
    'util/shadowbox_init',
    'simplekey/glossarize'
], function($, PhotoHelper, sidebar, activate_search_suggest, shadowbox_init,
            glossarize) {

    var genus = {};

    var _setup_page = function() {
        glossarize($('.description'));
        sidebar.setup();

        var photo_helper = PhotoHelper();

        // Wire up each image link to a Shadowbox popup handler.
        var $images = $('.pics .plant');
        $images.each(function(i, plant_image_div) {
            var frame = $(plant_image_div).children('.frame');
            var link = $(plant_image_div).children('a');
            var href = $(link).attr('href');
            var title = $(link).attr('title');
            $(frame).click(function() {
                // Open the image.
                Shadowbox.open({
                    content: href,
                    player: 'img',
                    title: title,
                    options: {
                        onOpen: photo_helper.prepare_to_enlarge,
                        onFinish: photo_helper.process_credit
                    }
                });
            });
        });
    };

    genus.init = function() {
        $(document).ready(function() {
            _setup_page();
        });
    };

    return genus;
});
