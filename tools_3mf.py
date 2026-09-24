import requests
import zipfile
import tempfile
import xml.etree.ElementTree as ET
import pycurl
import urllib.parse
import os
import re
import time
import io
import json
from datetime import datetime
import config as app_config
from urllib.parse import urlparse
from logger import log


_BBL_PATH_CACHE = {}


def parse_ftp_listing(line):
    parts = line.split(maxsplit=8)
    if len(parts) < 9:
        return None
    return {
        'permissions': parts[0], 'links': int(parts[1]), 'owner': parts[2],
        'group': parts[3], 'size': int(parts[4]), 'month': parts[5],
        'day': int(parts[6]), 'time_or_year': parts[7], 'name': parts[8]
    }


def get_base_name(filename):
    return filename.rsplit('.', 1)[0]


def parse_date(item):
    try:
        date_str = f"{item['month']} {item['day']} {item['time_or_year']}"
        return datetime.strptime(date_str, "%b %d %H:%M")
    except ValueError:
        return None


def get_filament_order(file):
    filament_order = {}
    switch_count = 0
    for line in file:
        match_filament = re.match(r"^M620 S(\d+)[^;\r\n]*", line.decode("utf-8").strip())
        if match_filament:
            filament = int(match_filament.group(1))
            if filament not in filament_order and int(filament) != 255:
                filament_order[int(filament)] = switch_count
            switch_count += 1
    if len(filament_order) == 0:
        filament_order = {1: 0}
    return filament_order


def setupPycurlConnection(ftp_user, ftp_pass):
    c = pycurl.Curl()
    c.setopt(c.USERPWD, f"{ftp_user}:{ftp_pass}")
    c.setopt(c.SSL_VERIFYPEER, 0)
    c.setopt(c.SSL_VERIFYHOST, 0)
    c.setopt(c.FTP_SSL, c.FTPSSL_ALL)
    c.setopt(c.FTPSSLAUTH, c.FTPAUTH_TLS)
    c.setopt(c.CONNECTTIMEOUT, 5)
    c.setopt(c.TIMEOUT, 180)
    return c


def _ftp_read(remote_path, directory=False, connection=None):
    buffer = io.BytesIO()
    c = connection or setupPycurlConnection("bblp", app_config.PRINTER_CODE)
    owns_connection = connection is None
    try:
        encoded = urllib.parse.quote(remote_path if remote_path.startswith('/') else '/' + remote_path)
        c.setopt(c.URL, f"ftps://{app_config.PRINTER_IP}{encoded}")
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(c.DIRLISTONLY, bool(directory))
        c.perform()
        return buffer.getvalue()
    finally:
        if owns_connection:
            c.close()


def _current_print_context():
    try:
        import mqtt_bambulab
        state = getattr(mqtt_bambulab, "PRINTER_STATE", {}).get("print", {}) or {}
        return {
            "gcode_file": state.get("gcode_file"),
            "subtask_name": state.get("subtask_name"),
            "subtask_id": state.get("subtask_id"),
            "task_id": state.get("task_id"),
            "print_type": state.get("print_type"),
            "gcode_state": state.get("gcode_state"),
        }
    except Exception:
        return {}


def _normalize_printer_3mf_path(path):
    if not path:
        return None
    path = urllib.parse.unquote(str(path)).strip()
    if path.startswith("/sdcard/"):
        path = "/" + path[len("/sdcard/"):]
    if not path.startswith("/"):
        path = "/" + path
    return path


def _find_bbl_for_subtask(subtask_name):
    if not subtask_name:
        return None
    started = time.monotonic()
    connection = setupPycurlConnection("bblp", app_config.PRINTER_CODE)
    try:
        names = _ftp_read("/cache/", directory=True, connection=connection).decode(
            "utf-8", errors="replace"
        ).splitlines()
        bbl_names = [name.strip() for name in names if name.strip().lower().endswith(".bbl")]
        log(f"[3MF] Suche BBL fuer Subtask '{subtask_name}' unter {len(bbl_names)} BBL-Dateien.")
        for name in reversed(bbl_names):
            try:
                raw = _ftp_read(f"/cache/{name}", connection=connection)
                job = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                continue
            if str(job.get("subtask_name") or "").strip() == str(subtask_name).strip():
                log(
                    f"[3MF] Passende BBL gefunden: /cache/{name} "
                    f"nach {time.monotonic() - started:.2f}s"
                )
                return name, job
    except Exception as exc:
        log(f"[3MF] BBL-Verzeichnis konnte nicht gelesen werden: {exc}")
        return None
    finally:
        connection.close()
    log(
        f"[3MF] Keine passende BBL fuer Subtask '{subtask_name}' gefunden "
        f"nach {time.monotonic() - started:.2f}s."
    )
    return None


def _resolved_bbl_3mf_for_current_job():
    context = _current_print_context()
    cache_key = (
        str(context.get("task_id") or ""),
        str(context.get("subtask_id") or ""),
        str(context.get("subtask_name") or ""),
    )
    if cache_key in _BBL_PATH_CACHE:
        return _BBL_PATH_CACHE[cache_key]

    match = _find_bbl_for_subtask(context.get("subtask_name"))
    if not match:
        return None

    bbl_name, job = match
    file_path = job.get("file path")
    resolved = _normalize_printer_3mf_path(file_path)
    log(f"[3MF] BBL /cache/{bbl_name}: file path={file_path!r} -> FTP={resolved!r}")
    if resolved and resolved.lower().endswith(".3mf"):
        _BBL_PATH_CACHE[cache_key] = resolved
        return resolved
    return None


def resolve_local_print_3mf(source):
    context = _current_print_context()
    source = str(source or "").strip()
    log(
        "[3MF] Druckkontext: "
        f"gcode_file={context.get('gcode_file')!r}, "
        f"subtask_name={context.get('subtask_name')!r}, "
        f"subtask_id={context.get('subtask_id')!r}, "
        f"task_id={context.get('task_id')!r}, "
        f"print_type={context.get('print_type')!r}, "
        f"gcode_state={context.get('gcode_state')!r}"
    )
    log(f"[3MF] Vom MQTT-Tracking uebergebener Dateiwert: {source!r}")

    lower = source.lower()
    if lower.endswith(".3mf"):
        resolved = _normalize_printer_3mf_path(source)
        log(f"[3MF] Direkter 3MF-Pfad erkannt: {resolved}")
        return resolved

    if lower.endswith(".bbl"):
        bbl_path = source if source.startswith('/') else f"/cache/{os.path.basename(source)}"
        try:
            job = json.loads(_ftp_read(bbl_path).decode("utf-8", errors="replace"))
            file_path = job.get("file path")
            resolved = _normalize_printer_3mf_path(file_path)
            log(f"[3MF] BBL {bbl_path} -> file path={file_path!r} -> FTP={resolved!r}")
            return resolved
        except Exception as exc:
            log(f"[3MF] BBL {bbl_path} konnte nicht ausgewertet werden: {exc}")
            return None

    resolved = _resolved_bbl_3mf_for_current_job()
    if resolved:
        return resolved

    log("[3MF] Keine eindeutige 3MF-Datei fuer den aktuellen Druck ermittelt.")
    return None


def download3mfFromCloud(url, destFile, progress_callback=None):
    log("Downloading 3MF file from cloud...")
    response = requests.get(url, stream=True, timeout=(5, 180))
    response.raise_for_status()
    total = int(response.headers.get("content-length") or 0)
    downloaded = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        destFile.write(chunk)
        downloaded += len(chunk)
        if progress_callback:
            progress_callback(downloaded, total)


def _append_unique_path(paths, remote_path):
    if not remote_path:
        return
    remote_path = str(remote_path).strip()
    if not remote_path:
        return
    if not remote_path.startswith('/'):
        remote_path = '/' + remote_path
    if remote_path not in paths:
        paths.append(remote_path)


def download3mfFromFTP(filename, destFile, progress_callback=None):
    log("Downloading 3MF file from FTP...")
    ftp_host = app_config.PRINTER_IP
    ftp_user = "bblp"
    ftp_pass = app_config.PRINTER_CODE
    local_path = destFile.name

    filename = str(filename or "").strip()
    if not filename:
        raise RuntimeError("FTP Download abgebrochen: leerer Dateiname")
    if filename.startswith("/sdcard/"):
        filename = "/" + filename[len("/sdcard/"):]

    remote_paths = []
    if filename.startswith("/") and filename.lower().endswith(".3mf"):
        _append_unique_path(remote_paths, filename)
    else:
        base_name = os.path.basename(filename)

        # Resolve the authoritative path from the matching .bbl first.  The
        # display filename often does not exist in /cache and used to cost a
        # full timeout before the real path was attempted.
        bbl_resolved = _resolved_bbl_3mf_for_current_job()
        _append_unique_path(remote_paths, bbl_resolved)

        _append_unique_path(remote_paths, f"/cache/{base_name}")
        _append_unique_path(remote_paths, f"/{base_name}")
        _append_unique_path(remote_paths, f"/sdcard/{base_name}")

    last_error = None
    reconnect_codes = {7, 28, 35, 52, 55, 56}
    def configure_progress(connection):
        if progress_callback:
            connection.setopt(connection.NOPROGRESS, False)
            connection.setopt(connection.XFERINFOFUNCTION, lambda _download_total, downloaded, _upload_total, _uploaded: progress_callback(downloaded, _download_total))

    c = setupPycurlConnection(ftp_user, ftp_pass)
    configure_progress(c)
    try:
        for path_index, remote_path in enumerate(remote_paths, start=1):
            encoded_remote_path = urllib.parse.quote(remote_path)
            url = f"ftps://{ftp_host}{encoded_remote_path}"
            log(f"[3MF] FTP Download ({path_index}/{len(remote_paths)}): {remote_path}")

            for attempt in range(2):
                with open(local_path, "wb") as f:
                    try:
                        c.setopt(c.URL, url)
                        c.setopt(c.WRITEDATA, f)
                        c.perform()
                        if os.path.getsize(local_path) <= 0:
                            raise RuntimeError(f"FTP lieferte eine leere Datei: {remote_path}")
                        log(f"[3MF] FTP Download erfolgreich: {remote_path}")
                        return remote_path
                    except pycurl.error as exc:
                        last_error = exc
                        err_code = exc.args[0]
                        if err_code in reconnect_codes:
                            try:
                                c.close()
                            except Exception:
                                pass
                            c = setupPycurlConnection(ftp_user, ftp_pass)
                            configure_progress(c)
                        if attempt == 0 and err_code in reconnect_codes:
                            continue
                        if err_code == 9:
                            log(f"[3MF] Zugriff verweigert: {remote_path}")
                        elif err_code == 78:
                            log(f"[3MF] Pfadkandidat nicht vorhanden: {remote_path}")
                        else:
                            log(f"[3MF] FTP Fehler {err_code} fuer {remote_path}: {exc}")
                        break
                    except Exception as exc:
                        last_error = exc
                        log(f"[3MF] FTP Fehler fuer {remote_path}: {exc}")
                        break
    finally:
        if c is not None:
            try:
                c.close()
            except Exception:
                pass

    raise RuntimeError(
        f"3MF-Datei konnte nicht vom Drucker geladen werden; letzter Fehler: {last_error}"
    )


def download3mfFromLocalFilesystem(path, destFile, progress_callback=None):
    total = os.path.getsize(path) if os.path.exists(path) else 0
    downloaded = 0
    with open(path, "rb") as src_file:
        while True:
            chunk = src_file.read(64 * 1024)
            if not chunk:
                break
            destFile.write(chunk)
            downloaded += len(chunk)
            if progress_callback:
                progress_callback(downloaded, total)


def getMetaDataFrom3mf(url):
    try:
        metadata = {}
        original_url = url

        if not str(url or "").startswith(("http", "local:", "file://", "ftp://", "ftps://")):
            resolved = resolve_local_print_3mf(url)
            if not resolved:
                log(f"[3MF] Abbruch: keine 3MF-Datei zu {original_url!r} ermittelbar.")
                return {}
            url = resolved

        with tempfile.NamedTemporaryFile(delete_on_close=False, delete=True, suffix=".3mf") as temp_file:
            temp_file_name = temp_file.name
            downloaded_remote_path = None
            if url.startswith("http"):
                download3mfFromCloud(url, temp_file)
            elif url.startswith("local:"):
                download3mfFromLocalFilesystem(url.replace("local:", ""), temp_file)
            elif url.startswith(("file://", "ftp://", "ftps://")):
                parsed_source = urlparse(url)
                file_path = parsed_source.path or parsed_source.netloc
                downloaded_remote_path = download3mfFromFTP(file_path, temp_file)
            else:
                downloaded_remote_path = download3mfFromFTP(url, temp_file)

            temp_file.close()

            if downloaded_remote_path:
                metadata["model_path"] = downloaded_remote_path
                metadata["file"] = os.path.basename(downloaded_remote_path)
            else:
                metadata["model_path"] = url
                parsed_url = urlparse(url)
                metadata["file"] = os.path.basename(parsed_url.path or parsed_url.netloc or url)

            log(
                f"[3MF] Verwende 3MF: {metadata['model_path']!r}; "
                f"temporaer={temp_file_name}"
            )

            with zipfile.ZipFile(temp_file_name, 'r') as z:
                slice_info_path = "Metadata/slice_info.config"
                if slice_info_path not in z.namelist():
                    log(f"[3MF] '{slice_info_path}' fehlt im Archiv.")
                    return {}

                with z.open(slice_info_path) as slice_info_file:
                    tree = ET.parse(slice_info_file)
                    root = tree.getroot()
                    for meta in root.findall(".//plate/metadata"):
                        if meta.attrib.get("key") == "index":
                            metadata["plateID"] = meta.attrib.get("value", "")

                    usage = {}
                    filaments = {}
                    filamentId = 1
                    for plate in root.findall(".//plate"):
                        for filament in plate.findall(".//filament"):
                            used_g = filament.attrib.get("used_g")
                            usage[filamentId] = used_g
                            filaments[filamentId] = {
                                "id": filamentId,
                                "tray_info_idx": filament.attrib.get("tray_info_idx"),
                                "type": filament.attrib.get("type"),
                                "color": filament.attrib.get("color"),
                                "used_g": used_g,
                                "used_m": filament.attrib.get("used_m")
                            }
                            filamentId += 1
                    metadata["filaments"] = filaments
                    metadata["usage"] = usage

                if not metadata.get("plateID"):
                    log("[3MF] Keine Plate-ID in slice_info.config gefunden.")
                    return {}

                metadata["image"] = time.strftime('%Y%m%d%H%M%S') + ".png"
                image_path = "Metadata/plate_" + metadata["plateID"] + ".png"
                if image_path in z.namelist():
                    os.makedirs(os.path.join(os.getcwd(), 'static', 'prints'), exist_ok=True)
                    with z.open(image_path) as source_file:
                        with open(os.path.join(os.getcwd(), 'static', 'prints', metadata["image"]), 'wb') as target_file:
                            target_file.write(source_file.read())
                else:
                    log(f"[3MF] Thumbnail fehlt: {image_path}")
                    metadata["image"] = ""

                gcode_path = "Metadata/plate_" + metadata["plateID"] + ".gcode"
                metadata["gcode_path"] = gcode_path
                if gcode_path in z.namelist():
                    with z.open(gcode_path) as gcode_file:
                        metadata["filamentOrder"] = get_filament_order(gcode_file)

                log(
                    f"[3MF] Metadaten OK: file={metadata.get('file')!r}, "
                    f"plate={metadata.get('plateID')!r}, filaments={len(metadata.get('filaments', {}))}, "
                    f"image={metadata.get('image')!r}"
                )
                return metadata

    except requests.exceptions.RequestException as e:
        log(f"[3MF] Fehler beim Cloud-Download: {e}")
        return {}
    except zipfile.BadZipFile:
        log("[3MF] Die heruntergeladene Datei ist kein gueltiges 3MF/ZIP-Archiv.")
        return {}
    except ET.ParseError:
        log("[3MF] XML in der 3MF konnte nicht gelesen werden.")
        return {}
    except Exception as e:
        log(f"[3MF] Unerwarteter Fehler: {e}")
        return {}


def getMetaDataFromLocal3mf(path: str, model_path: str | None = None) -> dict:
    # Parse an already downloaded 3MF without starting another transfer.
    metadata = {
        "model_path": model_path or path,
        "file": os.path.basename(model_path or path),
    }
    try:
        with zipfile.ZipFile(path, "r") as z:
            slice_info_path = "Metadata/slice_info.config"
            if slice_info_path not in z.namelist():
                log(f"[3MF] '{slice_info_path}' fehlt im lokalen Archiv.")
                return {}

            with z.open(slice_info_path) as slice_info_file:
                tree = ET.parse(slice_info_file)
                root = tree.getroot()
                for meta in root.findall(".//plate/metadata"):
                    if meta.attrib.get("key") == "index":
                        metadata["plateID"] = meta.attrib.get("value", "")

                usage = {}
                filaments = {}
                filament_id = 1
                for plate in root.findall(".//plate"):
                    for filament in plate.findall(".//filament"):
                        used_g = filament.attrib.get("used_g")
                        usage[filament_id] = used_g
                        filaments[filament_id] = {
                            "id": filament_id,
                            "tray_info_idx": filament.attrib.get("tray_info_idx"),
                            "type": filament.attrib.get("type"),
                            "color": filament.attrib.get("color"),
                            "used_g": used_g,
                            "used_m": filament.attrib.get("used_m"),
                        }
                        filament_id += 1
                metadata["filaments"] = filaments
                metadata["usage"] = usage

            if not metadata.get("plateID"):
                log("[3MF] Keine Plate-ID in lokalem slice_info.config gefunden.")
                return {}

            metadata["image"] = time.strftime("%Y%m%d%H%M%S") + ".png"
            image_path = "Metadata/plate_" + metadata["plateID"] + ".png"
            if image_path in z.namelist():
                image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "prints")
                os.makedirs(image_dir, exist_ok=True)
                with z.open(image_path) as source_file:
                    with open(os.path.join(image_dir, metadata["image"]), "wb") as target_file:
                        target_file.write(source_file.read())
            else:
                metadata["image"] = ""

            gcode_path = "Metadata/plate_" + metadata["plateID"] + ".gcode"
            metadata["gcode_path"] = gcode_path
            if gcode_path in z.namelist():
                with z.open(gcode_path) as gcode_file:
                    metadata["filamentOrder"] = get_filament_order(gcode_file)

            log(
                f"[3MF] Lokale Metadaten OK: file={metadata.get('file')!r}, "
                f"plate={metadata.get('plateID')!r}, filaments={len(metadata.get('filaments', {}))}"
            )
            return metadata
    except zipfile.BadZipFile:
        log("[3MF] Die lokale Datei ist kein gültiges 3MF/ZIP-Archiv.")
    except ET.ParseError:
        log("[3MF] XML im lokalen 3MF konnte nicht gelesen werden.")
    except Exception as exc:
        log(f"[3MF] Fehler beim lokalen Parsen: {exc}")
    return {}
