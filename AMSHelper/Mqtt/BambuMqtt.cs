using System;
using System.Text;
using System.Threading;
using AMSHelper.Config;
using AMSHelper.Diagnostics;
using nanoFramework.M2Mqtt;
using nanoFramework.M2Mqtt.Messages;

namespace AMSHelper.Mqtt
{
#pragma warning disable CS0162
   public delegate void BambuStatusUpdateReceivedHandler(BambuStatusUpdate update);

   public sealed class BambuMqtt
   {
      private readonly BambuStatusParser _parser = new BambuStatusParser();
      private MqttClient _client;
      private Thread _worker;
      private bool _running;

      public event BambuStatusUpdateReceivedHandler StatusUpdateReceived;
      public bool IsConnected => _client != null && _client.IsConnected;

      public void Start()
      {
         if (_running)
         {
            return;
         }
         _running = true;
         _worker = new Thread(this.Run);
         _worker.Start();
      }

      public void Stop()
      {
         _running = false;
         try
         {
            if (_client != null && _client.IsConnected)
            {
               _client.Disconnect();
            }
         }
         catch
         {
         }
      }

      private void Run()
      {
         while (_running)
         {
            try
            {
               if (_client == null || !_client.IsConnected)
               {
                  this.ConnectAndSubscribe();
               }
            }
            catch (Exception ex)
            {
               TraceWriter.WriteLine("[BambuMQTT] Fehler: " + ex.Message);
               this.DisposeClient();
            }
            Thread.Sleep(Configuration.Bambu.MqttReconnectDelayMs);
         }
      }

      private void ConnectAndSubscribe()
      {
         this.DisposeClient();
         TraceWriter.WriteLine("[BambuMQTT] Verbinde " + Configuration.Bambu.PrinterIp + ":" + Configuration.Bambu.MqttPort + " ...");
         _client = new MqttClient(Configuration.Bambu.PrinterIp, Configuration.Bambu.MqttPort, Configuration.Bambu.MqttUseTls, null, null, MqttSslProtocols.TLSv1_2);
         _client.Settings.ValidateServerCertificate = Configuration.Bambu.ValidateServerCertificate;
         _client.MqttMsgPublishReceived += this.OnMessageReceived;
         MqttReasonCode result = _client.Connect(Configuration.Bambu.MqttClientId, Configuration.Bambu.MqttUsername, Configuration.Bambu.LanAccessCode);
         if (result != MqttReasonCode.Success)
         {
            throw new Exception("MQTT Connect fehlgeschlagen: " + result.ToString());
         }
         _client.Subscribe(new string[] { Configuration.Bambu.MqttReportTopic }, new MqttQoSLevel[] { MqttQoSLevel.AtMostOnce });
         TraceWriter.WriteLine("[BambuMQTT] Verbunden.");
         TraceWriter.WriteLine("[BambuMQTT] Subscribe: " + Configuration.Bambu.MqttReportTopic);
         this.RequestFullStatus();
      }

      private void RequestFullStatus()
      {
         if (_client == null || !_client.IsConnected)
         {
            return;
         }
         string payload = "{\"pushing\":{\"sequence_id\":\"0\",\"command\":\"pushall\"}}";
         TraceWriter.WriteLine("[BambuMQTT] Fordere aktuellen Gesamtstatus an (pushall)...");
         _client.Publish(Configuration.Bambu.MqttRequestTopic, Encoding.UTF8.GetBytes(payload), null, null, MqttQoSLevel.AtMostOnce, false);
         TraceWriter.WriteLine("[BambuMQTT] Gesamtstatus angefordert.");
      }

      private void OnMessageReceived(object sender, MqttMsgPublishEventArgs e)
      {
         string payload = e.Message == null ? string.Empty : Encoding.UTF8.GetString(e.Message, 0, e.Message.Length);
         BambuStatusUpdate update = _parser.Parse(payload);
         if (Configuration.Debugging.DumpRawAmsStatusFields)
         {
            BambuMqtt.DumpRawAmsStatusFields(update);
         }
         BambuStatusUpdateReceivedHandler handler = this.StatusUpdateReceived;
         if (handler != null)
         {
            handler(update);
         }
         if (!Configuration.Debugging.DumpAllBambuReports)
         {
            return;
         }
         bool hasAmsInformation = BambuMqtt.HasAmsInformation(update);
         if (update != null && update.HasCommand && update.Command == "ams_get_rfid")
         {
            return;
         }
         if (update != null && update.AmsOutputProduced)
         {
            return;
         }
         if (update != null && update.HasCommand && update.Command == "push_status")
         {
            return;
         }
         if (!hasAmsInformation && !Configuration.Debugging.DumpTelemetryOnlyBambuReports)
         {
            return;
         }
         TraceWriter.WriteLine(string.Empty);
         TraceWriter.WriteLine("================ BAMBU MQTT /report ================");
         TraceWriter.WriteLine("Topic: " + e.Topic);
         if (hasAmsInformation)
         {
            BambuMqtt.DumpCompactAmsReport(update);
         }
         else
         {
            TraceWriter.WriteLine("[nur Standard-Telemetrie]");
         }
         TraceWriter.WriteLine("================ END BAMBU MQTT =====================");
         TraceWriter.WriteLine(string.Empty);
      }

      private static void DumpRawAmsStatusFields(BambuStatusUpdate update)
      {
         if (update == null)
         {
            return;
         }
         bool hasRawAmsState = update.HasAmsStatus || update.HasActiveTray || update.HasTargetTray || update.HasPreviousTray || update.HasTrayReadingBits || update.HasTrayReadDoneBits || update.HasTrayExistBits || update.HasCommandSlotId || update.HasCommandTarget || (update.HasCommand && update.Command != null && update.Command.IndexOf("ams_") == 0);
         if (!hasRawAmsState)
         {
            return;
         }
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
         TraceWriter.WriteLine(line);
      }

      private static bool HasAmsInformation(BambuStatusUpdate update)
      {
         if (update == null)
         {
            return false;
         }
         if (update.HasAmsStatus || update.HasActiveTray || update.HasTargetTray || update.HasPreviousTray || update.HasTrayReadingBits || update.HasTrayReadDoneBits || update.HasAmsId || update.HasCommandSlotId || update.HasCommandTarget)
         {
            return true;
         }
         if (update.HasCommand && update.Command != null && update.Command.IndexOf("ams_") == 0)
         {
            return true;
         }
         for (int i = 0; i < update.Trays.Length; i++)
         {
            if (update.Trays[i] != null)
            {
               return true;
            }
         }
         return false;
      }

      private static void DumpCompactAmsReport(BambuStatusUpdate update)
      {
         if (update.HasCommand) { TraceWriter.WriteLine("command=" + update.Command); }
         if (update.HasAmsStatus) { TraceWriter.WriteLine("ams_status=" + update.AmsStatus + " (" + BambuStatusParser.DescribeAmsStatus(update.AmsStatus) + ")"); }
         if (update.HasCommandSlotId) { TraceWriter.WriteLine("slot_id=" + update.CommandSlotId + " (" + BambuStatusParser.DescribeTrayId(update.CommandSlotId, "angeforderter Tray") + ")"); }
         if (update.HasCommandTarget) { TraceWriter.WriteLine("target=" + update.CommandTarget + " (" + BambuStatusParser.DescribeTrayId(update.CommandTarget, "Ziel") + ")"); }
         if (update.HasTargetTray) { TraceWriter.WriteLine("tray_tar=" + update.TargetTray + " (" + BambuStatusParser.DescribeTrayId(update.TargetTray, "Ziel-Tray") + ")"); }
         if (update.HasActiveTray) { TraceWriter.WriteLine("tray_now=" + update.ActiveTray + " (" + BambuStatusParser.DescribeTrayId(update.ActiveTray, "aktiver Tray") + ")"); }
         if (update.HasPreviousTray) { TraceWriter.WriteLine("tray_pre=" + update.PreviousTray + " (" + BambuStatusParser.DescribeTrayId(update.PreviousTray, "vorheriger Tray") + ")"); }
         if (update.HasTrayReadingBits) { TraceWriter.WriteLine("tray_reading_bits=" + update.TrayReadingBits + " (" + BambuStatusParser.DescribeTrayBits(update.TrayReadingBits, "RFID-Lesen aktiv") + ")"); }
         if (update.HasTrayReadDoneBits) { TraceWriter.WriteLine("tray_read_done_bits=" + update.TrayReadDoneBits + " (" + BambuStatusParser.DescribeTrayBits(update.TrayReadDoneBits, "RFID-Lesen abgeschlossen") + ")"); }
         if (update.HasResult) { TraceWriter.WriteLine("result=" + update.Result); }
      }

      private void DisposeClient()
      {
         if (_client == null)
         {
            return;
         }
         try
         {
            _client.MqttMsgPublishReceived -= this.OnMessageReceived;
            if (_client.IsConnected)
            {
               _client.Disconnect();
            }
         }
         catch
         {
         }
         _client = null;
      }
   }
}
