namespace AMSHelper.Mqtt
{
    // Incremental update: only fields with Has... == true were present in the MQTT report.
    public sealed class BambuStatusUpdate
    {
        // Wird vom AMS-Interpreter gesetzt, sobald fuer diesen Report eine fachliche [AMS]-Ausgabe erzeugt wurde.
        public bool AmsOutputProduced;
        public string RawJson;
        public bool HasCommand;
        public string Command;
        public bool HasSequenceId;
        public string SequenceId;
        public bool HasGcodeFile;
        public string GcodeFile;
        public bool HasGcodeState;
        public string GcodeState;
        public bool HasSubtaskName;
        public string SubtaskName;
        public bool HasAmsHumidity;
        public string AmsHumidity;
        public bool HasAmsHumidityRaw;
        public string AmsHumidityRaw;
        public bool HasAmsTemperature;
        public string AmsTemperature;
        public bool HasAmsId;
        public string AmsId;
        public bool HasActiveTray;
        public string ActiveTray;
        public bool HasTargetTray;
        public string TargetTray;
        public bool HasPreviousTray;
        public string PreviousTray;
        public bool HasAmsStatus;
        public string AmsStatus;
        public bool HasTrayExistBits;
        public string TrayExistBits;
        public bool HasTrayReadingBits;
        public string TrayReadingBits;
        public bool HasTrayReadDoneBits;
        public string TrayReadDoneBits;
        public bool HasCommandAmsId;
        public string CommandAmsId;
        public bool HasCommandSlotId;
        public string CommandSlotId;
        public bool HasCommandTarget;
        public string CommandTarget;
        public bool HasReason;
        public string Reason;
        public bool HasResult;
        public string Result;
        public BambuTrayUpdate[] Trays = new BambuTrayUpdate[4];
    }

    public sealed class BambuTrayUpdate
    {
        public int Slot;
        public bool Present;
        public bool HasId;
        public string Id;
        public bool HasType;
        public string Type;
        public bool HasColor;
        public string Color;
        public bool HasUuid;
        public string Uuid;
        public bool HasRemain;
        public string Remain;
        public bool HasTagUid;
        public string TagUid;
    }
}
