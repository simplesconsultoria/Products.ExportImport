"""Tests for :mod:`Products.ExportImport.web`, published through ZPublisher."""

import os
import shutil
import tempfile
import unittest

from Products.CMFPlone.tests.PloneTestCase import default_password, default_user

from Products.ExportImport.config import EXPORT_DIR_ENV
from Products.ExportImport.tests.base import ExportImportFunctionalTestCase


class TestWeb(ExportImportFunctionalTestCase):

    def afterSetUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.saved_env = os.environ.get(EXPORT_DIR_ENV)
        os.environ[EXPORT_DIR_ENV] = self.base_dir
        self.path = '/' + self.portal.absolute_url(1) + '/exportimport_export'
        # PloneTestCase's portal_owner has an empty password, so it cannot
        # log in over basic auth: add a Manager that can.
        self.portal.acl_users._doAddUser('manager', default_password, ['Manager'], [])
        self.owner = 'manager:%s' % default_password

    def beforeTearDown(self):
        if self.saved_env is None:
            del os.environ[EXPORT_DIR_ENV]
        else:
            os.environ[EXPORT_DIR_ENV] = self.saved_env
        shutil.rmtree(self.base_dir)

    def test_anonymous_is_refused(self):
        response = self.publish(self.path)
        self.failIf(response.getStatus() == 200, response.getStatus())

    def test_member_is_refused(self):
        response = self.publish(
            self.path, basic='%s:%s' % (default_user, default_password))
        self.failIf(response.getStatus() == 200, response.getStatus())

    def test_get_renders_form_without_exporting(self):
        response = self.publish(self.path, basic=self.owner)
        self.assertEqual(response.getStatus(), 200)
        self.failUnless('<form method="post"' in response.getBody())
        self.assertEqual(os.listdir(self.base_dir), [])

    def test_post_exports(self):
        response = self.publish(self.path, basic=self.owner, request_method='POST')
        self.assertEqual(response.getStatus(), 200)
        self.failUnless('Export finished' in response.getBody())
        self.failUnless(os.path.exists(
            os.path.join(self.base_dir, 'export_ordering.json')))


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestWeb))
    return suite
