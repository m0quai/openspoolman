using System;

namespace AMSHelper.Mqtt
{
   public sealed class BambuStatusParser
   {
      public BambuStatusUpdate Parse(string json)
      {
         var update = new BambuStatusUpdate();
         if (string.IsNullOrEmpty(json))
         {
            return update;
         }

         update.RawJson = json;
         update.HasCommand = BambuStatusParser.TryGetValue(json, "command", out update.Command);
         update.HasSequenceId = BambuStatusParser.TryGetValue(json, "sequence_id", out update.SequenceId);
         update.HasGcodeFile = BambuStatusParser.TryGetValue(json, "gcode_file", out update.GcodeFile);
         update.HasGcodeState = BambuStatusParser.TryGetValue(json, "gcode_state", out update.GcodeState);
         update.HasSubtaskName = BambuStatusParser.TryGetValue(json, "subtask_name", out update.SubtaskName);
         update.HasActiveTray = BambuStatusParser.TryGetValue(json, "tray_now", out update.ActiveTray);
         update.HasTargetTray = BambuStatusParser.TryGetValue(json, "tray_tar", out update.TargetTray);
         update.HasPreviousTray = BambuStatusParser.TryGetValue(json, "tray_pre", out update.PreviousTray);
         update.HasAmsStatus = BambuStatusParser.TryGetValue(json, "ams_status", out update.AmsStatus);
         update.HasTrayExistBits = BambuStatusParser.TryGetValue(json, "tray_exist_bits", out update.TrayExistBits);
         update.HasTrayReadingBits = BambuStatusParser.TryGetValue(json, "tray_reading_bits", out update.TrayReadingBits);
         update.HasTrayReadDoneBits = BambuStatusParser.TryGetValue(json, "tray_read_done_bits", out update.TrayReadDoneBits);
         update.HasCommandAmsId = BambuStatusParser.TryGetValue(json, "ams_id", out update.CommandAmsId);
         update.HasCommandSlotId = BambuStatusParser.TryGetValue(json, "slot_id", out update.CommandSlotId);
         update.HasCommandTarget = BambuStatusParser.TryGetValue(json, "target", out update.CommandTarget);
         update.HasReason = BambuStatusParser.TryGetValue(json, "reason", out update.Reason);
         update.HasResult = BambuStatusParser.TryGetValue(json, "result", out update.Result);

         int amsPos = json.IndexOf("\"ams\"");
         if (amsPos >= 0)
         {
            update.HasAmsId = BambuStatusParser.TryGetValue(json, "ams_id", amsPos, out update.AmsId);
            BambuStatusParser.ParseTrays(json, update);
         }
         return update;
      }

      public static int ParseTrayId(string value)
      {
         int result;
         return BambuStatusParser.TryParseInt(value, out result) ? result : -1;
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
            return BambuStatusParser.TryParseInt(value, out result) ? result : 0;
         }
      }

      public static bool IsFilamentChangeStatus(string value)
      {
         int status;
         if (!BambuStatusParser.TryParseInt(value, out status))
         {
            return false;
         }
         return ((status >> 8) & 0xFF) == 1;
      }

      public static string InterpretAmsActivity(string value, bool unloading, out bool completed)
      {
         completed = false;
         int status;
         if (!BambuStatusParser.TryParseInt(value, out status) || status == 0)
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
         if (!BambuStatusParser.TryParseInt(value, out status))
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
               case 2:
                  return "Filamentwechsel - Vorbereitung / Aufheizen";
               case 3:
                  return "Filamentwechsel - Filament loesen / Wechsel vorbereiten";
               case 4:
                  return "Filamentwechsel - Rueckzug / Entladen";
               case 5:
                  return "Filamentwechsel - Filament zufuehren";
               case 6:
                  return "Filamentwechsel - Laden pruefen";
               case 7:
                  return "Filamentwechsel - Spuelen / Purge";
               default:
                  return "Filamentwechsel - Schritt " + sub;
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
         int tray = BambuStatusParser.ParseTrayId(value);
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
         int bits = BambuStatusParser.ParseTrayBits(value);
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
         int position = 0;
         while (position < json.Length)
         {
            int idKey = json.IndexOf("\"id\"", position);
            if (idKey < 0)
            {
               break;
            }
            int objectStart = json.LastIndexOf('{', idKey);
            int objectEnd = BambuStatusParser.FindObjectEnd(json, objectStart);
            if (objectStart < 0 || objectEnd < 0)
            {
               break;
            }
            string obj = json.Substring(objectStart, objectEnd - objectStart + 1);
            string id;
            if (BambuStatusParser.TryGetValue(obj, "id", out id))
            {
               int slot;
               if (BambuStatusParser.TryParseSlot(id, out slot) && slot >= 0 && slot < update.Trays.Length)
               {
                  var tray = new BambuTrayUpdate();
                  tray.Slot = slot;
                  tray.Present = true;
                  tray.HasId = true;
                  tray.Id = id;
                  tray.HasType = BambuStatusParser.TryGetValue(obj, "tray_type", out tray.Type);
                  tray.HasColor = BambuStatusParser.TryGetValue(obj, "tray_color", out tray.Color);
                  tray.HasUuid = BambuStatusParser.TryGetValue(obj, "tray_uuid", out tray.Uuid);
                  tray.HasRemain = BambuStatusParser.TryGetValue(obj, "remain", out tray.Remain);
                  tray.HasTagUid = BambuStatusParser.TryGetValue(obj, "tag_uid", out tray.TagUid);
                  if (tray.HasType || tray.HasColor || tray.HasUuid || tray.HasRemain || tray.HasTagUid)
                  {
                     update.Trays[slot] = tray;
                  }
               }
            }
            position = objectEnd + 1;
         }
      }

      private static bool TryParseSlot(string value, out int result)
      {
         result = -1;
         if (value == null || value.Length != 1 || value[0] < '0' || value[0] > '3')
         {
            return false;
         }
         result = value[0] - '0';
         return true;
      }

      private static int FindObjectEnd(string value, int start)
      {
         if (start < 0)
         {
            return -1;
         }
         int depth = 0;
         bool quoted = false;
         bool escape = false;
         for (int i = start; i < value.Length; i++)
         {
            char character = value[i];
            if (quoted)
            {
               if (escape)
               {
                  escape = false;
               }
               else if (character == '\\')
               {
                  escape = true;
               }
               else if (character == '"')
               {
                  quoted = false;
               }
               continue;
            }
            if (character == '"')
            {
               quoted = true;
            }
            else if (character == '{')
            {
               depth++;
            }
            else if (character == '}' && --depth == 0)
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
         int position = json.IndexOf(key, startIndex);
         if (position < 0)
         {
            return false;
         }
         position = json.IndexOf(':', position + key.Length);
         if (position < 0)
         {
            return false;
         }
         position++;
         while (position < json.Length && (json[position] == ' ' || json[position] == '\t' || json[position] == '\r' || json[position] == '\n'))
         {
            position++;
         }
         return BambuStatusParser.ReadValue(json, position, out value);
      }

      private static bool TryGetValue(string json, string name, out string value)
      {
         return BambuStatusParser.TryGetValue(json, name, 0, out value);
      }

      private static bool ReadValue(string json, int position, out string value)
      {
         value = null;
         if (position >= json.Length)
         {
            return false;
         }
         if (json[position] == '"')
         {
            position++;
            int start = position;
            bool escape = false;
            while (position < json.Length)
            {
               if (!escape && json[position] == '"')
               {
                  value = json.Substring(start, position - start);
                  return true;
               }
               escape = !escape && json[position] == '\\';
               if (json[position] != '\\')
               {
                  escape = false;
               }
               position++;
            }
            return false;
         }
         int end = position;
         while (end < json.Length && json[end] != ',' && json[end] != '}' && json[end] != ']')
         {
            end++;
         }
         value = json.Substring(position, end - position).Trim();
         return value.Length > 0;
      }
   }
}
