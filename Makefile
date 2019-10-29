SRC_DIR = .
DOCS_DIR = docs

.PHONY: all docs pot get-translations help update-translations

all: help

docs:
	# The following creates the HTML docs.
	# NOTE: cd and make must be in the same line.
	cd ${DOCS_DIR}; make SPHINXOPTS="-W" html

pot:
	cd ${SRC_DIR}/po; ./intltool-update --pot

get-translations:
	ssh pootletranslations ". /var/www/sites/pootle/env/bin/activate; python /var/www/sites/pootle/src/manage.py sync_stores --verbosity=3 --project=virtaal  --overwrite"
	rsync -az --delete --exclude="README" --exclude="LINGUAS*" --exclude="Makevars" --exclude="intltool-update" --exclude="testlocalisations" --exclude="POTFILES.*" --exclude=".translation_index" --exclude=pootle-terminology.po pootletranslations:/var/www/sites/pootle/translations/virtaal/ ${SRC_DIR}/po

po/%.po: po/virtaal.pot
	cd ${SRC_DIR}/po; ./intltool-update $(*F)

update-translations: ${SRC_DIR}/po/*.po

publish-pot:
	scp ${SRC_DIR}/po/virtaal.pot pootletranslations:/var/www/sites/pootle/translations/virtaal/
	ssh pootletranslations ". /var/www/sites/pootle/env/bin/activate; python /var/www/sites/pootle/src/manage.py update_stores --verbosity=3 --project=virtaal --language=templates"

publish-translations:
	scp ${SRC_DIR}/po/*.po pootletranslations:/var/www/sites/pootle/translations/virtaal/
	ssh pootletranslations ". /var/www/sites/pootle/env/bin/activate; python /var/www/sites/pootle/src/manage.py update_stores --verbosity=3 --project=virtaal; python /var/www/sites/pootle/src/manage.py update_translation_projects --verbosity=3 --project=virtaal"

help:
	@echo
	@echo "Help"
	@echo "----"
	@echo
	@echo "  docs - build Sphinx docs"
	@echo "  pot - update the POT translations templates"
	@echo "  get-translations - retrieve Pootle translations from server (requires ssh config for pootletranslations)"
	@echo "  update-translations - update *.po against virtaal.pot"
	@echo "  publish-translations - send all *.po to Pootle translations server"
	@echo "  publish-pot - send virtaal.pot to Pootle translations server"
	@echo

