#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""bin/virtaal's own command-line entry point, split out so bin/virtaal
    itself can stay a plain launcher with no translatable strings (and
    so xgettext, which only auto-detects source language by file
    extension, doesn't need a special case for an extensionless file).
    bin/virtaal's own "--run-module" frozen-build dispatch has to stay
    there, though - it needs to run before any of this module's own
    imports happen at all."""

import sys
from os import path

# A frozen build needs pycairo's C-API initialized before GTK's
# foreign-struct registration for cairo.Context runs, or every draw
# call fails with a TypeError. Harmless to do unconditionally.
import cairo  # noqa: F401

from virtaal.common import pan_app

# Some behaviour should vary, depending on whether Virtaal is packaged or not
packaged = getattr(sys, 'frozen', False)
# Distributions can just set this value to True, if dependencies are taken care
# of elsewhere:
#packaged = True

# Let's check for dependencies before we do anything else
if not packaged:
    # We can't meaningfully report on these, and we build our own windows
    # version, so let's leave this out for the benefit of startup time.
    from virtaal.support import depcheck
    optional_modules = ['enchant', 'gtkspell', 'libproxy']
    error_messages = {
        'translate':  'Translate Toolkit >= %s is required for Virtaal to function.' % str(depcheck.MIN_TRANSLATE_VERSION),
        'gtk':        'Gtk >= %s and PyGTK is required for Virtaal to function.' % str(depcheck.MIN_GTK_VERSION),
        'lxml.etree': 'LXML is required for XML-based format support as well as AutoCorrection.',
        'json':       'SimpleJSON or Python >= 2.6 is required for certain TM back-ends.',
        'pycurl':     'PyCurl is required for certain TM and terminology back-ends.',
        'sqlite3':    'SQLite3 is required for Virtaal to function.',
        'wsgiref':    'WSGIRef is required for Virtaal to function.',
        'enchant':    'Enchant not installed: Spell checking will not work.',
        'gtkspell':   'GtkSpell not installed: Spell checking will not work.',
        'libproxy':   'libproxy is not installed: it improves support for network proxies on Linux.',
        'diff_match_patch': 'diff_match_patch is not installed: it is required for TM functionality.',
    }

    failed = depcheck.check_dependencies(depcheck.import_checks + optional_modules)
    if failed:
        errors = '\n'.join([error_messages[name] for name in failed if name in depcheck.import_checks])
        warnings = '\n'.join([error_messages[name] for name in failed if name in optional_modules])

        if warnings:
            print('DEPENDENCY WARNINGS:')
            print(warnings)
        if errors:
            print('DEPENDENCY ERRORS:')
            print(errors)
        print()
        print("You can disable dependency checking to speed up startup by setting")
        print("  packaged = True")
        print("in the file '%s'" % __file__)
        if errors:
            sys.exit(1)
# OK, dependencies seem to be acceptable

def build_parser():
    """Construct bin/virtaal's own argparse.ArgumentParser. Split out
    from main() so test_cli.py can introspect the real option list
    (e.g. to check it's fully documented in docs/cli_options.rst)
    without duplicating it."""
    import argparse

    from virtaal import __version__

    # argparse's own _ is independent of Virtaal's gettext.install()
    # - without this, its generated chrome stays untranslated.
    argparse._ = _
    parser = argparse.ArgumentParser()
    # Note for a packaged Windows build: pan_app's stdout/stderr
    # redirection runs at import time, before this ever executes,
    # so this text lands in %APPDATA%\Virtaal\stdout_virtaal.log,
    # not a caller's console.
    parser.add_argument("-v", "--version", action="version", version=__version__.version_string())
    parser.add_argument("-l", "--log", dest="log", metavar=_("LOG"),
                         help=_("turn on logging, storing the result to the supplied filename."))
    parser.add_argument("-c", "--config", dest="config", metavar=_("CONFIG"),
                         help=_("use the configuration file given by the supplied filename."))
    parser.add_argument("-D", "--debug", dest="debug", action="store_true", default=False,
                         help=_("enable debugging features"))
    pseudo_group = parser.add_mutually_exclusive_group()
    pseudo_group.add_argument("--pseudo-translation", dest="pseudo_translation", action="store_true", default=False,
                         help=_("use a synthetic pseudo-translation for every UI string "
                                 "(see devsupport/pseudo-translation/generate_pseudo_translation.py)"))
    pseudo_group.add_argument("--pseudo-translation-bidi", dest="pseudo_translation_bidi", action="store_true", default=False,
                         help=_("like --pseudo-translation, but also simulates a right-to-left UI layout"))
    pseudo_group.add_argument("--lang", dest="lang", metavar=_("LANG"),
                         help=_("override the UI language for this run (e.g. \"fr\"; "
                                 "\"en\" for the untranslated source strings; \"system\" "
                                 "for the OS's own default), without changing the saved "
                                 "Preferences setting"))
    # Profiling does not make sense in packaged versions.  Set to True to disable profiling.
    if not packaged:
        parser.add_argument("-P", "--profile", dest="profile", metavar=_("PROFILE"),
                             #l10n: 'profiling' refers to performance testing
                             help=_("perform profiling, storing the result to the supplied filename."))
    # nargs='?' makes this genuinely optional and means argparse itself
    # rejects more than one positional argument (with its own
    # "unrecognized arguments" error).
    parser.add_argument("translation_file", nargs="?", default=None)
    return parser


def run_virtaal(startup_file):
    # The Virtaal class is imported here to allow changes made in this module (eg. pan_app.DEBUG)
    # to be visible to the rest of the program, seeing as Virtaal imports all controllers, which
    # basically imports the the whole core.
    from virtaal.main import Virtaal
    prog = Virtaal(startup_file)
    prog.run()


def _set_logging(options, parser):
    if options.log is None and not options.debug:
        return

    import logging

    from virtaal import __version__

    level = options.debug and logging.DEBUG or logging.INFO
    if options.debug:
        format = '%(levelname)7s %(module)s.%(funcName)s:%(lineno)d: %(message)s'
    else:
        format = '%(asctime)s %(levelname)s %(message)s'
    if options.log is None:
        logging.basicConfig(level=level, format=format, stream=sys.stderr)
    elif options.log.upper() in ('-', 'STDOUT'):
        logging.basicConfig(level=level, format=format, stream=sys.stdout)
    else:
        try:
            logging.basicConfig(level=level, format=format, filename=path.abspath(options.log), filemode='w')
        except OSError:
            parser.error(_("Could not open log file '%(filename)s'") % {"filename": options.log})

    logging.info("Virtaal %s", __version__.version_string())


def _set_config(options, parser):
    try:
        if options.config is not None:
            pan_app.settings = pan_app.Settings(path.abspath(options.config))
    except Exception:
        parser.error(_("Could not read configuration file '%(filename)s'") % {"filename": options.config})


def _set_pseudo_translation(options, parser):
    if not (options.pseudo_translation or options.pseudo_translation_bidi):
        return
    lang = 'pseudo-bidi' if options.pseudo_translation_bidi else 'pseudo'
    if not packaged:
        import importlib.util
        repo_root = path.dirname(path.dirname(path.abspath(__file__)))
        generator_path = path.join(repo_root, 'devsupport', 'pseudo-translation',
                                    'generate_pseudo_translation.py')
        spec = importlib.util.spec_from_file_location('generate_pseudo_translation', generator_path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        generator.generate_locale(lang)
    try:
        pan_app.set_ui_language(lang)
    except OSError:
        parser.error("No '%s' locale found - run "
                      "devsupport/pseudo-translation/generate_pseudo_translation.py first" % lang)
    if options.pseudo_translation_bidi:
        # Must run before the first widget is constructed.
        from gi.repository import Gtk
        Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)


def _set_lang(options, parser):
    if not options.lang:
        return
    try:
        pan_app.set_ui_language(options.lang)
    except OSError:
        parser.error(_("No translation found for language '%(lang)s'") % {"lang": options.lang})


def _run_profiled(profile_file, startup_file):
    import cProfile
    import logging
    try:
        import devsupport.profiling as profiling
    except ImportError:
        #l10n: This refers to performance profiling for developers
        logging.error(_("Profiling support is not available"))
        sys.exit(1)
    logging.info('Starting profiling run')
    profiler = cProfile.Profile()
    profiler.runcall(run_virtaal, startup_file)
    k_cache_grind = profiling.KCacheGrind(profiler)
    k_cache_grind.output(profile_file)
    profile_file.close()


def _profile_runner(options, parser, startup_file):
    try:
        _run_profiled(open(options.profile, 'w+', encoding='utf-8'), startup_file)
    except OSError:
        parser.error(_("Could not open profile file '%(filename)s'") % {"filename": options.profile})


def _default_runner(startup_file):
    if not pan_app.DEBUG:
        try:
            import psyco
            psyco.full()
        except Exception:
            pass
    run_virtaal(startup_file)
    # virtaal.main.Virtaal disables the cyclic GC for the whole
    # run (see there for why), but normal CPython interpreter
    # finalization forces one last gc.collect() regardless of
    # that, which reproduced the exact same GTK teardown
    # segfault at exit instead of during use. Skip normal
    # finalization to avoid it; there's nothing left to flush
    # or clean up at this point.
    import os
    os._exit(0)


def main(argv):
    options = None
    parser = None
    startup_file = None

    if len(argv) > 1:
        parser = build_parser()
        options = parser.parse_args(argv[1:])
        pan_app.DEBUG = options.debug
        _set_config(options, parser)
        _set_logging(options, parser)
        _set_pseudo_translation(options, parser)
        _set_lang(options, parser)
        startup_file = options.translation_file
    else:
        # No arguments given, so we save some time by avoiding all the things
        # that could have happened on the command line
        pan_app.DEBUG = False

    if options and getattr(options, "profile", None) != None:
        _profile_runner(options, parser, startup_file)
    else:
        _default_runner(startup_file)
