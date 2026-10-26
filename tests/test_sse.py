from api.sse import event


def test_sse_event_format():
    payload = event("token", {"text": "你好"})
    assert payload.startswith("event: token\n")
    assert '"text": "你好"' in payload
    assert payload.endswith("\n\n")
