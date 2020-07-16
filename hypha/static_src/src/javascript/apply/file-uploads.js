jQuery(function ($) {
    'use strict';

    // Initialize django-file-form
    $('form').get().forEach(function (form) {
        // Prevent initilising it multiple times and run it for forms
        // that have a `form_id` field added by django-file-form.
        if (!form.initUploadFieldsDone && form.querySelector('[name=form_id]')) {
            init(form);
            form.initUploadFieldsDone = true;
        }
    });

    function init(form) {
        window.initUploadFields(form);

        // Hide wrapper elements for hidden inputs added by django-file-form
        $('input[type=hidden]').closest('.form__group').hide();

        var allowedExtensions = form.querySelector('[name=files]').accept.split(', ');

        // TODO: this currently raises an exception when trying to remove an invalid file.
        // Remove files from the list that have an invalid file extension.
        $('.dff-files').on('drop', function (e) {
            var items = e.originalEvent.dataTransfer.items;
            var files = e.originalEvent.dataTransfer.files;
            for (var i = 0; i < files.length; i++) {
                var extension = '.' + files[i].name.split('.').slice(-1)[0];
                if (!allowedExtensions.includes(extension)) {
                    items.remove(i);
                }
            }
        });
    }

});
