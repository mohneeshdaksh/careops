from pathways.ivf.models import LabResult

# Illustrative thresholds for synthetic data only. Not clinical guidance.
RED_FLAG_RULES = {
    "estradiol": {"unit": "pg/mL", "max": 4000, "reason": "very high estradiol (risk of ovarian hyperstimulation)"},
    "progesterone": {"unit": "ng/mL", "max": 1.5, "reason": "early progesterone rise"},
}


def check_red_flags(labs: list[LabResult]) -> list[str]:
    flags = []
    for lab in labs:
        rule = RED_FLAG_RULES.get(lab.test_name.lower())
        if rule is None:
            continue
        if lab.unit != rule["unit"]:
            flags.append(f"Could not check {lab.test_name}: got {lab.unit}, expected {rule['unit']}")
        elif lab.value >= rule["max"]:
            flags.append(f"{rule['reason']}: {lab.test_name} {lab.value} {lab.unit} (limit {rule['max']})")
    return flags