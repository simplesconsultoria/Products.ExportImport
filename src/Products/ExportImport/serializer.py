"""Serialize one Archetypes object to a collective.exportimport item.

A hand-written port of plone.restapi 7.x's Archetypes serializer
(``serializer/atcontent.py`` and ``atfields.py``), followed by
collective.exportimport's migration fixups (``update_data_for_migration``).
The output is shaped for collective.exportimport's importer on Plone 6:
Dexterity field names, base64-inlined binaries and site-relative ``@id``s.

Field dispatch replaces the zope.component adapters with an ``isinstance``
chain. Order matters: in Archetypes 1.3 both ``ImageField`` and ``TextField``
subclass ``FileField``.

A rich text field can also hold a binary: Archetypes 1.3 lets a file be
uploaded into it. :meth:`Serializer.items` exports such a binary as a File or
Image inside the item, and replaces the text with a link to it.
"""

import base64
import cgi
import mimetypes
import os

try:
    from hashlib import md5
except ImportError:  # Python 2.4
    from md5 import new as md5

from Acquisition import aq_base, aq_inner, aq_parent
from Products.Archetypes.Field import FileField, ImageField, ReferenceField, TextField
from Products.Archetypes.Widget import RichWidget
from Products.CMFCore.utils import getToolByName

from Products.ExportImport import config
from Products.ExportImport.utils import json_compatible, safe_unicode


class Serializer:
    """Serialize Archetypes content of one Plone site.

    Tools and the site charset are looked up once and reused for every item.

    :param portal: the Plone site
    """

    def __init__(self, portal):
        self.portal = portal
        self.portal_path = portal.getPhysicalPath()
        self.wftool = getToolByName(portal, 'portal_workflow')
        self.types_tool = getToolByName(portal, 'portal_types')
        charset = portal.portal_properties.site_properties.getProperty('default_charset')
        self.charset = charset or 'utf-8'

    # -- helpers --------------------------------------------------------------

    def text(self, value):
        """Decode a site-charset byte string.

        :param value: str, unicode or None
        :returns: unicode or None
        """
        return safe_unicode(value, self.charset)

    def relative_path(self, obj):
        """Return the path of ``obj`` relative to the site, e.g. ``/news/item``.

        The site itself is ``/``. The importer treats a URL without a host as
        relative to the site it imports into.

        :param obj: an object inside the site
        :returns: unicode path
        """
        path = obj.getPhysicalPath()[len(self.portal_path):]
        return self.text('/' + '/'.join(path))

    def is_portal(self, obj):
        """Tell whether ``obj`` is the site root.

        :param obj: any object
        :returns: bool
        """
        return aq_base(obj) is aq_base(self.portal)

    def review_state(self, obj):
        """Return the workflow state of ``obj``, or None without a workflow.

        :param obj: a content object
        :returns: unicode or None
        """
        return self.text(self.wftool.getInfoFor(obj, 'review_state', None))

    def type_title(self, obj):
        """Return the (untranslated) title of the portal type of ``obj``.

        :param obj: a content object
        :returns: unicode or None
        """
        fti = self.types_tool.getTypeInfo(obj)
        if fti is None:
            return None
        return self.text(fti.Title())

    def uid(self, obj):
        """Return the Archetypes UID of ``obj``; None for non-AT objects.

        :param obj: any object
        :returns: unicode or None
        """
        method = getattr(aq_base(obj), 'UID', None)
        if method is None:
            return None
        return self.text(obj.UID())

    # -- summary --------------------------------------------------------------

    def summary(self, obj):
        """Return the summary used for ``parent`` in the item data.

        :param obj: a container, possibly the site
        :returns: dict
        """
        if self.is_portal(obj):
            return {
                '@id': u'/',
                '@type': u'Plone Site',
                'UID': None,
                'description': self.text(obj.getProperty('description', '')),
                'title': self.text(obj.Title()),
            }
        return {
            '@id': self.relative_path(obj),
            '@type': self.text(obj.portal_type),
            'UID': self.uid(obj),
            'description': self.text(obj.Description()),
            'image_field': None,
            'image_scales': None,
            'review_state': self.review_state(obj),
            'title': self.text(obj.Title()),
            'type_title': self.type_title(obj),
        }

    # -- fields ---------------------------------------------------------------

    def binary(self, field, obj):
        """Serialize a File or Image field, inlining its data as base64.

        :param field: an Archetypes ``FileField`` or ``ImageField``
        :param obj: the content object
        :returns: dict, or None when the field is empty
        """
        value = field.get(obj)
        if not value:
            return None
        data = getattr(value, 'data', value)
        chunks = []
        # OFS.Image stores large files as a linked chain of Pdata objects.
        while data is not None:
            if isinstance(data, str):
                chunks.append(data)
                break
            chunks.append(data.data)
            data = data.next
        payload = ''.join(chunks)
        # Files run to hundreds of megabytes: drop every copy as soon as the
        # next one exists, so no more than two are alive at once.
        del chunks
        if not payload:
            return None
        encoded = base64.b64encode(payload)
        del payload
        return {
            'content-type': self.text(field.getContentType(obj)),
            'data': encoded,
            'encoding': u'base64',
            'filename': self.text(field.getFilename(obj)),
        }

    def is_binary_text(self, field, obj):
        """Tell whether a rich text field holds an uploaded binary, not text.

        :param field: an Archetypes ``TextField`` with a rich widget
        :param obj: the content object
        :returns: bool
        """
        content_type = field.getContentType(obj) or ''
        if content_type.startswith('text/'):
            return False
        if content_type in config.TEXT_CONTENT_TYPES:
            return False
        return bool(field.getRaw(obj))

    def rich_text(self, field, obj):
        """Serialize a TextField with a rich widget as a Plone 6 RichText value.

        A binary in the field is left out here (None): decoded as text it is
        garbage. :meth:`items` exports it as an item of its own.

        :param field: an Archetypes ``TextField``
        :param obj: the content object
        :returns: dict, or None for a binary
        """
        if self.is_binary_text(field, obj):
            return None
        return {
            'content-type': self.text(field.getContentType(obj)),
            'data': self.text(field.getRaw(obj)),
            'encoding': u'utf-8',
        }

    def field_value(self, field, obj):
        """Serialize one field, dispatching on its class.

        :param field: an Archetypes field
        :param obj: the content object
        :returns: a JSON-compatible value
        """
        if isinstance(field, ImageField):
            return self.binary(field, obj)
        if isinstance(field, TextField):
            if isinstance(field.widget, RichWidget):
                return self.rich_text(field, obj)
            return self.text(field.getRaw(obj))
        if isinstance(field, FileField):
            return self.binary(field, obj)
        accessor = field.getAccessor(obj)
        if accessor is None:
            value = field.get(obj)
        else:
            value = accessor()
        return json_compatible(value, self.charset)

    def fields(self, obj):
        """Serialize every readable, non-reference schema field of ``obj``.

        References are skipped: in migration mode collective.exportimport
        exports them separately, as relations.

        :param obj: an Archetypes content object
        :returns: dict keyed by Archetypes field name
        """
        result = {}
        for field in obj.Schema().fields():
            if 'r' not in field.mode or not field.checkPermission('r', obj):
                continue
            if isinstance(field, ReferenceField):
                continue
            result[field.getName()] = self.field_value(field, obj)
        return result

    # -- item -----------------------------------------------------------------

    def workflow_history(self, obj):
        """Return the workflow history as ``{workflow_id: [entries]}``.

        :param obj: a content object
        :returns: dict
        """
        history = getattr(aq_base(obj), 'workflow_history', None) or {}
        result = {}
        for wf_id, entries in history.items():
            result[self.text(wf_id)] = json_compatible(list(entries), self.charset)
        return result

    def migrate(self, item):
        """Apply collective.exportimport's migration fixups, in place.

        Renames Archetypes fields to their Dexterity names, converts type
        constraints and maps old folder layouts.

        :param item: the item data being built
        """
        for old, new in config.FIELD_RENAMES.items():
            if old in item:
                item[new] = item.pop(old)

        # allowDiscussion is a StringField in AT 1.3; Dexterity wants a bool.
        allow = item.get('allow_discussion')
        item['allow_discussion'] = allow in (True, 1, u'1', u'True', u'on')

        if item.get('event_url') == u'':
            item['event_url'] = None

        mode = item.get('constrainTypesMode')
        if mode == config.CONSTRAIN_ENABLED:
            item['exportimport.constrains'] = {
                'locally_allowed_types': item.get('locallyAllowedTypes') or [],
                'immediately_addable_types': item.get('immediatelyAddableTypes') or [],
            }
        for name in config.CONSTRAIN_FIELDS:
            if name in item:
                del item[name]

        layout = item.get('layout')
        if item.get('is_folderish') and layout in config.LISTING_VIEW_MAPPING:
            item['layout'] = config.LISTING_VIEW_MAPPING[layout]

    def binary_text_extension(self, field, obj):
        """Return the file extension for a binary stored in a rich text field.

        Taken from the field's filename when it has one -- the content type
        alone can mislead: Word files are stored as ``application/zip``.

        :param field: an Archetypes ``TextField``
        :param obj: the content object
        :returns: lowercase extension, without the dot
        """
        filename = field.getFilename(obj) or ''
        extension = os.path.splitext(filename)[1][1:].lower()
        if extension and extension.isalnum():
            return extension
        content_type = field.getContentType(obj)
        if content_type in config.BINARY_TEXT_EXTENSIONS:
            return config.BINARY_TEXT_EXTENSIONS[content_type]
        guessed = mimetypes.guess_extension(content_type or '')
        if guessed:
            return guessed[1:]
        return 'bin'

    def binary_text_item(self, field, obj, item):
        """Build a File or Image item from the binary in a rich text field.

        The new item lives inside ``obj`` as ``file.<ext>`` or
        ``image.<ext>``, with a UID derived from the UID of ``obj`` (the same
        one on every export) and the workflow state, history and dates of
        ``obj``. The field in ``item`` is replaced, in place, by an HTML link
        to it.

        :param field: an Archetypes ``TextField`` holding a binary
        :param obj: the content object
        :param item: the serialized ``obj``, as returned by :meth:`__call__`
        :returns: dict, the new item
        """
        content_type = field.getContentType(obj)
        if content_type.startswith('image/'):
            portal_type, kind, layout = 'Image', 'image', 'image_view'
        else:
            portal_type, kind, layout = 'File', 'file', 'file_view'
        name = u'%s.%s' % (kind, self.text(self.binary_text_extension(field, obj)))
        uid = u'%s' % md5('%s:%s' % (str(item['UID']), field.getName())).hexdigest()
        filename = self.text(field.getFilename(obj)) or name

        if kind == 'image':
            html = u'<p><img src="resolveuid/%s/@@images/image" alt="%s" /></p>' % (
                uid, cgi.escape(item.get('title') or u'', True))
        else:
            html = u'<p><a href="resolveuid/%s/@@download/file">%s</a></p>' % (
                uid, cgi.escape(filename, True))
        item[field.getName()] = {
            'content-type': u'text/html',
            'data': html,
            'encoding': u'utf-8',
        }

        fti = self.types_tool.getTypeInfo(portal_type)
        new = {
            '@id': u'%s/%s' % (item['@id'], name),
            '@type': self.text(portal_type),
            'UID': uid,
            'id': name,
            'title': name,
            'description': u'',
            'subjects': [],
            'allow_discussion': False,
            'exclude_from_nav': False,
            'is_folderish': False,
            'layout': self.text(layout),
            'lock': {},
            'parent': self.summary(obj),
            'type_title': fti and self.text(fti.Title()) or None,
            'version': u'current',
            'working_copy': None,
            'working_copy_of': None,
            kind: {
                'content-type': self.text(content_type),
                'data': base64.b64encode(field.getRaw(obj)),
                'encoding': u'base64',
                'filename': filename,
            },
        }
        for key in ('created', 'modified', 'effective', 'expires', 'creators',
                    'contributors', 'language', 'rights', 'review_state',
                    'workflow_history'):
            if key in item:
                new[key] = item[key]
        return new

    def items(self, obj):
        """Serialize ``obj``, plus one item per binary in its rich text fields.

        :param obj: an Archetypes content object inside the site
        :returns: list of dicts, ``obj`` first
        """
        item = self(obj)
        result = [item]
        for field in obj.Schema().fields():
            if not isinstance(field, TextField) or not isinstance(field.widget, RichWidget):
                continue
            if 'r' not in field.mode or not field.checkPermission('r', obj):
                continue
            if self.is_binary_text(field, obj):
                result.append(self.binary_text_item(field, obj, item))
        return result

    def __call__(self, obj):
        """Serialize ``obj``.

        :param obj: an Archetypes content object inside the site
        :returns: dict ready for :func:`Products.ExportImport.utils.dumps`
        """
        get_layout = getattr(obj, 'getLayout', None)
        layout = None
        if get_layout is not None:
            layout = self.text(get_layout())
        item = self.fields(obj)
        item.update({
            '@id': self.relative_path(obj),
            '@type': self.text(obj.portal_type),
            'UID': self.uid(obj),
            'id': self.text(obj.getId()),
            'is_folderish': bool(getattr(aq_base(obj), 'isPrincipiaFolderish', False)),
            'layout': layout,
            'lock': {},
            'parent': self.summary(aq_parent(aq_inner(obj))),
            'review_state': self.review_state(obj),
            'type_title': self.type_title(obj),
            'version': u'current',
            'workflow_history': self.workflow_history(obj),
            'working_copy': None,
            'working_copy_of': None,
        })
        self.migrate(item)
        return item
