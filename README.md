# Export Import for Plone 2.x - 3.x

This codebase is a simplified port of `collective.exportimport` that will run as a `Products` in older Plone sites:

* Python 2.4.6
* Plone 2.1 with Archetypes
* Zope 2.8.12
* simplejson

It is important to mention that `plone.restapi` 7.x was the last series to support Archetypes, and `collective.exportimport` needs `Plone 4.x`.

Use `docker run --platform linux/amd64 -it -p8080:8080 plone/plone:2.1-demo` to check the code

## Goals

* Implement the bare minimum solution to export Archetypes content items from Plone 2.1
* This package should not require additional packages.

## Installation

Copy (or symlink) `src/Products/ExportImport` into the instance's `Products/`
directory and restart Zope. There is nothing to install in the Plone site.

## Usage

The export always covers the whole site. It writes to `$EXPORTIMPORT_DIR`, or
`<CLIENT_HOME>/export` (normally `var/export`) when the variable is unset.

**From the browser**: as a Manager, open `<site>/exportimport_export` and press
*Export*. A GET only shows the form; the export runs on POST.

**From the command line**, with the instance stopped (the script needs the
database lock):

```sh
SITE_ID=Plone EXPORTIMPORT_DIR=/tmp/export \
    bin/zopectl run Products/ExportImport/scripts/export.py
```

`EXPORTIMPORT_TYPES=Document,Image` limits the export to those portal types.
`zopectl run` discards the script's exit status. Check that the output ends
with `EXPORT-OK` instead.

The output is meant for `collective.exportimport`'s importer on Plone 6. Fields
use their Dexterity names (`subjects`, `created`, `exclude_from_nav`, ...) and
files and images are inlined as base64. Reference fields are left out.

Every string is valid for strict JSON parsers such as `orjson`: bytes that are
not valid in the site charset, and UTF-16 surrogates without their pair, are
replaced with U+FFFD.

### Binaries in rich text fields

Archetypes 1.3 lets a file be uploaded into a rich text field. When a rich
text field holds a content type other than `text/*`, the export does not
decode it as text. Instead, it:

1. Writes a new `Image` (for `image/*`) or `File` item **inside** the item,
   with id and title `image.<ext>` or `file.<ext>`. The extension comes from
   the filename stored in the field, falling back to the content type (Word
   files, for instance, are stored as `application/zip`).
2. Gives it the UID `md5("<item UID>:<field name>")`, which stays the same
   across exports.
3. Copies the item's dates, creators, review state and workflow history.
4. Numbers it right after the item, and lists it in `export_ordering.json`.
5. Replaces the field with a link to it: `resolveuid/<uid>/@@download/file`
   for a File, an `<img>` with `resolveuid/<uid>/@@images/image` for an Image.

The importing site must have folderish `Document` and `Event` types, as with
`plone.volto`. The export summary reports how many items were extracted.

Memory stays bounded on large sites: the ZODB cache is trimmed after each item,
and items are streamed to disk.

## Development

Everything runs in the `plone/plone:2.1-demo` image (Python 2.4.6, Zope 2.8.12,
Plone 2.1.4), with the product bind-mounted read-only:

| Command | What it does |
|---|---|
| `make start` | Plone on http://localhost:8080/Plone (`admin`/`admin`), exporting to `./export` |
| `make export` | Export the site in the data volume to `./export` (`SITE_ID=`, `TYPES=`) |
| `make check` | Compile every `.py` file under Python 2.4 |
| `make test` | `make check`, then the test suite (`zopectl test` + `PloneTestCase`) |
| `make clean-data` | Delete the data volume; the next run starts from the demo site again |

Write Python **2.4**. Not available: conditional expressions (`a if c else b`),
`with`, `except E as e` (use `sys.exc_info()`), `try`/`except`/`finally` in one
statement, `any()`/`all()`, `str.format`, class decorators. Keep source files
ASCII-only, because 2.4 has no default source encoding. `make check` catches
the syntax errors.

Plone 2.1 behaviour worth knowing:

* The catalog cannot `sort_on='path'` (the path index is not sortable), so the
  exporter sorts brains by `getPath()` itself.
* `DateTime` in Zope 2.8 has no `asdatetime()`. Dates are converted with
  `toZone('UTC')`.
* `description` and `rights` are `TextField`s with a plain widget and are
  exported as strings. `allowDiscussion` is a `StringField`.

## Export format

Data in a structure:

```
export/
    <Site ID>/
        1.json
        2.json
    export_ordering.json (order on folder)
    export_localroles.json (local roles)
```

The enumerator for the contents need to be ordered by the path in the site ("getPATH() for a brain")

Each content should look like:

```json
{
  "@id": "/images/50441750333_2a73c9d305_o.jpg",
  "@type": "Image",
  "UID": "5cbf5393ee6c46d2bc55b6ec9e222f39",
  "allow_discussion": false,
  "contributors": [],
  "created": "2022-05-24T18:38:11+00:00",
  "creators": [
    "ericof"
  ],
  "description": "",
  "effective": null,
  "exclude_from_nav": false,
  "expires": null,
  "id": "50441750333_2a73c9d305_o.jpg",
  "image": {
    "content-type": "image/jpeg",
    "data": "<base64>",
    "encoding": "base64",
    "filename": "50441750333_2a73c9d305_o.jpg"
  },
  "is_folderish": false,
  "language": "",
  "layout": "image_view",
  "lock": {},
  "modified": "2022-05-24T18:38:11+00:00",
  "parent": {
    "@id": "/images",
    "@type": "Folder",
    "UID": "b8e4d1590c3d4c35a197f853db537aca",
    "description": "Banco de imagens.",
    "image_field": null,
    "image_scales": null,
    "review_state": "published",
    "title": "Imagens",
    "type_title": "Pasta"
  },
  "review_state": null,
  "rights": "",
  "subjects": [],
  "title": "50441750333_2a73c9d305_o.jpg",
  "type_title": "Imagem",
  "version": "current",
  "workflow_history": {
    "simple_publication_workflow": [
      {
        "action": null,
        "actor": "ericof",
        "comments": "",
        "review_state": "private",
        "time": "2022-06-20T15:28:28+00:00"
      },
      {
        "action": "publish",
        "actor": "ericof",
        "comments": "",
        "review_state": "published",
        "time": "2022-06-20T15:28:33+00:00"
      }
    ]
  },
  "working_copy": null,
  "working_copy_of": null
}
```