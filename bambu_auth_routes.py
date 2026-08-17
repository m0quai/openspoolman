import json
from pathlib import Path

from flask import Blueprint, render_template

from config import PRINTER_CODE, PRINTER_ID, PRINTER_IP, PRINTER_NAME
import mqtt_bambulab

bp = Blueprint("bambu_cloud", __name__, url_prefix="/bambu-cloud")
RUNTIME_STATUS = Path("/home/app/data/bambu_mqtt_runtime_status.json")


def _runtime_status():
    try:
        return json.loads(RUNTIME_STATUS.read_text(encoding="utf-8"))
    except Exception:
        return {}


@bp.route("/", methods=["GET"])
def index():
    config = {
        "printer_name": PRINTER_NAME,
        "printer_ip": PRINTER_IP,
        "printer_id": PRINTER_ID,
        "port": 8883,
        "username": "bblp",
        "access_code_present": bool(PRINTER_CODE),
        "access_code_length": len(PRINTER_CODE or ""),
        "source": "config.env",
    }
    return render_template(
        "bambu_auth.html",
        config=config,
        connected=mqtt_bambulab.isMqttClientConnected(),
        status=_runtime_status(),
    )
