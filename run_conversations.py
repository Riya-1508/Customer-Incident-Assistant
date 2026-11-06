import json
import urllib.request
import sys

BASE = "http://localhost:8000/chat"


def post(session_id, message):
    data = json.dumps({"session_id": session_id, "message": message}).encode()
    req = urllib.request.Request(
        BASE, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


conversations = [
    {
        "name": "Conv 1 -- detail accumulates across 3 messages",
        "turns": [
            ("c1", "documents are not loading at all"),
            ("c1", "it is happening on our production system"),
            ("c1", "component BC-SRV-ARL"),
        ],
    },
    {
        "name": "Conv 2 -- nothing matches",
        "turns": [
            ("c2", "payroll results are incorrect after the latest HR configuration change"),
        ],
    },
    {
        "name": "Conv 3 -- PDF viewer, component added on second turn",
        "turns": [
            ("c3", "PDFs keep opening in the built-in viewer instead of Adobe"),
            ("c3", "component BC-CCM-PRN"),
        ],
    },
    {
        "name": "Conv 4 -- auth error, already_tried added",
        "turns": [
            ("c4", "user gets permission denied running the archive report"),
            ("c4", "already tried checking with the basis team"),
        ],
    },
    {
        "name": "Conv 5 -- background job, no refresh on second turn",
        "turns": [
            ("c5", "archiving works fine when I test it but fails when scheduled overnight"),
            ("c5", "already checked SM37"),
        ],
    },
]

for conv in conversations:
    print(f"\n{'='*60}")
    print(f"  {conv['name']}")
    print(f"{'='*60}")
    for session_id, message in conv["turns"]:
        try:
            resp = post(session_id, message)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            continue
        incident = resp["incident"]
        results  = resp["results"]
        print(f"\n  msg       : \"{message}\"")
        print(f"  refreshed : {resp['refreshed']}")
        print(f"  symptoms  : {incident['symptoms']}")
        print(f"  system_type: {incident['system_type']}  component: {incident['component']}")
        print(f"  already_tried: {incident['already_tried']}")
        if isinstance(results, list):
            print(f"  tickets   :")
            for r in results:
                print(f"    [{r['score']}]  {r['case_number']}  {r['short_description']}")
        elif results:
            print(f"  tickets   : {results}")
        else:
            print(f"  tickets   : (none yet)")
