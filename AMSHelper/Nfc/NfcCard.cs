using System;
using System.Diagnostics;
using Iot.Device.Card;
using Iot.Device.Pn532;
using Iot.Device.Rfid;

namespace AMSHelper.Nfc
{
   public enum NfcCardType
   {
      Unknown = 0,

      // MIFARE Classic
      MifareClassicMini,
      MifareClassic1K,
      MifareClassic4K,

      // MIFARE Ultralight / NTAG-Familie
      MifareUltralightOrNtag,

      // NXP NTAG21x
      Ntag213,
      Ntag215,
      Ntag216,
      MifareUltralightOrUnknownType2
   }
   public static class NfcCard
   {
      public static NfcCardType DetectTagType(Pn532 pn532 ,Data106kbpsTypeA tag)
      {
         ushort atqa = tag.Atqa;
         byte sak = tag.Sak;

         // ---------------------------------------------------------
         // MIFARE Classic
         // ---------------------------------------------------------

         // MIFARE Classic 1K
         if (sak == 0x08)
         {
            return NfcCardType.MifareClassic1K;
         }

         // MIFARE Classic 4K
         if (sak == 0x18)
         {
            return NfcCardType.MifareClassic4K;
         }

         // MIFARE Mini
         if (sak == 0x09)
         {
            return NfcCardType.MifareClassicMini;
         }

         // ---------------------------------------------------------
         // MIFARE Ultralight / NTAG21x
         //
         // Diese Familie meldet typischerweise SAK = 0x00.
         // ATQA/SAK reichen NICHT, um 213/215/216 zu unterscheiden.
         // ---------------------------------------------------------

         if (sak == 0x00)
         {
            NfcCardType ntag =
                DetectNtag21x(pn532 ,tag.TargetNumber);

            if (ntag != NfcCardType.Unknown)
            {
               return ntag;
            }

            return NfcCardType.MifareUltralightOrNtag;
         }

         return NfcCardType.Unknown;
      }
      public static string GetTagTypeName(NfcCardType tagType)
      {
         switch (tagType)
         {
            case NfcCardType.MifareClassicMini:
               return "MifareClassicMini";

            case NfcCardType.MifareClassic1K:
               return "MifareClassic1K";

            case NfcCardType.MifareClassic4K:
               return "MifareClassic4K";

            case NfcCardType.MifareUltralightOrUnknownType2:
               return "MifareUltralightOrUnknownType2";

            case NfcCardType.Ntag213:
               return "Ntag213";

            case NfcCardType.Ntag215:
               return "Ntag215";

            case NfcCardType.Ntag216:
               return "Ntag216";

            default:
               return "Unknown";
         }
      }
      public static byte[] ReadNtagPages(Pn532 pn532 ,byte targetNumber ,byte startPage)
      {
         // NTAG21x READ command:
         // 0x30 + Startseite
         // Antwort: 4 Seiten = 16 Byte
         byte[] command =
         {
            0x30,
            startPage
         };

         byte[] response = new byte[16];

         var send = new SpanByte(
             command ,
             0 ,
             command.Length);

         var receive = new SpanByte(
             response ,
             0 ,
             response.Length);

         try
         {
            int bytesRead = pn532.Transceive(
                targetNumber ,
                send ,
                receive ,
                NfcProtocol.Mifare);

            if (bytesRead < 16)
            {
               Debug.WriteLine("READ fehlgeschlagen. Bytes: " + bytesRead);
               return null;
            }
            return response;
         }
         catch (Exception ex)
         {
            Debug.WriteLine("NTAG READ Fehler ab Seite " + startPage + ": " + ex.Message);
            return null;
         }
      }
      public static void DumpNtagPages(byte startPage ,byte[] data)
      {
         if (data == null)
         {
            return;
         }

         for (int i = 0; i < 4; i++)
         {
            int offset = i * 4;

            Debug.WriteLine("Page " +
                (startPage + i) +
                ": " +
                data[offset + 0].ToString("X2") + "-" +
                data[offset + 1].ToString("X2") + "-" +
                data[offset + 2].ToString("X2") + "-" +
                data[offset + 3].ToString("X2"));
         }
      }
      private static NfcCardType DetectNtag21x(Pn532 pn532 ,byte targetNumber)
      {
         // NXP NTAG21x GET_VERSION
         byte[] command = new byte[]
         {
            0x60
         };

         // GET_VERSION liefert 8 Bytes.
         byte[] response = new byte[8];

         var commandSpan = new SpanByte(
             command ,
             0 ,
             command.Length);

         var responseSpan = new SpanByte(
             response ,
             0 ,
             response.Length);

         try
         {
            int bytesRead = pn532.Transceive(
                targetNumber ,
                commandSpan ,
                responseSpan ,
                NfcProtocol.Mifare);

            if (bytesRead < 8)
            {
               return NfcCardType.Unknown;
            }

            // -----------------------------------------------------
            // NTAG21x GET_VERSION Format:
            //
            // [0] Header
            // [1] Vendor ID
            // [2] Product Type
            // [3] Product Subtype
            // [4] Major Version
            // [5] Minor Version
            // [6] Storage Size
            // [7] Protocol Type
            //
            // NXP Vendor ID = 0x04
            // -----------------------------------------------------

            if (response[1] != 0x04)
            {
               return NfcCardType.Unknown;
            }

            // NXP NTAG Product Type
            if (response[2] != 0x04)
            {
               return NfcCardType.Unknown;
            }

            // NTAG21x Storage Size
            switch (response[6])
            {
               case 0x0F:
                  return NfcCardType.Ntag213;

               case 0x11:
                  return NfcCardType.Ntag215;

               case 0x13:
                  return NfcCardType.Ntag216;

               default:
                  return NfcCardType.Unknown;
            }
         }
         catch
         {
            // Ein Ultralight-/Type-2-Tag muss GET_VERSION
            // nicht zwingend unterstützen.
            return NfcCardType.Unknown;
         }
      }
   }
}
