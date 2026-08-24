using System;
using System.IO;
using System.Net;
using System.Text;
using AMSHelper.Config;
using AMSHelper.Diagnostics;

namespace AMSHelper.OpenSpoolMan
{
   public sealed class OpenSpoolManClient
   {
      public bool AssignUid(int trayIndex, string uid)
      {
         if (string.IsNullOrEmpty(uid))
         {
            return false;
         }

         return this.PostAssignment(trayIndex, uid);
      }

      public bool ClearTray(int trayIndex)
      {
         return this.PostAssignment(trayIndex, "CLEAR");
      }

      private bool PostAssignment(int trayIndex, string uid)
      {
         if (string.IsNullOrEmpty(Configuration.OpenSpoolMan.BaseUrl))
         {
            TraceWriter.WriteLine("[OSM] Host nicht konfiguriert.");
            return false;
         }

         string url = Configuration.OpenSpoolMan.BaseUrl + "/ams/nfc/" + trayIndex.ToString() + "/assign";
         string json = "{\"uid\":\"" + OpenSpoolManClient.EscapeJson(uid) + "\"}";
         byte[] data = Encoding.UTF8.GetBytes(json);

         try
         {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = "POST";
            request.ContentType = "application/json";
            request.ContentLength = data.Length;
            request.Timeout = Configuration.OpenSpoolMan.RequestTimeoutMs;

            using (Stream stream = request.GetRequestStream())
            {
               stream.Write(data, 0, data.Length);
            }

            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {
               int statusCode = (int)response.StatusCode;
               bool success = statusCode >= 200 && statusCode < 300;
               TraceWriter.WriteLine("[OSM] Tray " + trayIndex.ToString() + " -> " + uid + " | HTTP " + statusCode.ToString());
               return success;
            }
         }
         catch (Exception ex)
         {
            TraceWriter.WriteLine("[OSM] Tray " + trayIndex.ToString() + " Fehler: " + ex.Message);
            return false;
         }
      }

      private static string EscapeJson(string value)
      {
         if (value == null)
         {
            return string.Empty;
         }

         return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
      }
   }
}
