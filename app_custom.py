"""Custom OpenSpoolMan entry point; keeps local extensions outside upstream app.py."""
from app import app

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

if __name__ == "__main__":
    app.run(debug=True)
