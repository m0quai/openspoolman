using System;
using System.Device.I2c;
using System.Diagnostics;
using System.Threading;
using nanoFramework.Hardware.Esp32;
using Iot.Device.Pn532;
using Iot.Device.Pn532.ListPassive;
using Iot.Device.Pn532.RfConfiguration;

namespace AMSHelper.Hardware
{
   public sealed class Pn532Device
   {
      public delegate void UidReadHandler(string uid);
      public event UidReadHandler UidRead;

      private readonly int _trayIndex;
      private readonly bool _enabled;
      private Thread _readerThread;
      private bool _polling;
      private string _lastUid = string.Empty;

      public Pn532Device(int trayIndex)
      {
         _trayIndex = trayIndex;
         _enabled = IsTrayEnabled(trayIndex);
      }

      public bool Enabled { get { return _enabled; } }
      public bool IsPolling { get { return _polling; } }

      public void Start()
      {
         if (!_enabled || !Config.Configuration.Nfc.Enabled || _readerThread != null)
         {
            return;
         }

         _readerThread = new Thread(RunReader);
         _readerThread.Start();
      }

      public bool StartPolling()
      {
         if (_polling)
         {
            return false;
         }

         _lastUid = string.Empty;
         _polling = true;
         return true;
      }

      public bool StopPolling()
      {
         if (!_polling)
         {
            return false;
         }

         _polling = false;
         return true;
      }

      private void RunReader()
      {
         Thread.Sleep(Config.Configuration.Nfc.StartupDelayMs);
         Debug.WriteLine("[NFC] Tray " + _trayIndex + " Thread gestartet.");

         int sdaPin = GetSdaPin(_trayIndex);
         int sclPin = GetSclPin(_trayIndex);
         if (sdaPin < 0 || sclPin < 0)
         {
            Debug.WriteLine("[NFC] Tray " + _trayIndex + " I2C-Pins sind nicht konfiguriert.");
            return;
         }

         nanoFramework.Hardware.Esp32.Configuration.SetPinFunction(sdaPin, DeviceFunction.I2C1_DATA);
         nanoFramework.Hardware.Esp32.Configuration.SetPinFunction(sclPin, DeviceFunction.I2C1_CLOCK);

         var settings = new I2cConnectionSettings(
            Config.Configuration.Nfc.I2cBus,
            Config.Configuration.Nfc.Pn532I2cAddress,
            I2cBusSpeed.StandardMode);

         try
         {
            using (I2cDevice i2cDevice = I2cDevice.Create(settings))
            {
               using (Pn532 pn532 = new Pn532(i2cDevice))
               {
                  pn532.ReadTimeOut = Config.Configuration.Nfc.ReadTimeoutMs;
                  Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 erkannt: " + pn532.FirmwareVersion.Version);
                  pn532.SetMaxRetriesInitialization(new MaxRetriesMode
                  {
                     MaxRetryAnswerToReset = 0x00,
                     MaxRetryPSL = 0x00,
                     MaxRetryPassiveActivation = 0x01
                  });

                  while (true)
                  {
                     if (!_polling)
                     {
                        Thread.Sleep(Config.Configuration.Nfc.ScanDelayMs);
                        continue;
                     }

                     try
                     {
                        byte[] data = pn532.ListPassiveTarget(MaxTarget.One, TargetBaudRate.B106kbpsTypeA);
                        if (data != null && data.Length > 1)
                        {
                           var tag = pn532.TryDecode106kbpsTypeA(new SpanByte(data, 1, data.Length - 1));
                           if (tag != null)
                           {
                              string uid = BitConverter.ToString(tag.NfcId);
                              if (_polling && uid != _lastUid)
                              {
                                 _lastUid = uid;
                                 UidReadHandler handler = UidRead;
                                 if (handler != null)
                                 {
                                    handler(uid);
                                 }
                              }

                              pn532.ReleaseTarget(tag.TargetNumber);
                           }
                        }
                     }
                     catch (Exception ex)
                     {
                        Debug.WriteLine("[NFC] Tray " + _trayIndex + " Tag-Lesefehler: " + ex.Message);
                     }

                     Thread.Sleep(Config.Configuration.Nfc.ScanDelayMs);
                  }
               }
            }
         }
         catch (Exception ex)
         {
            Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 Fehler: " + ex.Message);
         }
      }

      private static bool IsTrayEnabled(int trayIndex)
      {
         switch (trayIndex)
         {
            case 0:
               return Config.Configuration.Nfc.Tray0Enabled;
            case 1:
               return Config.Configuration.Nfc.Tray1Enabled;
            case 2:
               return Config.Configuration.Nfc.Tray2Enabled;
            case 3:
               return Config.Configuration.Nfc.Tray3Enabled;
            default:
               return false;
         }
      }

      private static int GetSdaPin(int trayIndex)
      {
         switch (trayIndex)
         {
            case 0:
               return Config.Configuration.Nfc.Tray0I2cSdaPin;
            case 1:
               return Config.Configuration.Nfc.Tray1I2cSdaPin;
            case 2:
               return Config.Configuration.Nfc.Tray2I2cSdaPin;
            case 3:
               return Config.Configuration.Nfc.Tray3I2cSdaPin;
            default:
               return -1;
         }
      }

      private static int GetSclPin(int trayIndex)
      {
         switch (trayIndex)
         {
            case 0:
               return Config.Configuration.Nfc.Tray0I2cSclPin;
            case 1:
               return Config.Configuration.Nfc.Tray1I2cSclPin;
            case 2:
               return Config.Configuration.Nfc.Tray2I2cSclPin;
            case 3:
               return Config.Configuration.Nfc.Tray3I2cSclPin;
            default:
               return -1;
         }
      }
   }
}
