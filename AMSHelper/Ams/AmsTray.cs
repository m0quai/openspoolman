using System;
using System.Diagnostics;
using AMSHelper.Mqtt;
using AMSHelper.Hardware;

namespace AMSHelper.Ams
{
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
      private string _activity = "Unbekannt";
      private string _lastSummary = string.Empty;
      private bool _occupied;
      private bool _occupiedKnown;
      private TrayOperation _operation = TrayOperation.None;
      private bool _isActiveTray;
      private bool _wasPreviousTray;
      private bool _isTargetTray;
      private bool _nfcUidCapturedInCycle;

      public AmsTray(int index, BambuMqtt mqtt)
      {
         this.Index = index;
         this._mqtt = mqtt;
         this._pn532Device = new Pn532Device(index);
         this._pn532Device.UidRead += this.Pn532UidRead;

         if (this._mqtt != null)
         {
            this._mqtt.StatusUpdateReceived += this.BambuStatusUpdateReceived;
         }
      }

      public int Index { get; private set; }
      public bool Pn532Enabled { get { return this._pn532Device.Enabled; } }
      public string Uid { get { return this._uid; } }
      public string Activity { get { return this._activity; } }
      public bool IsOccupied { get { return this._occupied; } }
      public bool IsNfcPolling { get { return this._pn532Device.IsPolling; } }

      public void Start()
      {
         this._pn532Device.Start();
      }

      private void BambuStatusUpdateReceived(BambuStatusUpdate update)
      {
         if (update == null) { return; }
         bool relevant = false;

         if (update.HasTrayExistBits)
         {
            int bits = BambuStatusParser.ParseTrayBits(update.TrayExistBits);
            if (this.SetOccupied((bits & (1 << this.Index)) != 0)) { relevant = true; }
         }

         if (update.HasCommand && update.Command == "ams_get_rfid" && update.HasCommandSlotId)
         {
            int rfidSlot = BambuStatusParser.ParseTrayId(update.CommandSlotId);
            if (rfidSlot == this.Index)
            {
               this._nfcUidCapturedInCycle = false;
               this._uid = string.Empty;
               this._lastSummary = string.Empty;
               if (this.StartNfcPolling())
               {
                  Write("[AMS] Tray " + this.Index + " -> NFC-Trigger durch ams_get_rfid");
                  relevant = true;
               }
            }
         }

         if (update.HasCommand && update.Command == "ams_change_filament")
         {
            int requested = this.GetRequestedTray(update);
            if (requested == this.Index)
            {
               if (this.BeginLoading()) { relevant = true; }
            }
            else if (requested == 255 && (this._isActiveTray || this._wasPreviousTray))
            {
               this._operation = TrayOperation.Unloading;
               this.StopNfcPolling();
               if (this.SetActivity("ENTLADEN gestartet")) { relevant = true; }
            }
         }

         if (update.HasTargetTray)
         {
            int target = BambuStatusParser.ParseTrayId(update.TargetTray);
            this._isTargetTray = target == this.Index;
            if (this._isTargetTray)
            {
               if (this.BeginLoading()) { relevant = true; }
            }
            else if (target == 255 && (this._isActiveTray || this._wasPreviousTray || this._operation != TrayOperation.None))
            {
               this._operation = TrayOperation.Unloading;
               this.StopNfcPolling();
               relevant = true;
            }
         }

         if (update.HasPreviousTray)
         {
            int previous = BambuStatusParser.ParseTrayId(update.PreviousTray);
            this._wasPreviousTray = previous == this.Index;
            if (this._wasPreviousTray) { relevant = true; }
         }

         if (update.HasActiveTray)
         {
            int active = BambuStatusParser.ParseTrayId(update.ActiveTray);
            bool wasActive = this._isActiveTray;
            this._isActiveTray = active == this.Index;
            if (this._isActiveTray)
            {
               if (this._operation != TrayOperation.Unloading && this.SetActivity("GELADEN / aktiv")) { relevant = true; }
            }
            else if (active == 255 && wasActive && this._operation == TrayOperation.Unloading)
            {
               if (this.SetActivity("ENTLADEN abgeschlossen / kein Filament aktiv")) { relevant = true; }
            }
         }

         if (update.HasTrayReadingBits)
         {
            int bits = BambuStatusParser.ParseTrayBits(update.TrayReadingBits);
            bool reading = (bits & (1 << this.Index)) != 0;
            if (reading)
            {
               if (!this._nfcUidCapturedInCycle)
               {
                  if (this.SetActivity("RFID wird gelesen")) { relevant = true; }
                  if (this.StartNfcPolling()) { relevant = true; }
               }
            }
            else
            {
               bool pollingStopped = this.StopNfcPolling();
               if (this._activity == "RFID wird gelesen")
               {
                  if (this.SetActivity(this._isActiveTray ? "GELADEN / aktiv" : "BEREIT")) { relevant = true; }
               }
               if (pollingStopped) { relevant = true; }
            }
         }

         if (update.HasTrayReadDoneBits)
         {
            int bits = BambuStatusParser.ParseTrayBits(update.TrayReadDoneBits);
            if ((bits & (1 << this.Index)) != 0)
            {
               this.StopNfcPolling();
               if (this._activity == "RFID wird gelesen") { this.SetActivity(this._isActiveTray ? "GELADEN / aktiv" : "BEREIT"); }
               relevant = true;
            }
         }

         if (update.HasAmsStatus && this._operation != TrayOperation.None)
         {
            bool completed;
            string activity = BambuStatusParser.InterpretAmsActivity(update.AmsStatus, this._operation == TrayOperation.Unloading, out completed);
            if (!string.IsNullOrEmpty(activity))
            {
               if (this.SetActivity(activity)) { relevant = true; }
            }
            if (completed)
            {
               this._operation = TrayOperation.None;
               this._isTargetTray = false;
               this.StopNfcPolling();
            }
            else if (this._operation != TrayOperation.Unloading && BambuStatusParser.IsFilamentChangeStatus(update.AmsStatus))
            {
               this._operation = TrayOperation.Loading;
            }
         }

         if (relevant) { update.AmsOutputProduced = true; }
      }

      private bool BeginLoading()
      {
         bool changed = false;
         this._operation = TrayOperation.Loading;
         this._isTargetTray = true;
         if (this.SetActivity("LADEN gestartet")) { changed = true; }
         if (!this._nfcUidCapturedInCycle && this.StartNfcPolling()) { changed = true; }
         return changed;
      }

      private int GetRequestedTray(BambuStatusUpdate update)
      {
         int requested = -1;
         if (update.HasCommandSlotId) { requested = BambuStatusParser.ParseTrayId(update.CommandSlotId); }
         if (requested < 0 && update.HasCommandTarget) { requested = BambuStatusParser.ParseTrayId(update.CommandTarget); }
         return requested;
      }

      private bool SetOccupied(bool occupied)
      {
         bool changed = !this._occupiedKnown || this._occupied != occupied;
         this._occupiedKnown = true;
         this._occupied = occupied;
         if (!occupied)
         {
            this._uid = string.Empty;
            this._lastSummary = string.Empty;
            this._isActiveTray = false;
            this._wasPreviousTray = false;
            this._isTargetTray = false;
            this._operation = TrayOperation.None;
            this._nfcUidCapturedInCycle = false;
            this.StopNfcPolling();
            return this.SetActivity("LEER");
         }
         if (this._activity == "LEER" || this._activity == "Unbekannt") { return this.SetActivity("BELEGT"); }
         if (changed) { this.WriteSummaryIfStable(); }
         return changed;
      }

      private bool SetActivity(string activity)
      {
         if (activity == null || this._activity == activity) { return false; }
         this._activity = activity;
         if (activity != "GELADEN / aktiv" && activity != "BELEGT" && activity != "BEREIT" && activity != "LEER")
         {
            Write("[AMS] Tray " + this.Index + " -> " + activity);
         }
         else { this.WriteSummaryIfStable(); }
         return true;
      }

      private bool StartNfcPolling()
      {
         if (this._nfcUidCapturedInCycle) { return false; }
         bool started = this._pn532Device.StartPolling();
         if (started && this._pn532Device.Enabled) { Write("[AMS] Tray " + this.Index + " -> NFC-Polling START"); }
         return started;
      }

      private bool StopNfcPolling()
      {
         bool stopped = this._pn532Device.StopPolling();
         if (stopped && this._pn532Device.Enabled) { Write("[AMS] Tray " + this.Index + " -> NFC-Polling ENDE"); }
         if (stopped) { this.WriteSummaryIfStable(); }
         return stopped;
      }

      private void Pn532UidRead(string uid)
      {
         if (string.IsNullOrEmpty(uid)) { return; }
         this._uid = uid;
         this._nfcUidCapturedInCycle = true;
         this._lastSummary = string.Empty;
         Write("[NFC] Tray " + this.Index + " UID=" + uid);
         this.StopNfcPolling();
         this.WriteSummaryIfStable();
      }

      private void WriteSummaryIfStable()
      {
         string activity = this._activity;
         if (activity == "Unbekannt" && this._occupiedKnown && this._occupied) { activity = "BELEGT"; }
         bool stable = activity == "BELEGT" || activity == "GELADEN / aktiv" || activity == "BEREIT" || activity == "LEER";
         if (!stable) { return; }
         string info = "[AMS] Tray " + this.Index + ": " + activity;
         if (this._pn532Device.Enabled)
         {
            info += " | PN532=aktiv";
            if (this._uid.Length > 0) { info += " | UID=" + this._uid; }
            else if (activity != "LEER") { info += " | UID=noch nicht gelesen"; }
         }
         else { info += " | PN532=deaktiviert"; }
         if (this._lastSummary == info) { return; }
         this._lastSummary = info;
         Write(info);
      }

      private static void Write(string text)
      {
         Debug.WriteLine(text);
      }
   }
}
