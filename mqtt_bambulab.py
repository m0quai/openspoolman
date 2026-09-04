

import json
import ssl
import traceback
from threading import Thread
from typing import Any, Iterable

import paho.mqtt.client as mqtt
import bambu_mqtt_signing

from config import (
    PRINTER_ID,
    PRINTER_CODE,
    PRINTER_IP,
    AUTO_SPEND,
    EXTERNAL_SPOOL_ID,
    EXTERNAL_SPOOL_AMS_ID,
    TRACK_LAYER_USAGE,
    LOG_AMS_MODE,
    CLEAR_ASSIGNMENT_WHEN_EMPTY,
)
from messages import GET_VERSION, PUSH_ALL, AMS_FILAMENT_SETTING
from spoolman_service import spendFilaments, setActiveTray, fetchSpools, clear_active_spool_for_tray
from tools_3mf import getMetaDataFrom3mf
import time
import threading
import copy
from collections.abc import Mapping
from logger import application_log_file, append_to_rotating_file, log
from print_history import insert_print, insert_filament_usage
from filament_usage_tracker import FilamentUsageTracker
MQTT_CLIENT = {}  # Global variable storing MQTT Client
MQTT_CLIENT_CONNECTED = False
MQTT_KEEPALIVE = 60
LAST_AMS_CONFIG = {}  # Global variable storing last AMS configuration
LAST_AMS_CONFIG_GENERATION = 0  # Incremented whenever fresh AMS data arrives from MQTT
LAST_LOGGED_AMS_STATE = None
FORCE_AMS_STATUS_LOG = False
# Last successfully acknowledged AMS material settings for non-RFID/third-party trays.
# P1/P1S can acknowledge ams_filament_setting with success and then emit sparse
# push_status tray objects whose material fields are empty. Keep the confirmed
# values locally so the UI does not immediately fall back to "No AMS material selected".
LAST_CONFIRMED_AMS_FILAMENT_SETTINGS = {}
PENDING_AMS_FILAMENT_SETTINGS = {}
FORCE_CLEAR_AMS_TRAYS = set()
PROFILE_RESPONSE_SAMPLES = {}
PENDING_PA_PROFILE_COMMANDS = {}
PENDING_AMS_STATUS_CONFIRMATIONS = {}
PENDING_EXTERNAL_OPERATION = None
AMS_STATUS_SAMPLES = {}
AMS_STATUS_CONFIRMATION_TIMEOUT = 10
AMS_STATUS_QUERY_ATTEMPTS = 10
AMS_STATUS_QUERY_INTERVAL = 2
ACTIVE_SPOOL_LOOKUP_ATTEMPTS = 5
ACTIVE_SPOOL_LOOKUP_INTERVAL = 0.4

PRINTER_STATE = {}
PRINTER_STATE_LAST = {}

PENDING_PRINT_METADATA = {}
FILAMENT_TRACKER = FilamentUsageTracker()
LOG_FILE = application_log_file("mqtt.log")
def getPrinterModel():
    global PRINTER_ID
    model_code = PRINTER_ID[:3]

    model_map = {
      # H2-Serie
      "093": "H2S",
      "094": "H2D",
      "239": "H2D Pro",
      "109": "H2C",

      # X1-Serie
      "00W": "X1",
      "00M": "X1 Carbon",
      "03W": "X1E",

      # P1-Serie
      "01S": "P1P",
      "01P": "P1S",

      # P2-Serie
      "22E": "P2S",

      # A1-Serie
      "039": "A1",
      "030": "A1 Mini"
    }

    model_name = model_map.get(model_code, f"Unknown model ({model_code})")

    numeric_tail = ''.join(filter(str.isdigit, PRINTER_ID))
    device_id = numeric_tail[-3:] if len(numeric_tail) >= 3 else numeric_tail

    device_name = f"3DP-{model_code}-{device_id}"

    return {
        "model": model_name,
        "devicename": device_name
    }

def identify_ams_model_from_module(module: dict[str, Any]) -> str | None:
    """Guess the AMS variant that a version module represents."""

    product_name = (module.get("product_name") or "").strip().lower()
    module_name = (module.get("name") or "").strip().lower()

    if "ams lite" in product_name or module_name.startswith("ams_f1"):
        return "AMS Lite"
    if "ams 2 pro" in product_name or module_name.startswith("n3f"):
        return "AMS 2 Pro"
    if "ams ht" in product_name or module_name.startswith("ams_ht"):
        return "AMS HT"
    if module_name == "ams" or module_name.startswith("ams/"):
        return "AMS"

    return None


def identify_ams_models_from_modules(modules: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
  """Return per-module metadata, including the detected model when available."""

  results: dict[str, dict[str, Any]] = {}
  for module in modules or []:
    name = module.get("name")
    if not name:
      continue

    results[name] = {
      "model": identify_ams_model_from_module(module),
      "product_name": module.get("product_name"),
      "serial": module.get("sn"),
      "hw_ver": module.get("hw_ver"),
    }

  return results


def extract_ams_id_from_module_name(name: str) -> int | None:
  parts = name.split("/")
  if len(parts) != 2:
    return None
  try:
    return int(parts[1])
  except ValueError:
    return None


def identify_ams_models_by_id(modules: Iterable[dict[str, Any]]) -> dict[str, str]:
  """Return the detected AMS model per numeric AMS ID (module suffix)."""

  results: dict[str, str] = {}
  for module in modules or []:
    name = module.get("name")
    if not name:
      continue

    ams_id = extract_ams_id_from_module_name(name)
    if ams_id is None:
      continue

    model = identify_ams_model_from_module(module)
    if model:
      results[str(ams_id)] = model
      results[ams_id] = model

  return results


def num2letter(num):
  return chr(ord("A") + int(num))
  
def update_dict(original: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if isinstance(value, Mapping) and key in original and isinstance(original[key], Mapping):
            original[key] = update_dict(original[key], value)
        else:
            original[key] = value
    return original


def _parse_grams(value):
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _metadata_is_usable(metadata):
  return bool(
    isinstance(metadata, dict)
    and metadata.get("file") is not None
    and metadata.get("image") is not None
    and isinstance(metadata.get("filaments"), dict)
  )


def _mask_serial(serial: str | None, keep_chars: int = 3) -> str:
  if not serial:
    return ""
  visible = serial[:keep_chars]
  if len(serial) <= keep_chars:
    return visible
  return f"{visible}..."

def _mask_sn_values(value):
  if isinstance(value, dict):
    for key, item in value.items():
      if key.lower() == "sn" and isinstance(item, str):
        value[key] = _mask_serial(item)
      else:
        _mask_sn_values(item)
  elif isinstance(value, list):
    for elem in value:
      _mask_sn_values(elem)

def _mask_mqtt_payload(payload: str) -> str:
  try:
    data = json.loads(payload)
    _mask_sn_values(data)
    masked = json.dumps(data, separators=(",", ":"))
  except ValueError:
    masked = payload

  masked_serial = _mask_serial(PRINTER_ID)
  if masked_serial:
    masked = masked.replace(PRINTER_ID, masked_serial)

  return masked

def map_filament(tray_tar):
  global PENDING_PRINT_METADATA
  # Prüfen, ob ein Filamentwechsel aktiv ist (stg_cur == 4)
  #if stg_cur == 4 and tray_tar is not None:
  if PENDING_PRINT_METADATA:
    PENDING_PRINT_METADATA["filamentChanges"].append(tray_tar)  # Jeder Wechsel zählt, auch auf das gleiche Tray
    log(f'Filamentchange {len(PENDING_PRINT_METADATA["filamentChanges"])}: Tray {tray_tar}')

    # Anzahl der erkannten Wechsel
    change_count = len(PENDING_PRINT_METADATA["filamentChanges"]) - 1  # -1, weil der erste Eintrag kein Wechsel ist

    filament_order = PENDING_PRINT_METADATA.get("filamentOrder") or {}
    ordered_filaments = sorted(filament_order.items(), key=lambda entry: entry[1])
    assigned_trays = PENDING_PRINT_METADATA.setdefault("assigned_trays", [])
    filament_assigned = None
    if tray_tar not in assigned_trays:
      assigned_trays.append(tray_tar)
      unique_index = len(assigned_trays) - 1
      if unique_index < len(ordered_filaments):
        filament_assigned = ordered_filaments[unique_index][0]
      else:
        for filamentId, usage_count in filament_order.items():
          if usage_count == change_count:
            filament_assigned = filamentId
            break

    if filament_assigned is not None:
      mapping = PENDING_PRINT_METADATA.setdefault("ams_mapping", [])
      filament_idx = int(filament_assigned)
      while len(mapping) <= filament_idx:
        mapping.append(None)
      mapping[filament_idx] = tray_tar
      log(f"✅ Tray {tray_tar} assigned to Filament {filament_assigned}")

      for filament, tray in enumerate(mapping):
        if tray is None:
          continue
        log(f"  Filament pos: {filament} → Tray {tray}")

    target_filaments = set(filament_order.keys())
    if target_filaments:
      assigned_filaments = {
        idx for idx, tray in enumerate(PENDING_PRINT_METADATA.get("ams_mapping", []))
        if tray is not None
      }
      if target_filaments.issubset(assigned_filaments):
        log("\n✅ All trays assigned:")
        return True
  
  return False
  
def processMessage(data):
  global LAST_AMS_CONFIG, PRINTER_STATE, PRINTER_STATE_LAST, PENDING_PRINT_METADATA

   # Prepare AMS spending estimation
  if "print" in data:    
    update_dict(PRINTER_STATE, data)
    
    if data["print"].get("command") == "project_file" and data["print"].get("url"):
      PENDING_PRINT_METADATA = getMetaDataFrom3mf(data["print"]["url"])
      if not _metadata_is_usable(PENDING_PRINT_METADATA):
        log(f"[3MF] project_file Metadaten unvollstaendig; Print-Tracking wird fuer diese Meldung nicht gestartet: {data['print'].get('url')!r}")
        PENDING_PRINT_METADATA = {}
        PRINTER_STATE_LAST = copy.deepcopy(PRINTER_STATE)
        return

      PENDING_PRINT_METADATA["print_type"] = PRINTER_STATE["print"].get("print_type")
      PENDING_PRINT_METADATA["task_id"] = PRINTER_STATE["print"].get("task_id")
      PENDING_PRINT_METADATA["subtask_id"] = PRINTER_STATE["print"].get("subtask_id")
      print_id = insert_print(PRINTER_STATE["print"].get("subtask_name") or PENDING_PRINT_METADATA["file"], "cloud", PENDING_PRINT_METADATA["image"])

      if PRINTER_STATE["print"].get("use_ams"):
        PENDING_PRINT_METADATA["ams_mapping"] = PRINTER_STATE["print"].get("ams_mapping") or []
      else:
        PENDING_PRINT_METADATA["ams_mapping"] = [EXTERNAL_SPOOL_ID]

      PENDING_PRINT_METADATA["print_id"] = print_id
      PENDING_PRINT_METADATA["complete"] = True
      if TRACK_LAYER_USAGE:
        # The tracker must receive the database ID after insert_print();
        # assigning metadata before that left active cloud jobs with no ID.
        FILAMENT_TRACKER.set_print_metadata(PENDING_PRINT_METADATA)

      for id, filament in PENDING_PRINT_METADATA["filaments"].items():
        parsed_grams = _parse_grams(filament.get("used_g"))
        parsed_length_m = _parse_grams(filament.get("used_m"))
        estimated_length_mm = parsed_length_m * 1000 if parsed_length_m is not None else None
        grams_used = parsed_grams if parsed_grams is not None else 0.0
        length_used = estimated_length_mm if estimated_length_mm is not None else 0.0
        if TRACK_LAYER_USAGE:
          grams_used = 0.0
          length_used = 0.0
        insert_filament_usage(
            print_id,
            filament["type"],
            filament["color"],
            grams_used,
            id,
            estimated_grams=parsed_grams,
            length_used=length_used,
            estimated_length=estimated_length_mm,
        )
  
    #if ("gcode_state" in data["print"] and data["print"]["gcode_state"] == "RUNNING") and ("print_type" in data["print"] and data["print"]["print_type"] != "local") \
    #  and ("tray_tar" in data["print"] and data["print"]["tray_tar"] != "255") and ("stg_cur" in data["print"] and data["print"]["stg_cur"] == 0 and PRINT_CURRENT_STAGE != 0):
    
    #TODO: What happens when printed from external spool, is ams and tray_tar set?
    if PRINTER_STATE.get("print", {}).get("print_type") == "local" and PRINTER_STATE_LAST.get("print"):

      if (
          PRINTER_STATE["print"].get("gcode_state") == "RUNNING" and
          PRINTER_STATE_LAST["print"].get("gcode_state") == "PREPARE" and 
          PRINTER_STATE["print"].get("gcode_file")
        ):

        if not PENDING_PRINT_METADATA:
          PENDING_PRINT_METADATA = getMetaDataFrom3mf(PRINTER_STATE["print"]["gcode_file"])
        if PENDING_PRINT_METADATA and not _metadata_is_usable(PENDING_PRINT_METADATA):
          log(f"[3MF] Lokale Druckmetadaten unvollstaendig; verwerfe Zwischenstand fuer {PRINTER_STATE['print'].get('gcode_file')!r}.")
          PENDING_PRINT_METADATA = {}

        if _metadata_is_usable(PENDING_PRINT_METADATA):
          PENDING_PRINT_METADATA["print_type"] = PRINTER_STATE["print"].get("print_type")
          PENDING_PRINT_METADATA["task_id"] = PRINTER_STATE["print"].get("task_id")
          PENDING_PRINT_METADATA["subtask_id"] = PRINTER_STATE["print"].get("subtask_id")

          if not PENDING_PRINT_METADATA.get("tracking_started"):
            print_id = insert_print(PENDING_PRINT_METADATA["file"], PRINTER_STATE["print"]["print_type"], PENDING_PRINT_METADATA["image"])

            PENDING_PRINT_METADATA["ams_mapping"] = []
            PENDING_PRINT_METADATA["filamentChanges"] = []
            PENDING_PRINT_METADATA["assigned_trays"] = []
            PENDING_PRINT_METADATA["complete"] = False
            PENDING_PRINT_METADATA["print_id"] = print_id
            FILAMENT_TRACKER.start_local_print_from_metadata(PENDING_PRINT_METADATA)

            for id, filament in PENDING_PRINT_METADATA["filaments"].items():
              parsed_grams = _parse_grams(filament.get("used_g"))
              parsed_length_m = _parse_grams(filament.get("used_m"))
              estimated_length_mm = parsed_length_m * 1000 if parsed_length_m is not None else None
              grams_used = parsed_grams if parsed_grams is not None else 0.0
              length_used = estimated_length_mm if estimated_length_mm is not None else 0.0
              if TRACK_LAYER_USAGE:
                grams_used = 0.0
                length_used = 0.0
              insert_filament_usage(
                  print_id,
                  filament["type"],
                  filament["color"],
                  grams_used,
                  id,
                  estimated_grams=parsed_grams,
                  length_used=length_used,
                  estimated_length=estimated_length_mm,
              )

            PENDING_PRINT_METADATA["tracking_started"] = True

        #TODO 
    
      # When stage changed to "change filament" and PENDING_PRINT_METADATA is set
      if (PENDING_PRINT_METADATA and 
          (
            (
              int(PRINTER_STATE["print"].get("stg_cur", -1)) == 4 and      # change filament stage (beginning of print)
              ( 
                PRINTER_STATE_LAST["print"].get("stg_cur", -1) == -1 or                                           # last stage not known
                (
                  int(PRINTER_STATE_LAST["print"].get("stg_cur")) != int(PRINTER_STATE["print"].get("stg_cur")) and
                  PRINTER_STATE_LAST["print"].get("ams", {}).get("tray_tar") == "255"             # stage has changed and last state was 255 (retract to ams)
                )
                or not PRINTER_STATE_LAST["print"].get("ams")                                               # ams not set in last state
              )
            )
            or                                                                                            # filament changes during printing are in mc_print_sub_stage
            (
              int(PRINTER_STATE_LAST["print"].get("mc_print_sub_stage", -1)) == 4  # last state was change filament
              and int(PRINTER_STATE["print"].get("mc_print_sub_stage", -1)) == 2                                                           # current state 
            )
            or (
              PRINTER_STATE["print"].get("ams", {}).get("tray_tar") == "254"
            )
            or 
            (
              int(PRINTER_STATE["print"].get("stg_cur", -1)) == 24 and int(PRINTER_STATE_LAST["print"].get("stg_cur", -1)) == 13
            )
            or (
              int(PRINTER_STATE["print"].get("stg_cur", -1)) == 4 and
              PRINTER_STATE["print"].get("ams", {}).get("tray_tar") not in (None, "255") and
              (PRINTER_STATE_LAST["print"].get("ams", {}).get("tray_tar") is None or PRINTER_STATE_LAST["print"].get("ams", {}).get("tray_tar") != PRINTER_STATE["print"].get("ams", {}).get("tray_tar"))
            )

          )
      ):
        if PRINTER_STATE["print"].get("ams"):
            mapped = False
            tray_tar_value = PRINTER_STATE["print"].get("ams").get("tray_tar")
            if tray_tar_value and tray_tar_value != "255":
                mapped = map_filament(int(tray_tar_value))
            FILAMENT_TRACKER.apply_ams_mapping(PENDING_PRINT_METADATA.get("ams_mapping") or [])
            if mapped:
                PENDING_PRINT_METADATA["complete"] = True

    if PENDING_PRINT_METADATA and PENDING_PRINT_METADATA.get("complete"):
      if TRACK_LAYER_USAGE:
        if PENDING_PRINT_METADATA.get("print_type") == "local":
          FILAMENT_TRACKER.apply_ams_mapping(PENDING_PRINT_METADATA.get("ams_mapping") or [])
        else:
          FILAMENT_TRACKER.set_print_metadata(PENDING_PRINT_METADATA)
        # Per-layer tracker will handle consumption; skip upfront spend.
      else:
        spendFilaments(PENDING_PRINT_METADATA)

      PENDING_PRINT_METADATA = {}
  
    PRINTER_STATE_LAST = copy.deepcopy(PRINTER_STATE)

_MQTT_SEQUENCE_ID = int(time.time() * 1000)

def _next_mqtt_sequence_id():
  global _MQTT_SEQUENCE_ID
  _MQTT_SEQUENCE_ID += 1
  return str(_MQTT_SEQUENCE_ID)

def publish(client, msg):
  message_to_send = copy.deepcopy(msg)

  # Bambu rejects reused/non-monotonic sequence IDs on protected print commands.
  if isinstance(message_to_send, dict) and isinstance(message_to_send.get("print"), dict):
    message_to_send["print"]["sequence_id"] = _next_mqtt_sequence_id()

  print_command = message_to_send.get("print") if isinstance(message_to_send, dict) else None
  if isinstance(print_command, dict) and print_command.get("command") == "ams_filament_setting":
    # Start a fresh profile processing sequence for this explicit Fill.
    # The printer normally answers ams_filament_setting only once, so waiting
    # for several identical responses would leave the PA profile untouched.
    if any(str(print_command.get(field) or "").strip() for field in ("tray_type", "tray_info_idx", "setting_id")):
      sample_key = _ams_tray_key(print_command.get("ams_id"), print_command.get("tray_id"))
      PROFILE_RESPONSE_SAMPLES.pop(sample_key, None)
    target = "EX" if str(print_command.get("tray_id")) in {"254", "255"} else f"{num2letter(print_command.get('ams_id'))}{int(print_command.get('tray_id', 0)) + 1}"
    log("PROFIL OUT " + f"[{target}]: {print_command.get('tray_type') or '<leer>'} | {print_command.get('tray_sub_brands') or '<leer>'} | {print_command.get('tray_color') or '<leer>'} | {print_command.get('tray_info_idx') or '<leer>'} | {print_command.get('setting_id') or '<leer>'}")
    clear_key = _ams_tray_key(print_command.get("ams_id"), print_command.get("tray_id"))
    clear_command = clear_key in FORCE_CLEAR_AMS_TRAYS or not any(
      str(print_command.get(field) or "").strip()
      for field in ("tray_type", "tray_sub_brands", "setting_id", "tray_info_idx")
    )
    FORCE_CLEAR_AMS_TRAYS.discard(clear_key)
    PENDING_AMS_FILAMENT_SETTINGS[str(print_command["sequence_id"])] = {
        "ams_id": print_command.get("ams_id"),
        "tray_id": print_command.get("tray_id"),
        "operation": "clear" if clear_command else "fill",
        "message": message_to_send,
    }

  try:
    if (
      isinstance(message_to_send, dict)
      and "print" in message_to_send
      and bambu_mqtt_signing.certificate_is_valid()
    ):
      wire_payload = bambu_mqtt_signing.sign_message_json(message_to_send)
    else:
      wire_payload = json.dumps(message_to_send, ensure_ascii=False, separators=(",", ":"))
  except Exception as exc:
    # Protected print commands must not silently fall back to unsigned transmission.
    if isinstance(message_to_send, dict) and "print" in message_to_send:
      log(f"MQTT signing failed: {exc}. Protected print command NOT sent.")
      return False
    wire_payload = json.dumps(message_to_send, ensure_ascii=False, separators=(",", ":"))

  result = client.publish(f"device/{PRINTER_ID}/request", wire_payload)
  status = result[0]
  if status == 0:
    if LOG_AMS_MODE == "everything":
      log(f"Sent {message_to_send} to topic device/{PRINTER_ID}/request")
    return True
  log(f"Failed to send message to topic device/{PRINTER_ID}/request")
  return False

def _ams_tray_key(ams_id, tray_id):
  return (str(ams_id), str(tray_id))

def is_ams_tray_operation_pending(ams_id, tray_id):
  """Return whether a tray is still changing and must reject new actions."""
  key = _ams_tray_key(ams_id, tray_id)
  aliases = {key}
  if str(ams_id) == str(EXTERNAL_SPOOL_AMS_ID):
    aliases.update({_ams_tray_key(EXTERNAL_SPOOL_AMS_ID, EXTERNAL_SPOOL_ID), _ams_tray_key(EXTERNAL_SPOOL_AMS_ID, 255)})
  if any(alias in PENDING_AMS_STATUS_CONFIRMATIONS or alias in PENDING_PA_PROFILE_COMMANDS for alias in aliases):
    return True
  if any(
      _ams_tray_key(pending.get("ams_id"), pending.get("tray_id")) == key
      for pending in PENDING_AMS_FILAMENT_SETTINGS.values()
  ):
    return True
  if str(ams_id) == str(EXTERNAL_SPOOL_AMS_ID) and PENDING_EXTERNAL_OPERATION:
    return True
  return False

def is_any_ams_operation_pending():
  """Return whether any tray is waiting for a stable AMS result."""
  return bool(
    PENDING_AMS_FILAMENT_SETTINGS
    or PENDING_AMS_STATUS_CONFIRMATIONS
    or PENDING_PA_PROFILE_COMMANDS
    or PENDING_EXTERNAL_OPERATION
  )

def _find_active_spool_for_tray(ams_id, tray_id):
  """Find the current Spoolman assignment after an AMS write.

  Spoolman persists the active-tray tag before the printer answers, but the
  MQTT response can arrive before the subsequent API read sees that write.
  Retry a few times instead of dropping the profile update permanently.
  """
  lookup_tray_id = EXTERNAL_SPOOL_ID if str(ams_id) == str(EXTERNAL_SPOOL_AMS_ID) and str(tray_id) == "255" else tray_id
  active_key = json.dumps(f"{PRINTER_ID}_{ams_id}_{lookup_tray_id}")
  for attempt in range(ACTIVE_SPOOL_LOOKUP_ATTEMPTS):
    try:
      spool = next(
        (item for item in fetchSpools(False)
         if item.get("extra", {}).get("active_tray") == active_key),
        None,
      )
      if spool:
        return spool
    except Exception:
      pass
    if attempt + 1 < ACTIVE_SPOOL_LOOKUP_ATTEMPTS:
      time.sleep(ACTIVE_SPOOL_LOOKUP_INTERVAL)
  return None

def _send_pa_profile_selection(client, ams_id, tray_id, cali_idx, filament_id="", persist=True):
  """Serialize PA-profile commands so one tray cannot receive duplicates."""
  pa_tray_id = 255 if str(ams_id) == str(EXTERNAL_SPOOL_AMS_ID) and str(tray_id) == str(EXTERNAL_SPOOL_ID) else tray_id
  key = _ams_tray_key(ams_id, pa_tray_id)
  if key in PENDING_PA_PROFILE_COMMANDS:
    return False

  command = {
    "print": {
      "command": "extrusion_cali_sel",
      "ams_id": ams_id,
      "tray_id": pa_tray_id,
      "slot_id": pa_tray_id,
      "cali_idx": int(cali_idx),
      "filament_id": str(filament_id or ""),
      "nozzle_diameter": "0.4",
      "sequence_id": str(_next_mqtt_sequence_id()),
    }
  }
  if not publish(client, command):
    return False
  PENDING_PA_PROFILE_COMMANDS[key] = {
    "cali_idx": int(cali_idx),
    "filament_id": str(filament_id or ""),
    "persist": bool(persist),
  }
  log(
    f"PA PROFIL OUT: Fach={ams_id}/{pa_tray_id}; "
    f"cali_idx={int(cali_idx)}; filament_id={filament_id or '<leer>'}"
  )
  return True

def _extra_text(value):
  """Return a Spoolman extra value without JSON quote wrappers."""
  try:
    parsed = json.loads(value) if isinstance(value, str) else value
    return str(parsed).strip() if parsed is not None else ""
  except (TypeError, ValueError):
    return str(value or "").strip()

def _persist_confirmed_pa_profile(ams_id, tray_id, cali_idx, reported_filament_id):
  """Save a confirmed Bambu PA index only for the matching active filament."""
  try:
    index = int(cali_idx)
  except (TypeError, ValueError):
    return False
  spool = _find_active_spool_for_tray(ams_id, tray_id)
  if not spool or not spool.get("filament", {}).get("id"):
    return False

  extras = spool.get("filament", {}).get("extra") or {}
  expected_filament_id = _extra_text(extras.get("filament_id"))
  actual_filament_id = str(reported_filament_id or "").strip()
  if expected_filament_id and actual_filament_id and expected_filament_id != actual_filament_id:
    log(
      f"PA PROFIL nicht gespeichert: Filament-ID passt nicht "
      f"({actual_filament_id} != {expected_filament_id})"
    )
    return False

  import spoolman_client
  spoolman_client.patchFilamentExtra(
    spool["filament"]["id"],
    extras,
    {"cali_idx": index},
  )
  return True

def _repeat_ams_status_query(label, confirmation_key, attempt=1):
  if attempt > AMS_STATUS_QUERY_ATTEMPTS or not MQTT_CLIENT or confirmation_key not in PENDING_AMS_STATUS_CONFIRMATIONS:
    return
  publish(MQTT_CLIENT, PUSH_ALL)
  if attempt < AMS_STATUS_QUERY_ATTEMPTS:
    timer = threading.Timer(AMS_STATUS_QUERY_INTERVAL, _repeat_ams_status_query, args=(label, confirmation_key, attempt + 1))
    timer.daemon = True
    timer.start()

def _remember_confirmed_ams_filament_setting(print_reply):
  """Persist the last printer-acknowledged material setting in memory.

  P1/P1S third-party trays use an all-zero RFID UUID. After a successful
  ams_filament_setting write the printer may publish sparse status data with
  empty tray_type/tray_info_idx even though the setting was accepted.
  """
  global LAST_CONFIRMED_AMS_FILAMENT_SETTINGS, LAST_AMS_CONFIG

  try:
    key = _ams_tray_key(print_reply.get("ams_id"), print_reply.get("tray_id"))
    if key[0] == "None" or key[1] == "None":
      return

    fields = {
      name: copy.deepcopy(print_reply.get(name))
      for name in (
        "tray_color",
        "nozzle_temp_min",
        "nozzle_temp_max",
        "tray_type",
        "setting_id",
        "tray_info_idx",
        "tray_sub_brands",
      )
      if name in print_reply
    }
    LAST_CONFIRMED_AMS_FILAMENT_SETTINGS[key] = fields

    # Update the current cache immediately, if the tray already exists.
    for ams in LAST_AMS_CONFIG.get("ams", []):
      if str(ams.get("id")) != key[0]:
        continue
      for tray in ams.get("tray", []):
        if str(tray.get("id")) == key[1]:
          tray.update(copy.deepcopy(fields))
          return
  except Exception as exc:
    log(f"[AMS-CACHE] Could not remember confirmed filament setting: {exc!r}")

def _apply_confirmed_ams_filament_settings(ams_data):
  """Restore confirmed material fields omitted by sparse P1/P1S status packets.

  Non-empty values reported by the printer always win. Empty/missing material
  values on a non-RFID tray fall back to the last successful write. A successful
  explicit Clear stores empty values and therefore clears this fallback as well.
  """
  for ams in ams_data or []:
    ams_id = str(ams.get("id"))
    for tray in ams.get("tray", []) or []:
      key = _ams_tray_key(ams_id, tray.get("id"))
      confirmed = LAST_CONFIRMED_AMS_FILAMENT_SETTINGS.get(key)
      if not confirmed:
        continue

      tray_uuid = str(tray.get("tray_uuid") or "")
      is_non_rfid = not tray_uuid or tray_uuid == "00000000000000000000000000000000"
      if not is_non_rfid:
        continue

      for field, confirmed_value in confirmed.items():
        current_value = tray.get(field)
        if current_value not in (None, ""):
          # A concrete value from the printer is newer/more authoritative.
          confirmed[field] = copy.deepcopy(current_value)
          continue
        # Empty confirmed values represent an explicit successful Clear.
        if confirmed_value in (None, ""):
          tray[field] = confirmed_value
        else:
          tray[field] = copy.deepcopy(confirmed_value)

def clear_ams_tray_assignment(ams_id, tray_id):
  """Clear the material assignment on the printer and in the local AMS cache.

  The P1/P1S can publish sparse/stale tray values after a write.  Therefore a
  successful Clear must invalidate the confirmed-material cache immediately so
  the OpenSpoolMan header does not continue to show the previous material while
  we wait for the printer's next status packet.
  """
  global LAST_CONFIRMED_AMS_FILAMENT_SETTINGS, LAST_AMS_CONFIG

  if not MQTT_CLIENT:
    return False

  ams_message = copy.deepcopy(AMS_FILAMENT_SETTING)
  ams_message["print"]["ams_id"] = int(ams_id)
  ams_message["print"]["tray_id"] = int(tray_id)
  # P1/P1S: reset a third-party tray to the unconfigured state.
  # Do not send null for numeric temperature fields.
  ams_message["print"]["tray_color"] = "FFFFFFFF"
  ams_message["print"]["nozzle_temp_min"] = 0
  ams_message["print"]["nozzle_temp_max"] = 0
  ams_message["print"]["tray_type"] = ""
  ams_message["print"]["setting_id"] = ""
  ams_message["print"]["tray_info_idx"] = ""
  ams_message["print"]["tray_sub_brands"] = ""

  # Mark this exact request as Clear before publishing.  Color is deliberately
  # not used for classification because a genuine white spool can also report
  # FFFFFFFF.
  FORCE_CLEAR_AMS_TRAYS.add(_ams_tray_key(ams_id, tray_id))
  if not publish(MQTT_CLIENT, ams_message):
    FORCE_CLEAR_AMS_TRAYS.discard(_ams_tray_key(ams_id, tray_id))
    return False

  key = _ams_tray_key(ams_id, tray_id)
  LAST_CONFIRMED_AMS_FILAMENT_SETTINGS.pop(key, None)

  # Update the currently displayed AMS snapshot immediately.  This prevents the
  # old material/color from surviving in the tray header until the next pushall.
  for ams in LAST_AMS_CONFIG.get("ams", []):
    if str(ams.get("id")) != key[0]:
      continue
    for tray in ams.get("tray", []):
      if str(tray.get("id")) != key[1]:
        continue
      tray["tray_color"] = ""
      tray["nozzle_temp_min"] = None
      tray["nozzle_temp_max"] = None
      tray["tray_type"] = ""
      tray["setting_id"] = ""
      tray["tray_info_idx"] = ""
      tray["tray_sub_brands"] = ""
      break

  return True

# Inspired by https://github.com/Donkie/Spoolman/issues/217#issuecomment-2303022970
def on_message(client, userdata, msg):
  global LAST_AMS_CONFIG, LAST_AMS_CONFIG_GENERATION, LAST_LOGGED_AMS_STATE, FORCE_AMS_STATUS_LOG, PRINTER_STATE, PRINTER_STATE_LAST, PENDING_PRINT_METADATA, PRINTER_MODEL, PENDING_EXTERNAL_OPERATION, PENDING_PA_PROFILE_COMMANDS
  
  try:
    data = json.loads(msg.payload.decode())

    print_data = data.get("print", {}) if isinstance(data, dict) else {}
    if print_data.get("command") == "extrusion_cali_sel":
      pa_key = _ams_tray_key(print_data.get("ams_id"), print_data.get("tray_id"))
      pending_pa = PENDING_PA_PROFILE_COMMANDS.pop(pa_key, None)
      log(
        "PA PROFIL IN: "
        f"result={print_data.get('result') or '<leer>'}; "
        f"Fach={print_data.get('ams_id', '<leer>')}/{print_data.get('tray_id', '<leer>')}; "
        f"cali_idx={print_data.get('cali_idx', '<leer>')}; "
        f"filament_id={print_data.get('filament_id') or '<leer>'}"
      )
      returned_idx = print_data.get("cali_idx")
      requested_idx = (pending_pa or {}).get("cali_idx")
      returned_matches_request = (
        pending_pa is not None
        and returned_idx is not None
        and (
          (requested_idx == -1 and str(returned_idx).strip() == "-1")
          or (requested_idx != -1 and str(returned_idx).strip() == str(requested_idx))
        )
      )
      if pending_pa and print_data.get("result") == "success" and returned_matches_request and pending_pa.get("persist", True):
        # The printer's successful response is authoritative.  Persist the
        # accepted index so the next assignment does not resend a rejected or
        # stale value from Spoolman.
        try:
          _persist_confirmed_pa_profile(
            print_data.get("ams_id"),
            print_data.get("tray_id"),
            returned_idx,
            print_data.get("filament_id"),
          )
        except Exception as pa_store_error:
          log(f"PA PROFIL Speicherung fehlgeschlagen: {pa_store_error}")
      elif pending_pa and print_data.get("result") == "success" and not returned_matches_request:
        # A late status packet can arrive after a rejected command.  It is not
        # an acknowledgement for the currently pending request and must not
        # overwrite Spoolman's PA index.
        log(
          f"PA PROFIL IN ignoriert: erwartet={requested_idx}; "
          f"empfangen={returned_idx}"
        )
      elif pending_pa and print_data.get("result") == "fail" and pending_pa.get("cali_idx") != -1 and not str(print_data.get("ams_id")) == str(EXTERNAL_SPOOL_AMS_ID):
        # Never leave Bambu displaying the previously selected profile after a
        # rejected index.  Reset that tray to the printer default once.
        _send_pa_profile_selection(client, print_data.get("ams_id"), print_data.get("tray_id"), -1, persist=False)
      elif not pending_pa and print_data.get("result") == "success":
        # Bambu emits this after a manual PA-profile selection in its UI.  A
        # matching active filament makes that response safe to synchronize.
        try:
          _persist_confirmed_pa_profile(
            print_data.get("ams_id"),
            print_data.get("tray_id"),
            returned_idx,
            print_data.get("filament_id"),
          )
        except Exception as pa_store_error:
          log(f"PA PROFIL Speicherung fehlgeschlagen: {pa_store_error}")

    # A successful Fill ACK must be followed by a physical AMS status.  If
    # the printer never reports that tray, do not leave the assignment pending.
    now = time.monotonic()
    for confirmation_key, pending_confirmation in list(PENDING_AMS_STATUS_CONFIRMATIONS.items()):
      pending_label, pending_started, _ = pending_confirmation
      if now - pending_started < AMS_STATUS_CONFIRMATION_TIMEOUT:
        continue
      PENDING_AMS_STATUS_CONFIRMATIONS.pop(confirmation_key, None)
      log(f"AMS Fill Timeout für {pending_label}: kein verwertbarer AMS-Fachstatus")
      clear_active_spool_for_tray(confirmation_key[0], confirmation_key[1])

    # Remember successfully acknowledged AMS writes. P1/P1S may return sparse
    # material fields in subsequent push_status messages for third-party spools.
    try:
      print_reply = data.get("print", {}) if isinstance(data, dict) else {}
      if print_reply.get("command") == "ams_filament_setting":
        target = "EX" if str(print_reply.get("tray_id")) in {"254", "255"} else f"{num2letter(print_reply.get('ams_id'))}{int(print_reply.get('tray_id', 0)) + 1}"
        log("PROFIL IN  " + f"[{target}]: {print_reply.get('result') or '<leer>'} | {print_reply.get('tray_type') or '<leer>'} | {print_reply.get('tray_sub_brands') or '<leer>'} | {print_reply.get('tray_color') or '<leer>'} | {print_reply.get('tray_info_idx') or '<leer>'} | {print_reply.get('setting_id') or '<leer>'}")
        sequence_id = str(print_reply.get("sequence_id") or "")
        pending = PENDING_AMS_FILAMENT_SETTINGS.pop(sequence_id, None)
        result = print_reply.get("result")
        reason = print_reply.get("reason")
        ams_id = print_reply.get("ams_id", (pending or {}).get("ams_id"))
        tray_id = print_reply.get("tray_id", (pending or {}).get("tray_id"))
        operation = (pending or {}).get("operation", "fill")
        if operation == "fill" and print_reply.get("tray_info_idx") and print_reply.get("setting_id") and ams_id is not None and tray_id is not None:
          try:
            spool = _find_active_spool_for_tray(ams_id, tray_id)
            sample_key = (str(ams_id), str(tray_id))
            sample = (str(print_reply.get("tray_info_idx") or ""), str(print_reply.get("setting_id") or ""))
            if PROFILE_RESPONSE_SAMPLES.get(sample_key) == sample:
              # Duplicate profile reply for the same tray: the corresponding
              # PA command is already pending or was confirmed.
              pass
            elif spool and spool.get("filament", {}).get("id"):
              PROFILE_RESPONSE_SAMPLES[sample_key] = sample
              import spoolman_client
              spoolman_client.patchFilamentExtra(
                spool["filament"]["id"],
                spool["filament"].get("extra") or {},
                {"filament_id": print_reply["tray_info_idx"], "setting_id": print_reply["setting_id"]},
              )
              extras = spool.get("filament", {}).get("extra", {}) or {}
              def _extra_value(value):
                try:
                  parsed = json.loads(value) if isinstance(value, str) else value
                  return parsed if not isinstance(parsed, str) else parsed
                except (TypeError, ValueError):
                  return value
              extras = {key: _extra_value(value) for key, value in extras.items()}
              cali_idx = extras.get("cali_idx")
              if cali_idx is not None and str(cali_idx).strip() != "":
                # extrusion_cali_sel identifies the material by Bambu's
                # filament/tray-info ID, not by the AMS setting ID.
                pa_filament_id = str(extras.get("filament_id") or print_reply["tray_info_idx"])
                _send_pa_profile_selection(client, ams_id, tray_id, int(cali_idx), pa_filament_id)
              else:
                # No stored PA profile means Bambu must be reset explicitly;
                # otherwise its UI keeps the last selected profile active.
                default_filament_id = str(
                  print_reply.get("tray_info_idx")
                  or ""
                )
                _send_pa_profile_selection(client, ams_id, tray_id, -1, default_filament_id, persist=True)
          except Exception as profile_error:
            log(f"Bambu-Profil konnte nicht gespeichert werden: {profile_error}")
        elif operation == "clear" and result == "success" and ams_id is not None and tray_id is not None:
          PROFILE_RESPONSE_SAMPLES.pop(_ams_tray_key(ams_id, tray_id), None)
          _send_pa_profile_selection(client, ams_id, tray_id, -1, persist=False)
        is_external = str(ams_id) in {"-1", "255"} or str(tray_id) == "255"
        tray_label = "[EX]" if is_external else (f"[{num2letter(ams_id)}{int(tray_id) + 1}]" if ams_id is not None and tray_id is not None else "[unbekanntes Fach]")
        if result == "success" and reason == "success":
          if is_external:
            # A successful EX profile response is already the stable result
            # for this operation.  Do not leave the EX card locked while
            # waiting for a vt_tray packet that may not be emitted.
            PENDING_EXTERNAL_OPERATION = None if operation == "fill" else operation
            external_tray = LAST_AMS_CONFIG.get("vt_tray") or {}
            if operation == "clear" and not any(str(external_tray.get(field) or "").strip() for field in ("tray_type", "tray_sub_brands", "tray_info_idx", "setting_id")):
              clear_active_spool_for_tray(EXTERNAL_SPOOL_AMS_ID, EXTERNAL_SPOOL_ID)
              PENDING_EXTERNAL_OPERATION = None
            if operation == "fill":
              # EX does not reliably emit a follow-up vt_tray packet.  Push
              # the complete status so the UI reflects the assignment.
              publish(client, PUSH_ALL)
            return
          if operation == "fill":
            _remember_confirmed_ams_filament_setting(print_reply)
          PENDING_AMS_STATUS_CONFIRMATIONS[_ams_tray_key(ams_id, tray_id)] = (tray_label, time.monotonic(), operation)
          _repeat_ams_status_query(tray_label, _ams_tray_key(ams_id, tray_id))
        else:
          log(f"AMS Fill fehlgeschlagen für {tray_label}: result={result!r}, reason={reason!r}")
          if ams_id is not None and tray_id is not None:
            clear_active_spool_for_tray(ams_id, tray_id)
    except Exception as response_error:
      log(f"Could not process AMS filament-setting response: {response_error!r}")

    info = data.get("info")
    if info and info.get("command") == "get_version":
      modules = info.get("module", [])
      detected = identify_ams_models_from_modules(modules)
      models_by_id = identify_ams_models_by_id(modules)
      LAST_AMS_CONFIG["get_version"] = {
        "info": info,
        "modules": modules,
        "detected_models": detected,
        "models_by_id": models_by_id,
      }

    if "print" in data:
      append_to_rotating_file(LOG_FILE, _mask_mqtt_payload(msg.payload.decode()))

    #print(data)

    if AUTO_SPEND:
        processMessage(data)

    # Layer tracking is independent of the legacy upfront-spending switch.
    # It must continue receiving telemetry whenever it is enabled.
    if TRACK_LAYER_USAGE:
        FILAMENT_TRACKER.on_message(data)
      
    # Save external spool tray data
    if "print" in data and "vt_tray" in data["print"]:
      LAST_AMS_CONFIG["vt_tray"] = data["print"]["vt_tray"]
      external_tray = LAST_AMS_CONFIG["vt_tray"] or {}
      external_spools = fetchSpools(True)
      external_assigned = next((spool for spool in external_spools if spool.get("extra", {}).get("active_tray") == json.dumps(f"{PRINTER_ID}_{EXTERNAL_SPOOL_AMS_ID}_{EXTERNAL_SPOOL_ID}")), None)
      external_has_material = any(str(external_tray.get(field) or "").strip() for field in ("tray_type", "tray_sub_brands", "tray_info_idx", "setting_id"))
      external_empty = not external_has_material
      if PENDING_EXTERNAL_OPERATION == "clear" and external_empty:
        clear_active_spool_for_tray(EXTERNAL_SPOOL_AMS_ID, EXTERNAL_SPOOL_ID)
        PENDING_EXTERNAL_OPERATION = None
        external_assigned = None
      elif PENDING_EXTERNAL_OPERATION == "clear" and not external_empty:
        # The clear command was acknowledged, but the stable EX status still
        # contains material. Unlock the tray and keep its assignment intact.
        PENDING_EXTERNAL_OPERATION = None
      elif PENDING_EXTERNAL_OPERATION == "fill" and not external_empty:
        # A stable, populated EX status completes the fill operation.
        PENDING_EXTERNAL_OPERATION = None
      external_decision = "FACH_LEER" if external_empty else ("ZUGEORDNET" if external_assigned else "NICHT_ZUGEORDNET")

    # Save ams spool data
    if "print" in data and "ams" in data["print"] and "ams" in data["print"]["ams"]:
      LAST_AMS_CONFIG["ams"] = copy.deepcopy(data["print"]["ams"]["ams"])
      for ams in LAST_AMS_CONFIG["ams"]:
        for tray in ams.get("tray", []):
          if not str(tray.get("tray_uuid") or "").strip() and not any(str(tray.get(field) or "").strip() for field in ("tray_type", "tray_sub_brands")):
            LAST_CONFIRMED_AMS_FILAMENT_SETTINGS.pop(_ams_tray_key(ams.get("id"), tray.get("id")), None)
      # Do not apply ACK/cache values before evaluating physical AMS status.
      # The printer may echo the requested Fill values even when the tray is empty.
      LAST_AMS_CONFIG_GENERATION += 1
      spool_list = fetchSpools(True)
      ams_log_state = [
        {"id": ams.get("id"), "trays": [
          {key: tray.get(key) for key in ("id", "tray_sub_brands", "tray_color", "remain", "tray_uuid")}
          for tray in ams.get("tray", [])
        ]}
        for ams in LAST_AMS_CONFIG["ams"]
      ]
      log_ams = LOG_AMS_MODE != "none" and (
        FORCE_AMS_STATUS_LOG or LOG_AMS_MODE == "everything" or ams_log_state != LAST_LOGGED_AMS_STATE
      )
      FORCE_AMS_STATUS_LOG = False
      if log_ams:
        LAST_LOGGED_AMS_STATE = ams_log_state
      for ams in LAST_AMS_CONFIG["ams"]:
        for tray in ams["tray"]:
          raw_uuid = str(tray.get("tray_uuid") or "")
          # A reported all-zero UUID still means a physical spool is present
          # (typically a non-RFID/third-party spool). Only an actually missing
          # UUID is evidence that the tray is physically empty.
          uuid_empty = not raw_uuid.strip()
          raw_type = str(tray.get("tray_type") or "")
          raw_brand = str(tray.get("tray_sub_brands") or "")
          raw_color = str(tray.get("tray_color") or "")
          profile_idx = str(tray.get("tray_info_idx") or "").strip()
          setting_idx = str(tray.get("setting_id") or "").strip()
          has_non_default_color = raw_color.strip().upper() not in {"", "FFFFFFFF"}
          tray["ams_empty"] = (
            uuid_empty
            and not raw_type.strip()
            and not raw_brand.strip()
            and not profile_idx
            and not setting_idx
            and not has_non_default_color
          )
          active_tray_key = json.dumps(f"{PRINTER_ID}_{ams['id']}_{tray['id']}")
          assigned_spool = next((spool for spool in spool_list if spool.get("extra", {}).get("active_tray") == active_tray_key), None)
          # Bambu's explicit "no spool" state (empty fields, often zero UUID)
          # is authoritative even without an OSM Clear button action.
          if tray["ams_empty"] and assigned_spool:
            clear_active_spool_for_tray(ams["id"], tray.get("id"))
            assigned_spool = None
          loading_status = str(tray.get("tray_status") or tray.get("status") or "").lower()
          is_loading = loading_status in {"loading", "unloading", "changing", "load", "unload"}
          raw_decision = "LADEVORGANG" if is_loading else ("FACH_LEER" if tray["ams_empty"] else ("ZUGEORDNET" if assigned_spool else ("NICHT_ZUGEORDNET" if raw_uuid or raw_type or raw_brand or raw_color else "UNBEKANNT")))
          confirmation_key = _ams_tray_key(ams["id"], tray.get("id"))
          if confirmation_key in PENDING_AMS_STATUS_CONFIRMATIONS:
            pending_label, pending_started, operation = PENDING_AMS_STATUS_CONFIRMATIONS[confirmation_key]
            tray_uuid_value = str(tray.get("tray_uuid") or "")
            if operation == "clear" and not str(tray.get("tray_type") or "").strip() and not str(tray.get("tray_sub_brands") or "").strip():
              PENDING_AMS_STATUS_CONFIRMATIONS.pop(confirmation_key, None)
              AMS_STATUS_SAMPLES.pop(confirmation_key, None)
              clear_active_spool_for_tray(ams["id"], tray.get("id"))
              continue
            sample = tuple(str(tray.get(field) or "") for field in ("tray_type", "tray_sub_brands", "tray_color", "tray_info_idx", "setting_id", "remain"))
            samples = AMS_STATUS_SAMPLES.setdefault(confirmation_key, {"last": None, "count": 0, "attempts": 0})
            samples["attempts"] += 1
            if samples["last"] == sample:
              samples["count"] += 1
            else:
              samples["last"] = sample
              samples["count"] = 1
            if samples["count"] < 3 and samples["attempts"] < AMS_STATUS_QUERY_ATTEMPTS:
              continue
            AMS_STATUS_SAMPLES.pop(confirmation_key, None)
            stable_status = samples["count"] >= 3
            if not stable_status:
              PENDING_AMS_STATUS_CONFIRMATIONS.pop(confirmation_key)
              log(f"AMS {('Clear' if operation == 'clear' else 'Fill')} abgebrochen für {pending_label}: Fachstatus nicht eindeutig")
              clear_ams_tray_assignment(ams["id"], tray.get("id"))
              continue
            tray_is_empty = (
                not tray_uuid_value.strip()
                and not str(tray.get("tray_type") or "").strip()
                and not str(tray.get("tray_sub_brands") or "").strip()
            )
            tray["ams_empty"] = tray_is_empty
            if tray_is_empty:
              PENDING_AMS_STATUS_CONFIRMATIONS.pop(confirmation_key)
              if operation != "clear":
                log(f"AMS Fill fehlgeschlagen für {pending_label}: Fach weiterhin leer")
              clear_active_spool_for_tray(ams["id"], tray.get("id"))
            elif tray.get("tray_type") or tray.get("tray_sub_brands") or tray.get("tray_color"):
              PENDING_AMS_STATUS_CONFIRMATIONS.pop(confirmation_key)
              if operation == "clear":
                log(f"AMS Clear fehlgeschlagen für {pending_label}: Fach weiterhin belegt")
          if "tray_sub_brands" in tray:
            if log_ams:
              log(
                  f"    - [{num2letter(ams['id'])}{int(tray['id']) + 1}] {tray.get('tray_sub_brands', '')} {tray.get('tray_color', '')} ({str(tray.get('remain', '---')).zfill(3)}%) [[ {tray.get('tray_uuid', '')} ]]")

            found = False
            tray_uuid = str(tray.get("tray_uuid") or "")
            zero_uuid = "00000000000000000000000000000000"

            if not tray_uuid or tray_uuid == zero_uuid:
              # Third-party/non-RFID spool: Bambu cannot identify the physical spool.
              # OpenSpoolMan can, because Fill/assignment stores its tray in Spoolman's
              # active_tray extra field. Prefer that authoritative assignment.
              active_tray = json.dumps(f"{PRINTER_ID}_{ams['id']}_{tray['id']}")
              for spool in spool_list:
                if spool.get("extra", {}).get("active_tray") != active_tray:
                  continue
                found = True
                filament = spool.get("filament") or {}
                vendor = (filament.get("vendor") or {}).get("name") or ""
                material = filament.get("material") or ""
                name = filament.get("name") or ""
                description = " - ".join(value for value in (material, name, vendor) if value)
                if log_ams:
                  log(f"      - Spool #{spool.get('id')}: {description or 'zugeordnet'}")
                break
            else:
              for spool in spool_list:
                if not spool.get("extra", {}).get("tag"):
                  continue
                try:
                  tag = json.loads(spool["extra"]["tag"])
                except (TypeError, ValueError):
                  continue
                if tag != tray_uuid:
                  continue

                found = True
                setActiveTray(spool['id'], spool["extra"], ams['id'], tray["id"])
                filament = spool.get("filament") or {}
                vendor = (filament.get("vendor") or {}).get("name") or ""
                material = filament.get("material") or ""
                name = filament.get("name") or ""
                description = " - ".join(value for value in (material, name, vendor) if value)
                if log_ams:
                  log(f"      - Spool #{spool.get('id')}: {description or 'RFID zugeordnet'}")
                break

            if not found and (not tray_uuid or tray_uuid == zero_uuid):
              if log_ams:
                log("      - Fach leer" if tray.get("ams_empty") else "      - Keine Spule")
            elif not found:
              if log_ams:
                log("      - Keine Spule")
              tray["unmapped_bambu_tag"] = tray_uuid
              tray["issue"] = True

              # Read-only AMS synchronization:
              # Never clear either the printer material or OpenSpoolMan's assignment
              # merely because this push_status has no/mismatched Bambu RFID UUID.
              # Fill and explicit Clear are the only operations allowed to mutate a tray.
              pass
          else:
            # Passive status packets never remove a durable mapping. Only an
            # explicit Clear or a confirmed Fill/Clear result may mutate it.
            if log_ams:
              log(
                  f"    - [{num2letter(ams['id'])}{int(tray['id']) + 1}]")
              log("      - Fach leer" if tray.get("ams_empty") else "      - Keine Spule")

      # Keep the external spool in the normal status output, after A1-A4.
      external_active_tray = json.dumps(f"{PRINTER_ID}_{EXTERNAL_SPOOL_AMS_ID}_{EXTERNAL_SPOOL_ID}")
      external_assigned = next(
        (spool for spool in spool_list if spool.get("extra", {}).get("active_tray") == external_active_tray),
        None,
      )
      if log_ams:
        if external_assigned:
          filament = external_assigned.get("filament") or {}
          vendor = (filament.get("vendor") or {}).get("name") or ""
          material = filament.get("material") or ""
          name = filament.get("name") or ""
          description = " - ".join(value for value in (material, name, vendor) if value)
          log(f"    - [EX] Spool #{external_assigned.get('id')}: {description or 'zugeordnet'}")
        else:
          log("    - [EX] Keine Spule")

  except Exception:
    traceback.print_exc()

def on_connect(client, userdata, flags, rc):
  global MQTT_CLIENT_CONNECTED
  MQTT_CLIENT_CONNECTED = (rc == 0)
  meanings = {
    0: "Connection accepted",
    1: "Unacceptable protocol version",
    2: "Identifier rejected",
    3: "Server unavailable",
    4: "Bad username or password",
    5: "Not authorized",
  }
  meaning = meanings.get(rc, mqtt.error_string(rc))
  log(f"Connection result code {rc}: {meaning}")
  if rc != 0:
    log("MQTT authentication was rejected; no subscribe or publish will be attempted.")
    return

  topic = f"device/{PRINTER_ID}/report"
  sub_result = client.subscribe(topic)
  subscribe_code = sub_result[0] if isinstance(sub_result, tuple) else sub_result
  if subscribe_code == mqtt.MQTT_ERR_SUCCESS:
    subscribe_result = "OK"
  else:
    subscribe_result = f"Fehler {subscribe_code}: {mqtt.error_string(subscribe_code)}"
  log(f"Subscribed to {topic}; Result: {subscribe_result}")

  publish(client, GET_VERSION)
  publish(client, PUSH_ALL)

def on_disconnect(client, userdata, rc):
  global MQTT_CLIENT_CONNECTED
  MQTT_CLIENT_CONNECTED = False
  disconnect_meanings = {
    0: "Normal disconnection",
    7: "Connection lost",
  }
  meaning = disconnect_meanings.get(rc, mqtt.error_string(rc))
  log(f"Disconnected with result code {rc}: {meaning}")

def async_subscribe():
  global MQTT_CLIENT
  global MQTT_CLIENT_CONNECTED

  MQTT_CLIENT_CONNECTED = False
  MQTT_CLIENT = mqtt.Client()
  MQTT_CLIENT.username_pw_set("bblp", PRINTER_CODE)
  ssl_ctx = ssl.create_default_context()
  ssl_ctx.check_hostname = False
  ssl_ctx.verify_mode = ssl.CERT_NONE
  MQTT_CLIENT.tls_set_context(ssl_ctx)
  MQTT_CLIENT.tls_insecure_set(True)
  MQTT_CLIENT.on_connect = on_connect
  MQTT_CLIENT.on_disconnect = on_disconnect
  MQTT_CLIENT.on_message = on_message
  reconnect_started_at = time.monotonic()
  reconnect_backoff_logged = False
  while True:
    try:
      log("Trying to connect ...", flush=True)
      MQTT_CLIENT.connect(PRINTER_IP, 8883, MQTT_KEEPALIVE)
      MQTT_CLIENT.loop_start()
      return
    except Exception as exc:
      elapsed = time.monotonic() - reconnect_started_at
      retry_delay = 15 if elapsed < 10 * 60 else 60
      log(
        f"Connection failed: {exc}, retrying in {retry_delay} seconds...",
        flush=True,
      )
      if retry_delay == 60 and not reconnect_backoff_logged:
        log(
          "Connection retry interval changed from 15 to 60 seconds after 10 minutes.",
          flush=True,
        )
        reconnect_backoff_logged = True
      time.sleep(retry_delay)

def init_mqtt(daemon: bool = False):
  # Start the asynchronous processing in a separate thread
  thread = Thread(target=async_subscribe, daemon=daemon)
  thread.start()

def getLastAMSConfig():
  global LAST_AMS_CONFIG
  return LAST_AMS_CONFIG


def getDetectedAmsModelsById():
  global LAST_AMS_CONFIG
  detected = LAST_AMS_CONFIG.get("get_version", {}).get("models_by_id") or {}
  return dict(detected)


def getMqttClient():
  global MQTT_CLIENT
  return MQTT_CLIENT

def isMqttClientConnected():
  global MQTT_CLIENT_CONNECTED

  return MQTT_CLIENT_CONNECTED


def reconfigure_printer(printer_id, access_code, printer_ip, wait_seconds=12):
  """Apply a selected cloud printer and reconnect MQTT immediately.

  Returns True when the new MQTT session is connected within wait_seconds.
  """
  global PRINTER_ID, PRINTER_CODE, PRINTER_IP, MQTT_CLIENT, MQTT_CLIENT_CONNECTED
  PRINTER_ID = (printer_id or "").upper()
  PRINTER_CODE = access_code or ""
  PRINTER_IP = printer_ip or ""
  MQTT_CLIENT_CONNECTED = False

  try:
    if MQTT_CLIENT:
      MQTT_CLIENT.disconnect()
  except Exception as exc:
    log(f"MQTT disconnect during reconfiguration failed: {exc}")

  # Update the existing productive client and force a connection immediately,
  # rather than waiting for the background 15-second retry cycle.
  try:
    if MQTT_CLIENT:
      MQTT_CLIENT.username_pw_set("bblp", PRINTER_CODE)
      MQTT_CLIENT.connect(PRINTER_IP, 8883, MQTT_KEEPALIVE)
  except Exception as exc:
    log(f"MQTT immediate reconnect after reconfiguration failed: {exc}")

  deadline = time.time() + max(0, wait_seconds)
  while time.time() < deadline:
    if MQTT_CLIENT_CONNECTED:
      return True
    time.sleep(0.2)
  return bool(MQTT_CLIENT_CONNECTED)
