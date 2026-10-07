
.. _weblookups#web-lookups:

Web-Lookups
***********

Web-lookups allow you to execute web queries based on text selected in the
source or target window. For instance if you see a word in the source text that
you would like to search for in Wikipedia, before web lookups you would have
copied and pasted the text.  With web lookups, select the text, right click,
and then select the web lookup.

Virtaal comes with Google, Wikipedia and Wiktionary enabled, and Bing and
Yahoo disabled. The *Web Look-ups* dialog can enable or disable these built-in
look-ups but not remove them, and Virtaal keeps their names and URLs up to
date. Look-ups you add yourself can be removed. Each needs its own name, and
names starting with "virtaal-" are reserved.

Below are user contributed web-lookup queries that you can add to Virtaal.  If
you have others that you think could be useful then please add them to the
list.

You can also :ref:`create your own web-lookups
<weblookups#create_your_own_web-lookup>`.

.. _weblookups#search_engines:

Search Engines
==============

These are not bound to any language and deal specifically with lookups
performed against search engines.

.. _weblookups#bing:

Bing
----

Use Microsoft's `Bing <https://bing.com>`_ search engine.

- quote: yes

::

    https://www.bing.com/search?q=%(query)s

.. _weblookups#google:

Google
------

Use the `Google <https://google.com>`_ search engine.

- quote: yes

::

    https://www.google.com/search?q=%(query)s

.. _weblookups#yahoo:

Yahoo
-----

Use the `Yahoo <https://yahoo.com>`_ search engine.

- quote: yes

::

    https://search.yahoo.com/search?p=%(query)s

.. _weblookups#dictionaries:

Dictionaries
============

Various dictionaries for a single language, multiple languages or specialist
domain dictionaries.  Not limited to English dictionaries.

.. _weblookups#wiktionary:

Wiktionary
----------

- `Wiktionary <https://wiktionary.org/>`_
- language: various
- quote: no

::

    https://%(querylang)s.wiktionary.org/wiki/%(query)s

.. _weblookups#dict.org:

dict.org
--------

- `dict.org <https://dict.org/>`_
- quote: no

::

    https://www.dict.org/bin/Dict?Form=Dict2&Database=*&Query=%(query)s

.. _weblookups#thefreedict:

TheFreeDict
-----------

- `TheFreeDict <https://www.thefreedictionary.com/>`_
- quote: no

::

    https://www.thefreedictionary.com/%(query)s

.. _weblookups#yourdictionary.com:

YourDictionary.com
------------------

- `YourDictionary.com <https://www.yourdictionary.com/>`_
- language: English
- quote: no

::

    https://www.yourdictionary.com/%(query)s

.. _weblookups#google_translate:

Google Translate
----------------

- `Google Translate <https://translate.google.com/>`_
- language: various
- quote: no

::

    https://translate.google.com/?sl=%(querylang)s&tl=%(nonquerylang)s&text=%(query)s

.. _weblookups#general:

General
=======

These are not bound to any language, such as where language is not important,
or will work in almost any source or target language, such as Wikipedia where
the query will ask the correct language version of Wikipedia.

.. _weblookups#wikipedia:

Wikipedia
---------

The `Wikipedia <https://wikipedia.org>`_ encyclopaedia, queried in the
language of the selected text.

- quote: no

::

    https://%(querylang)s.wikipedia.org/wiki/%(query)s

.. _weblookups#wordnet:

WordNet
-------

- `WordNet <https://wordnet.princeton.edu/>`_
- quote: no

::

    https://wordnetweb.princeton.edu/perl/webwn?s=%(query)s&sub=Search+WordNet&o2=&o0=1&o7=&o5=&o1=1&o6=&o4=&o3=&h=

.. _weblookups#termium:

Termium
-------

- `Termium <https://www.btb.termiumplus.gc.ca/>`_
- quote: no

::

    https://btb.termiumplus.gc.ca/tpv2alpha/alpha-eng.html?lang=eng&i=1&srchtxt=%(query)s&index=ent&go=Find

.. _weblookups#termic:

termic
------

- `termic <https://termic.me/>`_ searches Microsoft's terminology and
  translation memories.
- language: various
- quote: no

termic needs a language code with a country, such as ``fr_fr``, which Virtaal
doesn't provide, so write the target language into the URL yourself. English
to French::

    https://termic.me/?q=%(query)s&sl=en_us&tl=fr_fr

Similarly use ``pt_br`` for Brazilian Portuguese, ``de_de`` for German, and so
on - termic's language menu lists the rest.

.. _weblookups#language_specific:

Language Specific
=================

These queries are only relevant to one language, such as a monolingual
dictionary, or only a few languages such as a terminology list that covers a
single pair or limited pairs of languages.

.. _weblookups#create_your_own_web-lookup:

Create your own web-lookup
==========================

You need to know the following information:

- **display_name**: The name that will be shown in the context menu
- **url**: The actual URL that will be queried. See below for template
  variables.
- **quoted**: Whether or not the query string should be put in quotes (").

Valid template variables in 'url' fields are:

- **%(query)s**: The selected text that makes up the look-up query.
- **%(querylang)s**: The language of the query string (one of *%(srclang)s* or
  *%(tgtlang)s*).
- **%(nonquerylang)s**: The source- or target language which is **not** the
  language that the query (selected text) is in.
- **%(srclang)s**: The currently selected source language.
- **%(tgtlang)s**: The currently selected target language.
