import os

import pytest

from chart import save_chart
from data import INCIDENTS, incident_days, make_orders
from demo import rows
from detector import flagged, precision_recall, rolling_zscores


# --- the maths, checked by hand -------------------------------------------

def test_z_score_matches_hand_calculation():
    # Baseline 10, 12, 14: mean 12, sample std 2. Next value 20 -> z = (20 - 12) / 2 = 4.
    points = rolling_zscores([10, 12, 14, 20], window=3, threshold=3)
    last = points[-1]
    assert last.mean == pytest.approx(12)
    assert last.std == pytest.approx(2)
    assert last.z == pytest.approx(4)
    assert last.is_anomaly


def test_current_point_is_not_in_its_own_baseline():
    # If the spike were in its own window it would pull the mean up and hide itself.
    points = rolling_zscores([10, 12, 14, 1000], window=3, threshold=3)
    assert points[-1].mean == pytest.approx(12)


def test_drops_are_flagged_as_well_as_spikes():
    points = rolling_zscores([10, 12, 14, 4], window=3, threshold=3)
    assert points[-1].z == pytest.approx(-4)
    assert points[-1].is_anomaly


def test_warm_up_points_are_never_flagged():
    points = rolling_zscores([1, 1000, 1, 1000, 5], window=4, threshold=1)
    assert [p.z for p in points[:4]] == [None] * 4
    assert not any(p.is_anomaly for p in points[:4])


def test_flat_baseline_does_not_divide_by_zero():
    points = rolling_zscores([5, 5, 5, 5, 9], window=4, threshold=3)
    assert points[-1].std == 0
    assert points[-1].z is None
    assert not points[-1].is_anomaly


@pytest.mark.parametrize("window, threshold", [(1, 3), (0, 3), (5, 0), (5, -1)])
def test_bad_settings_are_rejected(window, threshold):
    with pytest.raises(ValueError):
        rolling_zscores([1, 2, 3, 4, 5, 6], window=window, threshold=threshold)


def test_precision_and_recall():
    assert precision_recall([1, 2, 3, 4], [2, 4, 6]) == (0.5, pytest.approx(2 / 3))
    assert precision_recall([], [1]) == (1.0, 0.0)


# --- the shop data: the numbers in the README -------------------------------

def test_series_is_deterministic():
    assert make_orders() == make_orders()
    assert len(make_orders()) == 90


def test_threshold_3_catches_every_incident_with_no_false_alarms():
    found = flagged(rolling_zscores(make_orders(), window=14, threshold=3))
    assert found == incident_days() == [40, 62, 75]


def test_readme_table():
    # (threshold, alerts, caught, false alarms, precision, recall)
    table = [(t, a, c, f, round(p, 2), round(r, 2)) for t, a, c, f, p, r in rows()]
    assert table == [
        (2.0, 5, 3, 2, 0.6, 1.0),
        (2.5, 4, 3, 1, 0.75, 1.0),
        (3.0, 3, 3, 0, 1.0, 1.0),
    ]


def test_an_earlier_incident_in_the_window_masks_the_next_one():
    # Day 62's drop is inside day 75's 14-day baseline, which widens the std
    # and roughly halves day 75's z-score. Without day 62, z is above 6.
    series = make_orders()
    with_drop = rolling_zscores(series, 14, 3)[75].z

    repaired = list(series)
    repaired[62] -= INCIDENTS[62][0]
    without_drop = rolling_zscores(repaired, 14, 3)[75].z

    assert without_drop > 6
    assert 3 < with_drop < 3.5  # still caught at 3, but only just
    assert with_drop < without_drop / 1.8


# --- the chart --------------------------------------------------------------

def test_chart_is_written(tmp_path):
    out = tmp_path / "chart.png"
    save_chart(rolling_zscores(make_orders(), 14, 3), str(out), 3, "test")
    assert out.exists()
    with open(out, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(out) > 5_000
