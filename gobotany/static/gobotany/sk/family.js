dojo.provide('gobotany.sk.family');

dojo.require('dojox.data.JsonRestStore');

dojo.require('gobotany.sk.glossarize');
dojo.require('gobotany.sk.image_browse');

gobotany.sk.family.init = function(family_slug) {
    var img = dojo.query('#family #images img')[0];
    var msg = dojo.query('#family #images span')[0];

    // Load the family URL and set up the images.
    family_url = '/families/' + family_slug + '/';
    var family_store = new dojox.data.JsonRestStore({target: family_store});
    // TODO: call family URL as is done with taxon URL for species pages


    // Make glossary highlights appear where appropriate throughout the page.
    var glossarizer = gobotany.sk.results.Glossarizer();
    dojo.query('#info p').forEach(function(node) {
        glossarizer.markup(node);
    });
}
