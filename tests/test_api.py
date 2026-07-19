import json

from fastapi.testclient import TestClient

from api.server import app


def test_turn_endpoint_streams_sse_events():
    client = TestClient(app)
    response = client.post('/turn', json={'session_id': 'test-session-1', 'utterance': 'is my site healthy?'})
    assert response.status_code == 200
    kinds = []
    for line in response.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        if not line.startswith('data: '):
            continue
        payload_data = line[len('data: '):]
        if payload_data.startswith('data: '):
            payload_data = payload_data[len('data: '):]
        payload = json.loads(payload_data)
        kinds.append(payload['kind'])

    assert 'transcript' in kinds
    assert 'tool_call' in kinds
    assert 'tool_result' in kinds
