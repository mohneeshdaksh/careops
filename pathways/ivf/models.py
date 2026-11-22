from dataclasses import dataclass
from typing import Literal


@dataclass
class LabResult:
    test_name: str      # e.g. "estradiol"
    value: float
    unit: str           # e.g. "pg/mL"


@dataclass
class DoctorReview:
    decision: Literal["approve", "reject"]
    reviewer: str
    note: str = ""