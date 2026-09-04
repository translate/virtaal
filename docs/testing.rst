.. _testing#testing:

Testing
*******

.. _testing#unit_tests:

The pytest Suite
=================

Real, automated, runs in CI on every push against the actively
supported Python versions - see ``.github/workflows/ci.yml``'s
``test`` job for the current matrix. Lives under
``virtaal/`` as ``test_*.py`` files next to the code they cover (e.g.
``virtaal/test/test_storemodel.py``,
``virtaal/plugins/test_spellchecker.py``), plus a couple of
``demo_*.py`` files (``virtaal/views/widgets/demo_textbox.py`` and
siblings) that are deliberately *not* picked up by pytest - those are
manual, interactive GTK demo runners predating the automated suite,
kept for hands-on widget debugging, not real coverage.

Run it the same way CI does::

  pip install --no-build-isolation .[test]
  pytest -rvxs virtaal

On Linux without a real display, wrap it in ``xvfb-run`` (CI does)::

  xvfb-run -a --server-args="-screen 0 1024x768x24" pytest -rvxs virtaal

Real translation files for manual testing live under
``devsupport/testfiles/``, one per format or scenario worth testing
directly:

* ``checks.po`` - exercises most quality checks.
* ``plurals.po``/``plurals-zero.po`` - nplurals=3 and nplurals=1
  respectively.
* ``workflow.po``/``workflow.xliff`` - between the two, covers five of
  ``WorkflowMode``'s six states.
* ``workflow.mo`` - a compiled Gettext catalog (``pocompile``), one
  translated unit; compilation itself drops untranslated/fuzzy
  entries.
* ``workflow.tmx``, ``workflow.tbx``, ``workflow.ts`` (Qt Linguist),
  ``workflow.qph`` (Qt Phrase Book), ``workflow.ftl`` (Fluent) - cover
  translate-toolkit's other supported formats beyond Gettext PO.

Add more here as a format or scenario needs its own dedicated
coverage.

.. _testing#pseudo_translation:

Pseudo-Translation
===================

Generate and run against synthetic locales, covering every
translatable string without needing a real translation::

  python devsupport/pseudo-translation/generate_pseudo_translation.py
  virtaal --pseudo-translation devsupport/testfiles/checks.po
  virtaal --pseudo-translation-bidi devsupport/testfiles/checks.po

``--pseudo-translation`` wraps every string in brackets (``[Save]``) -
useful for spotting hardcoded strings and layout truncation.
``--pseudo-translation-bidi`` wraps every string in Unicode RTL
isolate marks too, simulating a right-to-left translation's text runs
while keeping the text itself readable Latin script.

The same script also writes a third, ``fa``-tagged locale with every
string's glyphs visually flipped (not a real Farsi translation - a
real RTL-recognised language code, for exercising actual whole-window
RTL mirroring under a genuine locale rather than just isolate-wrapped
text)::

  LANG=fa_IR.UTF-8 LANGUAGE=fa virtaal devsupport/testfiles/checks.po

See ``devsupport/testing/windows/Enable-VirtaalRtlDebug.ps1`` for
installing this into a frozen build instead of a dev checkout.

.. _testing#windows_ci:

Windows CI Checks
==================

``test-windows`` runs the pytest suite above under `gvsbuild
<https://github.com/wingtk/gvsbuild>`_'s GTK3 build.
``build-windows-installer`` goes further: it builds the real frozen
``.exe`` (PyInstaller + Inno Setup, see :doc:`building`) and drives
it directly, since a packaged build can hit bugs a dev checkout
never does (missing bundled data files, frozen-mode-only code paths).

``devsupport/testing/windows/virtaal_ui_test_helpers.ps1`` provides
the Win32 plumbing this needs - launch the real ``.exe``, get a
window handle, read its geometry/title, send keystrokes, detect and
drive popup dialogs, clean up - so each check doesn't reinvent P/Invoke
boilerplate. Two checks currently use it: a basic launch-and-verify
(open a real file, confirm the process stays alive, check the frozen
build's log files for anything unexpected), and a regression check for
a real bug found this way (the main window growing wider on every
Enter-to-advance during translation - see
``virtaal/views/widgets/storetreeview.py``'s ``select_index()``).

This is CI-only tooling - see below for a local, hands-on Windows
test harness.

.. _testing#windows_local:

Local Windows Testing
======================

CI's checks above run headless against a raw PyInstaller bundle, not
the actual installer/uninstaller a real user goes through - at least
one real report ("the unsaved marker seems to persist between
reinstalls") was specifically about behaviour across that cycle,
something CI's bundle-only checks can't reach at all. It's also worth
actually watching Virtaal run on a real Windows desktop rather than
only trusting a headless pass.

``devsupport/testing/windows/`` has the pieces for this:

* ``virtaal_install_helpers.ps1`` - installs/uninstalls Virtaal's real
  Inno Setup package silently and idempotently.
* ``Invoke-VirtaalLocalTestPass.ps1`` - orchestrates a full pass:
  uninstall, install, a battery of UI regression checks against the
  real installed app, uninstall again, with a pass/fail summary and a
  process exit code.
* ``Enable-VirtaalRtlDebug.ps1`` - installs a synthetic right-to-left
  UI catalog for manually checking that the app's whole chrome (menus,
  toolbar, status bar), not just editor text, mirrors correctly under
  an RTL language.

Run from the repo root, in PowerShell, on Windows::

  .\devsupport\testing\windows\Invoke-VirtaalLocalTestPass.ps1

See ``devsupport/testing/windows/README.md`` for the full detail -
useful switches, what the battery covers, and using the helper
functions directly for a one-off manual check.

Getting a real Windows 11 desktop
-----------------------------------

On an Apple Silicon Mac, `UTM <https://mac.getutm.app>`_ (free) runs
Windows 11 ARM64 natively via Apple's own virtualization framework -
fast, no CPU emulation involved.

1. Install UTM from `mac.getutm.app <https://mac.getutm.app>`_ (or the
   Mac App Store).
2. Get a Windows 11 ARM64 installer ISO. Easiest: install
   `CrystalFetch <https://apps.apple.com/app/crystalfetch/id6461174912>`_
   (free, App Store) - it downloads the current official build directly
   from Microsoft. Alternatively, UTM's own guide links a direct
   `Windows 11 for Apple Silicon Macs <https://docs.getutm.app/guides/windows/>`_
   ISO download if you'd rather not install another app. Either way, you
   need a real Windows license to activate it - a VM doesn't get you
   around that.
3. In UTM: **+** -> **Virtualize** -> **Windows** -> pick RAM/CPU (4GB/2
   cores minimum; more if your Mac has the headroom) -> Continue -> make
   sure **"Install Windows 10 or higher"** and **"Install drivers and
   SPICE tools"** are both checked -> Browse to the ISO -> Continue -> give
   it at least 64GB of disk -> Continue -> Save.
4. Boot it, press any key when prompted to boot from the ISO. Newer UTM
   versions handle Secure Boot/TPM automatically; if Windows Setup
   refuses with "This PC can't run Windows 11," see
   `UTM's troubleshooting section <https://docs.getutm.app/guides/windows/>`_
   for the ``LabConfig`` registry bypass.
5. To skip the Microsoft-account requirement and set up a local account
   instead: at the network-connection screen during Setup, press
   **Shift+F10** for a command prompt and run ``start ms-cxh:localonly``
   (the older ``OOBE\BYPASSNRO`` trick is now blocked by Microsoft on
   current builds).
6. Known UTM gotcha on Windows 11 24H2: the installer can go to a black
   screen because of the bundled guest-tools graphics driver. If that
   happens, eject the guest-tools ISO from UTM's CD menu, finish
   Windows Setup without it, then remount the tools ISO afterward and
   run "Install Windows Guest Tools" - you may need to reset the VM once
   more for the drivers to load cleanly.
7. Install the SPICE guest tools if they didn't run automatically (needed
   for working networking - without them Windows may insist there's no
   internet connection even once you're on the desktop).

Match what ``test-windows`` in ``.github/workflows/ci.yml`` actually
installs inside the VM, rather than improvising a different setup:

1. Install `Git for Windows <https://git-scm.com/download/win>`_ and a
   current Python (matching what ``windows-latest`` runs) from
   `python.org <https://www.python.org/downloads/windows/>`_ - ARM64
   builds are available directly.
2. Install `Visual Studio Build Tools <https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio>`_
   with the "Desktop development with C++" workload - this gives you
   ``cl.exe`` (needed to build PyGObject) and, usefully for debugging,
   ``cdb.exe``/WinDbg under ``Windows Kits\10\Debuggers\``.
3. Download the same ``gvsbuild`` GTK3 build CI uses (check
   ``gvsbuild_version`` in ``ci.yml`` for the current pinned version) from
   `wingtk/gvsbuild releases <https://github.com/wingtk/gvsbuild/releases>`_
   and extract to ``C:\gtk``.
4. Clone the repo, then in a Developer PowerShell for VS (so ``cl.exe`` is
   on ``PATH``), set the same environment variables ``ci.yml``'s Windows job
   sets - ``PKG_CONFIG_PATH``, ``GI_TYPELIB_PATH``, ``INCLUDE``/``LIB`` pointing
   at ``C:\gtk``, and add ``C:\gtk\bin`` to ``PATH`` - before
   ``pip install --no-build-isolation .[test]``. Read through the
   ``test-windows`` job's steps directly for the exact current values and
   ordering (some of them, like ``PKG_CONFIG_PATH``, get silently
   overwritten by other tools if set in the wrong order - see that
   job's own comments for why).

This is also the most useful environment for chasing a Windows-only
native crash - no 30-minute ``tmate`` session time limit, real WinDbg
instead of just ``cdb.exe``'s command-line interface, and a real GUI
to actually watch what happens.
