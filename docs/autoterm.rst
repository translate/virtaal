
.. _autoterm:

Automatic Terminology Assistance
********************************

.. versionadded:: 0.5

Virtaal can provide terminology help in many ways. One of the most powerful
ways is where Virtaal downloads a recommended file of localisation terms for
your language.

By default, this file comes from `Mozilla Pontoon
<https://pontoon.mozilla.org/terminology/>`_, for any language pair it
covers - no configuration needed for that.

This powerful feature has many benefits:

- This works without any configuration, as long as a terminology plugin
  providing it is enabled.
- Inexperienced translators will get terminology configured, even if they don't
  know that they should be doing something like this.
- Since the terminology is not packaged with Virtaal, teams can maintain their
  terminology, and don't need to "have it ready" for a Virtaal release.
- Since Virtaal will check every few days for new versions of the file,
  translators can use up to date terminology, without having to even know that
  maintenance was done on the list.

You can also point Virtaal at your own terminology file's URL instead - a PO
file from a Pootle/Weblate server, for example, so the same terms are also
recommended there. All file formats supported by Virtaal can be used.
