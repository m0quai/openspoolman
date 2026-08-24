using System.Diagnostics;
using System.Threading;
using AMSHelper.Hardware;
using AMSHelper.Mqtt;
using AMSHelper.Network;

namespace AMSHelper.Ams
{
   /// <summary>
   /// Root device: lifecycle, shared ESP hardware setup, MQTT and global telemetry only.
   /// Tray state and NFC hardware are owned by the individual AmsTray instances.
   /// </summary>
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
         this._mqtt.StatusUpdateReceived += this.BambuStatusUpdateReceived;

         this.SetTray(0, new AmsTray(0, this._mqtt));
         this.SetTray(1, new AmsTray(1, this._mqtt));
         this.SetTray(2, new AmsTray(2, this._mqtt));
         this.SetTray(3, new AmsTray(3, this._mqtt));

         for (int i = 0; i < this.Trays.Length; i++)
         {
            AmsTray tray = this.GetTray(i);
            if (tray != null)
            {
               tray.Start();
            }
         }

         // nanoFrameworks nativer TLS-Handshake kann bei einem fehlgeschlagenen
         // Verbindungsversuch fuer viele Sekunden die Managed-Ausfuehrung stark
         // ausbremsen. Deshalb bekommt die NFC-Hardware vor dem ersten MQTT/TLS-
         // Versuch Zeit, ihre Initialisierung vollstaendig abzuschliessen.
         Thread.Sleep(Config.Configuration.Bambu.InitialConnectDelayMs);

         this._mqtt.Start();

         while (true)
         {
            Thread.Sleep(Config.Configuration.Device.MainLoopDelayMs);
         }
      }

      /// <summary>
      /// Device subscriber receives global telemetry only. No tray state is kept here.
      /// Every AmsTray subscribes independently to the same MQTT status event.
      /// </summary>
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
      }
   }
}
