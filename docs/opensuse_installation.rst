
.. _opensuse_installation#=_installing_virtaal_on_opensuse:

Installing Virtaal on openSUSE
******************************

Virtaal is packaged in repositories kindly maintained by Luiz Fernando
Ranghetti.  If you add these repositories to your system, you can access
Virtaal through your package manager and receive updates.

.. _opensuse_installation#add_the_correct_repository:

Add the Correct Repository
==========================
You can add a repository in YaST by specifying a URL.

- **for openSUSE Factory**:
  http://download.opensuse.org/repositories/home:/elchevive/openSUSE_Factory/
- **for openSUSE 12.1**:
  http://download.opensuse.org/repositories/home:/elchevive/openSUSE_12.1/

If you want to add it on the command line, perform the correct command based on
your version openSUSE::

  zypper ar -f http://r.opensu.se/home:elchevive/openSUSE_Factory/  translate

or ::

  zypper ar -f http://r.opensu.se/home:elchevive/openSUSE_12.1/  translate

Here "ar" means "add repository", "-'f" to make it refresh and "translate" is
the name that you give to the repository.

Now you can install Virtaal through YaST or zypper. 

.. _opensuse_installation#installing_virtaal:

Installing Virtaal
==================

You can install Virtaal with YaST, by searching for it in the software manager.

Alternatively you can install it on the command-line with zypper::

    zypper in virtaal

.. _opensuse_installation#note:

Note
====
You will be asked to accept the key for the new repository.  After accepting
the key, it shouldn't ask again, and everything should work.

To install only the Translate Toolkit from the repositories you added, just
search for translate-toolkit.  On the command-line, that means ::

  zypper in translate-toolkit
