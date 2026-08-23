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

      public string AmsHumidity { get { return _amsHumidity; } }
      public string AmsHumidityRaw { get { return _amsHumidityRaw; } }
      public string AmsTemperature { get { return _amsTemperature; } }

      public void Start()
      {
         Debug.WriteLine("================================");
         Debug.WriteLine(Config.Configuration.Device.Name + " gestartet");
         Debug.WriteLine("================================");

         var wifi = new WifiConnection();
         wifi.Connect();


         _mqtt = new BambuMqtt();
         _mqtt.StatusUpdateReceived += BambuStatusUpdateReceived;

         SetTray(0, new AmsTray(0, _mqtt));
         SetTray(1, new AmsTray(1, _mqtt));
         SetTray(2, new AmsTray(2, _mqtt));
         SetTray(3, new AmsTray(3, _mqtt));

         for (int i = 0; i < Trays.Length; i++)
         {
            AmsTray tray = GetTray(i);
            if (tray != null)
            {
               tray.Start();
            }
         }

         _mqtt.Start();

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
            _amsHumidity = update.AmsHumidity;
         }

         if (update.HasAmsHumidityRaw)
         {
            _amsHumidityRaw = update.AmsHumidityRaw;
         }

         if (update.HasAmsTemperature)
         {
            _amsTemperature = update.AmsTemperature;
         }
      }
   }
}
