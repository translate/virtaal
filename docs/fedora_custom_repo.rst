
.. _fedora_custom_repo#fedora_custom_repo:

Fedora Custom Repo
==================

Fedora package policy limits updates to security and bufix releases.  Thus new
versions of Virtaal won't make it into the official repository.  But if you
would like the latest Virtaal we have built them for your version of Fedora.

To install follow these instructions:

- Download `fedora-translate-tools.repo
  <http://repos.fedorapeople.org/repos/dwayne/translate-tools/fedora-translate-tools.repo>`_
- Copy it to ``/etc/yum.repo.d``
- Run ``yum update virtaal``
- Run Virtaal and check Help->About to verify that Virtaal is at the latest
  version
