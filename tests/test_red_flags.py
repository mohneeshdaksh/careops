from pathways.ivf.models import LabResult
from pathways.ivf.red_flags import check_red_flags


def test_normal_estradiol_has_no_flags():
    labs = [LabResult("estradiol", 850, "pg/mL")]
    assert check_red_flags(labs) == []


def test_high_estradiol_is_flagged():
    labs = [LabResult("estradiol", 5000, "pg/mL")]
    flags = check_red_flags(labs)
    assert len(flags) == 1


def test_unexpected_unit_cannot_be_checked():
    labs = [LabResult("estradiol", 1000, "pmol/L")]
    flags = check_red_flags(labs)
    assert len(flags) == 1
    assert "Could not check" in flags[0]