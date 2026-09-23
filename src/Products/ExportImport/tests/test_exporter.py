"""Tests for :mod:`Products.ExportImport.exporter`."""

import os
import shutil
import tempfile
import unittest

from Products.ExportImport.exporter import export_site
from Products.ExportImport.tests.base import ExportImportTestCase
from Products.ExportImport.utils import json


def read_json(path):
    handle = open(path)
    try:
        return json.loads(handle.read())
    finally:
        handle.close()


class TestExporter(ExportImportTestCase):

    def afterSetUp(self):
        ExportImportTestCase.afterSetUp(self)
        self.base_dir = tempfile.mkdtemp()
        self.site_dir = os.path.join(self.base_dir, self.portal.getId())

    def beforeTearDown(self):
        shutil.rmtree(self.base_dir)

    def items(self):
        names = [n for n in os.listdir(self.site_dir) if n[:-5].isdigit()]
        names.sort(lambda a, b: cmp(int(a[:-5]), int(b[:-5])))
        return [read_json(os.path.join(self.site_dir, n)) for n in names]

    def test_summary(self):
        summary = export_site(self.portal, base_dir=self.base_dir)
        self.assertEqual(summary['site_dir'], self.site_dir)
        self.assertEqual(summary['items'], len(self.items()))
        self.assertEqual(summary['errors'], 0)
        self.failIf(os.path.exists(os.path.join(self.site_dir, 'errors.json')))

    def test_files_are_numbered_in_path_order(self):
        export_site(self.portal, base_dir=self.base_dir)
        ids = [item['@id'] for item in self.items()]
        sorted_ids = ids[:]
        sorted_ids.sort()
        self.assertEqual(ids, sorted_ids)
        self.failUnless(u'/images' in ids, ids)
        self.failUnless(ids.index(u'/images') < ids.index(u'/images/pixel.gif'))

    def test_portal_types_filter(self):
        export_site(self.portal, base_dir=self.base_dir, portal_types=['Image'])
        self.assertEqual([i['@id'] for i in self.items()], [u'/images/pixel.gif'])

    def test_stale_files_are_removed(self):
        os.makedirs(self.site_dir)
        stale = os.path.join(self.site_dir, '999.json')
        other = os.path.join(self.site_dir, 'notes.txt')
        for path in (stale, other):
            open(path, 'w').close()
        export_site(self.portal, base_dir=self.base_dir)
        self.failIf(os.path.exists(stale))
        self.failUnless(os.path.exists(other))

    def test_ordering(self):
        export_site(self.portal, base_dir=self.base_dir)
        ordering = read_json(os.path.join(self.base_dir, 'export_ordering.json'))
        by_uid = {}
        for entry in ordering:
            by_uid[entry['uuid']] = entry['order']
        self.assertEqual(by_uid[self.image.UID()], 0)
        orders = [entry['order'] for entry in ordering]
        sorted_orders = orders[:]
        sorted_orders.sort()
        self.assertEqual(orders, sorted_orders)

    def test_localroles(self):
        self.folder_obj.manage_setLocalRoles('someone', ['Reviewer'])
        self.folder_obj.__ac_local_roles_block__ = 1
        export_site(self.portal, base_dir=self.base_dir)
        entries = read_json(os.path.join(self.base_dir, 'export_localroles.json'))
        by_uid = {}
        for entry in entries:
            by_uid[entry['uuid']] = entry
        entry = by_uid[self.folder_obj.UID()]
        self.assertEqual(entry['localroles']['someone'], [u'Reviewer'])
        self.assertEqual(entry['block'], 1)
        self.failIf('block' in by_uid[self.document.UID()])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestExporter))
    return suite
