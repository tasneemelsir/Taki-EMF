import pytest

from engine import standards as st


def test_frequency_dependent_limits():
    s98, s10 = st.get_standard("ICNIRP_1998"), st.get_standard("ICNIRP_2010")
    assert s98.b_limit(50) == pytest.approx(100.0) and s98.e_limit(50) == pytest.approx(5.0)
    assert s98.b_limit(60) == pytest.approx(83.333, rel=1e-4) and s98.e_limit(60) == pytest.approx(4.1667, rel=1e-4)
    assert s10.b_limit(50) == pytest.approx(200.0) and s10.b_limit(60) == pytest.approx(200.0)
    assert s10.e_limit(50) == pytest.approx(5.0) and s10.e_limit(60) == pytest.approx(4.1667, rel=1e-4)


def test_registry_entries_and_aliases():
    ids = set(st.get_standards())
    for needed in ("MY_ICNIRP_1998", "ICNIRP_2010", "ICNIRP_1998", "EU_1999_519_EC", "IEEE_C95_6_2002",
                   "SI_ZONE_I", "IT_ATTENTION", "IT_QUALITY", "CH_ONIR", "NL_ADVISORY"):
        assert needed in ids
    assert st.resolve_id("MS_2332_1_2009") == "MY_ICNIRP_1998"
    assert st.resolve_id("SI_IT_RESIDENTIAL") == "SI_ZONE_I"
    assert st.get_standard("MY_ICNIRP_1998").needs_verification is True
    assert st.get_standard("SI_ZONE_I").b_limit(50) == 10.0 and st.get_standard("SI_ZONE_I").e_limit(50) == 0.5
    assert st.get_standard("IT_QUALITY").b_limit(50) == 3.0
    assert st.get_standard("CH_ONIR").b_limit(50) == 1.0
    assert st.get_standard("NL_ADVISORY").b_limit(50) == 0.4
    assert st.get_standard("IEEE_C95_6_2002").b_limit(50) == pytest.approx(904.0)


def test_classification_bands():
    res = st.evaluate(50.0, 1.0, ["ICNIRP_1998"], 50.0)[0]
    assert res.b.status == st.PASS and res.overall == st.PASS
    res = st.evaluate(80.0, 1.0, ["ICNIRP_1998"], 50.0)[0]
    assert res.b.status == st.MARGINAL and res.overall == st.MARGINAL
    res = st.evaluate(120.0, 1.0, ["ICNIRP_1998"], 50.0)[0]
    assert res.b.status == st.FAIL and res.overall == st.FAIL


def test_governing_quantity_can_be_the_electric_field():
    results = st.evaluate(5.0, 4.6, ["ICNIRP_1998", "ICNIRP_2010"], 50.0)
    res, q = st.governing(results)
    assert q.quantity == "E" and q.percent_of_limit == pytest.approx(92.0)
    assert st.overall_status(results) == st.MARGINAL


def test_no_standard_selected():
    assert st.evaluate(1.0, 1.0, [], 50.0) == []
    assert st.governing([]) == (None, None)
