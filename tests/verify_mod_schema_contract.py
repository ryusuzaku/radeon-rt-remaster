"""Contract: the mod manifest schema, its Python validator and the workflow doc agree.

The manifest is strict about unknown fields and unknown kinds, so every name it
will ever accept has to be stated in three places: the machine-readable schema
(`docs/schemas/mod-v1.schema.json`), the reader/validator (`tools/mod_scene.py`)
and the workflow documentation (`docs/MOD_WORKFLOW.md`). Nothing linked the
three, so a convention value or the reserved auxiliary-texture slot could land
on one side and be silently rejected -- or silently accepted -- on another.

This test reads all three sources and requires them to describe the same
contract:

  * the `normal_convention` values, their order and their documented default,
  * the implemented replacement kinds,
  * the reserved auxiliary-texture kind, which must stay out of the accepted set
    so the reservation cannot ship as an accident,
  * the documented captured-D3D9 default and the fail-closed rule for
    `unspecified`,
  * the rule that keeps existing manifests valid: `normal_convention` stays
    optional.

Behaviour is covered separately -- `tests/test_mods.py` asserts what the
validator accepts and rejects, including that a manifest without the field
keeps its meaning.
"""
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                    help='repository root containing tools/ and docs/')
args = parser.parse_args()
root = args.root.resolve()

schema_path = root / 'docs' / 'schemas' / 'mod-v1.schema.json'
reader = root / 'tools' / 'mod_scene.py'
doc_path = root / 'docs' / 'MOD_WORKFLOW.md'
for required in (schema_path, reader, doc_path):
    assert required.is_file(), f'missing required file: {required}'

sys.path.insert(0, str(root / 'tools'))
import mod_scene  # noqa: E402  (path has to be set up first)

schema = json.loads(schema_path.read_text(encoding='utf-8'))
doc = doc_path.read_text(encoding='utf-8')


def need(condition, message):
    assert condition, message


# --- the normal-map convention field ---------------------------------------------
entries = schema['properties']['replacements']['items']
properties = entries['properties']
need('normal_convention' in properties, 'the schema reserves no normal_convention field')
normal = properties['normal_convention']
need(list(normal['enum']) == list(mod_scene.NORMAL_CONVENTIONS),
     f'schema enum {normal["enum"]} and the validator {list(mod_scene.NORMAL_CONVENTIONS)} disagree')
need(normal.get('default') == mod_scene.DEFAULT_NORMAL_CONVENTION,
     f'schema default {normal.get("default")!r} and the validator default '
     f'{mod_scene.DEFAULT_NORMAL_CONVENTION!r} disagree')
need(mod_scene.DEFAULT_NORMAL_CONVENTION in mod_scene.NORMAL_CONVENTIONS,
     'the documented default is not one of the accepted values')
# The field is a reservation, not a requirement: existing manifests must keep
# validating unchanged, which means the field cannot become required.
need('normal_convention' not in entries.get('required', []),
     'normal_convention must stay optional so existing manifests keep validating')
need(entries.get('additionalProperties') is False,
     'the entry schema must stay strict about unknown fields')

# --- the replacement kinds and the reserved auxiliary texture slot ----------------
accepted = list(properties['kind']['enum'])
need(accepted == list(mod_scene.REPLACEMENT_KINDS),
     f'schema kinds {accepted} and the validator {list(mod_scene.REPLACEMENT_KINDS)} disagree')
reserved = schema.get('x-reserved-kinds') or {}
need(sorted(reserved) == sorted(mod_scene.RESERVED_KINDS),
     f'schema reserves {sorted(reserved)} and the validator rejects {sorted(mod_scene.RESERVED_KINDS)}')
need(all(purpose for purpose in reserved.values()),
     'every reserved kind must state its purpose in the schema')
need(not set(reserved) & set(accepted),
     'a reserved kind is also accepted by the schema; the reservation failed closed open')
need(not set(reserved) & set(mod_scene.REPLACEMENT_KINDS),
     'a reserved kind is also accepted by the validator')

# --- the workflow documentation --------------------------------------------------
for value in mod_scene.NORMAL_CONVENTIONS:
    need(f'`{value}`' in doc,
         f'docs/MOD_WORKFLOW.md does not document the normal_convention value {value!r}')
for name in mod_scene.RESERVED_KINDS:
    need(name in doc, f'docs/MOD_WORKFLOW.md does not record the reserved kind {name!r}')
need(mod_scene.DEFAULT_NORMAL_CONVENTION in doc,
     'docs/MOD_WORKFLOW.md does not name the default convention')
need('captured D3D9' in doc,
     'docs/MOD_WORKFLOW.md does not document the default as the captured D3D9 convention')
need('fails closed' in doc,
     'docs/MOD_WORKFLOW.md does not state the fail-closed rule for unspecified')

print(f'PASS mod schema contract: {len(mod_scene.NORMAL_CONVENTIONS)} normal conventions '
      f'(default {mod_scene.DEFAULT_NORMAL_CONVENTION}), '
      f'{len(accepted)} implemented kinds, {len(reserved)} reserved kind(s), '
      f'schema, validator and docs agree')
