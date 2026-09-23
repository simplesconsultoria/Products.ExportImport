"""Tests for :mod:`Products.ExportImport.utils`."""

import unittest
from StringIO import StringIO

import Missing
from DateTime import DateTime
from Persistence import PersistentMapping

from Products.ExportImport.utils import datetime_to_iso, dump, dumps, json_compatible, safe_unicode


class TestDatetimeToIso(unittest.TestCase):

    def test_converts_to_utc(self):
        value = DateTime('2022/05/24 15:38:11 GMT-3')
        self.assertEqual(datetime_to_iso(value), u'2022-05-24T18:38:11+00:00')

    def test_drops_fractions_of_a_second(self):
        value = DateTime('2026/08/28 19:54:53.995 UTC')
        self.assertEqual(datetime_to_iso(value), u'2026-08-28T19:54:53+00:00')

    def test_none(self):
        self.assertEqual(datetime_to_iso(None), None)


class TestSafeUnicode(unittest.TestCase):

    def test_decodes_utf8(self):
        self.assertEqual(safe_unicode('a\xc3\xa7\xc3\xa3o'), u'a\xe7\xe3o')

    def test_replaces_invalid_bytes(self):
        self.assertEqual(safe_unicode('a\xff'), u'a\ufffd')

    def test_leaves_other_values_alone(self):
        self.assertEqual(safe_unicode(1), 1)
        self.assertEqual(safe_unicode(u'x'), u'x')


class TestJsonCompatible(unittest.TestCase):

    def test_scalars(self):
        self.assertEqual(json_compatible(None), None)
        self.assertEqual(json_compatible(True), True)
        self.assertEqual(json_compatible(1.5), 1.5)
        self.assertEqual(json_compatible(long(3)), 3)
        self.failUnless(isinstance(json_compatible(long(3)), int))

    def test_strings_become_unicode(self):
        self.assertEqual(json_compatible('a\xc3\xa7'), u'a\xe7')

    def test_missing_value(self):
        self.assertEqual(json_compatible(Missing.Value), None)

    def test_nested_structures(self):
        value = PersistentMapping({
            'wf': ({'time': DateTime('2022/05/24 18:38:11 UTC'), 'actor': 'admin'},),
        })
        self.assertEqual(json_compatible(value), {
            u'wf': [{u'time': u'2022-05-24T18:38:11+00:00', u'actor': u'admin'}],
        })

    def test_unknown_types_become_strings(self):
        class Custom:
            def __str__(self):
                return 'custom'
        self.assertEqual(json_compatible(Custom()), u'custom')


class TestDumps(unittest.TestCase):

    def test_sorted_and_indented(self):
        self.assertEqual(dumps({'b': 1, 'a': 2}), '{\n    "a": 2,\n    "b": 1\n}')

    def test_dump_matches_dumps(self):
        data = {'b': [1, {'y': u'\xe9', 'x': None}], 'a': 'text'}
        handle = StringIO()
        dump(data, handle)
        self.assertEqual(handle.getvalue(), dumps(data))


def test_suite():
    suite = unittest.TestSuite()
    for case in (TestDatetimeToIso, TestSafeUnicode, TestJsonCompatible, TestDumps):
        suite.addTest(unittest.makeSuite(case))
    return suite
