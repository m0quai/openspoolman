# NFC-/AMS-/Spoolman-Architektur

## Festgelegtes Konzept

Die NFC-Lösung verbindet Bambu-AMS-Slots über einen ESP32-S3 und NTAG215-Tags mit OpenSpoolMan/Spoolman.

## Controller

- ESP32-S3
- C# mit .NET nanoFramework

## NFC-Tag

- NTAG215
- Hardware-UID dient als stabile Identität.

## Initialisierung

Bei einem neuen oder leeren Tag:

1. Hardware-UID lesen.
2. NDEF-Inhalt prüfen.
3. Falls der Tag noch nicht initialisiert ist, einmalig eine URL mit der unveränderlichen UID schreiben.
4. Beispiel: `/nfc/<UID>`.

Diese URL bleibt bei späterer Wiederverwendung des Tags unverändert.

## Zuordnungsmodell

Der Tag wird bei einem Spulenwechsel nicht mit einer neuen Spulenidentität überschrieben.

Stattdessen:

- UID-zu-Spule-Zuordnung liegt in OpenSpoolMan/Spoolman.
- iPhone öffnet die URL direkt vom NFC-Tag.
- Die Weboberfläche kann die UID einer Spule zuordnen, freigeben oder neu zuordnen.

## AMS

Der ESP32-S3 meldet:

- NFC-UID;
- AMS-Slot

an OpenSpoolMan.

Serverseitig wird daraus die zugeordnete Spule ermittelt.

## Unveränderliche Designregel

**Tag-UID und Tag-URL bleiben unverändert; die Spulenzuordnung ist serverseitig veränderbar.**

Keine Lösung implementieren, die bei jedem Spulenwechsel die Spulenidentität neu auf den NFC-Tag schreibt, sofern diese Architektur nicht ausdrücklich geändert wird.
