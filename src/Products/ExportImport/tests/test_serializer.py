"""Tests for :mod:`Products.ExportImport.serializer`."""

import base64
import re
import unittest

from Products.ExportImport.serializer import Serializer, md5
from Products.ExportImport.tests.base import GIF, ExportImportTestCase
from Products.ExportImport.utils import dumps

ISO = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$')


class TestSerializer(ExportImportTestCase):

    def serialize(self, obj):
        return Serializer(self.portal)(obj)

    def test_base_keys(self):
        item = self.serialize(self.document)
        self.assertEqual(item['@id'], u'/page')
        self.assertEqual(item['@type'], u'Document')
        self.assertEqual(item['id'], u'page')
        self.assertEqual(item['UID'], self.document.UID())
        self.assertEqual(item['version'], u'current')
        self.assertEqual(item['is_folderish'], False)
        self.assertEqual(item['lock'], {})
        self.assertEqual(item['working_copy'], None)

    def test_site_root_parent(self):
        parent = self.serialize(self.document)['parent']
        self.assertEqual(parent['@id'], u'/')
        self.assertEqual(parent['@type'], u'Plone Site')

    def test_folder_parent(self):
        parent = self.serialize(self.image)['parent']
        self.assertEqual(parent['@id'], u'/images')
        self.assertEqual(parent['@type'], u'Folder')
        self.assertEqual(parent['UID'], self.folder_obj.UID())
        self.assertEqual(parent['title'], u'Imagens de a\xe7\xe3o')
        self.assertEqual(parent['description'], u'Banco de imagens.')

    def test_fields_renamed_for_dexterity(self):
        item = self.serialize(self.document)
        for old in ('subject', 'creation_date', 'modification_date',
                    'effectiveDate', 'expirationDate', 'excludeFromNav',
                    'allowDiscussion'):
            self.failIf(old in item, old)
        self.assertEqual(item['subjects'], [u'one', u'two'])
        self.failUnless(ISO.match(item['created']), item['created'])
        self.failUnless(ISO.match(item['modified']), item['modified'])
        self.assertEqual(item['exclude_from_nav'], False)
        self.assertEqual(item['allow_discussion'], False)

    def test_rich_text(self):
        text = self.serialize(self.document)['text']
        self.assertEqual(text['content-type'], u'text/html')
        self.assertEqual(text['encoding'], u'utf-8')
        self.failUnless(u'Ol\xe1' in text['data'], text['data'])

    def test_plain_text_field_is_a_string(self):
        item = self.serialize(self.document)
        self.assertEqual(item['description'], u'Plain description')

    def test_image_is_inlined_as_base64(self):
        image = self.serialize(self.image)['image']
        self.assertEqual(image['encoding'], u'base64')
        self.assertEqual(base64.decodestring(image['data']), GIF)
        self.failUnless(image['content-type'].startswith(u'image/'), image)

    def test_empty_image_is_none(self):
        self.folder_obj.invokeFactory('Image', 'empty')
        self.assertEqual(self.serialize(self.folder_obj.empty)['image'], None)

    def test_references_are_dropped(self):
        self.failIf('relatedItems' in self.serialize(self.document))

    def test_folder_layout_is_mapped(self):
        self.folder_obj.setLayout('folder_listing')
        item = self.serialize(self.folder_obj)
        self.assertEqual(item['is_folderish'], True)
        self.assertEqual(item['layout'], u'listing_view')

    def test_type_constraints(self):
        self.folder_obj.setConstrainTypesMode(1)
        self.folder_obj.setLocallyAllowedTypes(('Document', 'Image'))
        self.folder_obj.setImmediatelyAddableTypes(('Document',))
        item = self.serialize(self.folder_obj)
        self.assertEqual(item['exportimport.constrains'], {
            'locally_allowed_types': [u'Document', u'Image'],
            'immediately_addable_types': [u'Document'],
        })
        for name in ('constrainTypesMode', 'locallyAllowedTypes',
                     'immediatelyAddableTypes'):
            self.failIf(name in item, name)

    def test_no_constraints_by_default(self):
        self.failIf('exportimport.constrains' in self.serialize(self.folder_obj))

    def test_workflow_history(self):
        history = self.serialize(self.document)['workflow_history']
        self.failUnless(history, history)
        for entries in history.values():
            for entry in entries:
                self.failUnless(ISO.match(entry['time']), entry)

    def test_event_fields(self):
        self.portal.invokeFactory('Event', 'party')
        item = self.serialize(self.portal.party)
        self.failUnless(ISO.match(item['start']), item['start'])
        self.failUnless(ISO.match(item['end']), item['end'])
        self.assertEqual(item['event_url'], None)
        self.failIf('startDate' in item)

    def test_json_serializable(self):
        for obj in (self.folder_obj, self.image, self.document):
            dumps(self.serialize(obj))


class TestBinaryText(ExportImportTestCase):
    """A file uploaded into a rich text field becomes an item of its own."""

    def afterSetUp(self):
        ExportImportTestCase.afterSetUp(self)
        self.serializer = Serializer(self.portal)

    def items(self, data, mimetype, filename=None):
        self.document.setText(data, mimetype=mimetype, filename=filename)
        return self.serializer.items(self.document)

    def expected_uid(self):
        return md5('%s:text' % self.document.UID()).hexdigest()

    def test_text_document_has_no_extra_items(self):
        self.assertEqual(len(self.serializer.items(self.document)), 1)

    def test_image_is_extracted(self):
        item, image = self.items(GIF, 'image/gif', 'pixel.gif')
        uid = self.expected_uid()
        self.assertEqual(image['@type'], u'Image')
        self.assertEqual(image['@id'], u'/page/image.gif')
        self.assertEqual(image['id'], u'image.gif')
        self.assertEqual(image['title'], u'image.gif')
        self.assertEqual(image['UID'], uid)
        self.assertEqual(image['layout'], u'image_view')
        self.assertEqual(base64.decodestring(image['image']['data']), GIF)
        self.assertEqual(image['image']['encoding'], u'base64')
        self.assertEqual(image['image']['content-type'], u'image/gif')
        self.assertEqual(image['image']['filename'], u'pixel.gif')
        self.assertEqual(image['parent']['@id'], u'/page')
        self.assertEqual(image['parent']['UID'], self.document.UID())
        self.assertEqual(item['text']['content-type'], u'text/html')
        self.failUnless(
            u'src="resolveuid/%s/@@images/image"' % uid in item['text']['data'],
            item['text']['data'])

    def test_file_is_extracted_with_the_filename_extension(self):
        item, extracted = self.items('PK\x03\x04 fake docx', 'application/zip',
                                     'Pauta 2015.docx')
        uid = self.expected_uid()
        self.assertEqual(extracted['@type'], u'File')
        self.assertEqual(extracted['@id'], u'/page/file.docx')
        self.assertEqual(extracted['layout'], u'file_view')
        self.assertEqual(extracted['file']['filename'], u'Pauta 2015.docx')
        self.assertEqual(base64.decodestring(extracted['file']['data']),
                         'PK\x03\x04 fake docx')
        self.failUnless(
            u'<a href="resolveuid/%s/@@download/file">Pauta 2015.docx</a>' % uid
            in item['text']['data'], item['text']['data'])

    def test_extension_from_content_type_without_filename(self):
        extracted = self.items('%PDF-1.4 fake', 'application/pdf')[1]
        self.assertEqual(extracted['id'], u'file.pdf')

    def test_metadata_is_inherited(self):
        item, extracted = self.items(GIF, 'image/gif', 'pixel.gif')
        for key in ('created', 'modified', 'effective', 'creators',
                    'review_state', 'workflow_history'):
            self.assertEqual(extracted[key], item[key], key)

    def test_uid_is_stable(self):
        first = self.items(GIF, 'image/gif', 'pixel.gif')[1]['UID']
        second = self.serializer.items(self.document)[1]['UID']
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)

    def test_json_serializable(self):
        for item in self.items('\xed\xa0\x80\xff', 'application/octet-stream'):
            dumps(item)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSerializer))
    suite.addTest(unittest.makeSuite(TestBinaryText))
    return suite
