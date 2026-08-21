using System;
using System.Device.I2c;
using System.Diagnostics;
using System.Net.NetworkInformation;
using System.Threading;
using Iot.Device.Pn532;
using nanoFramework.Hardware.Esp32;

namespace AMSHelper
{
   using System;
   using System.Diagnostics;
   using System.Net;
   using System.Threading;
   using nanoFramework.Networking;

   namespace AMSHelper
   {
      public class Program
      {
         private const string WifiSsid = "LRWN";
         private const string WifiPassword = "Network@Home4711007";

         public static void Main()
         {
             Debug.WriteLine("================================");
            Debug.WriteLine("AMSHelper WLAN-Test");
            Debug.WriteLine("================================");

            try
            {
               Debug.WriteLine("Verbinde mit WLAN: " + WifiSsid);

               bool success = WifiNetworkHelper.ConnectDhcp(
                   WifiSsid ,
                   WifiPassword ,
                   requiresDateTime: false);

               if (success)
               {
                  Debug.WriteLine("WLAN VERBUNDEN!");

                  NetworkInterface[] interfaces =
                      NetworkInterface.GetAllNetworkInterfaces();

                  for (int i = 0; i < interfaces.Length; i++)
                  {
                     NetworkInterface ni = interfaces[i];

                     if (ni.NetworkInterfaceType ==
                         NetworkInterfaceType.Wireless80211)
                     {
                        Debug.WriteLine("-----------------------------");
                        Debug.WriteLine("WLAN-INTERFACE");
                        Debug.WriteLine("IP:      " + ni.IPv4Address);
                        Debug.WriteLine("Subnetz: " + ni.IPv4SubnetMask);
                        Debug.WriteLine("Gateway: " + ni.IPv4GatewayAddress);
                        Debug.WriteLine("DHCP:    " + ni.IsDhcpEnabled);

                        if (ni.IPv4DnsAddresses != null)
                        {
                           for (int d = 0; d < ni.IPv4DnsAddresses.Length; d++)
                           {
                              Debug.WriteLine(
                                  "DNS " + (d + 1) + ":   " +
                                  ni.IPv4DnsAddresses[d]);
                           }
                        }

                        byte[] mac = ni.PhysicalAddress;

                        if (mac != null && mac.Length > 0)
                        {
                           string macString = "";

                           for (int m = 0; m < mac.Length; m++)
                           {
                              if (m > 0)
                              {
                                 macString += ":";
                              }

                              macString += mac[m].ToString("X2");
                           }

                           Debug.WriteLine("MAC:     " + macString);
                        }

                        Debug.WriteLine("-----------------------------");
                        Debug.WriteLine("");
                        Debug.WriteLine("Teste Verbindung zu NBK-01-548...");

                        Debug.WriteLine("");
                        Debug.WriteLine("Teste Namensauflösung NBK-01-548...");

                        try
                        {
                           IPHostEntry host = Dns.GetHostEntry("NBK-01-548");

                           if (host.AddressList != null && host.AddressList.Length > 0)
                           {
                              for (int i1 = 0; i1 < host.AddressList.Length; i1++)
                              {
                                 Debug.WriteLine(
                                     "NBK-01-548 -> " +
                                     host.AddressList[i].ToString());
                              }
                           }
                           else
                           {
                              Debug.WriteLine("Keine IP-Adresse gefunden.");
                           }
                        }
                        catch (Exception ex)
                        {
                           Debug.WriteLine("Namensauflösung fehlgeschlagen:");
                           Debug.WriteLine(ex.Message);
                        }


                     }
                  }
               }
               else
               {
                  Debug.WriteLine("WLAN-VERBINDUNG FEHLGESCHLAGEN");

                  Debug.WriteLine(
                      "Status: " +
                      WifiNetworkHelper.Status.ToString());

                  if (WifiNetworkHelper.HelperException != null)
                  {
                     Debug.WriteLine(
                         "Fehler: " +
                         WifiNetworkHelper.HelperException.Message);
                  }
               }
            }
            catch (Exception ex)
            {
               Debug.WriteLine("EXCEPTION:");
               Debug.WriteLine(ex.Message);
            }

            Debug.WriteLine("Test beendet.");

            Thread.Sleep(Timeout.Infinite);
         }
      }
   }
   //public class ProgramX
   //{
   //   private const int I2cBus = 1;

   //   private const int SdaPin = 8;
   //   private const int SclPin = 9;

   //   public static void MainI2C()
   //   {
   //      Debug.WriteLine("AMSHelper gestartet.");
   //      Debug.WriteLine("Initialisiere PN532 über I2C...");

   //      // ESP32-S3 GPIO-Zuordnung für I2C1
   //      Configuration.SetPinFunction(
   //          SdaPin ,
   //          DeviceFunction.I2C1_DATA);

   //      Configuration.SetPinFunction(
   //          SclPin ,
   //          DeviceFunction.I2C1_CLOCK);

   //      Debug.WriteLine(
   //          $"I2C1: SDA=GPIO{SdaPin}, SCL=GPIO{SclPin}");

   //      var settings = new I2cConnectionSettings(
   //          I2cBus ,
   //          Pn532.I2cDefaultAddress ,
   //          I2cBusSpeed.StandardMode);

   //      try
   //      {
   //         using (I2cDevice i2cDevice = I2cDevice.Create(settings))
   //         using (Pn532 pn532 = new Pn532(i2cDevice))
   //         {
   //            var firmware = pn532.FirmwareVersion;

   //            if (firmware == null)
   //            {
   //               Debug.WriteLine(
   //                   "FEHLER: PN532 antwortet, aber Firmware-Version konnte nicht gelesen werden.");
   //            }
   //            else
   //            {
   //               Debug.WriteLine("PN532 erkannt.");
   //               Debug.WriteLine(
   //                   $"Chip-ID: 0x{firmware.IdentificationCode:X2}");
   //               Debug.WriteLine(
   //                   $"Firmware: {firmware.Version}");
   //               Debug.WriteLine(
   //                   $"Ist PN532: {firmware.IsPn532}");
   //            }
   //         }
   //      }
   //      catch (Exception ex)
   //      {
   //         Debug.WriteLine("PN532 FEHLER:");
   //         Debug.WriteLine(ex.Message);
   //      }

   //      Thread.Sleep(Timeout.Infinite);
   //   }
   //}
}