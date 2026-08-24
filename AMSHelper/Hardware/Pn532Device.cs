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
         this._trayIndex = trayIndex;
         this._enabled = trayIndex == 0 && Config.Configuration.Nfc.Enabled && Config.Configuration.Nfc.Tray0Enabled;
      }

      public bool Enabled { get { return this._enabled; } }
      public bool IsPolling { get { return this._polling; } }
      public bool IsInitialized { get { return !this._enabled || this._initialized; } }
      public bool InitializationFailed { get { return this._initializationFailed; } }

      public void Start()
      {
         if (!this._enabled || this._readerThread != null) { return; }
         this._readerThread = new Thread(this.RunReader);
         this._readerThread.Start();
      }

      public bool StartPolling()
      {
         if (!this._enabled || !this._initialized || this._polling) { return false; }
         this._lastUid = string.Empty;
         this._pollingStartedTicks = DateTime.UtcNow.Ticks;
         this._polling = true;
         return true;
      }

      public bool StopPolling()
      {
         if (!this._polling) { return false; }
         this._polling = false;
         return true;
      }

      private bool HasPollingTimedOut()
      {
         if (!this._polling) { return false; }
         long timeoutTicks = (long)Config.Configuration.Nfc.PollingCycleTimeoutMs * TimeSpan.TicksPerMillisecond;
         return DateTime.UtcNow.Ticks - this._pollingStartedTicks >= timeoutTicks;
      }

      private void RunReader()
      {
         Thread.Sleep(Config.Configuration.Nfc.StartupDelayMs);
         Debug.WriteLine("[NFC] Tray " + this._trayIndex + " Thread gestartet.");
         int sdaPin = Config.Configuration.Nfc.Tray0I2cSdaPin;
         int sclPin = Config.Configuration.Nfc.Tray0I2cSclPin;
         if (sdaPin < 0 || sclPin < 0)
         {
            this._initializationFailed = true;
            Debug.WriteLine("[NFC] Tray " + this._trayIndex + " I2C-Pins sind nicht konfiguriert.");
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
                  Debug.WriteLine("[NFC] Tray " + this._trayIndex + " PN532 erkannt: " + pn532.FirmwareVersion.Version);
                  pn532.SetMaxRetriesInitialization(new MaxRetriesMode { MaxRetryAnswerToReset = 0x00, MaxRetryPSL = 0x00, MaxRetryPassiveActivation = 0x00 });
                  this._initialized = true;
                  while (true)
                  {
                     if (!this._polling)
                     {
                        Thread.Sleep(Config.Configuration.Nfc.IdleDelayMs);
                        continue;
                     }
                     if (this.HasPollingTimedOut())
                     {
                        this._polling = false;
                        Debug.WriteLine("[NFC] Tray " + this._trayIndex + " Polling TIMEOUT nach " + Config.Configuration.Nfc.PollingCycleTimeoutMs.ToString() + " ms");
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
                              if (this._polling && uid != this._lastUid)
                              {
                                 this._lastUid = uid;
                                 UidReadHandler handler = this.UidRead;
                                 if (handler != null) { handler(uid); }
                              }
                              pn532.ReleaseTarget(tag.TargetNumber);
                           }
                        }
                     }
                     catch (Exception ex)
                     {
                        Debug.WriteLine("[NFC] Tray " + this._trayIndex + " FEHLER bei ReadPassiveTarget: " + ex.GetType().FullName + " | " + ex.Message);
                     }
                     Thread.Sleep(Config.Configuration.Nfc.ScanDelayMs);
                  }
               }
            }
         }
         catch (Exception ex)
         {
            this._initializationFailed = true;
            Debug.WriteLine("[NFC] Tray " + this._trayIndex + " PN532 Fehler: " + ex.GetType().FullName + " | " + ex.Message);
         }
      }
   }
}
