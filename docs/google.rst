
.. _google#google_translate:

Google Translate
****************

.. versionadded:: 0.5

`Google Translate <http://translate.google.com/>`_ is an online service for
machine translation (MT). Familiarise yourself with Google's `terms of service
<https://developers.google.com/translate/v2/terms>`_. Note that since Virtaal
version 1.0 you need to have an API key in your configuration (``tm.init``).

The Virtaal plugin provides the output of Google Translate as suggestions.

The plugin queries a web service over the Internet, and suggestions might
therefore take a moment before they are displayed. Also keep in mind that your
source text is sent unencrypted over the Internet, and therefore no
confidential translation should be done using this plug-in.

Remember that the suggestions from the Google Translate plugin are unreviewed
machine-generated translations, that could be wrong, inaccurate, or flawed in
some other way. It is meant as a way to help you increase your productivity,
not to substitute the expertise of a human translator.

