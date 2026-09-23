#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import xmlrpc.client as xmlrpclib

from virtaal.support.mosesclient import MosesClient, fixup, prepare


def test_prepare_spaces_out_punctuation():
    assert prepare('Hello, world!') == 'hello , world !'


def test_prepare_spaces_out_parentheses():
    assert prepare('(hi) there') == '( hi ) there'


def test_prepare_encodes_newlines():
    assert prepare('line1\nline2') == 'line1 __::__ line2'


def test_fixup_restores_punctuation_spacing():
    assert fixup('src', 'hello , world !') == 'hello, world!'


def test_fixup_restores_parentheses():
    assert fixup('src', '( hi)') == '(hi)'


def test_fixup_restores_newlines():
    assert fixup('src', 'a __::__ b') == 'a\nb'


def test_fixup_applies_autocorrect_against_the_source():
    # translate.filters.autocorrect.correct() capitalizes/punctuates
    # the response to match the source's own casing/terminal period.
    assert fixup('Hello.', 'hello') == 'Hello.'


def _client_with_captured_requests():
    client = MosesClient('http://example.com')
    requests = []
    client.add = lambda request: requests.append(request)
    return client, requests


def test_init_appends_rpc2_to_the_url():
    client = MosesClient('http://example.com')

    assert client.url == 'http://example.com/RPC2'
    assert client.multilang is False


def test_set_multilang_defaults_to_enabling():
    client = MosesClient('http://example.com')

    client.set_multilang()

    assert client.multilang is True


def test_set_multilang_can_disable():
    client = MosesClient('http://example.com')
    client.set_multilang(True)

    client.set_multilang(False)

    assert client.multilang is False


def test_translate_unit_posts_the_prepared_text():
    client, requests = _client_with_captured_requests()

    client.translate_unit('Hello, world!')

    assert len(requests) == 1
    request = requests[0]
    assert request.url == 'http://example.com/RPC2'
    assert request.method == 'POST'
    assert request.source_text == 'Hello, world!'
    (params,), method = xmlrpclib.loads(request.data)
    assert method == 'translate'
    assert params == {'text': 'hello , world !'}


def test_translate_unit_includes_the_system_param_when_multilang():
    client, requests = _client_with_captured_requests()
    client.set_multilang(True)

    client.translate_unit('hi', target_language='af')

    (params,), _method = xmlrpclib.loads(requests[0].data)
    assert params == {'text': 'hi', 'system': 'af'}


def test_translate_unit_wires_the_callback_to_a_successful_response():
    client, requests = _client_with_captured_requests()
    calls = []
    client.translate_unit('hi there', callback=lambda source, translation: calls.append((source, translation)))

    response_body = xmlrpclib.dumps(({'text': 'daar'},), methodresponse=True)
    requests[0].emit('http-success', response_body)

    assert calls == [('hi there', 'daar')]


def test_translate_unit_without_a_callback_does_not_raise_on_success():
    client, requests = _client_with_captured_requests()

    client.translate_unit('hi')
    requests[0].emit('http-success', b'ignored')  # must not raise


def test_loads_safe_returns_the_decoded_struct():
    client = MosesClient('http://example.com')
    body = xmlrpclib.dumps(({'text': 'jou'},), methodresponse=True)

    assert client._loads_safe(body) == {'text': 'jou'}


def test_loads_safe_disables_multilang_on_unknown_system_fault():
    client = MosesClient('http://example.com')
    client.set_multilang(True)
    fault_body = xmlrpclib.dumps(
        xmlrpclib.Fault(1, 'Unknown translation system id: xx'), methodresponse=True)

    result = client._loads_safe(fault_body)

    assert result is None
    assert client.multilang is False


def test_loads_safe_returns_none_for_unparseable_data():
    client = MosesClient('http://example.com')

    assert client._loads_safe(b'not xml at all') is None


def test_handle_response_returns_none_without_a_suggestion(monkeypatch):
    client = MosesClient('http://example.com')
    monkeypatch.setattr(client, '_loads_safe', lambda response: None)

    assert client._handle_response('src', b'ignored') is None


def test_handle_response_fixes_up_the_translated_text():
    client = MosesClient('http://example.com')
    body = xmlrpclib.dumps(({'text': 'hello , world !'},), methodresponse=True)

    assert client._handle_response('src', body) == 'hello, world!'
