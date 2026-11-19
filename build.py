import json
from pathlib import Path
from simulation import experiment

ROOT = Path(__file__).resolve().parent

def render(report):
    payload = json.dumps(report, separators=(",", ":"), allow_nan=False)
    template = (ROOT / "explorer.html").read_text(encoding="utf-8")
    return template.replace("<!-- REPORT -->", payload)

if __name__ == "__main__":
    (ROOT / "index.html").write_text(render(experiment()), encoding="utf-8", newline="\n")
