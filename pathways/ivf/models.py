from dataclasses import dataclass


@dataclass
class LabResult:
    test_name: str      # e.g. "estradiol"
    value: float
    unit: str           # e.g. "pg/mL"