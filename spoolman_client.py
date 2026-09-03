import requests
from config import SPOOLMAN_API_URL, SPOOL_SORTING
import json
from logger import application_log_file, append_to_rotating_file

SPOOLMAN_LOG_FILE = application_log_file("spoolman.log")


def _log_spoolman_change(action, spool_id=None, payload=None, status=None):
  parts = [action]

  if spool_id is not None:
    parts.append(f"spool_id={spool_id}")

  if status is not None:
    parts.append(f"status={status}")

  if payload is not None:
    try:
      payload_str = json.dumps(payload)
    except TypeError:
      payload_str = str(payload)
    parts.append(f"payload={payload_str}")

  try:
    append_to_rotating_file(SPOOLMAN_LOG_FILE, " | ".join(parts))
  except Exception:
    pass

def patchExtraTags(spool_id, old_extras, new_extras):
  for key, value in new_extras.items():
    old_extras[key] = value

  resp = requests.patch(f"{SPOOLMAN_API_URL}/spool/{spool_id}", json={
    "extra": old_extras
  })
  _log_spoolman_change(
    "patch_extra_tags",
    spool_id=spool_id,
    payload={"extra": old_extras},
    status=resp.status_code,
  )
  #print(resp.text)
  #print(resp.status_code)


def getSpoolById(spool_id):
  response = requests.get(f"{SPOOLMAN_API_URL}/spool/{spool_id}")
  #print(response.status_code)
  #print(response.text)
  return response.json()

def patchFilamentExtra(filament_id, old_extra, new_values):
  """Persist Bambu profile identifiers on the filament record."""
  extra = dict(old_extra or {})
  extra.update({key: json.dumps(str(value), ensure_ascii=False) for key, value in new_values.items() if value})
  response = requests.patch(f"{SPOOLMAN_API_URL}/filament/{filament_id}", json={"extra": extra})
  if response.status_code >= 400:
    raise RuntimeError(f"Spoolman-Filamentupdate fehlgeschlagen ({response.status_code}): {response.text}")
  response.raise_for_status()
  return response.json()


def fetchSpoolList():
  url = f"{SPOOLMAN_API_URL}/spool"
  if SPOOL_SORTING:
    url += f"?sort={SPOOL_SORTING}"
  response = requests.get(url, timeout=10)
  response.raise_for_status()
  try:
    data = response.json()
  except ValueError as exc:
    raise RuntimeError(
      f"Spoolman returned invalid JSON (HTTP {response.status_code})"
    ) from exc
  if not isinstance(data, list):
    raise RuntimeError("Spoolman returned an unexpected spool-list format")
  return data

def consumeSpool(spool_id, use_weight=None, use_length=None):
  if use_weight is None and use_length is None:
    raise ValueError("use_weight or use_length is required")

  payload = {}
  if use_weight is not None:
    payload["use_weight"] = use_weight
  if use_length is not None:
    payload["use_length"] = use_length

  response = requests.put(f"{SPOOLMAN_API_URL}/spool/{spool_id}/use", json=payload)
  _log_spoolman_change(
    "consume_spool",
    spool_id=spool_id,
    payload=payload,
    status=response.status_code,
  )
  #print(response.status_code)
  #print(response.text)

def fetchSettings():
  response = requests.get(f"{SPOOLMAN_API_URL}/setting/")
  #print(response.status_code)
  #print(response.text)

  # JSON in ein Python-Dictionary laden
  data = response.json()

  # Extrahiere die Werte aus den relevanten Feldern
  extra_fields_spool = json.loads(data["extra_fields_spool"]["value"])
  extra_fields_filament = json.loads(data["extra_fields_filament"]["value"])
  base_url = data["base_url"]["value"]
  currency = data["currency"]["value"]

  settings = {}
  settings["extra_fields_spool"] = extra_fields_spool 
  settings["extra_fields_filament"] = extra_fields_filament
  settings["base_url"] = base_url.replace('"', '')
  settings["currency"] = currency.replace('"', '')

  return settings
