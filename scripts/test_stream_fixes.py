import sys
import os
import json
from fastapi.testclient import TestClient

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api import app
from backend.app.deps import get_current_user

app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin"}
client = TestClient(app)

print("==================================================")
print("TEST STREAMING /chat/stream with client.stream()")
print("==================================================")
tokens = []
final_done_event = None

with client.stream("POST", "/chat/stream", json={"message": "xin chào"}) as res:
    print(f"Status Code: {res.status_code}")
    for line in res.iter_lines():
        line = line.strip()
        if line.startswith("data: "):
            try:
                d = json.loads(line[6:])
                if d.get("token"):
                    tokens.append(d["token"])
                if d.get("done"):
                    final_done_event = d
            except:
                pass

full_streamed = "".join(tokens)
print("Streamed Content:\n", full_streamed)
print("\nFinal done event:\n", final_done_event)
print(f"Contains 'Nguồn:'? {'Nguồn:' in full_streamed} (Expect: False)")
print(f"Session ID received? {final_done_event and 'session_id' in final_done_event} (Expect: True)")
