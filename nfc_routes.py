import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

import mqtt_bambulab
import spoolman_client
import spoolman_service

bp = Blueprint("ams_nfc", __name__, url_prefix="/ams/nfc")
_PENDING_FILE = Path(__file__).resolve().parent / "data" / "nfc_pending.json"


def _clean_extra_value(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _normalize_uid(value):
    return str(value or "").strip().upper().replace(":", "-")


def _find_spool_by_uid(uid):
    wanted = _normalize_uid(uid)
    for spool in spoolman_service.fetchSpools(cached=True):
        extras = spool.get("extra") or {}
        tag = _normalize_uid(_clean_extra_value(extras.get("tag")))
        if tag == wanted:
            return spool
    return None


def _resolve_tray(tray_index):
    config = mqtt_bambulab.getLastAMSConfig() or {}
    for ams in config.get("ams", []):
        ams_id = int(ams.get("id", -1))
        for tray in ams.get("tray", []):
            if int(tray.get("id", -1)) == tray_index:
                return ams_id, tray_index
    if 0 <= tray_index <= 3:
        return 0, tray_index
    return None, None


def _load_pending():
    try:
        data = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_pending(items):
    _PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PENDING_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _remember_pending(uid, tray_index, ams_id):
    items = _load_pending()
    items = [item for item in items if _normalize_uid(item.get("uid")) != uid]
    items.append({
        "uid": uid,
        "tray_index": tray_index,
        "ams_id": ams_id,
        "seen_at": datetime.now(timezone.utc).isoformat(),
    })
    _save_pending(items)


def _remove_pending(uid):
    wanted = _normalize_uid(uid)
    items = [item for item in _load_pending() if _normalize_uid(item.get("uid")) != wanted]
    _save_pending(items)


def _assign_spool_to_tray(spool, ams_id, tray_id):
    spool_id = spool["id"]
    mqtt_bambulab.setActiveTray(spool_id, spool.get("extra") or {}, ams_id, tray_id)
    from app import setActiveSpool
    setActiveSpool(ams_id, tray_id, spool)
    return spool_id


@bp.post("/<int:tray_index>/set")
def set_nfc_tray(tray_index):
    body = request.get_json(silent=True) or {}
    uid = _normalize_uid(body.get("uid"))
    if not uid:
        return jsonify({"success": False, "error": "Field 'uid' is required."}), 400

    ams_id, tray_id = _resolve_tray(tray_index)
    if ams_id is None:
        return jsonify({"success": False, "error": f"Tray '{tray_index}' not found."}), 404

    try:
        if uid == "CLEAR":
            spoolman_service.clear_active_spool_for_tray(ams_id, tray_id)
            return jsonify({"success": True, "action": "clear", "tray_index": tray_index, "ams_id": ams_id})

        spool = _find_spool_by_uid(uid)
        if not spool or spool.get("id") is None:
            _remember_pending(uid, tray_index, ams_id)
            return jsonify({
                "success": True,
                "action": "pending",
                "tray_index": tray_index,
                "ams_id": ams_id,
                "uid": uid,
                "message": "Unknown NFC tag stored for assignment.",
            }), 202

        spool_id = _assign_spool_to_tray(spool, ams_id, tray_id)
        _remove_pending(uid)
        return jsonify({"success": True, "action": "assign", "tray_index": tray_index, "ams_id": ams_id, "uid": uid, "spool_id": spool_id})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/pending")
def pending_tags():
    return render_template("nfc_pending.html", pending_tags=_load_pending(), spools=spoolman_service.fetchSpools(cached=True))


@bp.post("/pending/<path:uid>/assign")
def assign_pending_tag(uid):
    normalized_uid = _normalize_uid(uid)
    spool_id_raw = request.form.get("spool_id", "").strip()
    try:
        spool_id = int(spool_id_raw)
    except ValueError:
        return redirect(url_for("ams_nfc.pending_tags", error="Bitte eine Spule auswählen."))

    pending = next((item for item in _load_pending() if _normalize_uid(item.get("uid")) == normalized_uid), None)
    if pending is None:
        return redirect(url_for("ams_nfc.pending_tags", error="NFC-Tag wurde nicht gefunden."))

    spool = next((item for item in spoolman_service.fetchSpools(cached=False) if int(item.get("id", -1)) == spool_id), None)
    if spool is None:
        return redirect(url_for("ams_nfc.pending_tags", error="Spule wurde nicht gefunden."))

    extras = spool.get("extra") or {}
    spoolman_client.patchExtraTags(spool_id, extras, {"tag": json.dumps(normalized_uid)})
    spool.setdefault("extra", {})["tag"] = json.dumps(normalized_uid)
    _assign_spool_to_tray(spool, int(pending["ams_id"]), int(pending["tray_index"]))
    _remove_pending(normalized_uid)
    return redirect(url_for("ams_nfc.pending_tags", success="NFC-Tag wurde der Spule zugeordnet."))
