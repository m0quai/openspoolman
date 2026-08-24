using System;
using System.Diagnostics;
using System.Text;
using System.Threading;
using AMSHelper.Config;
using nanoFramework.M2Mqtt;
using nanoFramework.M2Mqtt.Messages;

namespace AMSHelper.Mqtt
{
#pragma warning disable CS0162

   public delegate void BambuStatusUpdateReceivedHandler(BambuStatusUpdate update);
   public sealed class BambuMqtt
   {
      private readonly BambuStatusParser _parser = new BambuStatusParser();
      public event BambuStatusUpdateReceivedHandler StatusUpdateReceived;
      private MqttClient _client;
      private Thread _worker;
      private bool _running;

      public bool IsConnected => this._client != null && this._client.IsConnected;

      public void Start()
      {
         if (this._running) { return; }
         this._running = true;
         this._worker = new Thread(this.Run);
         this._worker.Start();
      }

      public void Stop()
      {
         this._running = false;
         try
         {
            if (this._client != null && this._client.IsConnected) { this._client.Disconnect(); }
         }
         catch { }
      }

      private void Run()
      {
         while (this._running)
         {
            try
            {
               if (this._client == null || !this._client.IsConnected) { this.ConnectAndSubscribe(); }
            }
            catch (Exception ex)
            {
               Debug.WriteLine("[BambuMQTT] Fehler: " + ex.Message);
               this.DisposeClient();
            }
            Thread.Sleep(Configuration.Bambu.MqttReconnectDelayMs);
         }
      }

      private void ConnectAndSubscribe()
      {
         this.DisposeClient();
         Debug.WriteLine("[BambuMQTT] Verbinde " + Configuration.Bambu.PrinterIp + ":" + Configuration.Bambu.MqttPort + " ...");
         this._client = new MqttClient(Configuration.Bambu.PrinterIp, Configuration.Bambu.MqttPort, Configuration.Bambu.MqttUseTls, null, null, MqttSslProtocols.TLSv1_2);
         this._client.Settings.ValidateServerCertificate = Configuration.Bambu.ValidateServerCertificate;
         this._client.MqttMsgPublishReceived += this.OnMessageReceived;
         MqttReasonCode result = this._client.Connect(Configuration.Bambu.MqttClientId, Configuration.Bambu.MqttUsername, Configuration.Bambu.LanAccessCode);
         if (result != MqttReasonCode.Success) { throw new Exception("MQTT Connect fehlgeschlagen: " + result.ToString()); }
         this._client.Subscribe(new string[] { Configuration.Bambu.MqttReportTopic }, new MqttQoSLevel[] { MqttQoSLevel.AtMostOnce });
         Debug.WriteLine("[BambuMQTT] Verbunden.");
         Debug.WriteLine("[BambuMQTT] Subscribe: " + Configuration.Bambu.MqttReportTopic);
         this.RequestFullStatus();
      }

      private void RequestFullStatus()
      {
         if (this._client == null || !this._client.IsConnected) { return; }
         string payload = "{\"pushing\":{\"sequence_id\":\"0\",\"command\":\"pushall\"}}";
         Debug.WriteLine("[BambuMQTT] Fordere aktuellen Gesamtstatus an (pushall)...");
         this._client.Publish(Configuration.Bambu.MqttRequestTopic, Encoding.UTF8.GetBytes(payload), null, null, MqttQoSLevel.AtMostOnce, false);
         Debug.WriteLine("[BambuMQTT] Gesamtstatus angefordert.");
      }

      private void OnMessageReceived(object sender, MqttMsgPublishEventArgs e)
      {
         string payload = e.Message == null ? string.Empty : Encoding.UTF8.GetString(e.Message, 0, e.Message.Length);
         BambuStatusUpdate update = this._parser.Parse(payload);
         if (Configuration.Debugging.DumpRawAmsStatusFields) { DumpRawAmsStatusFields(update); }
         BambuStatusUpdateReceivedHandler handler = this.StatusUpdateReceived;
         if (handler != null) { handler(update); }
         if (!Configuration.Debugging.DumpAllBambuReports) { return; }
         bool hasAmsInformation = HasAmsInformation(update);
         if (update != null && update.HasCommand && update.Command == "ams_get_rfid") { return; }
         if (update != null && update.AmsOutputProduced) { return; }
         if (update != null && update.HasCommand && update.Command == "push_status") { return; }
         if (!hasAmsInformation && !Configuration.Debugging.DumpTelemetryOnlyBambuReports) { return; }
         Debug.WriteLine("");
         Debug.WriteLine("================ BAMBU MQTT /report ================");
         Debug.WriteLine("Topic: " + e.Topic);
         if (hasAmsInformation) { DumpCompactAmsReport(update); }
         else { Debug.WriteLine("[nur Standard-Telemetrie]"); }
         Debug.WriteLine("================ END BAMBU MQTT =====================");
         Debug.WriteLine("");
      }

      private static void DumpRawAmsStatusFields(BambuStatusUpdate update)
      {
         if (update == null) { return; }
         bool hasRawAmsState = update.HasAmsStatus || update.HasActiveTray || update.HasTargetTray || update.HasPreviousTray || update.HasTrayReadingBits || update.HasTrayReadDoneBits || update.HasTrayExistBits || update.HasCommandSlotId || update.HasCommandTarget || (update.HasCommand && update.Command != null && update.Command.IndexOf("ams_") == 0);
         if (!hasRawAmsState) { return; }
         string line = "[AMS-RAW]";
         if (update.HasCommand) { line += " cmd=" + update.Command; }
         if (update.HasAmsStatus) { line += " ams_status=" + update.AmsStatus; }
         if (update.HasTargetTray) { line += " tray_tar=" + update.TargetTray; }
         if (update.HasActiveTray) { line += " tray_now=" + update.ActiveTray; }
         if (update.HasPreviousTray) { line += " tray_pre=" + update.PreviousTray; }
         if (update.HasTrayReadingBits) { line += " reading=" + update.TrayReadingBits; }
         if (update.HasTrayReadDoneBits) { line += " read_done=" + update.TrayReadDoneBits; }
         if (update.HasTrayExistBits) { line += " exist=" + update.TrayExistBits; }
         if (update.HasCommandSlotId) { line += " slot_id=" + update.CommandSlotId; }
         if (update.HasCommandTarget) { line += " target=" + update.CommandTarget; }
         if (update.HasResult) { line += " result=" + update.Result; }
         if (update.HasReason) { line += " reason=" + update.Reason; }
         Debug.WriteLine(line);
      }

      private static bool HasAmsInformation(BambuStatusUpdate update)
      {
         if (update == null) { return false; }
         if (update.HasAmsStatus || update.HasActiveTray || update.HasTargetTray || update.HasPreviousTray || update.HasTrayReadingBits || update.HasTrayReadDoneBits || update.HasAmsId || update.HasCommandSlotId || update.HasCommandTarget) { return true; }
         if (update.HasCommand && update.Command != null && update.Command.IndexOf("ams_") == 0) { return true; }
         for (int i = 0; i < update.Trays.Length; i++) { if (update.Trays[i] != null) { return true; } }
         return false;
      }

      private static void DumpCompactAmsReport(BambuStatusUpdate update)
      {
         if (update.HasCommand) { Debug.WriteLine("command=" + update.Command); }
         if (update.HasAmsStatus) { Debug.WriteLine("ams_status=" + update.AmsStatus + " (" + BambuStatusParser.DescribeAmsStatus(update.AmsStatus) + ")"); }
         if (update.HasCommandSlotId) { Debug.WriteLine("slot_id=" + update.CommandSlotId + " (" + BambuStatusParser.DescribeTrayId(update.CommandSlotId, "angeforderter Tray") + ")"); }
         if (update.HasCommandTarget) { Debug.WriteLine("target=" + update.CommandTarget + " (" + BambuStatusParser.DescribeTrayId(update.CommandTarget, "Ziel") + ")"); }
         if (update.HasTargetTray) { Debug.WriteLine("tray_tar=" + update.TargetTray + " (" + BambuStatusParser.DescribeTrayId(update.TargetTray, "Ziel-Tray") + ")"); }
         if (update.HasActiveTray) { Debug.WriteLine("tray_now=" + update.ActiveTray + " (" + BambuStatusParser.DescribeTrayId(update.ActiveTray, "aktiver Tray") + ")"); }
         if (update.HasPreviousTray) { Debug.WriteLine("tray_pre=" + update.PreviousTray + " (" + BambuStatusParser.DescribeTrayId(update.PreviousTray, "vorheriger Tray") + ")"); }
         if (update.HasTrayReadingBits) { Debug.WriteLine("tray_reading_bits=" + update.TrayReadingBits + " (" + BambuStatusParser.DescribeTrayBits(update.TrayReadingBits, "RFID-Lesen aktiv") + ")"); }
         if (update.HasTrayReadDoneBits) { Debug.WriteLine("tray_read_done_bits=" + update.TrayReadDoneBits + " (" + BambuStatusParser.DescribeTrayBits(update.TrayReadDoneBits, "RFID-Lesen abgeschlossen") + ")"); }
         if (update.HasResult) { Debug.WriteLine("result=" + update.Result); }
      }

      private void DisposeClient()
      {
         if (this._client == null) { return; }
         try
         {
            this._client.MqttMsgPublishReceived -= this.OnMessageReceived;
            if (this._client.IsConnected) { this._client.Disconnect(); }
         }
         catch { }
         this._client = null;
      }
   }
}
