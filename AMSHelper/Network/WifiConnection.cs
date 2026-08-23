using System;
using System.Diagnostics;
using System.Net.NetworkInformation;
using System.Threading;
using AMSHelper.Config;
using nanoFramework.Networking;

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
                    Debug.WriteLine("[WiFi] Verbinde mit " + Configuration.Wifi.Ssid + " ...");
                    bool connected = WifiNetworkHelper.ConnectDhcp(
                        Configuration.Wifi.Ssid,
                        Configuration.Wifi.Password,
                        requiresDateTime: Configuration.Wifi.RequiresDateTime);

                    if (connected)
                    {
                        Debug.WriteLine("[WiFi] Verbunden.");
                        DumpNetworkInformation();
                        return true;
                    }

                    Debug.WriteLine("[WiFi] Verbindung fehlgeschlagen: " + WifiNetworkHelper.Status.ToString());
                    if (WifiNetworkHelper.HelperException != null)
                    {
                        Debug.WriteLine("[WiFi] " + WifiNetworkHelper.HelperException.Message);
                    }
                }
                catch (Exception ex)
                {
                    Debug.WriteLine("[WiFi] Fehler: " + ex.Message);
                }

                Thread.Sleep(Configuration.Wifi.ReconnectDelayMs);
            }
        }

        private static void DumpNetworkInformation()
        {
            NetworkInterface[] interfaces = NetworkInterface.GetAllNetworkInterfaces();
            for (int i = 0; i < interfaces.Length; i++)
            {
                NetworkInterface ni = interfaces[i];
                if (ni.NetworkInterfaceType != NetworkInterfaceType.Wireless80211)
                {
                    continue;
                }

                Debug.WriteLine("[WiFi] IP: " + ni.IPv4Address);
                Debug.WriteLine("[WiFi] Gateway: " + ni.IPv4GatewayAddress);
                break;
            }
        }
    }
}
