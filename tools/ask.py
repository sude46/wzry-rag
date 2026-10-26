# tools/ask.py  用法: uv run python tools/ask.py web003 "名刀多少钱"
import sys,json,requests

sid,q=sys.argv[1],sys.argv[2]

r = requests.post("http://localhost:8000/ask",
                  json={"session_id": sid, "question": q},
                  stream=True)
r.raise_for_status()
event = ""
for line in r.iter_lines(decode_unicode=True):
    line = line.strip()
    if not line:
        continue
    if line.startswith("event:"):
        event = line[6:].strip()
    elif line.startswith("data:"):
        data = json.loads(line[5:])
        if event == "token":
            print(data["text"], end="", flush=True)
        elif event == "citation":
            print(f"\n[引用] {data.get('subject')} {data.get('source_url')}")
        elif event == "done":
            print(f"\n--- done (cached={data.get('cached')}) ---")

