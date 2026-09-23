"""Serialize one Archetypes object to a collective.exportimport item.

A hand-written port of plone.restapi 7.x's Archetypes serializer
(``serializer/atcontent.py`` and ``atfields.py``), followed by
collective.exportimport's migration fixups (``update_data_for_migration``).
The output is shaped for collective.exportimport's importer on Plone 6:
Dexterity field names, base64-inlined binaries and site-relative ``@id``s.

Field dispatch replaces the zope.component adapters with an ``isinstance``
chain. Order matters: in Archetypes 1.3 both ``ImageField`` and ``TextField``
subclass ``FileField``.
"""

import base64

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

    def rich_text(self, field, obj):
        """Serialize a TextField with a rich widget as a Plone 6 RichText value.

        :param field: an Archetypes ``TextField``
        :param obj: the content object
        :returns: dict
        """
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
