using System;
using System.Collections;
using System.Threading;
using nanoFramework.Hardware.Esp32;
using AppConfiguration = AMSHelper.Config.Configuration;
using SystemDebug = System.Diagnostics.Debug;

namespace AMSHelper.Diagnostics
{
   public static class TraceWriter
   {
      private sealed class TraceEntry
      {
         public string Text;
         public bool NewLine;
      }

      private static readonly object _syncRoot = new object();
      private static readonly Queue _entries = new Queue();
      private static Thread _writerThread;
      private static bool _running;
      private static int _droppedEntries;

      public static void Start()
      {
         lock (TraceWriter._syncRoot)
         {
            if (_running)
            {
               return;
            }

            _running = true;
            _writerThread = new Thread(TraceWriter.RunWriter);
            _writerThread.Start();
         }
      }

      public static void Write(string text)
      {
         TraceWriter.Enqueue(text, false);
      }

      public static void WriteLine(string text)
      {
         TraceWriter.Enqueue(text, true);
      }

      private static void Enqueue(string text, bool newLine)
      {
         TraceWriter.Start();
         lock (TraceWriter._syncRoot)
         {
            if (TraceWriter._entries.Count >= AppConfiguration.Debugging.TraceQueueSize)
            {
               TraceWriter._entries.Dequeue();
               _droppedEntries++;
            }

            TraceWriter._entries.Enqueue(new TraceEntry { Text = text == null ? string.Empty : text, NewLine = newLine });
         }
      }

      private static void RunWriter()
      {
         long lastHeartbeatTicks = DateTime.UtcNow.Ticks;
         long heartbeatIntervalTicks = (long)AppConfiguration.Device.TrayHeartbeatIntervalMs * TimeSpan.TicksPerMillisecond;
         while (true)
         {
            TraceEntry entry = null;
            int queueCount;
            int droppedEntries;
            lock (TraceWriter._syncRoot)
            {
               if (TraceWriter._entries.Count > 0)
               {
                  entry = (TraceEntry)TraceWriter._entries.Dequeue();
               }

               queueCount = TraceWriter._entries.Count;
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
               Thread.Sleep(AppConfiguration.Debugging.TraceWriterIdleDelayMs);
            }

            long nowTicks = DateTime.UtcNow.Ticks;
            if (nowTicks - lastHeartbeatTicks >= heartbeatIntervalTicks)
            {
               TraceWriter.WriteHeartbeat(queueCount, droppedEntries);
               lastHeartbeatTicks = nowTicks;
            }
         }
      }

      private static void WriteHeartbeat(int queueCount, int droppedEntries)
      {
         uint total;
         uint free;
         uint largestBlock;
         NativeMemory.GetMemoryInfo(NativeMemory.MemoryType.Internal, out total, out free, out largestBlock);
         SystemDebug.WriteLine("[Heartbeat] Free=" + (free / 1024).ToString() + " KB | Largest=" + (largestBlock / 1024).ToString() + " KB | TraceQueue=" + queueCount.ToString() + "/" + AppConfiguration.Debugging.TraceQueueSize.ToString() + " | Dropped=" + droppedEntries.ToString());
      }
   }
}
