"""Value conversion helpers: everything the JSON encoder cannot take as-is.

This replaces plone.restapi's ``json_compatible`` adapters, which need the
component architecture, and its ``datetimelike_to_iso``, which needs
``DateTime.asdatetime()`` -- absent from the DateTime shipped with Zope 2.8.

Python 2.4 only: no conditional expressions, no ``with``, no ``except ... as``.
"""

try:
    import simplejson as json
except ImportError:  # Python >= 2.6
    import json

import re

import Missing
from DateTime import DateTime
from Persistence import PersistentMapping

try:
    from ZODB.PersistentList import PersistentList
except ImportError:
    PersistentList = list

DEFAULT_CHARSET = 'utf-8'

# A UTF-16 surrogate without its other half. Python 2 decodes UTF-8-encoded
# surrogates (``\xed\xa0\x80``) without complaint and simplejson escapes
# them as ``\ud800``, which strict parsers such as orjson reject.
LONE_SURROGATE = re.compile(
    u'[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]'
)

SEQUENCE_TYPES = (list, tuple, set, frozenset, PersistentList)
MAPPING_TYPES = (dict, PersistentMapping)


def safe_unicode(value, encoding=DEFAULT_CHARSET):
    """Return ``value`` as unicode if it is a byte string.

    Plone 2.1 stores text as byte strings in the site charset. Bytes that are
    not valid in that charset are replaced rather than raising, so one bad
    value cannot abort an export; so are unpaired surrogates, so the result
    always encodes to valid JSON.

    :param value: any value
    :param encoding: charset of byte strings
    :returns: unicode for ``str`` input, ``value`` unchanged otherwise
    """
    if isinstance(value, str):
        return LONE_SURROGATE.sub(u'\ufffd', unicode(value, encoding, 'replace'))
    return value


def datetime_to_iso(value):
    """Format a ``DateTime`` as ISO 8601 in UTC, dropping fractions of a second.

    Matches plone.restapi's output: ``2022-05-24T18:38:11+00:00`` (never ``Z``).

    :param value: a ``DateTime`` or ``None``
    :returns: unicode ISO string, or ``None``
    """
    if value is None:
        return None
    utc = value.toZone('UTC')
    return u'%04d-%02d-%02dT%02d:%02d:%02d+00:00' % (
        utc.year(),
        utc.month(),
        utc.day(),
        utc.hour(),
        utc.minute(),
        int(utc.second()),
    )


def json_compatible(value, encoding=DEFAULT_CHARSET):
    """Convert ``value`` recursively into something the JSON encoder accepts.

    :param value: any value read from content
    :param encoding: charset used to decode byte strings
    :returns: a structure of unicode, numbers, booleans, None, lists and dicts
    """
    if value is None or isinstance(value, (bool, int, float, unicode)):
        return value
    if isinstance(value, long):
        return int(value)
    if isinstance(value, str):
        return safe_unicode(value, encoding)
    if isinstance(value, DateTime):
        return datetime_to_iso(value)
    if value is Missing.Value:
        return None
    if isinstance(value, SEQUENCE_TYPES):
        return [json_compatible(item, encoding) for item in value]
    if isinstance(value, MAPPING_TYPES):
        result = {}
        for key, item in value.items():
            result[json_compatible(key, encoding)] = json_compatible(item, encoding)
        return result
    # Unknown types (custom field values): keep the export going.
    return safe_unicode(str(value), encoding)


JSON_OPTIONS = {
    'sort_keys': True,
    'indent': 4,
    # simplejson 2.0.9 defaults to ', ', leaving a trailing space on every
    # line once ``indent`` is set.
    'separators': (',', ': '),
}


def dump(data, handle):
    """Write ``data`` to ``handle`` exactly as :func:`dumps` formats it.

    Streams the encoder's chunks instead of building the whole document in
    memory first -- for an item with a large file inlined, that string is as
    big as the file's base64 data.

    :param data: a JSON-compatible structure
    :param handle: a file open for writing
    """
    json.dump(data, handle, **JSON_OPTIONS)


def dumps(data):
    """Serialize ``data`` the way collective.exportimport writes its files.

    :param data: a JSON-compatible structure
    :returns: an ASCII ``str``
    """
    return json.dumps(data, **JSON_OPTIONS)
