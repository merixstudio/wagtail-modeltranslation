# coding: utf-8

import json

from six import iteritems

from django.conf import settings
from django.conf.urls import url
from django.http import HttpResponse, QueryDict
from django.templatetags.static import static
from django.utils.html import escape, format_html, format_html_join
from django.views.decorators.csrf import csrf_exempt
from wagtail_modeltranslation import settings as wmt_settings
from modeltranslation import settings as mt_settings

try:
    from wagtail.core import hooks
    from wagtail.core.models import Page
    from wagtail.core.rich_text.pages import PageLinkHandler
except ImportError:
    from wagtail.wagtailcore import hooks
    from wagtail.wagtailcore.models import Page
    from wagtail.wagtailcore.rich_text import PageLinkHandler


@hooks.register('insert_editor_js')
def translated_slugs():
    js_files = [
        'wagtail_modeltranslation/js/wagtail_translated_slugs.js',
    ]

    js_includes = format_html_join('\n', '<script src="{0}"></script>', (
        (static(filename),) for filename in js_files)
    )

    lang_codes = []
    for lang in settings.LANGUAGES:
        lang_codes.append("'%s'" % lang[0])

    js_languages = """
<script>
    var langs=[{langs}];
    var default_lang='{default_lang}';
    var translate_slugs={translate_slugs};
</script>
    """.format(
        langs=", ".join(lang_codes),
        default_lang=mt_settings.DEFAULT_LANGUAGE,
        translate_slugs='true' if wmt_settings.TRANSLATE_SLUGS else 'false'
    )

    return format_html(js_languages) + js_includes


###############################################################################
# Copy StreamFields content
###############################################################################
@csrf_exempt
def return_translation_target_field_rendered_html(request, page_id):
    """
    Ajax view that allows to duplicate content
    between translated streamfields
    """

    page = Page.objects.get(pk=page_id)

    if request.is_ajax():
        origin_field_name = request.POST.get('origin_field_name')
        target_field_name = request.POST.get('target_field_name')
        origin_field_serialized = json.loads(
            request.POST.get('serializedOriginField'))

        # Patch field prefixes from origin field to target field
        target_field_patched = []
        for item in origin_field_serialized:
            patched_item = {'name': None, 'value': None}
            for att in iteritems(item):
                target_value = att[1]
                if att[0] == 'name':
                    target_value = att[1].replace(
                        origin_field_name, target_field_name)
                    patched_item["name"] = target_value
                else:
                    patched_item["value"] = att[1]

            target_field_patched.append(patched_item)

        # convert to QueryDict
        q_data = QueryDict('', mutable=True)
        for item in target_field_patched:
            q_data.update({item['name']: item['value']})

        # get render html

        target_field = page.specific._meta.get_field(target_field_name)
        value_data = target_field.stream_block.value_from_datadict(
            q_data, {}, target_field_name)
        target_field_content_html = target_field.formfield().widget.render(
            target_field_name, value_data)

    # return html json
    return HttpResponse(
        json.dumps(target_field_content_html), content_type='application/json')


@hooks.register('register_admin_urls')
def copy_streamfields_content():
    return [
        url(r'(?P<page_id>\d+)/edit/copy_translation_content$',
            return_translation_target_field_rendered_html, name=''),
    ]


@hooks.register('insert_editor_js')
def streamfields_translation_copy():
    """
    Includes script in editor html file that creates
    buttons to copy content between translated stream fields
    and send a ajax request to copy the content.
    """

    # includes the javascript file in the html file
    js_files = [
        'wagtail_modeltranslation/js/copy_stream_fields.js',
    ]

    js_includes = format_html_join('\n', '<script src="{0}"></script>', (
        (static(filename),) for filename in js_files)
    )

    return js_includes


@hooks.register('insert_editor_css')
def modeltranslation_page_editor_css():
    filename = 'wagtail_modeltranslation/css/page_editor_modeltranslation.css'
    return format_html('<link rel="stylesheet" href="{}" >'.format(static(filename)))


@hooks.register('register_rich_text_link_handler')
def register_localized_page_link_handler():
    class LocalizedPageLinkHandler(PageLinkHandler):
        @staticmethod
        def expand_db_attributes(attrs, for_editor):
            # This method is a copy of the original one
            # the only difference is the .specific on the escape method
            try:
                page = Page.objects.get(id=attrs['id'])

                if for_editor:
                    editor_attrs = 'data-linktype="page" data-id="%d" ' % page.id
                    parent_page = page.get_parent()
                    if parent_page:
                        editor_attrs += 'data-parent-id="%d" ' % parent_page.id
                else:
                    editor_attrs = ''

                return '<a %shref="%s">' % (editor_attrs, escape(page.specific.url))
            except Page.DoesNotExist:
                return "<a>"

    return ('page', LocalizedPageLinkHandler)
