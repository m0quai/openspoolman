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
      private bool _initialized;
      private bool _initializationFailed;
      private string _lastUid = string.Empty;

      public Pn532Device(int trayIndex)
      {
         _trayIndex = trayIndex;
         _enabled = IsTrayEnabled(trayIndex);
      }

      public bool Enabled { get { return _enabled; } }
      public bool IsPolling { get { return _polling; } }
      public bool IsInitialized { get { return !_enabled || _initialized; } }
      public bool InitializationFailed { get { return _initializationFailed; } }

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
         if (!_enabled || !Config.Configuration.Nfc.Enabled || !_initialized || _polling)
         {
            return false;
         }

         _lastUid = string.Empty;
         _polling = true;
         Debug.WriteLine("[NFC] Tray " + _trayIndex + " READ angefordert");
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
            _initializationFailed = true;
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
                     MaxRetryPassiveActivation = 0x00
                  });

                  _initialized = true;

                  while (true)
                  {
                     if (!_polling)
                     {
                        Thread.Sleep(Config.Configuration.Nfc.IdleDelayMs);
                        continue;
                     }

                     try
                     {
                        Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 ReadPassiveTarget START");
                        byte[] data = pn532.ListPassiveTarget(MaxTarget.One, TargetBaudRate.B106kbpsTypeA);
                        Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 ReadPassiveTarget ENDE | bytes=" + (data == null ? "null" : data.Length.ToString()));

                        if (data != null && data.Length > 1)
                        {
                           var tag = pn532.TryDecode106kbpsTypeA(new SpanByte(data, 1, data.Length - 1));
                           if (tag != null)
                           {
                              string uid = BitConverter.ToString(tag.NfcId);
                              Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 Tag dekodiert | UID=" + uid);

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
                           else
                           {
                              Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 Antwort konnte nicht als Type-A-Tag dekodiert werden.");
                           }
                        }
                     }
                     catch (Exception ex)
                     {
                        Debug.WriteLine("[NFC] Tray " + _trayIndex + " FEHLER bei ReadPassiveTarget: " + ex.GetType().FullName + " | " + ex.Message);
                     }

                     Thread.Sleep(Config.Configuration.Nfc.ScanDelayMs);
                  }
               }
            }
         }
         catch (Exception ex)
         {
            _initializationFailed = true;
            Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 Fehler: " + ex.GetType().FullName + " | " + ex.Message);
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
