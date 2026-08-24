import json
import traceback

from flask import Blueprint, jsonify, request

import mqtt_bambulab
import spoolman_client
import spoolman_service

bp = Blueprint("ams_nfc", __name__, url_prefix="/ams/nfc")


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


@bp.post("/<int:tray_index>/assign")
def assign_nfc_tray(tray_index):
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
            return jsonify({
                "success": True,
                "tray_index": tray_index,
                "ams_id": ams_id,
                "cleared": True,
            })

        spool = _find_spool_by_uid(uid)
        if not spool or spool.get("id") is None:
            return jsonify({"success": False, "error": f"No spool found for UID '{uid}'."}), 404

        spool_id = spool["id"]
        mqtt_bambulab.setActiveTray(spool_id, spool.get("extra") or {}, ams_id, tray_id)

        from app import setActiveSpool
        setActiveSpool(ams_id, tray_id, spool)

        return jsonify({
            "success": True,
            "tray_index": tray_index,
            "ams_id": ams_id,
            "uid": uid,
            "spool_id": spool_id,
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(exc)}), 500
