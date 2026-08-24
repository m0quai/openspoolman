namespace AMSHelper.Hardware
{
   public abstract class EspDevice
   {
      protected EspDevice(int trayCount)
      {
         this.Trays = new Ams.AmsTray[trayCount];
      }

      public Ams.AmsTray[] Trays { get; private set; }

      protected void SetTray(int index, Ams.AmsTray tray)
      {
         if (index < 0 || index >= this.Trays.Length)
         {
            return;
         }

         this.Trays[index] = tray;
      }

      public Ams.AmsTray GetTray(int index)
      {
         if (index < 0 || index >= this.Trays.Length)
         {
            return null;
         }

         return this.Trays[index];
      }
   }
}
