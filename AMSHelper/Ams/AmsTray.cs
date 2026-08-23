using System;
using System.Diagnostics;
using AMSHelper.Mqtt;
using AMSHelper.Hardware;

namespace AMSHelper.Ams
{
   /// <summary>
   /// Complete state, Bambu status handling and optional NFC reader for one AMS tray.
   /// </summary>
   public sealed class AmsTray
   {
      private enum TrayOperation
      {
         None,
         Loading,
         Unloading
      }

      private readonly BambuMqtt _mqtt;
      private readonly Pn532Device _pn532Device;
      private string _uid = string.Empty;
      private string _material = string.Empty;
      private string _color = string.Empty;
      private string _uuid = string.Empty;
      private string _remain = string.Empty;
      private string _activity = "Unbekannt";
      private string _lastSummary = string.Empty;
      private bool _occupied;
      private bool _occupiedKnown;
      private string _bambuUid = string.Empty;
      private TrayOperation _operation = TrayOperation.None;
      private bool _isActiveTray;
      private bool _wasPreviousTray;
      private bool _isTargetTray;

      public AmsTray(int index, BambuMqtt mqtt)
      {
         Index = index;
         _mqtt = mqtt;
         _pn532Device = new Pn532Device(index);
         _pn532Device.UidRead += Pn532UidRead;

         if (_mqtt != null)
         {
            _mqtt.StatusUpdateReceived += BambuStatusUpdateReceived;
         }
      }

      public int Index { get; private set; }
      public bool Pn532Enabled { get { return _pn532Device.Enabled; } }
      public string Uid { get { return _uid; } }
      public string BambuUid { get { return _bambuUid; } }
      public string Material { get { return _material; } }
      public string Color { get { return _color; } }
      public string Uuid { get { return _uuid; } }
      public string Remain { get { return _remain; } }
      public string Activity { get { return _activity; } }
      public bool IsOccupied { get { return _occupied; } }
      public bool IsNfcPolling { get { return _pn532Device.IsPolling; } }

      public void Start()
      {
         _pn532Device.Start();
      }

      private void BambuStatusUpdateReceived(BambuStatusUpdate update)
      {
         if (update == null)
         {
            return;
         }

         bool relevant = false;

         BambuTrayUpdate trayUpdate = GetOwnTrayUpdate(update);
         if (trayUpdate != null)
         {
            WriteStatus(trayUpdate);
            relevant = true;
         }

         if (update.HasTrayExistBits)
         {
            int bits = BambuStatusParser.ParseTrayBits(update.TrayExistBits);
            if (SetOccupied((bits & (1 << Index)) != 0))
            {
               relevant = true;
            }
         }

         // Der P1S meldet ams_get_rfid fuer den betroffenen Slot deutlich frueher als
         // tray_reading_bits. Das ist deshalb unser fruehester belastbarer NFC-Trigger.
         if (update.HasCommand && update.Command == "ams_get_rfid" && update.HasCommandSlotId)
         {
            int rfidSlot = BambuStatusParser.ParseTrayId(update.CommandSlotId);
            if (rfidSlot == Index)
            {
               if (StartNfcPolling())
               {
                  Write("[AMS] Tray " + Index + " -> NFC-Trigger durch ams_get_rfid");
                  relevant = true;
               }
            }
         }

         if (update.HasCommand && update.Command == "ams_change_filament")
         {
            int requested = GetRequestedTray(update);
            if (requested == Index)
            {
               if (BeginLoading())
               {
                  relevant = true;
               }
            }
            else if (requested == 255 && (_isActiveTray || _wasPreviousTray))
            {
               _operation = TrayOperation.Unloading;
               StopNfcPolling();
               if (SetActivity("ENTLADEN gestartet"))
               {
                  relevant = true;
               }
            }
         }

         if (update.HasTargetTray)
         {
            int target = BambuStatusParser.ParseTrayId(update.TargetTray);
            _isTargetTray = target == Index;
            if (_isTargetTray)
            {
               if (BeginLoading())
               {
                  relevant = true;
               }
            }
            else if (target == 255 && (_isActiveTray || _wasPreviousTray || _operation != TrayOperation.None))
            {
               _operation = TrayOperation.Unloading;
               StopNfcPolling();
               relevant = true;
            }
         }

         if (update.HasPreviousTray)
         {
            int previous = BambuStatusParser.ParseTrayId(update.PreviousTray);
            _wasPreviousTray = previous == Index;
            if (_wasPreviousTray)
            {
               relevant = true;
            }
         }

         if (update.HasActiveTray)
         {
            int active = BambuStatusParser.ParseTrayId(update.ActiveTray);
            bool wasActive = _isActiveTray;
            _isActiveTray = active == Index;

            if (_isActiveTray)
            {
               // tray_now bedeutet nur, dass der Tray aktuell aktiv ist. Das ist kein
               // verlaessliches Ende des RFID-Lesefensters und stoppt NFC daher nicht.
               if (_operation != TrayOperation.Unloading && SetActivity("GELADEN / aktiv"))
               {
                  relevant = true;
               }
            }
            else if (active == 255 && wasActive && _operation == TrayOperation.Unloading)
            {
               if (SetActivity("ENTLADEN abgeschlossen / kein Filament aktiv"))
               {
                  relevant = true;
               }
            }
         }

         if (update.HasTrayReadingBits)
         {
            int bits = BambuStatusParser.ParseTrayBits(update.TrayReadingBits);
            bool reading = (bits & (1 << Index)) != 0;
            if (reading)
            {
               if (SetActivity("RFID wird gelesen"))
               {
                  relevant = true;
               }
               if (StartNfcPolling())
               {
                  relevant = true;
               }
            }
            else
            {
               bool pollingStopped = StopNfcPolling();
               if (_activity == "RFID wird gelesen")
               {
                  if (SetActivity(_isActiveTray ? "GELADEN / aktiv" : "BEREIT"))
                  {
                     relevant = true;
                  }
               }
               if (pollingStopped)
               {
                  relevant = true;
               }
            }
         }

         if (update.HasTrayReadDoneBits)
         {
            int bits = BambuStatusParser.ParseTrayBits(update.TrayReadDoneBits);
            if ((bits & (1 << Index)) != 0)
            {
               StopNfcPolling();
               if (_activity == "RFID wird gelesen")
               {
                  SetActivity(_isActiveTray ? "GELADEN / aktiv" : "BEREIT");
               }
               relevant = true;
            }
         }

         if (update.HasAmsStatus && _operation != TrayOperation.None)
         {
            bool completed;
            string activity = BambuStatusParser.InterpretAmsActivity(update.AmsStatus, _operation == TrayOperation.Unloading, out completed);
            if (!string.IsNullOrEmpty(activity))
            {
               if (SetActivity(activity))
               {
                  relevant = true;
               }
            }

            if (completed)
            {
               _operation = TrayOperation.None;
               _isTargetTray = false;
               StopNfcPolling();
            }
            else if (_operation != TrayOperation.Unloading && BambuStatusParser.IsFilamentChangeStatus(update.AmsStatus))
            {
               _operation = TrayOperation.Loading;
            }
         }

         if (relevant)
         {
            update.AmsOutputProduced = true;
         }
      }

      private bool BeginLoading()
      {
         bool changed = false;
         _operation = TrayOperation.Loading;
         _isTargetTray = true;

         if (SetActivity("LADEN gestartet"))
         {
            changed = true;
         }

         if (StartNfcPolling())
         {
            changed = true;
         }

         return changed;
      }

      private BambuTrayUpdate GetOwnTrayUpdate(BambuStatusUpdate update)
      {
         if (update.Trays == null)
         {
            return null;
         }

         for (int i = 0; i < update.Trays.Length; i++)
         {
            BambuTrayUpdate trayUpdate = update.Trays[i];
            if (trayUpdate != null && trayUpdate.Slot == Index)
            {
               return trayUpdate;
            }
         }

         return null;
      }

      private int GetRequestedTray(BambuStatusUpdate update)
      {
         int requested = -1;
         if (update.HasCommandSlotId)
         {
            requested = BambuStatusParser.ParseTrayId(update.CommandSlotId);
         }

         if (requested < 0 && update.HasCommandTarget)
         {
            requested = BambuStatusParser.ParseTrayId(update.CommandTarget);
         }

         return requested;
      }

      private void WriteStatus(BambuTrayUpdate update)
      {
         if (update == null || update.Slot != Index)
         {
            return;
         }

         if (update.HasType && update.Type != null && update.Type.Length > 0)
         {
            _material = update.Type;
         }

         if (update.HasColor && update.Color != null && update.Color.Length > 0)
         {
            if (!(update.Color == "FFFFFFFF" && _pn532Device.IsPolling))
            {
               _color = update.Color;
            }
         }

         if (update.HasUuid)
         {
            _uuid = update.Uuid == null ? string.Empty : update.Uuid;
         }

         if (update.HasRemain)
         {
            _remain = update.Remain == null ? string.Empty : update.Remain;
         }

         if (update.HasTagUid)
         {
            _bambuUid = NormalizeUid(update.TagUid);
         }

         WriteSummaryIfStable();
      }

      private bool SetOccupied(bool occupied)
      {
         bool changed = !_occupiedKnown || _occupied != occupied;
         _occupiedKnown = true;
         _occupied = occupied;

         if (!occupied)
         {
            _material = string.Empty;
            _color = string.Empty;
            _uuid = string.Empty;
            _remain = string.Empty;
            _uid = string.Empty;
            _bambuUid = string.Empty;
            _lastSummary = string.Empty;
            _isActiveTray = false;
            _wasPreviousTray = false;
            _isTargetTray = false;
            _operation = TrayOperation.None;
            StopNfcPolling();
            return SetActivity("LEER");
         }

         if (_activity == "LEER" || _activity == "Unbekannt")
         {
            return SetActivity("BELEGT");
         }

         return changed;
      }

      private bool SetActivity(string activity)
      {
         if (activity == null || _activity == activity)
         {
            return false;
         }

         _activity = activity;

         if (activity != "GELADEN / aktiv" && activity != "BELEGT" && activity != "BEREIT" && activity != "LEER")
         {
            Write("[AMS] Tray " + Index + " -> " + activity);
         }
         else
         {
            WriteSummaryIfStable();
         }

         return true;
      }

      private bool StartNfcPolling()
      {
         bool started = _pn532Device.StartPolling();
         if (started && _pn532Device.Enabled)
         {
            Write("[AMS] Tray " + Index + " -> NFC-Polling START");
         }

         return started;
      }

      private bool StopNfcPolling()
      {
         bool stopped = _pn532Device.StopPolling();
         if (stopped && _pn532Device.Enabled)
         {
            Write("[AMS] Tray " + Index + " -> NFC-Polling ENDE");
         }

         if (stopped)
         {
            WriteSummaryIfStable();
         }

         return stopped;
      }

      private void Pn532UidRead(string uid)
      {
         if (string.IsNullOrEmpty(uid))
         {
            return;
         }

         _uid = uid;
         _lastSummary = string.Empty;
         Write("[NFC] Tray " + Index + " UID=" + uid);
         WriteSummaryIfStable();
      }

      private void WriteSummaryIfStable()
      {
         string activity = _activity;
         if (activity == "Unbekannt" && _occupiedKnown && _occupied)
         {
            activity = "BELEGT";
         }

         bool stable = activity == "BELEGT" || activity == "GELADEN / aktiv" || activity == "BEREIT" || activity == "LEER";
         if (!stable)
         {
            return;
         }

         if (_pn532Device.IsPolling && activity == "GELADEN / aktiv")
         {
            return;
         }

         if (activity == "GELADEN / aktiv" && (_material.Length == 0 || _color.Length == 0 || _color == "FFFFFFFF"))
         {
            return;
         }

         string info = "[AMS] Tray " + Index + ": " + activity;
         if (activity != "LEER")
         {
            if (_material.Length > 0)
            {
               info += " | " + _material;
            }
            if (_color.Length > 0)
            {
               info += " | Farbe=" + _color;
            }
            if (_bambuUid.Length > 0)
            {
               info += " | BambuUID=" + _bambuUid;
            }
            if (_uid.Length > 0)
            {
               info += " | PN532UID=" + _uid;
            }
         }

         if (_lastSummary == info)
         {
            return;
         }

         _lastSummary = info;
         Write(info);
      }

      private static string NormalizeUid(string uid)
      {
         if (string.IsNullOrEmpty(uid) || uid == "0000000000000000")
         {
            return string.Empty;
         }

         return uid;
      }

      private static void Write(string text)
      {
         Debug.WriteLine(text);
      }
   }
}
