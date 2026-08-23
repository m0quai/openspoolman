using System;
using System.Collections;
using System.Threading;
using AMSHelper.Config;
using nanoFramework.Hardware.Esp32;
using SystemDebug = System.Diagnostics.Debug;

namespace AMSHelper.Diagnostics
{
   /// <summary>
   /// Central asynchronous debug output. Producers only enqueue messages;
   /// exactly one writer thread accesses System.Diagnostics.Debug.
   /// </summary>
   public static class TraceWriter
   {
      private sealed class TraceEntry
      {
         public string Text;
         public bool NewLine;
      }

      private static readonly object SyncRoot = new object();
      private static readonly Queue Entries = new Queue();
      private static Thread _writerThread;
      private static bool _running;
      private static int _droppedEntries;

      public static void Start()
      {
         lock (SyncRoot)
         {
            if (_running)
            {
               return;
            }

            _running = true;
            _writerThread = new Thread(RunWriter);
            _writerThread.Start();
         }
      }

      public static void Write(string text)
      {
         Enqueue(text, false);
      }

      public static void WriteLine(string text)
      {
         Enqueue(text, true);
      }

      private static void Enqueue(string text, bool newLine)
      {
         Start();

         lock (SyncRoot)
         {
            if (Entries.Count >= Configuration.Debugging.TraceQueueSize)
            {
               Entries.Dequeue();
               _droppedEntries++;
            }

            Entries.Enqueue(new TraceEntry
            {
               Text = text == null ? string.Empty : text,
               NewLine = newLine
            });
         }
      }

      private static void RunWriter()
      {
         int lastHeartbeat = Environment.TickCount;

         while (true)
         {
            TraceEntry entry = null;
            int queueCount;
            int droppedEntries;

            lock (SyncRoot)
            {
               if (Entries.Count > 0)
               {
                  entry = (TraceEntry)Entries.Dequeue();
               }

               queueCount = Entries.Count;
               droppedEntries = _droppedEntries;
            }

            if (entry != null)
            {
               if (entry.NewLine)
               {
                  SystemDebug.WriteLine(entry.Text);
               }
               else
               {
                  SystemDebug.Write(entry.Text);
               }
            }
            else
            {
               Thread.Sleep(Configuration.Debugging.TraceWriterIdleDelayMs);
            }

            int now = Environment.TickCount;
            if (unchecked(now - lastHeartbeat) >= Configuration.Device.TrayHeartbeatIntervalMs)
            {
               WriteHeartbeat(queueCount, droppedEntries);
               lastHeartbeat = now;
            }
         }
      }

      private static void WriteHeartbeat(int queueCount, int droppedEntries)
      {
         uint total;
         uint free;
         uint largestBlock;

         NativeMemory.GetMemoryInfo(NativeMemory.MemoryType.Internal, out total, out free, out largestBlock);

         SystemDebug.WriteLine(
            "[Heartbeat] Free=" + (free / 1024).ToString() + " KB" +
            " | Largest=" + (largestBlock / 1024).ToString() + " KB" +
            " | TraceQueue=" + queueCount.ToString() + "/" + Configuration.Debugging.TraceQueueSize.ToString() +
            " | Dropped=" + droppedEntries.ToString());
      }
   }
}

namespace AMSHelper.Ams
{
   internal static class Debug
   {
      public static void Write(string text) { Diagnostics.TraceWriter.Write(text); }
      public static void WriteLine(string text) { Diagnostics.TraceWriter.WriteLine(text); }
   }
}

namespace AMSHelper.Mqtt
{
   internal static class Debug
   {
      public static void Write(string text) { Diagnostics.TraceWriter.Write(text); }
      public static void WriteLine(string text) { Diagnostics.TraceWriter.WriteLine(text); }
   }
}

namespace AMSHelper.Hardware
{
   internal static class Debug
   {
      public static void Write(string text) { Diagnostics.TraceWriter.Write(text); }
      public static void WriteLine(string text) { Diagnostics.TraceWriter.WriteLine(text); }
   }
}

namespace AMSHelper.Network
{
   internal static class Debug
   {
      public static void Write(string text) { Diagnostics.TraceWriter.Write(text); }
      public static void WriteLine(string text) { Diagnostics.TraceWriter.WriteLine(text); }
   }
}

namespace AMSHelper.Nfc
{
   internal static class Debug
   {
      public static void Write(string text) { Diagnostics.TraceWriter.Write(text); }
      public static void WriteLine(string text) { Diagnostics.TraceWriter.WriteLine(text); }
   }
}
