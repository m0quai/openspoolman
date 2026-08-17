import json
from pathlib import Path
import requests

BASE = "https://api.bambulab.com"
STATE = Path(__file__).resolve().parent / "data" / "bambu_cloud_auth.json"


def _save(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def login(account, password=None, code=None):
    body = {"account": account}
    if code:
        body["code"] = code
    elif password:
        body["password"] = password
    else:
        raise ValueError("Password or verification code required")
    r = requests.post(f"{BASE}/v1/user-service/user/login", json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("accessToken"):
        token = data["accessToken"]
        p = requests.get(f"{BASE}/v1/design-user-service/my/preference",
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        p.raise_for_status()
        pref = p.json()
        state = {"account": account, "accessToken": token, "uid": str(pref.get("uid", "")),
                 "name": pref.get("name", ""), "handle": pref.get("handle", "")}
        _save(state)
        return {"status": "connected", **state}
    return {"status": "verification_required" if data.get("loginType") == "verifyCode" else "login_incomplete",
            "account": account, "loginType": data.get("loginType", "")}


def logout():
    if STATE.exists():
        STATE.unlink()


def validate():
    state = load_state()
    token = state.get("accessToken")
    if not token:
        return False, state
    try:
        r = requests.get(f"{BASE}/v1/design-user-service/my/preference",
                         headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.ok:
            pref = r.json()
            state.update(uid=str(pref.get("uid", state.get("uid", ""))), name=pref.get("name", state.get("name", "")))
            _save(state)
            return True, state
    except requests.RequestException:
        pass
    return False, state
