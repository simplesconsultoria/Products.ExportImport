"""Write a Plone site's content to disk in collective.exportimport's layout.

::

    <base dir>/
        <site id>/
            1.json
            2.json
            errors.json            (only when some items failed)
        export_ordering.json
        export_localroles.json

Items are numbered in path order, so every container is written before its
contents -- which is what the importer relies on. Plone 2.1's path index
cannot be used as a catalog ``sort_on``, so the sort happens here.
"""

import logging
import os
import sys

from Acquisition import aq_base, aq_inner, aq_parent
from Products.CMFCore.utils import getToolByName

from Products.ExportImport import config
from Products.ExportImport.serializer import Serializer
from Products.ExportImport.utils import dumps, json_compatible

logger = logging.getLogger('Products.ExportImport')


def _by_path(a, b):
    """``cmp``-style comparison of two catalog brains by path."""
    return cmp(a.getPath(), b.getPath())


def _write_json(path, data):
    """Write ``data`` as JSON to ``path``.

    :param path: target file path
    :param data: a JSON-compatible structure
    """
    handle = open(path, 'wb')
    try:
        handle.write(dumps(data))
    finally:
        handle.close()


def _is_archetypes(obj):
    """Tell whether ``obj`` is Archetypes content.

    :param obj: any object
    :returns: bool
    """
    base = aq_base(obj)
    return hasattr(base, 'Schema') and hasattr(base, 'UID')


def _clean_site_dir(site_dir):
    """Remove the files a previous export left in ``site_dir``.

    Only numbered ``N.json`` files and ``errors.json`` are removed. The
    importer reads every numbered file, so a stale one from a larger earlier
    export would otherwise be imported too.

    :param site_dir: the per-site export directory
    """
    for name in os.listdir(site_dir):
        stem, ext = os.path.splitext(name)
        if ext == '.json' and (stem.isdigit() or name == config.ERRORS_FILENAME):
            os.remove(os.path.join(site_dir, name))


class SiteExporter:
    """Export content, ordering and local roles of one Plone site.

    :param portal: the Plone site
    :param base_dir: base export directory; see
        :func:`Products.ExportImport.config.default_export_dir`
    :param portal_types: portal types to export, or None for all
    """

    def __init__(self, portal, base_dir=None, portal_types=None):
        self.portal = portal
        if base_dir is None:
            base_dir = config.default_export_dir()
        self.base_dir = base_dir
        self.site_dir = os.path.join(base_dir, portal.getId())
        self.portal_types = portal_types
        self.serializer = Serializer(portal)
        self.errors = []
        self._objects = None

    def objects(self):
        """Return ``(path, object)`` for Archetypes content, in path order.

        Computed once and cached. Objects that cannot be loaded are recorded
        through :meth:`error`; non-Archetypes objects are silently skipped.

        :returns: list of ``(path, object)`` tuples
        """
        if self._objects is not None:
            return self._objects
        result = []
        catalog = getToolByName(self.portal, 'portal_catalog')
        query = {'path': '/'.join(self.portal.getPhysicalPath())}
        if self.portal_types:
            query['portal_type'] = list(self.portal_types)
        brains = list(catalog.unrestrictedSearchResults(**query))
        brains.sort(_by_path)
        for brain in brains:
            path = brain.getPath()
            try:
                obj = brain.getObject()
            except Exception:
                self.error(path, sys.exc_info()[1])
                continue
            if obj is None:
                self.error(path, 'catalog entry without an object')
                continue
            if not _is_archetypes(obj):
                continue
            result.append((path, obj))
        self._objects = result
        return result

    def error(self, path, message):
        """Record an item that could not be exported.

        :param path: physical path of the item
        :param message: the error or exception
        """
        logger.warning('Could not export %s: %s', path, message)
        self.errors.append({'path': path, 'message': str(message)})

    def export_content(self):
        """Write one ``N.json`` file per content item.

        :returns: the number of items written
        """
        if not os.path.isdir(self.site_dir):
            os.makedirs(self.site_dir)
        _clean_site_dir(self.site_dir)
        counter = 0
        for path, obj in self.objects():
            try:
                data = self.serializer(obj)
            except Exception:
                logger.exception('Serializing %s failed', path)
                self.error(path, sys.exc_info()[1])
                continue
            counter += 1
            _write_json(os.path.join(self.site_dir, '%d.json' % counter), data)
        if self.errors:
            _write_json(
                os.path.join(self.site_dir, config.ERRORS_FILENAME),
                {'unexported_paths': json_compatible(self.errors)},
            )
        return counter

    def ordering(self):
        """Return the position of every item in its container.

        Items whose container is not ordered (e.g. inside a Topic) are left out.

        :returns: list of ``{"uuid", "order"}``, sorted by order
        """
        result = []
        for path, obj in self.objects():
            parent = aq_parent(aq_inner(obj))
            try:
                order = parent.getObjectPosition(obj.getId())
            except (AttributeError, ValueError):
                continue
            result.append({'uuid': obj.UID(), 'order': order})
        result.sort(lambda a, b: cmp(a['order'], b['order']))
        return json_compatible(result)

    def _localroles(self, obj):
        """Return the local roles entry for ``obj``, without its uuid.

        :param obj: a content object or the site
        :returns: dict, empty when there is nothing to export
        """
        base = aq_base(obj)
        entry = {}
        roles = getattr(base, '__ac_local_roles__', None)
        if roles:
            entry['localroles'] = dict(roles)
        if getattr(base, '__ac_local_roles_block__', None):
            entry['block'] = 1
        return entry

    def localroles(self):
        """Return the local roles of the site and every item that has any.

        :returns: list of ``{"uuid", "localroles"?, "block"?}``
        """
        result = []
        for path, obj in self.objects():
            entry = self._localroles(obj)
            if entry:
                entry['uuid'] = obj.UID()
                result.append(entry)
        entry = self._localroles(self.portal)
        if entry:
            entry['uuid'] = config.PORTAL_PLACEHOLDER
            result.append(entry)
        return json_compatible(result)

    def __call__(self):
        """Run the full export.

        :returns: dict summarising what was written
        """
        items = self.export_content()
        if not os.path.isdir(self.base_dir):
            os.makedirs(self.base_dir)
        ordering_path = os.path.join(self.base_dir, config.ORDERING_FILENAME)
        _write_json(ordering_path, self.ordering())
        localroles_path = os.path.join(self.base_dir, config.LOCALROLES_FILENAME)
        _write_json(localroles_path, self.localroles())
        return {
            'site_dir': self.site_dir,
            'items': items,
            'errors': len(self.errors),
            'ordering': ordering_path,
            'localroles': localroles_path,
        }


def export_site(portal, base_dir=None, portal_types=None):
    """Export a Plone site; see :class:`SiteExporter`.

    :param portal: the Plone site
    :param base_dir: base export directory, or None for the default
    :param portal_types: portal types to export, or None for all
    :returns: dict summarising what was written
    """
    return SiteExporter(portal, base_dir, portal_types)()
