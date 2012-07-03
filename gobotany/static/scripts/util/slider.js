define([
    'bridge/jquery'
], function ($) {
    // Constructor
    var Slider = function (container_element, options) {
        this.container_element = container_element;
        this.options = $.extend({}, this.defaults, options);
        this.is_down = false;
        this.is_touch = navigator.userAgent.match(
                        /(iPad|iPod|iPhone|Android)/) ? true : false;
        this.bar_width = null;
        this.thumb_width = null;
        this.init();
    };

    // Prototype definition
    Slider.prototype = {
        defaults: {
            id: 'gb-slider',
            left_offset: 295,
            orientation: 'horizontal',
            value: null
        },

        build_slider: function () {
            var slider = $('<div id="' + this.options.id + '">' +
                           '<div class="label"></div>' +
                           '<div class="bar"></div>' +
                           '<div class="thumb"></div>' +
                           '</div>');
            console.log('about to append:', slider);
            $(this.container_element).append(slider);
        },

        handle_press: function () {
            this.is_down = true;
            console.log('handle_press - is_down:', this.is_down);
        },

        handle_move: function (event, thumb) {
            var x = event.pageX;
            var client_x = event.clientX;
            var left = x - this.options.left_offset;
            if (this.is_down) {
                console.log('handle_move - is_down: ' + this.is_down +
                            ' pageX: ', + x + ' clientX:' + client_x +
                            ' left: ', left);
                if ((left >= 0) && (left <= this.options.bar_width -
                                    this.options.thumb_width )) {
                    $(thumb).css({'left': left});
                }
            }
            //else {
            //    console.log('handle_move - is_down: ' + this.is_down);
            //}
        },

        handle_release: function () {
            this.is_down = false;
            console.log('handle_release - is_down:', this.is_down);
        },

        id_selector: function () {
            return '#' + this.options.id;
        },

        set_label: function (value) {
            var label = $(this.container_element).find(this.id_selector() +
                                                       ' .label')[0];
            $(label).html(value);
        },

        init: function () {
            var self = this;
            var id_selector = '#' + this.options.id;

            console.log('Slider init(): value:', self.options.value);

            self.build_slider();
            self.set_label(self.options.value);
            
            var bar = $(this.container_element).find(self.id_selector() +
                                                     ' .bar')[0];
            this.options.bar_width = $(bar).width();
            console.log('bar_width:', this.options.bar_width);

            var thumb = $(this.container_element).find(self.id_selector() +
                                                       ' .thumb')[0];
            this.options.thumb_width = $(thumb).width();
            console.log('thumb_width:', this.options.thumb_width);

            if (this.is_touch) {
                $(thumb).bind({
                    'touchstart.Slider': function () {
                        self.handle_press();
                    },
                    'touchmove.Slider': function (event) {
                        event.preventDefault();   // prevent scrolling
                        var original_event = event.originalEvent;
                        self.handle_move(original_event, thumb);
                    },
                    'touchend.Slider': function () {
                        self.handle_release();
                    }
                });
            }
            else {
                $(thumb).bind({
                    'mousedown.Slider': function () {
                        self.handle_press();
                    },
                    'mousemove.Slider': function (event) {
                        event.preventDefault();   // prevent scrolling
                        var original_event = event.originalEvent;
                        self.handle_move(original_event, thumb);
                    },
                    'mouseout.Slider': function () {
                        self.handle_release();
                    }
                });

                $('body').bind({
                    'mouseup.Slider': function () {
                        self.handle_release();
                    }
                });
            }

        }   // end init()
    };   // end prototype definition

    // Extend jQuery with slider capability.
    $.fn.slider = function (options) {
        new Slider(this, options);
        return this;
    };
});
