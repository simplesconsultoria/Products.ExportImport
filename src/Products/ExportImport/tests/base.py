"""Shared test fixture: a Plone 2.1 site with a little Archetypes content.

``PloneTestCase`` builds its site (id ``portal``) at import time, once per
test run, and each test runs in a transaction that is aborted afterwards.
"""

from Testing import ZopeTestCase

ZopeTestCase.installProduct('ExportImport')

from Products.CMFPlone.tests import PloneTestCase  # noqa: E402

# A 1x1 transparent GIF.
GIF = (
    'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04'
    '\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D'
    '\x01\x00;'
)

# "Imagens de acao", with cedilla and tilde, in UTF-8: Plone 2.1 stores text
# as byte strings. (Source files stay ASCII: 2.4 has no default encoding.)
FOLDER_TITLE = 'Imagens de a\xc3\xa7\xc3\xa3o'


class ExportImportTestCase(PloneTestCase.PloneTestCase):
    """Site with a folder, an image inside it and a document at the root."""

    def afterSetUp(self):
        self.setRoles(['Manager'])
        portal = self.portal
        portal.invokeFactory('Folder', 'images')
        self.folder_obj = portal.images
        self.folder_obj.setTitle(FOLDER_TITLE)
        self.folder_obj.setDescription('Banco de imagens.')
        self.folder_obj.invokeFactory('Image', 'pixel.gif')
        self.image = self.folder_obj['pixel.gif']
        self.image.setImage(GIF)
        portal.invokeFactory('Document', 'page')
        self.document = portal.page
        self.document.setTitle('A page')
        self.document.setDescription('Plain description')
        self.document.setText('<p>Ol\xc3\xa1</p>', mimetype='text/html')
        self.document.setSubject(('one', 'two'))
        for obj in (self.folder_obj, self.image, self.document):
            obj.reindexObject()


class ExportImportFunctionalTestCase(PloneTestCase.FunctionalTestCase):
    """Functional variant, for publishing requests through ZPublisher."""
