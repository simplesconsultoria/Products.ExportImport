"""Constants shared by the serializer and the exporter.

The placeholder strings and the mappings below are copied from
``collective.exportimport``, whose importer consumes this package's output:
they must match it exactly.
"""

import os

# Site-root placeholder used by export_localroles (collective.exportimport).
PORTAL_PLACEHOLDER = '<Portal>'

# Environment variable naming the base export directory.
EXPORT_DIR_ENV = 'EXPORTIMPORT_DIR'

# File names written next to the per-site content directory.
ORDERING_FILENAME = 'export_ordering.json'
LOCALROLES_FILENAME = 'export_localroles.json'
ERRORS_FILENAME = 'errors.json'

# Archetypes field name -> Plone 6 (Dexterity) field name.
# From collective.exportimport ``update_data_for_migration``.
FIELD_RENAMES = {
    'allowDiscussion': 'allow_discussion',
    'contactEmail': 'contact_email',
    'contactName': 'contact_name',
    'contactPhone': 'contact_phone',
    'creation_date': 'created',
    'effectiveDate': 'effective',
    'endDate': 'end',
    'eventUrl': 'event_url',
    'excludeFromNav': 'exclude_from_nav',
    'expirationDate': 'expires',
    'modification_date': 'modified',
    'openEnd': 'open_end',
    'startDate': 'start',
    'subject': 'subjects',
    'wholeDay': 'whole_day',
}

# Archetypes fields handled separately (or not at all) in migration mode.
CONSTRAIN_FIELDS = (
    'constrainTypesMode',
    'locallyAllowedTypes',
    'immediatelyAddableTypes',
)

# ATContentTypes ``ENABLED`` constrain mode.
CONSTRAIN_ENABLED = 1

# Old (AT) layout -> Plone 6 layout, for folders and collections.
# Copied from plone.app.contenttypes via collective.exportimport.
LISTING_VIEW_MAPPING = {
    'all_content': 'full_view',
    'atct_album_view': 'album_view',
    'atct_topic_view': 'listing_view',
    'collection_view': 'listing_view',
    'folder_album_view': 'album_view',
    'folder_full_view': 'full_view',
    'folder_listing': 'listing_view',
    'folder_listing_view': 'listing_view',
    'folder_summary_view': 'summary_view',
    'folder_tabular_view': 'tabular_view',
    'standard_view': 'listing_view',
    'thumbnail_view': 'album_view',
    'view': 'listing_view',
}


def default_export_dir():
    """Return the base export directory.

    ``$EXPORTIMPORT_DIR`` when set, otherwise ``<CLIENT_HOME>/export`` --
    the same place ``collective.exportimport`` falls back to.

    :returns: an absolute path; it may not exist yet
    """
    path = os.environ.get(EXPORT_DIR_ENV)
    if path:
        return path
    import Globals
    return os.path.join(Globals.data_dir, 'export')
