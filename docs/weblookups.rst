
.. _weblookups#web-lookups:

Web-Lookups
***********

Web-lookups allow you to execute web queries based on text selected in the
source or target window. For instance if you see a word in the source text that
you would like to search for in Wikipedia, before web lookups you would have
copied and pasted the text.  With web lookups, select the text, right click,
and then select the web lookup.

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

Use Microsoft's `Bing <http://bing.com>`_ search engine.

- quote: yes

::

    http://www.bing.com/search?q=%(query)s

.. _weblookups#google:

Google
------

Use the `Google <http://google.com>`_ search engine.

- quote: yes

::

    http://www.google.com/search?q=%(query)s

.. _weblookups#yahoo:

Yahoo
-----

Use the `Yahoo <http://yahoo.com>`_ search engine.

- quote: yes

::

    http://search.yahoo.com/search?p=%(query)s

.. _weblookups#dictionaries:

Dictionaries
============

Various dictionaries for a single language, multiple languages or specialist
domain dictionaries.  Not limited to English dictionaries.

.. _weblookups#wiktionary:

Wiktionary
----------

- `Wiktionary <http://wiktionary.org/>`_
- language: various
- quote: no

::

    http://%(querylang)s.wiktionary.org/wiki/%(query)s

.. _weblookups#dict.org:

dict.org
--------

- `dict.org <http://dict.org/>`_
- quote: no

::

    http://www.dict.org/bin/Dict?Form=Dict2&Database=*&Query=%(query)s

.. _weblookups#thefreedict:

TheFreeDict
-----------

- `TheFreeDict <http://www.thefreedictionary.com/>`_
- quote: no

::

    http://www.thefreedictionary.com/%(query)s

.. _weblookups#yourdictionary.com:

YourDictionary.com
------------------

- `YourDictionary.com <http://www.yourdictionary.com/>`_
- language: English
- quote: no

::

    http://www.yourdictionary.com/%(query)s

.. _weblookups#google_translate:

Google Translate
----------------

- `Google Translate <http://translate.google.com/>`_
- language: various
- quote: no

::

    http://translate.google.com/#%(querylang)s|%(nonquerylang)s|%(query)s

.. _weblookups#general:

General
=======

These are not bound to any language, such as where language is not important,
or will work in almost any source or target language, such as Wikipedia where
the query will ask the correct language version of Wikipedia.

.. _weblookups#wikipedia:

Wikipedia
---------

The `Wikipedia <http://wikipedia.org>`_ encyclopaedia provides over 3 million
English articles for you to query.  The query will also work on any of the many
Wikipedia in other language encyclopaedias.

- quote: no

::

    http://%(querylang)s.wikipedia.org/wiki/%(query)s

.. _weblookups#open-tran.eu:

Open-Tran.eu
------------

`Open-Tran.eu <http://open-tran.eu/>`_ contains all of the open source software
translations available.  While there is already a Translation Memory plugin you
might want to quickly see how a phrase has been translated or used in other
software translations.

- quote: yes

::

    http://%(querylang)s.%(nonquerylang)s.open-tran.eu/suggest/%(query)s

.. _weblookups#wordnet:

WordNet
-------

- `WordNet <http://wordnet.princeton.edu/>`_
- quote: no

::

    http://wordnetweb.princeton.edu/perl/webwn?s=%(query)s&sub=Search+WordNet&o2=&o0=1&o7=&o5=&o1=1&o6=&o4=&o3=&h=

.. _weblookups#termium:

Termium
-------

- `Termium <http://www.btb.termiumplus.gc.ca/>`_
- quote: no

::

    http://btb.termiumplus.gc.ca/tpv2alpha/alpha-eng.html?lang=eng&i=1&srchtxt=%(query)s&index=ent&go=Find

.. _weblookups#microsoft_terminology:

Microsoft Terminology
---------------------

The Microsoft website contains information on a lot of their terms and
translations. It is not currently possible to define a single URL that will
work for all languages, since the language codes their site expects should
contain a country code in addition to the language code, which is not usually
the case in Virtaal. But it should still be easy to write a URL for your
language specifically. Here are a few examples for different languages. Note
how a country code is always added to the language code at the end of the URL.

- quote: no

Afrikaans ::

    http://www.microsoft.com/Language/en-US/Search.aspx?sString=%(query)s&langID=af-za

French ::

    http://www.microsoft.com/Language/en-US/Search.aspx?sString=%(query)s&langID=fr-fr

Similarly use 'pt-pt' for (Iberian) Portuguese, 'pt-br' for Brazilian
Portuguese, 'sw-TZ' for Swahili, etc.

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
