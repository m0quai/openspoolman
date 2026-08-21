# AMSHelper – bestätigter WLAN-Test

> Zur Gesamtübersicht: [START.md](../START.md)

Stand: 2026-08-21 08:49

## Ergebnis

WLAN auf dem eigenen ESP32-S3/nanoFramework-Target ist bestätigt funktionsfähig.

Bestätigt wurden:
- Verbindung zum WLAN
- DHCP
- IP-/Netzwerkdaten
- DNS
- Namensauflösung von `NBK-01-548`

## Relevantes NuGet-Paket

`nanoFramework.System.Device.Wifi`

Installation über Visual Studio Package Manager Console:

```powershell
Install-Package nanoFramework.System.Device.Wifi -ProjectName AMSHelper
```

## DNS-Test

Für den Test wird der Host bei jedem Durchlauf erneut aufgelöst:

```csharp
IPHostEntry hostEntry = Dns.GetHostEntry("NBK-01-548");
```

nanoFramework stellt hier keinen Windows-artigen `ipconfig /flushdns`-Befehl bereit. Der Test ruft die Namensauflösung bei jedem Durchlauf erneut auf.

## Hinweis

Die WLAN-Funktionalität gilt damit als abgeschlossenes Basisthema. Als nächstes folgt der einzelne PN532-I2C-Test.


## Entwicklungsumgebung

Der WLAN-Test läuft im neu angelegten nanoFramework-Projekt `AMSHelper`:

![AMSHelper-Projekt in Visual Studio](../img/amshelper/amshelper-project.png)
