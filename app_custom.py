"""Custom OpenSpoolMan entry point; keeps local extensions outside upstream app.py."""
import os
import logging
from pathlib import Path

# Waitress' startup banner is informational and duplicates the application
# startup log; retain warnings/errors while keeping normal container logs tidy.
logging.getLogger("waitress").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# OpenSpoolMan / Spoolman URL split
#
# Public URLs are for links opened by the browser/host.
# SPOOLMAN_INTERNAL_BASE_URL is only for OpenSpoolMan -> Spoolman API traffic.
#
# Missing values are written automatically to config.env. Existing values are
# never overwritten.
# ---------------------------------------------------------------------------
_CONFIG_ENV = Path(__file__).resolve().parent / "config.env"
_URL_DEFAULTS = {
    "HOST_IP": "localhost",
    "OPENSPOOLMAN_BASE_PORT": "8000",
    "SPOOLMAN_BASE_PORT": "7912",
    "SPOOLMAN_INTERNAL_BASE_URL": "http://spoolman:8000",
}

def _read_config_env(path):
    values = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return values

def _ensure_url_config():
    if not _CONFIG_ENV.exists():
        _CONFIG_ENV.write_text("", encoding="utf-8")

    values = _read_config_env(_CONFIG_ENV)
    missing = [(k, v) for k, v in _URL_DEFAULTS.items() if not values.get(k)]

    if missing:
        current = _CONFIG_ENV.read_text(encoding="utf-8")
        with _CONFIG_ENV.open("a", encoding="utf-8") as f:
            if current and not current.endswith("\n"):
                f.write("\n")
            f.write("\n# OpenSpoolMan public/internal URLs (automatically added)\n")
            for key, value in missing:
                f.write(f"{key}={value}\n")
                values[key] = value

    return values

_url_config = _ensure_url_config()

_host = _url_config.get("HOST_IP", _URL_DEFAULTS["HOST_IP"])
_openspoolman_port = _url_config.get("OPENSPOOLMAN_BASE_PORT", _URL_DEFAULTS["OPENSPOOLMAN_BASE_PORT"])
_spoolman_port = _url_config.get("SPOOLMAN_BASE_PORT", _URL_DEFAULTS["SPOOLMAN_BASE_PORT"])
_SPOOLMAN_PUBLIC_BASE_URL = f"http://{_host}:{_spoolman_port}".rstrip("/")
_SPOOLMAN_DOCKER_BASE_URL = _url_config.get(
    "SPOOLMAN_INTERNAL_BASE_URL", _SPOOLMAN_PUBLIC_BASE_URL
).rstrip("/")
_OPENSPOOLMAN_PUBLIC_BASE_URL = f"http://{_host}:{_openspoolman_port}".rstrip("/")

def _running_inside_docker():
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore").lower()
        return "docker" in cgroup or "containerd" in cgroup or "kubepods" in cgroup
    except Exception:
        return False

def _docker_spoolman_url():
    import socket
    from urllib.parse import urlparse

    configured = _SPOOLMAN_DOCKER_BASE_URL
    try:
        host = urlparse(configured).hostname
        if host:
            socket.getaddrinfo(host, None)
            return configured
    except OSError:
        pass

    host_fallback = "http://host.docker.internal:7912"
    try:
        socket.getaddrinfo("host.docker.internal", None)
        return host_fallback
    except OSError:
        pass

    return _SPOOLMAN_PUBLIC_BASE_URL

_SPOOLMAN_RUNTIME_BASE_URL = (
    _docker_spoolman_url() if _running_inside_docker()
    else _SPOOLMAN_PUBLIC_BASE_URL
)

os.environ["OPENSPOOLMAN_BASE_URL"] = _OPENSPOOLMAN_PUBLIC_BASE_URL
os.environ["SPOOLMAN_BASE_URL"] = _SPOOLMAN_RUNTIME_BASE_URL

from app import app

os.environ["SPOOLMAN_BASE_URL"] = _SPOOLMAN_PUBLIC_BASE_URL

import config as _openspoolman_config
import app as _openspoolman_app_module

_openspoolman_config.SPOOLMAN_BASE_URL = _SPOOLMAN_PUBLIC_BASE_URL
_openspoolman_config.SPOOLMAN_INTERNAL_BASE_URL = _SPOOLMAN_DOCKER_BASE_URL
_openspoolman_config.SPOOLMAN_RUNTIME_BASE_URL = _SPOOLMAN_RUNTIME_BASE_URL
_openspoolman_config.SPOOLMAN_API_URL = f"{_SPOOLMAN_RUNTIME_BASE_URL}/api/v1"
_openspoolman_app_module.SPOOLMAN_BASE_URL = _SPOOLMAN_PUBLIC_BASE_URL


def _readonly_augment_tray(spool_list, tray_data, ams_id, tray_id):
    _openspoolman_app_module.augmentTrayDataWithSpoolMan(
        spool_list, tray_data, ams_id, tray_id
    )

_openspoolman_app_module._augment_tray = _readonly_augment_tray


if not app.secret_key:
    import os
    import secrets
    from pathlib import Path

    _secret_file = Path(__file__).resolve().parent / "data" / ".flask_secret_key"
    _secret_file.parent.mkdir(parents=True, exist_ok=True)

    _configured_secret = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if _configured_secret:
        app.secret_key = _configured_secret
    else:
        try:
            app.secret_key = _secret_file.read_text(encoding="utf-8").strip()
        except Exception:
            app.secret_key = ""

        if not app.secret_key:
            app.secret_key = secrets.token_urlsafe(48)
            _secret_file.write_text(app.secret_key, encoding="utf-8")

from bambu_auth_routes import bp as bambu_cloud_bp
from nfc_routes import bp as ams_nfc_bp
from flask import jsonify, redirect, request, url_for, render_template, send_from_directory
import mqtt_bambulab
from __version__ import __build_number__, __version__
import tools_3mf as _tools_3mf
import filament_usage_tracker as _filament_usage_tracker
from logger import log as _log

_build_number_file = Path(__file__).resolve().parent / "build_number"
_runtime_build_number = os.environ.get("BUILD_NUMBER", "").strip()
if not _runtime_build_number or _runtime_build_number == "dev":
    try:
        _runtime_build_number = _build_number_file.read_text(encoding="utf-8").strip()
    except OSError:
        _runtime_build_number = ""
if not _runtime_build_number:
    _runtime_build_number = __build_number__
_log(f"OpenSpoolMan version {__version__} (Build {_runtime_build_number}) starting")

app.register_blueprint(bambu_cloud_bp)
app.register_blueprint(ams_nfc_bp)


@app.get("/print-images/<path:filename>")
def print_image(filename):
    """Serve print thumbnails from the persistent runtime location."""
    image_dir = os.path.join(app.root_path, "static", "prints")
    image_path = os.path.join(image_dir, filename)
    if not os.path.isfile(image_path):
        _log(f"[print-image] missing filename={filename!r} path={image_path!r}")
    return send_from_directory(image_dir, filename)


# Make the human-readable AMS console output match the values shown in the UI.
# Bambu's `humidity` field is a 1..5 level, not a percentage. If humidity_raw
# is available, show that as percent and retain the level as supplemental info.
# `remain == -1` means unknown, and an all-zero tray UUID is not a real UID.
_original_mqtt_log = mqtt_bambulab.log


def _format_ams_console_log(*args, **kwargs):
    import re

    if not args:
        return _original_mqtt_log(*args, **kwargs)

    text = str(args[0])
    ams_match = re.match(r"^AMS \[([A-Z])\] \(hum: ([^,]+), temp: (.+)\)$", text)
    if ams_match:
        ams_letter = ams_match.group(1)
        ams_id = ord(ams_letter) - ord("A")
        for ams in (getattr(mqtt_bambulab, "LAST_AMS_CONFIG", {}) or {}).get("ams", []):
            try:
                same_ams = int(ams.get("id")) == ams_id
            except (TypeError, ValueError):
                same_ams = False
            if not same_ams:
                continue

            level = ams.get("humidity")
            raw = ams.get("humidity_raw")
            temp = ams.get("temp")
            if raw not in (None, "", 0, "0"):
                return _original_mqtt_log(
                    f"AMS [{ams_letter}] (hum: {raw}%, level: {level}, temp: {temp}ºC)",
                    *args[1:],
                    **kwargs,
                )
            return _original_mqtt_log(
                f"AMS [{ams_letter}] (humidity level: {level}, temp: {temp}ºC)",
                *args[1:],
                **kwargs,
            )

    if text.lstrip().startswith("- [A"):
        text = re.sub(r"\s+\(-0?1%\)", "", text)
        text = re.sub(r"\s+\[\[\s*0{32}\s*\]\]", "", text)

    return _original_mqtt_log(text, *args[1:], **kwargs)


mqtt_bambulab.log = _format_ams_console_log


# Bambu's FTPS server can be very slow while a print is being prepared. A hard
# 30-second transfer timeout aborts valid multi-megabyte 3MF downloads halfway
# through. Keep the short connection timeout, but allow the actual transfer up
# to three minutes.
_original_setup_pycurl_connection = _tools_3mf.setupPycurlConnection


def _setup_pycurl_connection_for_large_3mf(ftp_user, ftp_pass):
    connection = _original_setup_pycurl_connection(ftp_user, ftp_pass)
    try:
        connection.setopt(connection.CONNECTTIMEOUT, 5)
        connection.setopt(connection.TIMEOUT, 180)
    except Exception:
        pass
    return connection


_tools_3mf.setupPycurlConnection = _setup_pycurl_connection_for_large_3mf

_original_download3mf_from_ftp = _tools_3mf.download3mfFromFTP


def _download3mf_with_unique_suffix_fallback(filename, dest_file):
    """Resolve printer-side filename prefixes without guessing between matches.

    Bambu .bbl files may reference /sdcard/Kerstin.gcode.3mf while FTPS exposes
    the same job as /ItsLitho_Kerstin.gcode.3mf. Try the normal resolver first.
    If that fails, inspect the FTPS root. An exact filename wins over suffix
    variants; otherwise a suffix match is accepted only when it is unique.
    """
    try:
        return _original_download3mf_from_ftp(filename, dest_file)
    except Exception as original_error:
        expected_name = os.path.basename(str(filename or "").strip())
        if not expected_name.lower().endswith(".3mf"):
            raise

        try:
            root_names = _tools_3mf._ftp_read("/", directory=True).decode(
                "utf-8", errors="replace"
            ).splitlines()
        except Exception as list_error:
            _log(
                f"[3MF] FTPS-Root konnte fuer Suffix-Fallback nicht gelesen werden: {list_error}"
            )
            raise original_error

        root_names = [name.strip() for name in root_names if name.strip()]
        expected_lower = expected_name.lower()

        exact_matches = [
            name for name in root_names
            if name.lower() == expected_lower and name.lower().endswith(".3mf")
        ]
        if len(exact_matches) == 1:
            resolved_path = "/" + exact_matches[0]
            _log(
                f"[3MF] Exakter FTPS-Root-Treffer fuer {expected_name!r}: {resolved_path}; erneuter Download."
            )
            return _original_download3mf_from_ftp(resolved_path, dest_file)

        matches = [
            name
            for name in root_names
            if name.lower().endswith(expected_lower)
            and name.lower().endswith(".3mf")
        ]

        if len(matches) == 1:
            resolved_path = "/" + matches[0]
            _log(
                f"[3MF] Eindeutiger FTPS-Suffix-Treffer fuer {expected_name!r}: {resolved_path}"
            )
            return _original_download3mf_from_ftp(resolved_path, dest_file)

        if len(matches) > 1:
            _log(
                f"[3MF] Suffix-Fallback mehrdeutig fuer {expected_name!r}: {matches}. Keine Datei gewaehlt."
            )
        else:
            _log(
                f"[3MF] Kein FTPS-Suffix-Treffer fuer {expected_name!r} im Root-Verzeichnis."
            )
        raise original_error


_tools_3mf.download3mfFromFTP = _download3mf_with_unique_suffix_fallback
_filament_usage_tracker.download3mfFromFTP = _download3mf_with_unique_suffix_fallback

_original_download3mf_from_cloud = _tools_3mf.download3mfFromCloud


def _download3mf_from_cloud_with_timeout(url, dest_file):
    """Download cloud 3MF files with bounded connect and transfer waits."""
    _log("Downloading 3MF file from cloud...")
    response = _tools_3mf.requests.get(url, timeout=(5, 180))
    response.raise_for_status()
    dest_file.write(response.content)


_tools_3mf.download3mfFromCloud = _download3mf_from_cloud_with_timeout
_filament_usage_tracker.download3mfFromCloud = _download3mf_from_cloud_with_timeout

_original_get_metadata_from_3mf = _tools_3mf.getMetaDataFrom3mf
_METADATA_RETRY_DELAYS = (2, 5)
_METADATA_RETRY_TIMEOUT_SECONDS = 240


def _metadata_source_with_filename(source):
    """Replace Bambu's pathless FTP URL with its accompanying 3MF filename."""
    from urllib.parse import urlparse

    parsed = urlparse(str(source or ""))
    if parsed.scheme not in ("ftp", "ftps") or parsed.path.strip("/"):
        return source

    print_state = getattr(mqtt_bambulab, "PRINTER_STATE", {}).get("print", {}) or {}
    for key in ("file", "gcode_file"):
        candidate = str(print_state.get(key) or "").strip()
        if candidate.lower().endswith(".3mf"):
            _log(f"[3MF] Pfadlose FTP-URL wird ueber {key}={candidate!r} aufgeloest.")
            return candidate
    return source


def _metadata_is_complete(metadata):
    if not isinstance(metadata, dict):
        return False
    required_values = (
        metadata.get("file"),
        metadata.get("model_path"),
        metadata.get("plateID"),
    )
    return bool(
        all(required_values)
        and metadata.get("image") is not None
        and isinstance(metadata.get("filaments"), dict)
        and metadata.get("filaments")
    )


def _get_metadata_from_3mf_with_retry(source):
    """Load complete print metadata with bounded retries for transient failures."""
    import time

    source = _metadata_source_with_filename(source)
    deadline = time.monotonic() + _METADATA_RETRY_TIMEOUT_SECONDS
    attempts = len(_METADATA_RETRY_DELAYS) + 1
    last_metadata = {}

    for attempt in range(1, attempts + 1):
        last_metadata = _original_get_metadata_from_3mf(source) or {}
        if _metadata_is_complete(last_metadata):
            if attempt > 1:
                _log(f"[3MF] Metadaten nach Versuch {attempt}/{attempts} vollstaendig geladen.")
            return last_metadata

        if attempt >= attempts:
            break

        delay = _METADATA_RETRY_DELAYS[attempt - 1]
        if time.monotonic() + delay >= deadline:
            _log("[3MF] Metadaten-Retry wegen erreichtem Gesamt-Timeout beendet.")
            break

        _log(
            f"[3MF] Metadaten nach Versuch {attempt}/{attempts} unvollstaendig; "
            f"neuer Versuch in {delay} Sekunden."
        )
        time.sleep(delay)

    _log(
        f"[3MF] Metadaten nach {attempt} Versuch(en) innerhalb von "
        f"{_METADATA_RETRY_TIMEOUT_SECONDS} Sekunden nicht vollstaendig."
    )
    return last_metadata


_tools_3mf.getMetaDataFrom3mf = _get_metadata_from_3mf_with_retry
mqtt_bambulab.getMetaDataFrom3mf = _get_metadata_from_3mf_with_retry


@app.before_request
def open_bambu_setup_when_mqtt_is_offline():
    if request.endpoint == "home" and not mqtt_bambulab.isMqttClientConnected():
        return redirect(url_for("bambu_cloud.index"))


def _load_openspoolman_version():
    from pathlib import Path
    import re
    version_file = Path(__file__).resolve().parent / "__version__.py"
    try:
        text = version_file.read_text(encoding="utf-8")
        match = re.search(r'^\s*__version__\s*=\s*["\x27]([^"\x27]+)["\x27]', text, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "unknown"


def _printer_temperature_status():
    print_state = getattr(mqtt_bambulab, "PRINTER_STATE", {}).get("print", {}) or {}
    return {
        "hotend": print_state.get("nozzle_temper"),
        "hotend_target": print_state.get("nozzle_target_temper"),
        "bed": print_state.get("bed_temper"),
        "bed_target": print_state.get("bed_target_temper"),
    }


@app.context_processor
def inject_openspoolman_version():
    return {
        "openspoolman_version": _load_openspoolman_version(),
        "printer_temperatures": _printer_temperature_status(),
    }


@app.get("/ams/state-generation")
def ams_state_generation():
    temperatures = _printer_temperature_status()
    return jsonify({
        "generation": getattr(mqtt_bambulab, "LAST_AMS_CONFIG_GENERATION", 0),
        "hotend": temperatures.get("hotend"),
        "hotend_target": temperatures.get("hotend_target"),
        "bed": temperatures.get("bed"),
        "bed_target": temperatures.get("bed_target"),
    })


@app.post("/refresh-ams")
def refresh_ams():
    """Read a fresh AMS state without writing filament settings to the printer."""
    import time
    import mqtt_bambulab
    from messages import PUSH_ALL

    if not mqtt_bambulab.isMqttClientConnected():
        return redirect(url_for(
            "home",
            success_message="AMS konnte nicht aktualisiert werden: MQTT ist nicht verbunden."
        ))

    before_generation = getattr(mqtt_bambulab, "LAST_AMS_CONFIG_GENERATION", 0)

    if not mqtt_bambulab.publish(mqtt_bambulab.getMqttClient(), PUSH_ALL):
        return redirect(url_for(
            "home",
            success_message="AMS-Abfrage konnte nicht gesendet werden."
        ))

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        time.sleep(0.10)
        if getattr(mqtt_bambulab, "LAST_AMS_CONFIG_GENERATION", 0) > before_generation:
            return redirect(url_for("home", success_message="AMS wurde aktualisiert."))

    return redirect(url_for(
        "home",
        success_message="AMS-Abfrage wurde gesendet, aber innerhalb von 3 Sekunden kam keine neue AMS-Antwort."
    ))


def _custom_tray_clear():
    import traceback
    import spoolman_service

    ams_id = request.form.get("ams")
    tray_id = request.form.get("tray")

    if ams_id is None or tray_id is None:
        return render_template("error.html", exception="Missing AMS ID or Tray ID.")

    if getattr(_openspoolman_app_module, "READ_ONLY_MODE", False):
        return render_template(
            "error.html",
            exception="Live read-only mode: clearing tray assignments is disabled.",
        )

    try:
        if not mqtt_bambulab.isMqttClientConnected():
            return render_template(
                "error.html",
                exception="MQTT is disconnected. The tray was not cleared on the printer.",
            )

        if not mqtt_bambulab.clear_ams_tray_assignment(ams_id, tray_id):
            return render_template(
                "error.html",
                exception="Could not send the AMS clear command to the printer.",
            )

        spoolman_service.clear_active_spool_for_tray(ams_id, tray_id)
        return redirect(
            url_for(
                "home",
                success_message=(
                    f"Tray cleared in OpenSpoolMan and on printer for AMS {ams_id}, "
                    f"Tray {int(tray_id) + 1}."
                ),
            )
        )
    except Exception as exc:
        traceback.print_exc()
        return render_template("error.html", exception=str(exc))

app.view_functions["tray_clear"] = _custom_tray_clear


_original_set_active_spool = _openspoolman_app_module.setActiveSpool

def _set_active_spool_bambu_compatible(ams_id, tray_id, spool_data):
    import copy

    normalized = copy.deepcopy(spool_data)
    filament = normalized.get("filament", {}) or {}
    extra = filament.setdefault("extra", {})
    vendor = ((filament.get("vendor") or {}).get("name") or "").strip().upper()
    material = str(filament.get("material") or "").strip()
    material_key = material.upper().replace(" ", "")

    if material_key == "PLA+":
        filament["material"] = "PLA"

    raw_filament_id = str(extra.get("filament_id", "") or "").strip().strip('"')
    if raw_filament_id.isdigit():
        extra["filament_id"] = ""

    if vendor not in {"BAMBU", "BAMBU LAB"}:
        extra["setting_id"] = ""

    return _original_set_active_spool(ams_id, tray_id, normalized)

_openspoolman_app_module.setActiveSpool = _set_active_spool_bambu_compatible


_original_mqtt_publish = mqtt_bambulab.publish

def _publish_without_empty_setting_id(client, message):
    if isinstance(message, dict):
        print_data = message.get("print")
        if (
            isinstance(print_data, dict)
            and print_data.get("command") == "ams_filament_setting"
            and not print_data.get("setting_id")
        ):
            import copy
            message = copy.deepcopy(message)
            message["print"].pop("setting_id", None)
    return _original_mqtt_publish(client, message)

mqtt_bambulab.publish = _publish_without_empty_setting_id


if __name__ == "__main__":
    app.run(debug=True)
