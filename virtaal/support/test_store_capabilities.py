#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage import qm

from virtaal.support.store_capabilities import can_serialize


def test_can_serialize_is_true_for_a_writable_format():
    from translate.storage import pypo
    assert can_serialize(pypo.pofile()) is True


def test_can_serialize_is_false_for_qm():
    assert can_serialize(qm.qmfile()) is False


def test_can_serialize_only_catches_notimplementederror():
    class _Broken:
        def serialize(self, out):
            raise ValueError("not the kind of failure this checks for")

    try:
        can_serialize(_Broken())
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError to propagate")
