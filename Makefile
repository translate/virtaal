SRC_DIR = .
DOCS_DIR = docs

.PHONY: all docs pot help update-translations

all: help

docs:
	# The following creates the HTML docs.
	# NOTE: cd and make must be in the same line.
	cd ${DOCS_DIR}; make SPHINXOPTS="-W -q" html

pot:
	cd ${SRC_DIR}/po; ./intltool-update --pot

po/%.po: po/virtaal.pot
	cd ${SRC_DIR}/po; ./intltool-update $(*F)

update-translations: ${SRC_DIR}/po/*.po

help:
	@echo
	@echo "Help"
	@echo "----"
	@echo
	@echo "  docs - build Sphinx docs"
	@echo "  pot - update the POT translations templates"
	@echo "  update-translations - update *.po against virtaal.pot"
	@echo
