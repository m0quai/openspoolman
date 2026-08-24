using System.Diagnostics;
using System.Threading;
using AMSHelper.Hardware;
using AMSHelper.Mqtt;
using AMSHelper.Network;

namespace AMSHelper.Ams
{
   public sealed class AmsHelperDevice : EspDevice
   {
      private BambuMqtt _mqtt;
      private string _amsHumidity = string.Empty;
      private string _amsHumidityRaw = string.Empty;
      private string _amsTemperature = string.Empty;

      public AmsHelperDevice() : base(Config.Configuration.Device.AmsSlotCount)
      {
      }

      public string AmsHumidity { get { return this._amsHumidity; } }
      public string AmsHumidityRaw { get { return this._amsHumidityRaw; } }
      public string AmsTemperature { get { return this._amsTemperature; } }

      public void Start()
      {
         Debug.WriteLine("================================");
         Debug.WriteLine(Config.Configuration.Device.Name + " gestartet");
         Debug.WriteLine("================================");

         var wifi = new WifiConnection();
         wifi.Connect();

         this._mqtt = new BambuMqtt();

         this.SetTray(0, new AmsTray(0, this._mqtt));
         this.SetTray(1, new AmsTray(1, this._mqtt));
         this.SetTray(2, new AmsTray(2, this._mqtt));
         this.SetTray(3, new AmsTray(3, this._mqtt));

         // Wichtig: Device-Handler zuletzt registrieren. Dadurch haben alle AmsTray-
         // Instanzen denselben MQTT-Status bereits verarbeitet, bevor der gemeinsame
         // Gesamtstatus ausgegeben wird.
         this._mqtt.StatusUpdateReceived += this.BambuStatusUpdateReceived;

         for (int i = 0; i < this.Trays.Length; i++)
         {
            AmsTray tray = this.GetTray(i);
            if (tray != null)
            {
               tray.Start();
            }
         }

         Thread.Sleep(Config.Configuration.Bambu.InitialConnectDelayMs);
         this._mqtt.Start();

         while (true)
         {
            Thread.Sleep(Config.Configuration.Device.MainLoopDelayMs);
         }
      }

      private void BambuStatusUpdateReceived(BambuStatusUpdate update)
      {
         if (update == null)
         {
            return;
         }

         if (update.HasAmsHumidity)
         {
            this._amsHumidity = update.AmsHumidity;
         }

         if (update.HasAmsHumidityRaw)
         {
            this._amsHumidityRaw = update.AmsHumidityRaw;
         }

         if (update.HasAmsTemperature)
         {
            this._amsTemperature = update.AmsTemperature;
         }

         if (update.AmsOutputProduced)
         {
            this.WriteTrayStatus();
         }
      }

      private void WriteTrayStatus()
      {
         Debug.WriteLine("[AMS] -------- Gesamtstatus --------");

         for (int i = 0; i < this.Trays.Length; i++)
         {
            AmsTray tray = this.GetTray(i);
            if (tray == null)
            {
               continue;
            }

            string line = "[AMS] Tray " + tray.Index + ": " + tray.Activity;
            line += tray.IsOccupied ? " | BELEGT" : " | LEER";
            line += tray.Pn532Enabled ? " | PN532=aktiv" : " | PN532=deaktiviert";

            if (tray.Pn532Enabled)
            {
               line += tray.Uid.Length > 0 ? " | UID=" + tray.Uid : " | UID=noch nicht gelesen";
            }

            Debug.WriteLine(line);
         }

         Debug.WriteLine("[AMS] ------------------------------");
      }
   }
}
