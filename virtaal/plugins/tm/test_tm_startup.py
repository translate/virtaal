#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The TM plugin's controller and models built the way the app builds
them, on a real main controller with a file open."""

import subprocess
import sys

import pytest
from gi.repository import GLib, GObject

from virtaal.plugins.tm.models.currentfile import TMModel as CurrentFileTMModel
from virtaal.plugins.tm.tmcontroller import TMController
from virtaal.test.test_scaffolding import TestScaffolding

MODELS = ['_dummytm', 'amagama', 'apertium', 'currentfile', 'google_translate', 'localtm', 'moses', 'remotetm']


class TestTMStartup(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        self.store_controller.open_file(self.testfile[1])

    @pytest.fixture(autouse=True)
    def _environment(self, monkeypatch, tmp_path):
        monkeypatch.setattr('virtaal.common.pan_app.get_config_dir', lambda: str(tmp_path))
        self.config_dir = tmp_path
        # Plug-ins load from idle callbacks; pumping the real main loop
        # hangs in this suite.
        monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args) and None)
        self.launched = []
        real_popen = subprocess.Popen
        def popen(command, **kwargs):
            # A child that lives until it's killed, in place of tmserver.
            self.launched.append(command)
            return real_popen([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        monkeypatch.setattr(subprocess, 'Popen', popen)
        self.controllers = []
        yield
        for controller in self.controllers:
            controller.destroy()

    def _controller(self, *enabled):
        controller = TMController(
            self.main_controller, {'disabled_models': [m for m in MODELS if m not in enabled]})
        self.controllers.append(controller)
        return controller

    def _remove(self, controller):
        self.controllers.remove(controller)
        controller.destroy()

    def _unit(self, source):
        unit = self.store_controller.get_store().get_units()[1].copy()
        unit.source = source
        return unit

    def _matches(self, model, source):
        found = []
        model.connect('match-found', lambda model, query, matches: found.append(matches))
        model.query(None, self._unit(source))
        return found

    def test_current_file_model_matches_against_the_open_file(self):
        model = self._controller('currentfile').plugin_controller.plugins['currentfile']

        found = self._matches(model, 'You must specify a folder or a translation file for --terminology')

        assert [m['target'] for m in found[0]] == [
            "U moet 'n gids of vertaallêer spesifiseer vir --terminology"]
        assert found[0][0]['tmsource'] == 'This file'

    def test_current_file_model_adds_a_newly_opened_file(self):
        model = self._controller('currentfile').plugin_controller.plugins['currentfile']
        matcher = model.matcher
        model.cache['stale'] = []

        model.recreate_matcher(self.store_controller)

        assert model.matcher is matcher
        assert model.cache == {}

    def test_current_file_model_waits_for_a_file(self, monkeypatch):
        monkeypatch.setattr(self.store_controller, 'get_store', lambda: None)

        model = CurrentFileTMModel('currentfile', self._controller())

        assert model.matcher is None
        model.destroy()

    def test_remote_tm_model_uses_the_configured_server(self):
        (self.config_dir / 'tm.ini').write_text('[remotetm]\nhost = tm.example.org\nport = 8080\n')

        model = self._controller('remotetm').plugin_controller.plugins['remotetm']

        assert model.tmclient.base_url == 'http://tm.example.org:8080/tmserver'
        assert model.source_lang == self.lang_controller.source_lang.code
        assert model.target_lang == self.lang_controller.target_lang.code

    def test_local_tm_model_starts_its_server_on_the_configured_database(self):
        (self.config_dir / 'tm.ini').write_text('[localtm]\ntmdb = memory.db\n')

        model = self._controller('localtm').plugin_controller.plugins['localtm']

        command = self.launched[0]
        assert command[command.index('-d') + 1] == str(self.config_dir / 'memory.db')
        port = command[command.index('-p') + 1]
        assert model.tmclient.base_url == 'http://localhost:%s/tmserver' % port

    def test_disabling_the_local_tm_stops_its_server_and_its_queries(self):
        controller = self._controller('localtm')
        model = controller.plugin_controller.plugins['localtm']
        server = model.tmserver
        queried = []
        model.tmclient.translate_unit = lambda *args, **kwargs: queried.append(args)

        controller.plugin_controller.disable_plugin('localtm')
        controller.emit('start-query', self._unit('hello'))

        assert server.wait(timeout=10) != 0
        assert queried == []

    def test_closing_saves_each_models_config(self):
        controller = self._controller('currentfile')

        self._remove(controller)

        assert '[currentfile]' in (self.config_dir / 'tm.ini').read_text()

    def test_google_translate_without_an_api_key_never_queries(self):
        model = self._controller('google_translate').plugin_controller.plugins['google_translate']

        assert not hasattr(model, 'client')
        assert self._matches(model, 'hello') == []

    def test_turning_suggestions_off_cancels_a_pending_query(self):
        controller = self._controller('currentfile')
        controller.view.mnu_suggestions.set_active(False)
        controller.unit = self._unit('PROFILE')
        controller.unit.target = 'PROFIEL'
        controller.start_query()
        pending = controller._delay_id

        controller.update_suggestions()

        assert controller._delay_id is None
        assert GLib.MainContext.default().find_source_by_id(pending) is None

    def test_a_new_query_replaces_the_editor_popup_handler(self):
        controller = self._controller('currentfile')
        unit_view = self.unit_controller.view
        controller.start_query()
        first = controller._popup_toggled_id

        controller.start_query()

        assert not GObject.signal_handler_is_connected(unit_view, first)
        assert GObject.signal_handler_is_connected(unit_view, controller._popup_toggled_id)

    def test_closing_while_the_main_window_settles_cancels_the_wait(self):
        controller = self._controller('currentfile')
        view = controller.view
        window = self.main_controller.view.main_window
        for x in (0, 10):
            view._on_configure_mainwindow(window, _Configure(x))
        pending = view._move_settle_id
        assert pending

        self._remove(controller)

        assert view._move_settle_id is None
        assert GLib.MainContext.default().find_source_by_id(pending) is None

    def test_suggestions_are_not_placed_for_a_target_that_isnt_shown(self):
        view = self._controller('currentfile').view

        assert not view._selected_target_in_view()


class _Configure:
    """A main window configure event, moved to C{x}."""
    def __init__(self, x):
        self.x, self.y, self.width, self.height = x, 0, 800, 600
