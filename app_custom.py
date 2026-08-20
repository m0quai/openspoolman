"""Custom OpenSpoolMan entry point; keeps local extensions outside upstream app.py."""
import os
from pathlib import Path

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
    "OPENSPOOLMAN_BASE_URL": "http://localhost:8000",
    "SPOOLMAN_BASE_URL": "http://localhost:7912",
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

# Preserve the public Spoolman URL. Before importing the original application,
# temporarily expose the Docker-internal URL as SPOOLMAN_BASE_URL. This makes
# the existing config.py build SPOOLMAN_API_URL from the internal address
# without requiring config.py to be modified or a migration script to be run.
_SPOOLMAN_PUBLIC_BASE_URL = _url_config.get(
    "SPOOLMAN_BASE_URL", _URL_DEFAULTS["SPOOLMAN_BASE_URL"]
).rstrip("/")
_SPOOLMAN_DOCKER_BASE_URL = _url_config.get(
    "SPOOLMAN_INTERNAL_BASE_URL", _SPOOLMAN_PUBLIC_BASE_URL
).rstrip("/")
_OPENSPOOLMAN_PUBLIC_BASE_URL = _url_config.get(
    "OPENSPOOLMAN_BASE_URL", _URL_DEFAULTS["OPENSPOOLMAN_BASE_URL"]
).rstrip("/")

def _running_inside_docker():
    # Docker creates /.dockerenv in normal Linux containers. The cgroup check
    # covers runtimes where that marker is absent.
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore").lower()
        return "docker" in cgroup or "containerd" in cgroup or "kubepods" in cgroup
    except Exception:
        return False

def _docker_spoolman_url():
    # Prefer the configured Docker/Compose URL only if its hostname is actually
    # resolvable from this container. This matters when OpenSpoolMan and Spoolman
    # are started by different Compose projects/networks.
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

    # Docker Desktop exposes host.docker.internal inside containers. Spoolman is
    # published on the Windows host as port 7912, so this works even when the
    # two containers do not share a Docker network.
    host_fallback = "http://host.docker.internal:7912"
    try:
        socket.getaddrinfo("host.docker.internal", None)
        return host_fallback
    except OSError:
        pass

    # Last fallback keeps the configured public URL. This is useful for native
    # Linux installations where localhost may actually host Spoolman.
    return _SPOOLMAN_PUBLIC_BASE_URL

# Native Windows debugger -> localhost:7912.
# Docker with shared network -> configured spoolman:8000.
# Docker without shared network -> host.docker.internal:7912.
_SPOOLMAN_RUNTIME_BASE_URL = (
    _docker_spoolman_url() if _running_inside_docker()
    else _SPOOLMAN_PUBLIC_BASE_URL
)

os.environ["OPENSPOOLMAN_BASE_URL"] = _OPENSPOOLMAN_PUBLIC_BASE_URL
os.environ["SPOOLMAN_BASE_URL"] = _SPOOLMAN_RUNTIME_BASE_URL

from app import app

# The original app and spoolman_client have now imported SPOOLMAN_API_URL using
# the internal address. Restore the public URL for templates/browser links.
os.environ["SPOOLMAN_BASE_URL"] = _SPOOLMAN_PUBLIC_BASE_URL

import config as _openspoolman_config
import app as _openspoolman_app_module

# config.SPOOLMAN_API_URL remains internal for code that reads it later.
_openspoolman_config.SPOOLMAN_BASE_URL = _SPOOLMAN_PUBLIC_BASE_URL
_openspoolman_config.SPOOLMAN_INTERNAL_BASE_URL = _SPOOLMAN_DOCKER_BASE_URL
_openspoolman_config.SPOOLMAN_RUNTIME_BASE_URL = _SPOOLMAN_RUNTIME_BASE_URL
_openspoolman_config.SPOOLMAN_API_URL = f"{_SPOOLMAN_RUNTIME_BASE_URL}/api/v1"

# app.py imports SPOOLMAN_BASE_URL by value for its template context processor.
# Restore that copy to the public URL, while spoolman_client keeps the already
# imported internal SPOOLMAN_API_URL.
_openspoolman_app_module.SPOOLMAN_BASE_URL = _SPOOLMAN_PUBLIC_BASE_URL


# Keep AMS rendering and refresh strictly read-only.
# Upstream _augment_tray() may clear assignments / send empty filament settings
# while merely rendering a printer state. Override that behavior here without
# modifying app.py. Explicit Fill/Clear routes remain responsible for writes.
def _readonly_augment_tray(spool_list, tray_data, ams_id, tray_id):
    _openspoolman_app_module.augmentTrayDataWithSpoolMan(
        spool_list, tray_data, ams_id, tray_id
    )

_openspoolman_app_module._augment_tray = _readonly_augment_tray


# Flask sessions are required by the Bambu verification-code flow.
# Keep this local to the running OpenSpoolMan instance. The authentication
# request itself is intentionally unchanged from the known mail-producing build.
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
from flask import redirect, request, url_for
import mqtt_bambulab

# Register the custom Bambu Cloud routes before any request handler uses them.
app.register_blueprint(bambu_cloud_bp)
@app.before_request
def open_bambu_setup_when_mqtt_is_offline():
    # On a fresh/unconfigured installation, opening the application should lead
    # directly to setup. Do not interfere with API/static/Bambu routes.
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

@app.context_processor
def inject_openspoolman_version():
    return {"openspoolman_version": _load_openspoolman_version()}




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

    # Wait for an actual NEW AMS MQTT response. Comparing the AMS JSON itself is
    # insufficient because a successful refresh can legitimately return exactly
    # the same values as before.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        time.sleep(0.10)
        if getattr(mqtt_bambulab, "LAST_AMS_CONFIG_GENERATION", 0) > before_generation:
            return redirect(url_for("home", success_message="AMS wurde aktualisiert."))

    return redirect(url_for(
        "home",
        success_message="AMS-Abfrage wurde gesendet, aber innerhalb von 3 Sekunden kam keine neue AMS-Antwort."
    ))


# ---------------------------------------------------------------------------
# AMS generic-material compatibility
#
# Keep Spoolman's material name (e.g. PLA+) unchanged, but normalize only the
# payload handed to the upstream setActiveSpool implementation.
#
# Bambu's AMS expects the base material "PLA" for PLA+ and a real Bambu
# tray_info_idx. Numeric legacy placeholders are not Bambu profile IDs.
# For non-Bambu filaments we deliberately omit setting_id; filament.py then
# supplies the established generic IDs such as GFL99 / GFU99 / GFG99.
# ---------------------------------------------------------------------------
_original_set_active_spool = _openspoolman_app_module.setActiveSpool

def _set_active_spool_bambu_compatible(ams_id, tray_id, spool_data):
    import copy

    normalized = copy.deepcopy(spool_data)
    filament = normalized.get("filament", {}) or {}
    extra = filament.setdefault("extra", {})
    vendor = ((filament.get("vendor") or {}).get("name") or "").strip().upper()
    material = str(filament.get("material") or "").strip()
    material_key = material.upper().replace(" ", "")

    # PLA+ remains PLA+ in Spoolman. Only the AMS write uses Bambu's base PLA.
    if material_key == "PLA+":
        filament["material"] = "PLA"

    # Old OpenSpoolMan fields sometimes contain Spoolman/local numeric IDs.
    # They must never be sent as Bambu tray_info_idx values.
    raw_filament_id = str(extra.get("filament_id", "") or "").strip().strip('"')
    if raw_filament_id.isdigit():
        extra["filament_id"] = ""

    # Generic/third-party AMS entries do not need a Bambu Studio preset
    # setting_id. Sending guessed values such as GFSL99 made the assignment
    # transient on the printer.
    if vendor not in {"BAMBU", "BAMBU LAB"}:
        extra["setting_id"] = ""

    return _original_set_active_spool(ams_id, tray_id, normalized)

_openspoolman_app_module.setActiveSpool = _set_active_spool_bambu_compatible



# Do not send an empty setting_id in ams_filament_setting.
# Bambu treats "field absent" differently from an explicitly empty preset id.
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
            print("[OpenSpoolMan] AMS Fill: omitted empty setting_id from MQTT payload", flush=True)
    return _original_mqtt_publish(client, message)

mqtt_bambulab.publish = _publish_without_empty_setting_id


if __name__ == "__main__":
    app.run(debug=True)
