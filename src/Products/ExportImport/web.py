"""Browser entry point: ``<site>/exportimport_export``.

Installed on every ``OFS.Folder.Folder`` through the product's ``methods``
mapping and restricted to Managers there. It works from any folder of the
site, but always exports the whole site.

A GET renders a small form; only a POST runs the export, so a crawler or a
prefetching browser following the link cannot trigger it.
"""

import cgi

from Products.CMFCore.utils import getToolByName

from Products.ExportImport import config
from Products.ExportImport.exporter import export_site

FORM = """<html><head><title>Export content</title></head><body>
<h1>Export %(title)s</h1>
<p>Content, ordering and local roles are written to
<code>%(base_dir)s</code> on the server.</p>
<form method="post" action="%(action)s">
<p><label>Portal types (one per line, empty for all)<br />
<textarea name="portal_types:lines" rows="6" cols="40"></textarea></label></p>
<p><input type="submit" value="Export" /></p>
</form>
</body></html>
"""

RESULT = """<html><head><title>Export finished</title></head><body>
<h1>Export finished</h1>
<ul>
<li>Items: %(items)d, errors: %(errors)d</li>
<li>Extracted from rich text: %(extracted)d</li>
<li>Content: <code>%(site_dir)s</code></li>
<li>Ordering: <code>%(ordering)s</code></li>
<li>Local roles: <code>%(localroles)s</code></li>
</ul>
</body></html>
"""


def exportimport_export(self, REQUEST=None):
    """Export the site's content to the server's export directory.

    :param self: the folder the method was called on
    :param REQUEST: the Zope request
    :returns: an HTML page
    """
    portal = getToolByName(self, 'portal_url').getPortalObject()
    if REQUEST is None or REQUEST.get('REQUEST_METHOD', 'GET') != 'POST':
        return FORM % {
            'title': cgi.escape(portal.Title()),
            'base_dir': cgi.escape(config.default_export_dir()),
            'action': portal.absolute_url() + '/exportimport_export',
        }
    portal_types = [t.strip() for t in REQUEST.get('portal_types', []) if t.strip()]
    summary = export_site(portal, portal_types=portal_types or None)
    for key in ('site_dir', 'ordering', 'localroles'):
        summary[key] = cgi.escape(summary[key])
    return RESULT % summary
