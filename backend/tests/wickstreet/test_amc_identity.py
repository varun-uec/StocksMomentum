"""AMC identity invariants and saved-screen compatibility; synthetic fund rows."""

from dataclasses import replace

import pytest

from tests.wickstreet.test_mf_metrics import FUND
from tests.wickstreet.test_mf_screening import row, run
from wickstreet.analytics.domain.fields import attributes
from wickstreet.mf_data.domain.amc_identity import (
    AMCS,
    amc_identity,
    amc_key,
    amc_provenance,
    canonical_amc,
)


def test_registry_has_unique_ids_and_unambiguous_aliases() -> None:
    assert len(AMCS) == len({a.id for a in AMCS}) == 55
    assert len({alias.casefold() for a in AMCS for alias in a.aliases}) == 110


@pytest.mark.parametrize("amc", AMCS, ids=lambda a: a.id)
def test_saved_source_labels_canonical_labels_and_ids_select_the_same_complete_set(amc) -> None:
    rows = (row(1, amc=amc.name), row(2, amc=amc.master_label), row(3, amc="Unrelated AMC"))
    for alias in (*amc.aliases, amc.id, amc.name.upper()):
        assert amc_identity(alias) == amc
        assert amc_key(alias) == amc.id
        assert canonical_amc(alias) == amc.name
        assert run(rows, {"field": "amc", "op": "in", "value": [alias]}) == [1, 2]
        assert run(rows, {"field": "amc", "op": "not_in", "value": [alias]}) == [3]
    assert run(rows, {"field": "amc", "op": "in", "value": list(amc.aliases)}) == [1, 2]
    fund = replace(FUND, amc=amc.master_label)
    assert attributes(fund, None)["amc"] == amc.name
    assert amc_provenance(fund.amc) == {"source_amc": amc.master_label, "amc_id": amc.id}
    assert fund.amc == amc.master_label  # classifications never mutate source records


@pytest.mark.parametrize(
    "label",
    [
        "",
        None,
        "Sahara Asset Management Company Private Limited",
        "HDFC unrelated AMC",
        "Reliance Mutual Fund",
        "IIFL Mutual Fund",
    ],
)
def test_unknown_and_historical_names_are_never_guessed(label) -> None:
    assert amc_identity(label) is None
    assert canonical_amc(label) == (label or "")
    assert amc_key(label) == (label or "")
    assert amc_provenance(label) == {"source_amc": label or ""}
