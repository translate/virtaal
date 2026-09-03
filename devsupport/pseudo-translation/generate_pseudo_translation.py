#!/usr/bin/env python3
"""Generates two synthetic gettext locales from po/virtaal.pot, for
exercising every translatable string in the UI without an actual
translation:

- pseudo: every string wrapped in brackets ("[Save]") - the classic
  pseudo-localization marker for untranslated strings and truncation.
- pseudo-bidi: every string bracketed and wrapped in Unicode RTL
  isolate marks (RIGHT-TO-LEFT ISOLATE ... POP DIRECTIONAL ISOLATE) -
  simulates a right-to-left translation's layout while keeping the
  text itself readable Latin script (an isolate only sets the base
  direction of the run it wraps, it doesn't reorder or transliterate).
  Bracketed too, since the isolate marks alone are invisible.

Compiled straight into the active environment's own share/locale/, so
bin/virtaal --pseudo-translation/--pseudo-translation-bidi work with
no separate install step.
"""
import os
import sys
import tempfile

from translate.storage.placeables import StringElem
from translate.tools import podebug
from translate.tools.pocompile import convertmo

RTL_ISOLATE_START = "\u2067"  # RIGHT-TO-LEFT ISOLATE
RTL_ISOLATE_END = "\u2069"  # POP DIRECTIONAL ISOLATE


def rewrite_bidi(self, string):
    if not isinstance(string, StringElem):
        string = StringElem(string)
    return self._rewrite_prepend_append(
        string, RTL_ISOLATE_START + "[", "]" + RTL_ISOLATE_END)


# podebug.convertpo() always instantiates the module's own podebug
# class directly - attaching the method here (rather than subclassing)
# is the only way to make its own getattr(self, f"rewrite_{style}")
# dispatch find rewrite_bidi.
podebug.podebug.rewrite_bidi = rewrite_bidi

LOCALES = {
    "pseudo": "bracket",
    "pseudo-bidi": "bidi",
}


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    potfile = os.path.join(root, "po", "virtaal.pot")
    localedir = os.path.join(sys.prefix, "share", "locale")

    for code, rewritestyle in LOCALES.items():
        with tempfile.NamedTemporaryFile(suffix=".po") as tmp_po:
            with open(potfile, "rb") as infile:
                podebug.convertpo(infile, tmp_po, None, rewritestyle=rewritestyle)
            tmp_po.flush()

            mo_dir = os.path.join(localedir, code, "LC_MESSAGES")
            os.makedirs(mo_dir, exist_ok=True)
            mo_path = os.path.join(mo_dir, "virtaal.mo")
            with open(tmp_po.name, "rb") as compile_in, open(mo_path, "w") as compile_out:
                convertmo(compile_in, compile_out, None)
            print("Wrote %s" % mo_path)


if __name__ == "__main__":
    main()
