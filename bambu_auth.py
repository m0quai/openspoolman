import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "data" / "bambu_cloud_auth.json"
CONFIG_ENV = ROOT / "config.env"
API = "https://api.bambulab.com"
WEB = "https://bambulab.com"

HEADERS = {
    "User-Agent": "bambu_network_agent/01.09.05.01",
    "X-BBL-Client-Name": "BambuStudio",
    "X-BBL-Client-Type": "slicer",
    "X-BBL-Client-Version": "02.08.02.54",
    "X-BBL-Language": "en-US",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _read_env():
    values={}
    try:
        for raw in CONFIG_ENV.read_text(encoding="utf-8").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            values[k.strip()]=v.strip()
    except Exception:
        pass
    return values

def _write_env_value(key, value):
    lines=[]
    found=False
    try:
        lines=CONFIG_ENV.read_text(encoding="utf-8").splitlines()
    except Exception:
        pass
    out=[]
    for line in lines:
        if line.strip().startswith(key+"="):
            out.append(f"{key}={value}")
            found=True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    CONFIG_ENV.write_text("\n".join(out)+"\n", encoding="utf-8")

def configured_account():
    e=_read_env()
    return e.get("BAMBU_EMAIL") or e.get("BAMBU_ACCOUNT") or ""

def configured_password():
    return _read_env().get("BAMBU_PASSWORD") or ""

def password_saved():
    return bool(configured_password())

def save_credentials(account, password=None, save_password=False):
    if account:
        _write_env_value("BAMBU_EMAIL", account)
    if save_password and password:
        _write_env_value("BAMBU_PASSWORD", password)
    elif not save_password:
        # Remove persisted password without touching other config.
        try:
            lines=CONFIG_ENV.read_text(encoding="utf-8").splitlines()
            lines=[x for x in lines if not x.strip().startswith("BAMBU_PASSWORD=")]
            CONFIG_ENV.write_text("\n".join(lines)+"\n", encoding="utf-8")
        except Exception:
            pass

def load_state():
    return _read_json(STATE)

def _profile(token):
    # Current community implementations use /my/profile; older Studio builds also
    # use design-user-service preference. Try profile first, then preference.
    hdr=dict(HEADERS)
    hdr["Authorization"]="Bearer "+token
    r=requests.get(API+"/v1/user-service/my/profile", headers=hdr, timeout=20)
    if r.status_code == 404:
        r=requests.get(API+"/v1/design-user-service/my/preference", headers=hdr, timeout=20)
    r.raise_for_status()
    return r.json()

def validate():
    state=load_state()
    token=state.get("accessToken")
    if not token:
        return False,state
    try:
        profile=_profile(token)
        state["profile"]=profile
        _write_json(STATE,state)
        return True,state
    except Exception:
        return False,state

def _persist_auth(data, account):
    token=data.get("accessToken")
    if not token:
        raise RuntimeError("Bambu hat keinen Access Token geliefert.")
    state={
        "accessToken": token,
        "refreshToken": data.get("refreshToken",""),
        "expiresIn": data.get("expiresIn"),
        "refreshExpiresIn": data.get("refreshExpiresIn"),
        "loginType": data.get("loginType",""),
        "account": account,
    }
    try:
        state["profile"]=_profile(token)
    except Exception:
        pass
    _write_json(STATE,state)
    return state

def request_email_verification_code(account):
    payload={"email": account, "type": "codeLogin"}
    r=requests.post(API+"/v1/user-service/user/sendemail/code",
                    headers=HEADERS, json=payload, timeout=30)
    # Preserve Bambu's response details without exposing credentials.
    try:
        body=r.json()
    except Exception:
        body={"text": r.text[:500]}
    if r.status_code < 200 or r.status_code >= 300:
        raise RuntimeError(f"Verification-Mail konnte nicht angefordert werden: HTTP {r.status_code}: {body}")
    return body

def login_password(account, password):
    payload={"account":account, "password":password}
    r=requests.post(API+"/v1/user-service/user/login", headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    data=r.json()
    if data.get("accessToken"):
        return {"status":"connected", "state":_persist_auth(data,account)}
    login_type=data.get("loginType") or ""
    if login_type == "verifyCode":
        mail_response=request_email_verification_code(account)
        return {"status":"verifyCode", "account":account, "mail_response":mail_response}
    if login_type == "tfa" or data.get("tfaKey"):
        return {"status":"tfa", "account":account, "tfaKey":data.get("tfaKey","")}
    msg=data.get("message") or data.get("error") or data.get("reason") or str(data)
    raise RuntimeError("Bambu-Login fehlgeschlagen: "+msg)

def login_verification_code(account, code):
    payload={"account":account, "code":code}
    r=requests.post(API+"/v1/user-service/user/login", headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    data=r.json()
    if data.get("accessToken"):
        return {"status":"connected", "state":_persist_auth(data,account)}
    if data.get("loginType") == "tfa" or data.get("tfaKey"):
        return {"status":"tfa", "account":account, "tfaKey":data.get("tfaKey","")}
    msg=data.get("message") or data.get("error") or str(data)
    raise RuntimeError("Verification fehlgeschlagen: "+msg)

def login_tfa(tfa_key, code, account=""):
    # Community auth implementations use Bambu's web TFA endpoint.
    payload={"tfaKey":tfa_key, "code":code}
    r=requests.post(WEB+"/api/sign-in/tfa", headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    data=r.json()
    if data.get("accessToken"):
        return {"status":"connected", "state":_persist_auth(data,account)}
    msg=data.get("message") or data.get("error") or str(data)
    raise RuntimeError("TFA-Anmeldung fehlgeschlagen: "+msg)

def logout():
    STATE.unlink(missing_ok=True)

def get_devices():
    ok,state=validate()
    if not ok:
        raise RuntimeError("Bambu Cloud ist nicht angemeldet.")
    hdr=dict(HEADERS)
    hdr["Authorization"]="Bearer "+state["accessToken"]
    r=requests.get(API+"/v1/iot-service/api/user/bind", headers=hdr, timeout=30)
    r.raise_for_status()
    payload=r.json()
    devices=payload.get("devices") or []
    result=[]
    for d in devices:
        result.append({
            "dev_id": d.get("dev_id") or d.get("devId") or "",
            "name": d.get("name") or d.get("dev_name") or "",
            "online": d.get("online", d.get("dev_online")),
            "print_status": d.get("print_status",""),
            "dev_model_name": d.get("dev_model_name",""),
            "dev_product_name": d.get("dev_product_name",""),
            "dev_access_code": d.get("dev_access_code") or d.get("access_code") or "",
        })
    return result
