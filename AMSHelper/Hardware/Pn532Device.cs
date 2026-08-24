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
      private long _pollingStartedTicks;

      public Pn532Device(int trayIndex)
      {
         _trayIndex = trayIndex;
         _enabled = trayIndex == 0 && Config.Configuration.Nfc.Enabled && Config.Configuration.Nfc.Tray0Enabled;
      }

      public bool Enabled { get { return _enabled; } }
      public bool IsPolling { get { return _polling; } }
      public bool IsInitialized { get { return !_enabled || _initialized; } }
      public bool InitializationFailed { get { return _initializationFailed; } }

      public void Start()
      {
         if (!_enabled || _readerThread != null) { return; }
         _readerThread = new Thread(this.RunReader);
         _readerThread.Start();
      }

      public bool StartPolling()
      {
         if (!_enabled || !_initialized || _polling) { return false; }
         _lastUid = string.Empty;
         _pollingStartedTicks = DateTime.UtcNow.Ticks;
         _polling = true;
         return true;
      }

      public bool StopPolling()
      {
         if (!_polling) { return false; }
         _polling = false;
         return true;
      }

      private bool HasPollingTimedOut()
      {
         if (!_polling) { return false; }
         long timeoutTicks = (long)Config.Configuration.Nfc.PollingCycleTimeoutMs * TimeSpan.TicksPerMillisecond;
         return DateTime.UtcNow.Ticks - _pollingStartedTicks >= timeoutTicks;
      }

      private void RunReader()
      {
         Thread.Sleep(Config.Configuration.Nfc.StartupDelayMs);
         Debug.WriteLine("[NFC] Tray " + _trayIndex + " Thread gestartet.");
         int sdaPin = Config.Configuration.Nfc.Tray0I2cSdaPin;
         int sclPin = Config.Configuration.Nfc.Tray0I2cSclPin;
         if (sdaPin < 0 || sclPin < 0)
         {
            _initializationFailed = true;
            Debug.WriteLine("[NFC] Tray " + _trayIndex + " I2C-Pins sind nicht konfiguriert.");
            return;
         }
         nanoFramework.Hardware.Esp32.Configuration.SetPinFunction(sdaPin, DeviceFunction.I2C1_DATA);
         nanoFramework.Hardware.Esp32.Configuration.SetPinFunction(sclPin, DeviceFunction.I2C1_CLOCK);
         var settings = new I2cConnectionSettings(Config.Configuration.Nfc.I2cBus, Config.Configuration.Nfc.Pn532I2cAddress, I2cBusSpeed.StandardMode);
         try
         {
            using (I2cDevice i2cDevice = I2cDevice.Create(settings))
            {
               using (Pn532 pn532 = new Pn532(i2cDevice))
               {
                  pn532.ReadTimeOut = Config.Configuration.Nfc.ReadTimeoutMs;
                  Debug.WriteLine("[NFC] Tray " + _trayIndex + " PN532 erkannt: " + pn532.FirmwareVersion.Version);
                  pn532.SetMaxRetriesInitialization(new MaxRetriesMode { MaxRetryAnswerToReset = 0x00, MaxRetryPSL = 0x00, MaxRetryPassiveActivation = 0x00 });
                  _initialized = true;
                  while (true)
                  {
                     if (!_polling)
                     {
                        Thread.Sleep(Config.Configuration.Nfc.IdleDelayMs);
                        continue;
                     }
                     if (this.HasPollingTimedOut())
                     {
                        _polling = false;
                        Debug.WriteLine("[NFC] Tray " + _trayIndex + " Polling TIMEOUT nach " + Config.Configuration.Nfc.PollingCycleTimeoutMs.ToString() + " ms");
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
                                 UidReadHandler handler = this.UidRead;
                                 if (handler != null) { handler(uid); }
                              }
                              pn532.ReleaseTarget(tag.TargetNumber);
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
   }
}
