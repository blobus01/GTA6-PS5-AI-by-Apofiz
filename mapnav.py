"""Помощники карты: открыть, зум, снимок."""
import base64, requests, sys
API="http://127.0.0.1:8765"; S=__import__("os").environ.get("SHOTS_DIR","shots"); __import__("os").makedirs(S,exist_ok=True)
def play(steps, name=None, w=1280):
    r=requests.post(f"{API}/api/play",json={"steps":steps,"frame_every_ms":sum(s.get('ms',0) for s in steps),"width":w},timeout=90).json()
    if name: open(f"{S}/{name}.jpg","wb").write(base64.b64decode(r["frames"][-1]["jpeg_b64"]))
    return r
if __name__=="__main__":
    import json; play(json.loads(sys.argv[1]), sys.argv[2])
