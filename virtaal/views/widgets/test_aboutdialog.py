#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.views.widgets.aboutdialog import AboutDialog


def test_on_url_mail_delegates_to_mailto(monkeypatch):
    dialog = AboutDialog.__new__(AboutDialog)
    calls = []
    monkeypatch.setattr('virtaal.views.widgets.aboutdialog.openmailto.mailto', calls.append)

    dialog.on_url(dialog, 'someone@example.com', 'mail')

    assert calls == ['someone@example.com']


def test_on_url_url_delegates_to_open(monkeypatch):
    dialog = AboutDialog.__new__(AboutDialog)
    calls = []
    monkeypatch.setattr('virtaal.views.widgets.aboutdialog.openmailto.open', calls.append)

    dialog.on_url(dialog, 'https://virtaal.translatehouse.org', 'url')

    assert calls == ['https://virtaal.translatehouse.org']


def test_on_url_ignores_an_unrecognised_data_value(monkeypatch):
    def _must_not_be_called(*_args):
        raise AssertionError('must not be called')

    dialog = AboutDialog.__new__(AboutDialog)
    monkeypatch.setattr('virtaal.views.widgets.aboutdialog.openmailto.mailto', _must_not_be_called)
    monkeypatch.setattr('virtaal.views.widgets.aboutdialog.openmailto.open', _must_not_be_called)

    dialog.on_url(dialog, 'irrelevant', 'something-else')  # must not raise
