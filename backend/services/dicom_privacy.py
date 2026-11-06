"""Remove identifying DICOM metadata while preserving image pixels and calibration."""

import uuid

_PATIENT_IDENTIFIER_KEYWORDS = {
    "PatientName",
    "PatientID",
    "PatientAge",
    "PatientSex",
    "PatientSize",
    "PatientWeight",
    "EthnicGroup",
    "Occupation",
    "SmokingStatus",
    "MedicalAlerts",
    "Allergies",
    "SpecialNeeds",
    "IssuerOfPatientID",
    "IssuerOfPatientIDQualifiersSequence",
    "TypeOfPatientID",
    "OtherPatientIDs",
    "OtherPatientIDsSequence",
    "OtherPatientNames",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientBirthName",
    "PatientMotherBirthName",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "ResponsiblePerson",
    "ResponsiblePersonRole",
    "ResponsibleOrganization",
    "DeidentificationMethod",
    "DeidentificationMethodCodeSequence",
    "AccessionNumber",
    "AdmissionID",
    "MedicalRecordLocator",
    "StudyID",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "StationName",
    "StationAETitle",
    "DeviceSerialNumber",
    "StudyDescription",
    "SeriesDescription",
    "ImageComments",
    "PatientComments",
    "AdditionalPatientHistory",
    "AcquisitionComments",
    "ReferringPhysicianIdentificationSequence",
    "PerformingPhysicianIdentificationSequence",
    "OperatorIdentificationSequence",
    "ReadingPhysicianIdentificationSequence",
}

_IDENTIFYING_VALUE_REPRESENTATIONS = {
    "AE",
    "AS",
    "DA",
    "DT",
    "LO",
    "LT",
    "PN",
    "SH",
    "ST",
    "TM",
    "UC",
    "UR",
    "UT",
}
_SYNTHETIC_UID_KEYWORDS = {
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "FrameOfReferenceUID",
    "SynchronizationFrameOfReferenceUID",
}
_STRUCTURAL_UID_KEYWORDS = {"SOPClassUID", "ReferencedSOPClassUID"}
_FILE_META_SOURCE_KEYWORDS = {
    "SourceApplicationEntityTitle",
    "SendingApplicationEntityTitle",
    "ReceivingApplicationEntityTitle",
}
_UID_NAMESPACE = uuid.UUID("e34f6ca6-2e43-4f4e-9d66-7a6f06cbe0a3")


def _uid_for(key: str) -> str:
    """Create a valid, stable 2.25 UID from an application-generated context key."""
    return f"2.25.{uuid.uuid5(_UID_NAMESPACE, key).int}"


def _remove_selected_metadata(dataset, replacement_uids: dict[str, str]) -> None:
    for element in list(dataset):
        if (
            element.tag.is_private
            or element.keyword in _PATIENT_IDENTIFIER_KEYWORDS
            or element.VR in _IDENTIFYING_VALUE_REPRESENTATIONS
        ):
            del dataset[element.tag]
            continue
        if element.VR == "SQ":
            for item in element.value:
                _remove_selected_metadata(item, replacement_uids)
            if not element.value or all(not item for item in element.value):
                del dataset[element.tag]
            continue
        if element.VR == "UI":
            if element.keyword in replacement_uids:
                element.value = replacement_uids[element.keyword]
            elif element.keyword not in _STRUCTURAL_UID_KEYWORDS:
                del dataset[element.tag]


def minimize_dicom_patient_metadata(
    dataset,
    *,
    study_key: str | None = None,
    series_key: str | None = None,
    instance_key: str | None = None,
) -> None:
    """Remove identity-bearing values and replace source instance UIDs.

    UIDs are deterministic within the application-generated study/series/image
    keys. Pixel data is preserved and never declared clean; burned-in annotations
    remain a manual review boundary.
    """
    study_key = study_key or uuid.uuid4().hex
    instance_key = instance_key or uuid.uuid4().hex
    series_key = series_key or f"{study_key}:{instance_key}"
    replacement_uids = {
        "StudyInstanceUID": _uid_for(f"study:{study_key}"),
        "SeriesInstanceUID": _uid_for(f"series:{series_key}"),
        "SOPInstanceUID": _uid_for(f"instance:{instance_key}"),
        "FrameOfReferenceUID": _uid_for(f"frame:{study_key}"),
        "SynchronizationFrameOfReferenceUID": _uid_for(f"sync:{study_key}"),
    }

    if "SOPClassUID" not in dataset and getattr(dataset, "file_meta", None):
        if "MediaStorageSOPClassUID" in dataset.file_meta:
            dataset.SOPClassUID = dataset.file_meta.MediaStorageSOPClassUID
    dataset.StudyInstanceUID = replacement_uids["StudyInstanceUID"]
    dataset.SeriesInstanceUID = replacement_uids["SeriesInstanceUID"]
    dataset.SOPInstanceUID = replacement_uids["SOPInstanceUID"]

    _remove_selected_metadata(dataset, replacement_uids)

    file_meta = getattr(dataset, "file_meta", None)
    if file_meta is not None:
        for element in list(file_meta):
            if element.tag.is_private or element.keyword in _FILE_META_SOURCE_KEYWORDS:
                del file_meta[element.tag]
        from pydicom.uid import PYDICOM_IMPLEMENTATION_UID

        file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
        if "ImplementationVersionName" in file_meta:
            del file_meta.ImplementationVersionName
        if "SOPClassUID" in dataset:
            file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
        file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID

    # Do not inherit an unverified source assertion that the object is de-identified.
    dataset.PatientIdentityRemoved = "NO"
    dataset.LongitudinalTemporalInformationModified = "REMOVED"
