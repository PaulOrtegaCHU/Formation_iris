from grongier.pex import Message
from dataclasses import dataclass

@dataclass
class FilterPatientResource(Message):
    patient_str: str