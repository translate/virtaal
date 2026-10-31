#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Import pyenchant only if it is really there: a leftover "enchant"
directory with no __init__.py imports as an empty namespace package."""

_USED = ('dict_exists', 'list_languages', 'get_user_config_dir')


def import_enchant():
    """Return the pyenchant module, or None if it isn't usable."""
    try:
        import enchant
    except ImportError:
        return None
    if not all(hasattr(enchant, name) for name in _USED):
        return None
    return enchant


def enchant_tag(code):
    """The tag enchant finds a dictionary by for a Virtaal language code.
        Enchant matches only "language_PART" (language lowercased, the
        part uppercased) and ignores file names containing "-" or "@", so
        ca@valencia is ca_VALENCIA and sr_Latn_RS is sr_LATNRS. A
        downloaded dictionary is saved under this name (#4665)."""
    lang, _, variant = code.replace('-', '_').partition('@')
    language, _, rest = lang.partition('_')
    rest = rest.replace('_', '') + variant
    return language.lower() + ('_' + rest.upper() if rest else '')


def self_check(lang):
    """Report which enchant library and providers this build uses, and
    whether lang's dictionary works with GtkSpell - for packaging smoke
    tests (virtaal --run-module virtaal.support.enchant_compat LANG)."""
    enchant = import_enchant()
    if enchant is None:
        return 'enchant: none\n'
    from enchant import _enchant
    lines = [
        'enchant: %s' % _enchant.enchant_lib_path,
        'providers: %s' % ' '.join(sorted(p.name for p in enchant.Broker().describe())),
        'dictionary: %s' % enchant.dict_exists(lang),
    ]
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('GtkSpell', '3.0')
        from gi.repository import GtkSpell
        GtkSpell.Checker().set_language(lang)
        lines.append('gtkspell: ok')
    except Exception as e:
        lines.append('gtkspell: %s' % e)
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    import sys
    sys.stdout.write(self_check(sys.argv[1] if len(sys.argv) > 1 else 'en_US'))
