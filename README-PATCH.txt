OpenSpoolMan Bambu reliable authentication

Research conclusion:
Bambu Studio's normal email/password sign-in page is an embedded WebView protocol,
not a generic OAuth redirect flow. The page sends native script messages
(user_login / user_ticket_login) to Bambu Studio. It asks the host for
get_localhost_url only for third-party/system-browser login. Therefore opening the
normal sign-in page in Chrome/Edge cannot hand the completed email login back to
OpenSpoolMan; an already-authenticated browser simply remains on bambulab.com.

This package uses the stable cloud API authentication path instead:
- Existing bambu_cloud_auth.json token is validated first and reused.
- Email is prefilled from config.env.
- Password is NEVER rendered into HTML.
- If BAMBU_PASSWORD exists and the password field is blank, the saved password is
  used server-side.
- Optional checkbox controls whether BAMBU_PASSWORD remains stored.
- POST /v1/user-service/user/login handles password and verification-code login.
- MFA/TFA is handled through the Bambu TFA endpoint when requested.
- Successful access/refresh tokens persist in data/bambu_cloud_auth.json.
- Bound printers are loaded automatically.
- dev_access_code + selected printer/IP are written to config.env and MQTT is
  reconfigured immediately.
- Browser callback listener, popup diagnostics, pending JSON, trace JSON and MQTT
  runtime diagnostic JSON are removed.

KNOWN MAIL FLOW + SESSION-ONLY FIX
==================================
Basis ist exakt OpenSpoolMan-bambu-reliable-auth-blueprint-fix.zip:
In diesem Stand wurde der Bambu-Login erfolgreich bis loginType=verifyCode
ausgeführt und die Verification-Mail tatsächlich versendet.

Absichtlich NICHT geändert:
- bambu_auth.py
- bambu_auth_routes.py
- Bambu Login Endpoint
- Request Payload
- Request Header
- verifyCode-Logik
- Passwort-/Mail-Logik
- Templates

Einzige funktionale Änderung:
- app_custom.py initialisiert vor Nutzung der Bambu-Routen einen Flask SECRET_KEY.
- FLASK_SECRET_KEY wird verwendet, falls gesetzt.
- Sonst wird einmalig data/.flask_secret_key erzeugt und wiederverwendet.

Damit bleibt der nachweislich Mail-auslösende Bambu-Request unverändert und nur
der danach aufgetretene Fehler 'session is unavailable because no secret key was set'
wird behoben.

EXPLICIT EMAIL CODE REQUEST
===========================
Research correction:
loginType=verifyCode means a code is required, but it is not reliable proof that
the password-login response itself caused a fresh email to be sent.

After loginType=verifyCode this build explicitly calls:
POST https://api.bambulab.com/v1/user-service/user/sendemail/code
JSON: {"email": "<account>", "type": "codeLogin"}

This endpoint/payload is independently documented by Bambu API research clients.
If the endpoint returns non-2xx, the UI shows the HTTP error instead of silently
claiming that an email was sent.

The known password-login request and the Flask session-only fix remain unchanged.

SINGLE PRINTER UI CLEANUP
- If the Bambu account returns exactly one printer and its dev_id is already the
  configured PRINTER_ID, the printer row is read-only.
- The "Drucker übernehmen" button, POST form and editable IP field are omitted.
- If multiple printers exist, or the single printer is not yet configured,
  selection/takeover remains available.

VERSION FOOTER
- Current version is read dynamically from __version__.py.
- Footer shows `v<version> @m0quai` immediately before the existing GitHub icon.
- No version number is hard-coded.

AUTOMATIC SPOOLMAN REQUIRED FIELDS
- Normal OpenSpoolMan startup checks the required Spoolman extra fields.
- Missing fields are created automatically.
- Existing fields are left untouched.
- Repeated starts are idempotent.
- If Spoolman is temporarily unavailable, OpenSpoolMan still starts.
- Uses the already selected runtime Spoolman URL (host or Docker).
- No PowerShell/setup script is required.

REQUIRED FIELDS - SERVER START FIX
- Field initialization now starts automatically with the OpenSpoolMan server.
- It runs asynchronously and does not block Flask/Waitress startup.
- If Spoolman is not ready yet (common with Docker Compose startup), it retries
  every 5 seconds until the fields can be verified/created.
- The actual Spoolman API URL is printed in the startup log.
- No page visit, button, PowerShell script, or manual action is required.

REQUIRED FIELDS RUNTIME URL FIX
- Fixed startup worker using the restored public SPOOLMAN_BASE_URL (localhost:7912)
  from inside Docker.
- app_custom.py now exports the actually selected server-to-server address as
  SPOOLMAN_RUNTIME_BASE_URL.
- spoolman_required_fields.py uses that runtime URL first.
- Therefore:
    native Windows -> localhost:7912
    Docker shared network -> spoolman:8000
    Docker without shared network -> host.docker.internal:7912
- Existing retry-on-start behavior remains unchanged.

SPOOLMAN EXTRA FIELD HTTP 422 FIX
- Connectivity is now confirmed: HTTP 422 came from Spoolman itself.
- Corrected creation to POST /api/v1/field/{entity} with `key` in JSON body.
- Removed the guessed default_value from nozzle_temperature.
- Choice values are sent as a JSON array rather than a JSON-encoded string.
- HTTP failures now include Spoolman's response body in the OpenSpoolMan log.
- Startup retry behavior remains unchanged.

SPOOLMAN EXTRA FIELD HTTP 405 FIX
- 405 proves POST /api/v1/field/{entity} is not a create endpoint in this Spoolman.
- Restored the documented/in-use create route:
  POST /api/v1/field/{entity}/{field_key}
- Field key is therefore no longer sent in the JSON body.
- Added required JSON-encoded default_value (null) to the create payload.
- Existing runtime URL selection and startup retries are retained.
- HTTP errors continue to include Spoolman's response body.
