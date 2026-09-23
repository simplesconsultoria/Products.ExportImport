"""Export a Plone site from the command line, through ``zopectl run``.

::

    docker run --rm --platform linux/amd64 \\
        -v "$PWD/export:/data/export" -e EXPORTIMPORT_DIR=/data/export \\
        -v <data volume>:/data plone/plone:2.1-demo \\
        run /app/instance/Products/ExportImport/scripts/export.py

Configured through the environment, because ``zopectl run`` in Zope 2.8 splits
the script's arguments on single spaces and pastes them into a ``python -c``
string, which mangles anything quoted:

``SITE_ID``
    id of the Plone site at the Zope root (default ``Plone``)
``EXPORTIMPORT_DIR``
    base export directory (default ``<CLIENT_HOME>/export``)
``EXPORTIMPORT_TYPES``
    comma-separated portal types to export (default: all)

``zopectl run`` runs the script through ``os.system`` and discards its exit
status, so success is signalled by printing ``EXPORT-OK`` as the last line, and by
nothing else.
"""

import os
import sys
import traceback

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SpecialUsers import system
from Testing.makerequest import makerequest

from Products.ExportImport.exporter import export_site

SENTINEL = 'EXPORT-OK'


def main(app):
    """Export the site named by ``$SITE_ID``.

    :param app: the Zope application root
    :returns: 0 on success
    :raises RuntimeError: if there is no such site
    """
    app = makerequest(app)
    newSecurityManager(None, system)
    site_id = os.environ.get('SITE_ID', 'Plone')
    site = getattr(app, site_id, None)
    if site is None or not hasattr(site, 'portal_catalog'):
        raise RuntimeError('no Plone site %r at the Zope root; found: %s' % (
            site_id, ', '.join(app.objectIds())))
    types = os.environ.get('EXPORTIMPORT_TYPES', '')
    portal_types = [t.strip() for t in types.split(',') if t.strip()]
    summary = export_site(site, portal_types=portal_types or None)
    print('exported %(items)d items (%(errors)d errors) to %(site_dir)s' % summary)
    print('ordering: %(ordering)s' % summary)
    print('local roles: %(localroles)s' % summary)
    return 0


try:
    status = main(app)  # noqa: F821 -- bound by zopectl run
except Exception:
    traceback.print_exc()
    status = 1
else:
    print(SENTINEL)

sys.exit(status)
