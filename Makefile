SRC_DIR = .

.PHONY: all pot get-translations help update-translations

all: help

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
	@echo "  pot - update the POT translations templates"
	@echo "  get-translations - retrieve Pootle translations from server (requires ssh config for pootletranslations)"
	@echo "  update-translations - update *.po against virtaal.pot"
	@echo "  publish-translations - send all *.po to Pootle translations server"
	@echo "  publish-pot - send virtaal.pot to Pootle translations server"
	@echo

