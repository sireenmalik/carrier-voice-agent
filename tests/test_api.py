import json

from fastapi.testclient import TestClient

from api.server import app


def test_turn_endpoint_streams_sse_events():
    client = TestClient(app)
    response = client.post('/turn', json={'session_id': 'test-session-1', 'utterance': 'is my site healthy?'}, stream=True)
    assert response.status_code == 200
    kinds = []
    for line in response.iter_lines():
        if not line:
            continue
        assert line.startswith(b'data: ')
        payload = json.loads(line[len(b'data: '):].decode('utf-8'))
        kinds.append(payload['kind'])

    assert 'transcript' in kinds
    assert 'tool_call' in kinds
    assert 'tool_result' in kinds
