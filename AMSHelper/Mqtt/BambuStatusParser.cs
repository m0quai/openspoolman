using System;

namespace AMSHelper.Mqtt
{
    // Deliberately independent of MQTT transport. It only inspects fields that are
    // actually present. Unknown Bambu fields remain available through RawJson.
    public sealed class BambuStatusParser
    {
        public BambuStatusUpdate Parse(string json)
        {
            var u = new BambuStatusUpdate();
            if (string.IsNullOrEmpty(json))
            {
                return u;
            }

            u.HasCommand = TryGetValue(json, "command", out u.Command);
            u.HasSequenceId = TryGetValue(json, "sequence_id", out u.SequenceId);
                        u.HasActiveTray = TryGetValue(json, "tray_now", out u.ActiveTray);
            u.HasTargetTray = TryGetValue(json, "tray_tar", out u.TargetTray);
            u.HasPreviousTray = TryGetValue(json, "tray_pre", out u.PreviousTray);
            u.HasAmsStatus = TryGetValue(json, "ams_status", out u.AmsStatus);
            u.HasTrayExistBits = TryGetValue(json, "tray_exist_bits", out u.TrayExistBits);
            u.HasTrayReadingBits = TryGetValue(json, "tray_reading_bits", out u.TrayReadingBits);
            u.HasTrayReadDoneBits = TryGetValue(json, "tray_read_done_bits", out u.TrayReadDoneBits);
            u.HasCommandAmsId = TryGetValue(json, "ams_id", out u.CommandAmsId);
            u.HasCommandSlotId = TryGetValue(json, "slot_id", out u.CommandSlotId);
            u.HasCommandTarget = TryGetValue(json, "target", out u.CommandTarget);
            u.HasReason = TryGetValue(json, "reason", out u.Reason);
            u.HasResult = TryGetValue(json, "result", out u.Result);

            int amsPos = json.IndexOf("\"ams\"");
            if (amsPos >= 0)
            {
                // Nicht json.Substring(amsPos) erzeugen: grosse push_status-Pakete
                // verursachen auf dem ESP32 sonst erheblichen zusaetzlichen Heap-Druck.
                u.HasAmsId = TryGetValue(json, "ams_id", amsPos, out u.AmsId);
                ParseTrays(json, u);
            }
            return u;
        }

        public static int ParseTrayId(string value)
        {
            int result;
            return TryParseInt(value, out result) ? result : -1;
        }

        public static int ParseTrayBits(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return 0;
            }

            try
            {
                return Convert.ToInt32(value, 16);
            }
            catch
            {
                int result;
                return TryParseInt(value, out result) ? result : 0;
            }
        }

        public static bool IsFilamentChangeStatus(string value)
        {
            int status;
            if (!TryParseInt(value, out status))
            {
                return false;
            }

            return ((status >> 8) & 0xFF) == 1;
        }

        public static string InterpretAmsActivity(string value, bool unloading, out bool completed)
        {
            completed = false;
            int status;
            if (!TryParseInt(value, out status))
            {
                return null;
            }

            if (status == 0)
            {
                return null;
            }

            int main = (status >> 8) & 0xFF;
            int sub = status & 0xFF;
            if (main != 1)
            {
                return null;
            }

            if (unloading)
            {
                switch (sub)
                {
                    case 2:
                        return "ENTLADEN - Vorbereitung / Aufheizen";
                    case 3:
                        return "ENTLADEN - Filament wird geloest";
                    case 4:
                        return "ENTLADEN - Filament wird ins AMS zurueckgezogen";
                    default:
                        return "ENTLADEN - Schritt " + sub;
                }
            }

            switch (sub)
            {
                case 2:
                    return "LADEN - Vorbereitung / Aufheizen";
                case 3:
                    return "LADEN - Filamentweg vorbereiten";
                case 4:
                    return "LADEN - Filamentwechsel / Rueckzug";
                case 5:
                    return "LADEN - Filament wird zugefuehrt";
                case 6:
                    return "LADEN - Filament wird geprueft";
                case 7:
                    return "LADEN - Spuelen / Purge";
                default:
                    return "LADEN - Schritt " + sub;
            }
        }

        public static string DescribeAmsStatus(string value)
        {
            int status;
            if (!TryParseInt(value, out status))
            {
                return "unbekannter AMS-Status";
            }

            if (status == 0)
            {
                return "AMS bereit / Idle";
            }

            int main = (status >> 8) & 0xFF;
            int sub = status & 0xFF;
            if (main == 1)
            {
                switch (sub)
                {
                    case 2: return "Filamentwechsel - Vorbereitung / Aufheizen";
                    case 3: return "Filamentwechsel - Filament loesen / Wechsel vorbereiten";
                    case 4: return "Filamentwechsel - Rueckzug / Entladen";
                    case 5: return "Filamentwechsel - Filament zufuehren";
                    case 6: return "Filamentwechsel - Laden pruefen";
                    case 7: return "Filamentwechsel - Spuelen / Purge";
                    default: return "Filamentwechsel - Schritt " + sub;
                }
            }
            if (main == 2)
            {
                return "RFID-Erkennung - Schritt " + sub;
            }
            if (main == 3)
            {
                return "AMS Assistenz - Schritt " + sub;
            }
            if (main == 4)
            {
                return "AMS Kalibrierung - Schritt " + sub;
            }
            return "AMS Main " + main + ", Schritt " + sub;
        }

        public static string DescribeTrayId(string value, string role)
        {
            int tray = ParseTrayId(value);
            if (tray < 0)
            {
                return role + ": unbekannt";
            }
            if (tray == 255)
            {
                return role + ": kein AMS-Tray / kein AMS-Filament aktiv";
            }
            if (tray == 254)
            {
                return role + ": externe Spule";
            }

            int ams = tray / 4;
            int slot = tray % 4;
            if (ams == 0)
            {
                return role + ": Tray " + slot;
            }
            return role + ": AMS " + ams + " / Tray " + slot;
        }

        public static string DescribeTrayBits(string value, string role)
        {
            int bits = ParseTrayBits(value);
            if (bits == 0)
            {
                return role + ": kein Tray";
            }

            string result = role + ": ";
            bool first = true;
            for (int i = 0; i < 4; i++)
            {
                if ((bits & (1 << i)) != 0)
                {
                    if (!first)
                    {
                        result += ", ";
                    }
                    result += "Tray " + i;
                    first = false;
                }
            }
            return result;
        }

        private static bool TryParseInt(string value, out int result)
        {
            result = 0;
            if (string.IsNullOrEmpty(value))
            {
                return false;
            }
            try
            {
                result = int.Parse(value);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static void ParseTrays(string json, BambuStatusUpdate update)
        {
            int p = 0;
            while (p < json.Length)
            {
                int idKey = json.IndexOf("\"id\"", p);
                if (idKey < 0)
                {
                    break;
                }
                int objStart = json.LastIndexOf('{', idKey);
                int objEnd = FindObjectEnd(json, objStart);
                if (objStart < 0 || objEnd < 0)
                {
                    break;
                }
                string obj = json.Substring(objStart, objEnd - objStart + 1);
                string id;
                if (TryGetValue(obj, "id", out id))
                {
                    int slot;
                    if (TryParseSlot(id, out slot) && slot >= 0 && slot < update.Trays.Length)
                    {
                        var t = new BambuTrayUpdate();
                        t.Slot = slot;
                        t.Present = true;
                        t.HasId = true;
                        t.Id = id;
                        t.HasType = TryGetValue(obj, "tray_type", out t.Type);
                        t.HasColor = TryGetValue(obj, "tray_color", out t.Color);
                        t.HasUuid = TryGetValue(obj, "tray_uuid", out t.Uuid);
                        t.HasRemain = TryGetValue(obj, "remain", out t.Remain);
                        t.HasTagUid = TryGetValue(obj, "tag_uid", out t.TagUid);
                        if (t.HasType || t.HasColor || t.HasUuid || t.HasRemain || t.HasTagUid)
                        {
                            update.Trays[slot] = t;
                        }
                    }
                }
                p = objEnd + 1;
            }
        }

        private static bool TryParseSlot(string s, out int value)
        {
            value = -1;
            if (s == null || s.Length != 1 || s[0] < '0' || s[0] > '3')
            {
                return false;
            }
            value = s[0] - '0';
            return true;
        }

        private static int FindObjectEnd(string s, int start)
        {
            if (start < 0)
            {
                return -1;
            }
            int depth = 0; bool quoted = false; bool escape = false;
            for (int i = start; i < s.Length; i++)
            {
                char c = s[i];
                if (quoted)
                {
                    if (escape)
                    {
                        escape = false;
                    }
                    else if (c == '\\')
                    {
                        escape = true;
                    }
                    else if (c == '"')
                    {
                        quoted = false;
                    }
                    continue;
                }
                if (c == '"')
                {
                    quoted = true;
                }
                else if (c == '{')
                {
                    depth++;
                }
                else if (c == '}' && --depth == 0)
                {
                    return i;
                }
            }
            return -1;
        }

        private static bool TryGetValue(string json, string name, int startIndex, out string value)
        {
            value = null;
            if (string.IsNullOrEmpty(json) || startIndex < 0 || startIndex >= json.Length)
            {
                return false;
            }

            string key = "\"" + name + "\"";
            int p = json.IndexOf(key, startIndex);
            if (p < 0)
            {
                return false;
            }
            p = json.IndexOf(':', p + key.Length);
            if (p < 0)
            {
                return false;
            }
            p++;
            while (p < json.Length && (json[p] == ' ' || json[p] == '\t' || json[p] == '\r' || json[p] == '\n'))
            {
                p++;
            }
            if (p >= json.Length)
            {
                return false;
            }
            if (json[p] == '"')
            {
                p++;
                int start = p;
                bool escape = false;
                while (p < json.Length)
                {
                    if (!escape && json[p] == '"')
                    {
                        value = json.Substring(start, p - start);
                        return true;
                    }
                    escape = !escape && json[p] == '\\';
                    if (json[p] != '\\')
                    {
                        escape = false;
                    }
                    p++;
                }
                return false;
            }
            int end = p;
            while (end < json.Length && json[end] != ',' && json[end] != '}' && json[end] != ']')
            {
                end++;
            }
            value = json.Substring(p, end - p).Trim();
            return value.Length > 0;
        }

        private static bool TryGetValue(string json, string name, out string value)
        {
            value = null;
            string key = "\"" + name + "\"";
            int p = json.IndexOf(key);
            if (p < 0)
            {
                return false;
            }
            p = json.IndexOf(':', p + key.Length);
            if (p < 0)
            {
                return false;
            }
            p++;
            while (p < json.Length && (json[p] == ' ' || json[p] == '\t' || json[p] == '\r' || json[p] == '\n')) p++;
            if (p >= json.Length)
            {
                return false;
            }
            if (json[p] == '"')
            {
                p++; int start = p; bool escape = false;
                while (p < json.Length)
                {
                    if (!escape && json[p] == '"')
                    {
                        value = json.Substring(start, p - start);
                        return true;
                    }
                    escape = !escape && json[p] == '\\';
                    if (json[p] != '\\')
                    {
                        escape = false;
                    }
                    p++;
                }
                return false;
            }
            int end = p;
            while (end < json.Length && json[end] != ',' && json[end] != '}' && json[end] != ']') end++;
            value = json.Substring(p, end - p).Trim();
            return value.Length > 0;
        }
    }
}
