SRC_DIR = .
DOCS_DIR = docs

.PHONY: all docs pot help update-translations

all: help

docs:
	# The following creates the HTML docs.
	# NOTE: cd and make must be in the same line.
	cd ${DOCS_DIR}; make SPHINXOPTS="-W -q" html

pot:
	cd ${SRC_DIR}/po; ./update-pot

po/%.po: po/virtaal.pot
	msgmerge --previous --update ${SRC_DIR}/po/$*.po ${SRC_DIR}/po/virtaal.pot

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
