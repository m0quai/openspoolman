

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
    TRACK_LAYER_USAGE,
    CLEAR_ASSIGNMENT_WHEN_EMPTY,
)
from messages import GET_VERSION, PUSH_ALL, AMS_FILAMENT_SETTING
from spoolman_service import spendFilaments, setActiveTray, fetchSpools, clear_active_spool_for_tray
from tools_3mf import getMetaDataFrom3mf
import time
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
# Last successfully acknowledged AMS material settings for non-RFID/third-party trays.
# P1/P1S can acknowledge ams_filament_setting with success and then emit sparse
# push_status tray objects whose material fields are empty. Keep the confirmed
# values locally so the UI does not immediately fall back to "No AMS material selected".
LAST_CONFIRMED_AMS_FILAMENT_SETTINGS = {}

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

  try:
    if (
      isinstance(message_to_send, dict)
      and "print" in message_to_send
      and bambu_mqtt_signing.certificate_is_valid()
    ):
      wire_payload = bambu_mqtt_signing.sign_message_json(message_to_send)
      log("MQTT print command signed using RSA-SHA256.")
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
    log(f"Sent {message_to_send} to topic device/{PRINTER_ID}/request")
    return True
  log(f"Failed to send message to topic device/{PRINTER_ID}/request")
  return False

def _ams_tray_key(ams_id, tray_id):
  return (str(ams_id), str(tray_id))

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

  if not publish(MQTT_CLIENT, ams_message):
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
  global LAST_AMS_CONFIG, LAST_AMS_CONFIG_GENERATION, PRINTER_STATE, PRINTER_STATE_LAST, PENDING_PRINT_METADATA, PRINTER_MODEL
  
  try:
    data = json.loads(msg.payload.decode())

    # Remember successfully acknowledged AMS writes. P1/P1S may return sparse
    # material fields in subsequent push_status messages for third-party spools.
    try:
      print_reply = data.get("print", {}) if isinstance(data, dict) else {}
      if (
        print_reply.get("command") == "ams_filament_setting"
        and print_reply.get("result") == "success"
        and print_reply.get("reason") == "success"
      ):
        _remember_confirmed_ams_filament_setting(print_reply)
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

    # Save ams spool data
    if "print" in data and "ams" in data["print"] and "ams" in data["print"]["ams"]:
      LAST_AMS_CONFIG["ams"] = copy.deepcopy(data["print"]["ams"]["ams"])
      _apply_confirmed_ams_filament_settings(LAST_AMS_CONFIG["ams"])
      LAST_AMS_CONFIG_GENERATION += 1
      spool_list = fetchSpools(True)
      for ams in LAST_AMS_CONFIG["ams"]:
        log(f"AMS [{num2letter(ams['id'])}] (hum: {ams['humidity']}, temp: {ams['temp']}ºC)")
        for tray in ams["tray"]:
          if "tray_sub_brands" in tray:
            log(
                f"    - [{num2letter(ams['id'])}{tray['id']}] {tray['tray_sub_brands']} {tray['tray_color']} ({str(tray['remain']).zfill(3)}%) [[ {tray['tray_uuid']} ]]")

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
                log(f"      - Spoolman Spool #{spool.get('id')}: {description or 'zugeordnet'}")
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
                log(f"      - Spoolman Spool #{spool.get('id')}: {description or 'RFID zugeordnet'}")
                break

            if not found and (not tray_uuid or tray_uuid == zero_uuid):
              log("      - Keine Spoolman-Spule diesem Tray zugeordnet.")
            elif not found:
              log("      - Not found. Update spool tag!")
              tray["unmapped_bambu_tag"] = tray_uuid
              tray["issue"] = True
              # Read-only AMS synchronization:
              # Never clear either the printer material or OpenSpoolMan's assignment
              # merely because this push_status has no/mismatched Bambu RFID UUID.
              # Fill and explicit Clear are the only operations allowed to mutate a tray.
              pass
          else:
            log(
                f"    - [{num2letter(ams['id'])}{tray['id']}]")
            log("      - No Spool!")

  except Exception:
    traceback.print_exc()

def on_connect(client, userdata, flags, rc):
  global MQTT_CLIENT_CONNECTED
  MQTT_CLIENT_CONNECTED = (rc == 0)
  meanings = {0: "accepted", 1: "unacceptable protocol version", 2: "identifier rejected", 3: "server unavailable", 4: "bad username/password", 5: "not authorized"}
  log(f"Connected with result code {rc} ({meanings.get(rc, 'unknown')})")
  if rc != 0:
    log("MQTT authentication was rejected; no subscribe or publish will be attempted.")
    return

  topic = f"device/{PRINTER_ID}/report"
  sub_result = client.subscribe(topic)
  log(f"Subscribed to {topic}; result={sub_result}")

  publish(client, GET_VERSION)
  publish(client, PUSH_ALL)

def on_disconnect(client, userdata, rc):
  global MQTT_CLIENT_CONNECTED
  MQTT_CLIENT_CONNECTED = False
  log("Disconnected with result code " + str(rc))

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
  while True:
    try:
      log("🔄 Trying to connect ...", flush=True)
      MQTT_CLIENT.connect(PRINTER_IP, 8883, MQTT_KEEPALIVE)
      MQTT_CLIENT.loop_start()
      return
    except Exception as exc:
      log(f"⚠️ connection failed: {exc}, new try in 15 seconds...", flush=True)
      time.sleep(15)

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
