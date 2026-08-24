using System;
using System.Net.NetworkInformation;
using System.Threading;
using AMSHelper.Config;
using AMSHelper.Diagnostics;

namespace AMSHelper.Network
{
   public sealed class WifiConnection
   {
      public bool Connect()
      {
         while (true)
         {
            try
            {
               TraceWriter.WriteLine("[WiFi] Verbinde mit " + Configuration.Wifi.Ssid + " ...");
               bool connected = nanoFramework.Networking.WifiNetworkHelper.ConnectDhcp(
                  Configuration.Wifi.Ssid,
                  Configuration.Wifi.Password,
                  requiresDateTime: Configuration.Wifi.RequiresDateTime);

               if (connected)
               {
                  TraceWriter.WriteLine("[WiFi] Verbunden.");
                  this.DumpNetworkInformation();
                  return true;
               }

               TraceWriter.WriteLine("[WiFi] Verbindung fehlgeschlagen: " + nanoFramework.Networking.WifiNetworkHelper.Status.ToString());
               if (nanoFramework.Networking.WifiNetworkHelper.HelperException != null)
               {
                  TraceWriter.WriteLine("[WiFi] " + nanoFramework.Networking.WifiNetworkHelper.HelperException.Message);
               }
            }
            catch (Exception ex)
            {
               TraceWriter.WriteLine("[WiFi] Fehler: " + ex.Message);
            }

            Thread.Sleep(Configuration.Wifi.ReconnectDelayMs);
         }
      }

      private void DumpNetworkInformation()
      {
         NetworkInterface[] interfaces = NetworkInterface.GetAllNetworkInterfaces();
         for (int i = 0; i < interfaces.Length; i++)
         {
            NetworkInterface ni = interfaces[i];
            if (ni.NetworkInterfaceType != NetworkInterfaceType.Wireless80211)
            {
               continue;
            }

            TraceWriter.WriteLine("[WiFi] IP: " + ni.IPv4Address);
            TraceWriter.WriteLine("[WiFi] Gateway: " + ni.IPv4GatewayAddress);
            break;
         }
      }
   }
}
