import math

from django.http import HttpResponse
from django.utils import simplejson

from operator import itemgetter

from piston.handler import BaseHandler
from piston.utils import rc

import xml.etree.ElementTree
from xml.etree.ElementTree import parse

from gobotany.core import botany, models
from gobotany.settings import STATIC_ROOT

def _taxon_image(image):
    if image:
        img = image.image
        return {'url': img.url,
                'type': image.image_type.name,
                'rank': image.rank,
                'title': image.alt,
                'description': image.description,
                'thumb_url': img.thumbnail.absolute_url,
                'thumb_width': img.thumbnail.width(),
                'thumb_height': img.thumbnail.height(),
                'scaled_url': img.extra_thumbnails['large'].absolute_url,
                'scaled_width': img.extra_thumbnails['large'].width(),
                'scaled_height': img.extra_thumbnails['large'].height(),
                }
    return ''

def _simple_taxon(taxon):
    res = {}

    first_common_name = '';
    common_names = taxon.common_names.all()
    if (common_names):
        first_common_name = common_names[0].common_name

    res['scientific_name'] = taxon.scientific_name
    res['common_name'] = first_common_name
    res['genus'] = taxon.scientific_name.split()[0] # faster than .genus.name
    res['family'] = taxon.family.name
    res['id'] = taxon.id
    res['taxonomic_authority'] = taxon.taxonomic_authority
    res['default_image'] = _taxon_image(taxon.get_default_image())
    # Get all rank 1 images
    res['images'] = [_taxon_image(i) for i
                     in botany.species_images(taxon, max_rank=1)]
    res['factoid'] = taxon.factoid
    return res

def _taxon_with_chars(taxon):
    res = _simple_taxon(taxon)
    piles = taxon.get_piles()
    res['piles'] = piles
    for cv in taxon.character_values.all():
        res[cv.character.short_name] = cv.value
    preview_characters_per_pile = {}
    for pile_name in piles:
        pile = models.Pile.objects.get(name=pile_name)
        preview_characters_per_pile[pile.slug] = \
            PileHandler.plant_preview_characters(pile)
    res['plant_preview_characters_per_pile'] = preview_characters_per_pile
    return res


class TaxonQueryHandler(BaseHandler):
    methods_allowed = ('GET',)

    def read(self, request, scientific_name=None):
        getdict = dict(request.GET.items())  # call items() to avoid lists
        kwargs = {}
        for k, v in getdict.items():
            kwargs[str(k)] = v
        try:
            species = botany.query_species(**kwargs)
        except models.Character.DoesNotExist:
            return rc.NOT_FOUND

        if not scientific_name:
            # Only return character values for single item lookup, keep the
            # result list simple
            listing = [ _simple_taxon(s) for s in species.all() ]

            return {'items': listing,
                    'label': 'scientific_name',
                    'identifier': 'scientific_name'}
        elif species.exists():
            try:
                taxon = species.filter(scientific_name=scientific_name)[0]
            except IndexError:
                # A taxon wasn't returned from the database.
                return rc.NOT_FOUND

            # Return full taxon with characters for single item query
            return _taxon_with_chars(taxon)
        return {}


class TaxonCountHandler(BaseHandler):
    methods_allowed = ('GET',)

    def read(self, request):
        kwargs = {}
        for k, v in request.GET.items():
            kwargs[str(k)] = v
        try:
            species = botany.query_species(**kwargs)
        except models.Character.DoesNotExist:
            return rc.NOT_FOUND

        matched = species.count()
        return {'matched': matched,
                'excluded': models.Taxon.objects.count() - matched}


class TaxonImageHandler(BaseHandler):
    methods_allowed = ('GET',)

    def read(self, request):
        kwargs = {}
        for k, v in request.GET.items():
            kwargs[str(k)] = v
        try:
            images = botany.species_images(**kwargs)
        except models.Taxon.DoesNotExist:
            return rc.NOT_FOUND

        return [_taxon_image(image) for image in images]


class CharactersHandler(BaseHandler):
    """List characters and character values across all piles."""
    methods_allowed = ('GET')

    def read(self, request):
        group_map = {}
        for character_group in models.CharacterGroup.objects.all():
            group_map[character_group.id] = {
                'name': character_group.name,
                'characters': [],
                }
        for character in models.Character.objects.all():
            group_map[character.character_group_id]['characters'].append({
                    'short_name': character.short_name,
                    'name': character.name,
                    })
        return sorted(group_map.values(), key=itemgetter('name'))


class CharacterHandler(BaseHandler):
    """Retrieve all character values for a character regardless of pile."""
    methods_allowed = ('GET')

    def read(self, request, character_short_name):
        r = {'type': '', 'list': []}
        for cv in models.CharacterValue.objects.filter(
            character__short_name=character_short_name):
            if cv.value_str:
                r['type'] = 'str'
                r['list'].append(cv.value_str)
            elif cv.value_min is not None and cv.value_max is not None:
                r['type'] = 'length'
                r['list'].append([cv.value_min, cv.value_max])
        return r


class BasePileHandler(BaseHandler):
    methods_allowed = ('GET', 'PUT', 'DELETE')
    fields = ('name', 'friendly_name', 'description', 'resource_uri',
              'youtube_id', 'key_characteristics', 'notable_exceptions',
              'question', 'hint', 'default_image')

    def read(self, request, slug):
        try:
            return self.model.objects.get(slug=slug)
        except (models.PileGroup.DoesNotExist, models.Pile.DoesNotExist):
            return rc.NOT_FOUND

    def update(self, request, slug):
        obj = self.model.objects.get(slug=slug)
        for k, v in request.PUT.items():
            if k in self.fields:
                setattr(obj, k, v)
        obj.save()
        return obj

    def delete(self, request, slug):
        obj = self.model.objects.get(slug=slug)
        obj.delete()
        return rc.DELETED

    @staticmethod
    def default_image(pile=None):
        if pile is not None:
            return _taxon_image(pile.get_default_image())


class PileHandler(BasePileHandler):
    model = models.Pile
    fields = BasePileHandler.fields + ('character_groups', 'default_filters',
        'plant_preview_characters')

    @staticmethod
    def resource_uri(pile=None):
        return 'api-pile', ['slug' if pile is None else pile.id]

    @staticmethod
    def character_groups(pile=None):
        groups = models.CharacterGroup.objects.filter(
            character__character_values__pile=pile).distinct()
        return [dict(name=group.name,
                     id=group.id) for group in groups]

    @staticmethod
    def default_filters(pile=None):
        filters = []
        default_filters = list(
            models.DefaultFilter.objects.filter(pile=pile)
            .select_related('character')
            )

        for default_filter in default_filters:
            filter = {}
            filter['character_short_name'] = \
                default_filter.character.short_name
            filter['character_friendly_name'] = \
                default_filter.character.friendly_name
            filter['order'] = default_filter.order
            filter['value_type'] = default_filter.character.value_type
            filter['unit'] = default_filter.character.unit
            filter['notable_exceptions'] = getattr(default_filter,
                                                   'notable_exceptions', u'')
            filter['key_characteristics'] = getattr(default_filter,
                                                    'key_characteristics', u'')
            filter['question'] = default_filter.character.question
            filter['hint'] = default_filter.character.hint
            filters.append(filter)
        return filters

    @staticmethod
    def plant_preview_characters(pile=None):
        characters_list = []
        plant_preview_characters = list(
            models.PlantPreviewCharacter.objects.filter(pile=pile)
            .select_related('character', 'partner_site')
            )

        for preview_character in plant_preview_characters:
            character = {}
            character['character_short_name'] = \
                preview_character.character.short_name
            character['character_friendly_name'] = \
                preview_character.character.friendly_name
            character['order'] = preview_character.order
            partner_site = None
            if preview_character.partner_site:
                partner_site = preview_character.partner_site.short_name
            character['partner_site'] = partner_site
            character['unit'] = preview_character.character.unit
            character['value_type'] = preview_character.character.value_type
            characters_list.append(character)
        return characters_list


class PileGroupHandler(BasePileHandler):
    model = models.PileGroup

    @staticmethod
    def resource_uri(pilegroup=None):
        return 'api-pilegroup', ['slug' if pilegroup is None else pilegroup.id]


class PileListingHandler(BaseHandler):
    methods_allowed = ('GET',)

    def read(self, request):
        lst = [x for x in models.Pile.objects.all()]
        return {'items': lst}


class PileGroupListingHandler(BaseHandler):
    methods_allowed = ('GET',)

    def read(self, request):
        lst = [x for x in models.PileGroup.objects.all()]
        return {'items': lst}


class CharacterValuesHandler(BaseHandler):
    methods_allowed = ('GET',)

    def _read(self, request, pile_slug, character_short_name):
        pile = models.Pile.objects.get(slug=pile_slug)
        character = models.Character.objects.get(
            short_name=character_short_name)

        for cv in models.CharacterValue.objects.filter(
            pile=pile, character=character):

            key_characteristics = cv.key_characteristics
            notable_exceptions = cv.notable_exceptions

            image_url = ''
            thumbnail_url = ''
            if cv.image:
                image_url = cv.image.url
                thumbnail_url = cv.image.thumbnail.absolute_url

            yield {'value': cv.value,
                   'friendly_text': cv.friendly_text,
                   'key_characteristics': key_characteristics,
                   'notable_exceptions': notable_exceptions,
                   'image_url': image_url,
                   'thumbnail_url': thumbnail_url}

    # Piston doesn't seem to like being returned a generator
    def read(self, request, pile_slug, character_short_name):
        try:
            return [x for x in self._read(request, pile_slug,
                                          character_short_name)]
        except (models.Pile.DoesNotExist, models.Character.DoesNotExist):
            return rc.NOT_FOUND

class DistributionMapHandler(BaseHandler):
    methods_allowed = ('GET',)

    def _shade_map(self, svgmap, distribution, hexcolor='#ff0000', opacity=1):
        """Color in New England states that match the passed distribution
        list. Note: this method needs to be modified to color in counties
        instead of states when we get the county level data."""

        # Shade in the color of the states.
        inkscape_label = '{http://www.inkscape.org/namespaces/inkscape}label'
        nodes = svgmap.findall('{http://www.w3.org/2000/svg}path')
        for node in nodes:
            if inkscape_label in node.keys():
                label = node.attrib[inkscape_label]   # e.g. Hartford, CT
                state = label[-2:]                    # e.g. CT
                if state in distribution:
                    style = node.get('style')
                    shaded_style = style.replace('fill:none;', 'fill:%s;' % \
                                                str(hexcolor))
                    shaded_style = shaded_style.replace('stroke-opacity:1;', \
                                                'stroke-opacity:%s;' % str(opacity))
                    node.set('style', shaded_style)

        # Shade in the color of the 'present' legend box.
        rect_nodes = svgmap.findall('{http://www.w3.org/2000/svg}rect')
        for rect_node in rect_nodes:
            if rect_node.get('id') == 'present-box':
                style = rect_node.get('style')
                shaded_style = style.replace('fill:#000000;fill-opacity:0;',
                                             'fill:%s;fill-opacity:%s;' % \
                                             (hexcolor, str(opacity)))
                rect_node.set('style', shaded_style)

    def read(self, request, genus, specific_epithet):
        """Return an SVG map of New England with counties that contain the
        species shaded in.
        """
        STATES_DELIMITER = '|'

        blank_map  = ''.join([STATIC_ROOT,
            '/graphics/new-england-counties.svg'])

        name = ' '.join([genus.title(), specific_epithet.lower()])
        taxon = models.Taxon.objects.filter(scientific_name=name)
        distribution = []
        if len(taxon) > 0:
            states = taxon[0].distribution.replace(' ', '').split( \
                STATES_DELIMITER)
            distribution = [state.strip() for state in states]

        svg = parse(blank_map)
        self._shade_map(svg, distribution, hexcolor='#D5ECC5', opacity=1)

        if taxon:
            return HttpResponse(xml.etree.ElementTree.tostring(svg.getroot()),
                mimetype="image/svg+xml")


class FamilyHandler(BaseHandler):
    methods_allowed = ('GET',)
    
    def read(self, request, family_slug):
        try:
            family = models.Family.objects.get(slug=family_slug)
        except (models.Family.DoesNotExist):
            return rc.NOT_FOUND

        #images = family.images.all() # TODO: filter image_type 'example image'
        # For now, just use all the images from this family's species.
        images = []
        taxa = models.Taxon.objects.filter(family=family)
        for taxon in taxa:
            images = images + [_taxon_image(i) for i in taxon.images.all()]

        drawings = family.images.all() # TODO: filter image_type 'example drawing'

        return {'name': family.name,
                'slug': family.slug,
                'images': images,
                'drawings': drawings}


class GenusHandler(BaseHandler):
    methods_allowed = ('GET',)

    def read(self, request, genus_slug):
        try:
            genus = models.Genus.objects.get(slug=genus_slug)
        except (models.Genus.DoesNotExist):
            return rc.NOT_FOUND

        #images = genus.images.all() # TODO: filter image_type 'example image'
        # For now, just use all the images from this genus's species.
        images = []
        taxa = models.Taxon.objects.filter(genus=genus)
        for taxon in taxa:
            images = images + [_taxon_image(i) for i in taxon.images.all()]

        drawings = genus.images.all() # TODO: filter image_type 'example drawing'

        return {'name': genus.name,
                'slug': genus.slug,
                'images': images,
                'drawings': drawings}


class PlantNamesHandler(BaseHandler):
    methods_allowed = ('GET',)

    """Return scientific and common name matches for a string."""
    def read(self, request):
        MAX_NAMES = 20   # Max. total names, both sci. and common
        query = request.GET.get('q', '')
        names = []
        if query != '':
            scientific_names = list(models.PlantName.objects.filter(
                scientific_name__istartswith=query)[:MAX_NAMES])
            common_names = list(models.PlantName.objects.filter(
                common_name__istartswith=query).order_by(
                'common_name')[:MAX_NAMES])

            # Balance the lists if necessary so that the total returned
            # is as close to the maximum as possible.
            half_max = int(math.floor(MAX_NAMES / 2))
            if len(scientific_names) >= half_max and \
               len(common_names) >= half_max:
                # Return half scientific and half common names.
                scientific_names = scientific_names[:half_max]
                common_names = common_names[:half_max]
            elif len(scientific_names) >= half_max and \
                 len(common_names) < half_max:
                 # Return more sci. names because common names are fewer.
                 scientific_names = scientific_names[:(MAX_NAMES - len(
                    common_names))]
            elif len(scientific_names) < half_max and \
                 len(common_names) >= half_max:
                 # Return more common names because sci. names are fewer.
                 common_names = common_names[:(MAX_NAMES - len(
                    scientific_names))]

            names = {'scientific': [unicode(n) for n in scientific_names],
                     'common': [unicode(n) for n in common_names]}
        return HttpResponse(simplejson.dumps(names),
            mimetype='application/json; charset=utf-8')
