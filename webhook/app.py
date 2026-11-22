from flask import Flask, request, jsonify
import logging
import subprocess
from pathlib import Path

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "ansible" / "restart-nginx.yml"

@app.post("/webhook")
def webhook():
    payload = request.get_json(silent=True) or {}
    alerts = payload.get("alerts", [])
    should_recover = any(
        a.get("labels", {}).get("alertname") == "NginxDown"
        and a.get("status") == "firing"
        for a in alerts
    )
    if not should_recover:
        return jsonify({"status": "ignored", "reason": "No firing NginxDown alert"}), 200

    logging.warning("NginxDown alert received; invoking fixed Ansible playbook")
    try:
        result = subprocess.run(
            ["ansible-playbook", str(PLAYBOOK)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        logging.info("ansible stdout:\n%s", result.stdout)
        if result.stderr:
            logging.warning("ansible stderr:\n%s", result.stderr)
        if result.returncode != 0:
            return jsonify({"status": "failed", "returncode": result.returncode}), 500
        return jsonify({"status": "recovery_playbook_executed"}), 200
    except Exception:
        logging.exception("Could not execute recovery playbook")
        return jsonify({"status": "error"}), 500

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    # Local lab only. Restrict access with firewall; do not expose publicly.
    app.run(host="0.0.0.0", port=5001)
