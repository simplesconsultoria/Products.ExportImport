"""Export Archetypes content from Plone 2.1 sites to JSON.

A simplified port of ``collective.exportimport`` that runs on Python 2.4,
Zope 2.8 and Plone 2.1, using nothing beyond what those ship with, plus
``simplejson``.

There is no ZCML here: Zope 2.8 predates it for classic products. The web
entry point is installed the old way, through the product's ``methods``
mapping, which Zope attaches to ``OFS.Folder.Folder`` at startup, together
with the ``__roles__`` that restrict it to Managers.
"""

from Products.ExportImport import web

methods = {
    'exportimport_export': web.exportimport_export,
    'exportimport_export__roles__': ('Manager',),
}


def initialize(context):
    """Zope 2 product initialization hook.

    Nothing to register: the export view is installed via :data:`methods`.

    :param context: the Zope ``ProductContext``
    """
