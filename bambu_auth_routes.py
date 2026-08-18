import os
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for, session, make_response

import bambu_auth
import config as app_config
import mqtt_bambulab

bp = Blueprint("bambu_cloud", __name__, url_prefix="/bambu-cloud")
ROOT = Path(__file__).resolve().parent
CONFIG_ENV = ROOT / "config.env"


@bp.app_context_processor
def mqtt_menu_context():
    try:
        return {"mqtt_connected": bool(mqtt_bambulab.isMqttClientConnected())}
    except Exception:
        return {"mqtt_connected": False}


def _write_config_env(values):
    """Update only supplied keys and preserve the rest of config.env."""
    lines = CONFIG_ENV.read_text(encoding="utf-8").splitlines() if CONFIG_ENV.exists() else []
    remaining = dict(values)
    output = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    for key, value in remaining.items():
        output.append(f"{key}={value}")
    CONFIG_ENV.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _apply_printer(device, printer_ip):
    dev_id = (device.get("dev_id") or "").strip().upper()
    access_code = (device.get("dev_access_code") or "").strip()
    name = (device.get("name") or device.get("dev_product_name") or dev_id).strip()
    printer_ip = (printer_ip or "").strip()
    if not dev_id or not access_code:
        raise RuntimeError("Der ausgewaehlte Drucker enthaelt keine Seriennummer oder keinen dev_access_code.")
    if not printer_ip:
        raise RuntimeError("Bitte die lokale IP-Adresse des Druckers eintragen.")

    values = {
        "PRINTER_ID": dev_id,
        "PRINTER_ACCESS_CODE": access_code,
        "PRINTER_IP": printer_ip,
        "PRINTER_NAME": name,
    }
    _write_config_env(values)

    # Apply immediately to the running debugger/server process as well. The file
    # remains the source of truth for the next real application restart.
    for key, value in values.items():
        os.environ[key] = value
    app_config.PRINTER_ID = dev_id
    app_config.PRINTER_CODE = access_code
    app_config.PRINTER_IP = printer_ip
    app_config.PRINTER_NAME = name
    return mqtt_bambulab.reconfigure_printer(dev_id, access_code, printer_ip, wait_seconds=12)


def _page(**extra):
    cloud_ok, cloud_state = bambu_auth.validate()
    config = {
        "printer_name": app_config.PRINTER_NAME,
        "printer_ip": app_config.PRINTER_IP,
        "printer_id": app_config.PRINTER_ID,
        "port": 8883,
        "username": "bblp",
        "access_code_present": bool(app_config.PRINTER_CODE),
        "access_code_length": len(app_config.PRINTER_CODE or ""),
        "source": "config.env",
    }
    args = dict(
        config=config,
        connected=mqtt_bambulab.isMqttClientConnected(),
        cloud_connected=cloud_ok,
        cloud_state=cloud_state,
        devices=None,
        configured_account=bambu_auth.configured_account(),
        password_saved=bambu_auth.password_saved(),
        auth_step=session.get("bambu_auth_step", "password"),
        auth_account=session.get("bambu_auth_account") or bambu_auth.configured_account(),
    )
    args.update(extra)
    return render_template("bambu_auth.html", **args)


@bp.route("/", methods=["GET"])
def index():
    cloud_ok, _ = bambu_auth.validate()
    if cloud_ok:
        try:
            return _page(devices=bambu_auth.get_devices())
        except Exception as exc:
            flash("Druckerliste konnte nicht geladen werden: " + str(exc), "danger")
    return _page()


@bp.route("/login", methods=["POST"])
def login():
    account=(request.form.get("account") or bambu_auth.configured_account() or "").strip()
    password=request.form.get("password") or bambu_auth.configured_password()
    save_password=request.form.get("save_password") == "1"

    if not account:
        flash("Bitte Bambu-E-Mail-Adresse eintragen.", "danger")
        return redirect(url_for("bambu_cloud.index"))
    if not password:
        flash("Bitte Bambu-Passwort eingeben.", "danger")
        return redirect(url_for("bambu_cloud.index"))

    try:
        result=bambu_auth.login_password(account,password)
        bambu_auth.save_credentials(account,password,save_password)
        if result["status"] == "connected":
            session.pop("bambu_auth_step",None)
            session.pop("bambu_auth_account",None)
            session.pop("bambu_tfa_key",None)
            flash("Bambu Cloud erfolgreich angemeldet.", "success")
        elif result["status"] == "verifyCode":
            session["bambu_auth_step"]="verifyCode"
            session["bambu_auth_account"]=account
            flash("Bambu verlangt einen Verification Code. Die Verification-Mail wurde jetzt explizit bei Bambu angefordert. Bitte den Code aus der E-Mail eingeben.", "warning")
        elif result["status"] == "tfa":
            session["bambu_auth_step"]="tfa"
            session["bambu_auth_account"]=account
            session["bambu_tfa_key"]=result.get("tfaKey","")
            flash("Bambu verlangt einen MFA/TFA-Code.", "warning")
    except Exception as exc:
        flash(str(exc), "danger")
    return redirect(url_for("bambu_cloud.index"))


@bp.route("/verify", methods=["POST"])
def verify():
    step=session.get("bambu_auth_step")
    account=session.get("bambu_auth_account") or bambu_auth.configured_account()
    code=(request.form.get("code") or "").strip()
    if not code:
        flash("Bitte den Code eingeben.", "danger")
        return redirect(url_for("bambu_cloud.index"))
    try:
        if step == "tfa":
            result=bambu_auth.login_tfa(session.get("bambu_tfa_key",""), code, account)
        else:
            result=bambu_auth.login_verification_code(account, code)

        if result["status"] == "connected":
            session.pop("bambu_auth_step",None)
            session.pop("bambu_auth_account",None)
            session.pop("bambu_tfa_key",None)
            flash("Bambu Cloud erfolgreich angemeldet.", "success")
        elif result["status"] == "tfa":
            session["bambu_auth_step"]="tfa"
            session["bambu_tfa_key"]=result.get("tfaKey","")
            flash("Zusätzlich wird ein MFA/TFA-Code benötigt.", "warning")
    except Exception as exc:
        flash(str(exc), "danger")
    return redirect(url_for("bambu_cloud.index"))


@bp.route("/logout", methods=["POST"])
def logout():
    bambu_auth.logout()
    session.pop("bambu_auth_step",None)
    session.pop("bambu_auth_account",None)
    session.pop("bambu_tfa_key",None)
    flash("Bambu Cloud abgemeldet.", "success")
    return redirect(url_for("bambu_cloud.index"))


@bp.route("/select-device", methods=["POST"])
def select_device():
    dev_id = (request.form.get("dev_id") or "").strip()
    printer_ip = (request.form.get("printer_ip") or "").strip()
    try:
        devices = bambu_auth.get_devices()
        device = next((d for d in devices if d.get("dev_id") == dev_id), None)
        if not device:
            raise RuntimeError("Der ausgewaehlte Drucker wurde in der Bambu-Cloud-Liste nicht gefunden.")
        connected = _apply_printer(device, printer_ip)
        if connected:
            flash(f"Drucker {device.get('name') or dev_id} wurde übernommen und MQTT neu verbunden.", "success")
            # Leave setup immediately after the new configuration is live.
            return redirect(url_for("home"))
        flash("Drucker wurde in config.env übernommen, aber MQTT konnte innerhalb von 12 Sekunden nicht verbunden werden.", "danger")
    except Exception as exc:
        flash("Drucker konnte nicht übernommen werden: " + str(exc), "danger")
    return redirect(url_for("bambu_cloud.index"))
