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

      public bool IsConnected => _client != null && _client.IsConnected;

      public void Start()
      {
         if (_running)
         {
            return;
         }

         _running = true;
         _worker = new Thread(Run);
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
                  ConnectAndSubscribe();
               }
            }
            catch (Exception ex)
            {
               Debug.WriteLine("[BambuMQTT] Fehler: " + ex.Message);
               DisposeClient();
            }

            Thread.Sleep(Configuration.Bambu.MqttReconnectDelayMs);
         }
      }

      private void ConnectAndSubscribe()
      {
         DisposeClient();

         Debug.WriteLine("[BambuMQTT] Verbinde " + Configuration.Bambu.PrinterIp + ":" + Configuration.Bambu.MqttPort + " ...");

         _client = new MqttClient(
             Configuration.Bambu.PrinterIp,
             Configuration.Bambu.MqttPort,
             Configuration.Bambu.MqttUseTls,
             null,
             null,
             MqttSslProtocols.TLSv1_2);

         _client.Settings.ValidateServerCertificate = Configuration.Bambu.ValidateServerCertificate;
         _client.MqttMsgPublishReceived += OnMessageReceived;

         MqttReasonCode result = _client.Connect(
             Configuration.Bambu.MqttClientId,
             Configuration.Bambu.MqttUsername,
             Configuration.Bambu.LanAccessCode);

         if (result != MqttReasonCode.Success)
         {
            throw new Exception("MQTT Connect fehlgeschlagen: " + result.ToString());
         }

         _client.Subscribe(
             new string[] { Configuration.Bambu.MqttReportTopic },
             new MqttQoSLevel[] { MqttQoSLevel.AtMostOnce });

         Debug.WriteLine("[BambuMQTT] Verbunden.");
         Debug.WriteLine("[BambuMQTT] Subscribe: " + Configuration.Bambu.MqttReportTopic);

         RequestFullStatus();
      }

      private void RequestFullStatus()
      {
         if (_client == null || !_client.IsConnected)
         {
            return;
         }

         string payload = "{\"pushing\":{\"sequence_id\":\"0\",\"command\":\"pushall\"}}";

         Debug.WriteLine("[BambuMQTT] Fordere aktuellen Gesamtstatus an (pushall)...");

         _client.Publish(
             Configuration.Bambu.MqttRequestTopic,
             Encoding.UTF8.GetBytes(payload),
             null,
             null,
             MqttQoSLevel.AtMostOnce,
             false);

         Debug.WriteLine("[BambuMQTT] Gesamtstatus angefordert.");
      }

      private void OnMessageReceived(object sender, MqttMsgPublishEventArgs e)
      {
         // Wichtig auf nanoFramework: pro MQTT-Nachricht nur EINEN Payload-String erzeugen.
         string payload = e.Message == null ? string.Empty : Encoding.UTF8.GetString(e.Message, 0, e.Message.Length);

         BambuStatusUpdate update = _parser.Parse(payload);

         // TEMPORAERE Diagnose: Rohwerte vor jeder fachlichen Tray-Auswertung ausgeben.
         // Dadurch ist sichtbar, wann der P1S die einzelnen AMS-Zustandsfelder wirklich sendet.
         if (Configuration.Debugging.DumpRawAmsStatusFields)
         {
            DumpRawAmsStatusFields(update);
         }

         if (StatusUpdateReceived != null)
         {
            StatusUpdateReceived(update);
         }

         if (!Configuration.Debugging.DumpAllBambuReports)
         {
            return;
         }

         bool hasAmsInformation = HasAmsInformation(update);

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
            Debug.Write(".");
            return;
         }

         if (!hasAmsInformation && !Configuration.Debugging.DumpTelemetryOnlyBambuReports)
         {
            Debug.Write(".");
            return;
         }

         Debug.WriteLine("");
         Debug.WriteLine("================ BAMBU MQTT /report ================");
         Debug.WriteLine("Topic: " + e.Topic);

         if (hasAmsInformation)
         {
            DumpCompactAmsReport(update);
         }
         else
         {
            Debug.WriteLine("[nur Standard-Telemetrie]");
         }

         Debug.WriteLine("================ END BAMBU MQTT =====================");
         Debug.WriteLine("");
      }

      private static void DumpRawAmsStatusFields(BambuStatusUpdate update)
      {
         if (update == null)
         {
            return;
         }

         bool hasRawAmsState = update.HasAmsStatus || update.HasActiveTray || update.HasTargetTray ||
             update.HasPreviousTray || update.HasTrayReadingBits || update.HasTrayReadDoneBits ||
             update.HasTrayExistBits || update.HasCommandSlotId || update.HasCommandTarget ||
             (update.HasCommand && update.Command != null && update.Command.IndexOf("ams_") == 0);

         if (!hasRawAmsState)
         {
            return;
         }

         string line = "[AMS-RAW]";

         if (update.HasCommand)
         {
            line += " cmd=" + update.Command;
         }
         if (update.HasAmsStatus)
         {
            line += " ams_status=" + update.AmsStatus;
         }
         if (update.HasTargetTray)
         {
            line += " tray_tar=" + update.TargetTray;
         }
         if (update.HasActiveTray)
         {
            line += " tray_now=" + update.ActiveTray;
         }
         if (update.HasPreviousTray)
         {
            line += " tray_pre=" + update.PreviousTray;
         }
         if (update.HasTrayReadingBits)
         {
            line += " reading=" + update.TrayReadingBits;
         }
         if (update.HasTrayReadDoneBits)
         {
            line += " read_done=" + update.TrayReadDoneBits;
         }
         if (update.HasTrayExistBits)
         {
            line += " exist=" + update.TrayExistBits;
         }
         if (update.HasCommandSlotId)
         {
            line += " slot_id=" + update.CommandSlotId;
         }
         if (update.HasCommandTarget)
         {
            line += " target=" + update.CommandTarget;
         }
         if (update.HasResult)
         {
            line += " result=" + update.Result;
         }
         if (update.HasReason)
         {
            line += " reason=" + update.Reason;
         }

         Debug.WriteLine(line);
      }

      private static bool HasAmsInformation(BambuStatusUpdate update)
      {
         if (update == null)
         {
            return false;
         }

         if (update.HasAmsStatus || update.HasActiveTray || update.HasTargetTray ||
             update.HasPreviousTray || update.HasTrayReadingBits || update.HasTrayReadDoneBits ||
             update.HasAmsId || update.HasCommandSlotId || update.HasCommandTarget)
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
         if (update.HasCommand)
         {
            Debug.WriteLine("command=" + update.Command);
         }
         if (update.HasAmsStatus)
         {
            Debug.WriteLine("ams_status=" + update.AmsStatus + " (" + BambuStatusParser.DescribeAmsStatus(update.AmsStatus) + ")");
         }
         if (update.HasCommandSlotId)
         {
            Debug.WriteLine("slot_id=" + update.CommandSlotId + " (" + BambuStatusParser.DescribeTrayId(update.CommandSlotId, "angeforderter Tray") + ")");
         }
         if (update.HasCommandTarget)
         {
            Debug.WriteLine("target=" + update.CommandTarget + " (" + BambuStatusParser.DescribeTrayId(update.CommandTarget, "Ziel") + ")");
         }
         if (update.HasTargetTray)
         {
            Debug.WriteLine("tray_tar=" + update.TargetTray + " (" + BambuStatusParser.DescribeTrayId(update.TargetTray, "Ziel-Tray") + ")");
         }
         if (update.HasActiveTray)
         {
            Debug.WriteLine("tray_now=" + update.ActiveTray + " (" + BambuStatusParser.DescribeTrayId(update.ActiveTray, "aktiver Tray") + ")");
         }
         if (update.HasPreviousTray)
         {
            Debug.WriteLine("tray_pre=" + update.PreviousTray + " (" + BambuStatusParser.DescribeTrayId(update.PreviousTray, "vorheriger Tray") + ")");
         }
         if (update.HasTrayReadingBits)
         {
            Debug.WriteLine("tray_reading_bits=" + update.TrayReadingBits + " (" + BambuStatusParser.DescribeTrayBits(update.TrayReadingBits, "RFID-Lesen aktiv") + ")");
         }
         if (update.HasTrayReadDoneBits)
         {
            Debug.WriteLine("tray_read_done_bits=" + update.TrayReadDoneBits + " (" + BambuStatusParser.DescribeTrayBits(update.TrayReadDoneBits, "RFID-Lesen abgeschlossen") + ")");
         }
         if (update.HasResult)
         {
            Debug.WriteLine("result=" + update.Result);
         }
      }

      private void DisposeClient()
      {
         if (_client == null)
         {
            return;
         }

         try
         {
            _client.MqttMsgPublishReceived -= OnMessageReceived;
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
