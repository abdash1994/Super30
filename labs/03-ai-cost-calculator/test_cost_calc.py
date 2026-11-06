from decimal import Decimal

import pytest

from cost_calc import Model, estimate, main, money, parse_model


def test_hand_checked_example():
    # 1,000 in x $3/1M + 500 out x $15/1M = $0.003 + $0.0075 = $0.0105 per request
    m = Model("large", Decimal("3"), Decimal("15"))
    e = estimate(m, input_tokens=1000, output_tokens=500, requests_per_day=10_000, days=30)
    assert e.per_request == Decimal("0.0105")
    assert e.per_1k_requests == Decimal("10.5")
    assert e.per_day == Decimal("105")
    assert e.per_month == Decimal("3150")


def test_decimal_has_no_float_drift():
    m = parse_model("x:0.1:0.2")
    e = estimate(m, input_tokens=1_000_000, output_tokens=1_000_000, requests_per_day=1, days=1)
    assert e.per_request == Decimal("0.3")


def test_zero_volume_costs_nothing():
    e = estimate(parse_model("x:3:15"), 1000, 500, requests_per_day=0)
    assert e.per_month == 0


def test_parse_model_ok():
    assert parse_model("small:0.15:0.60") == Model("small", Decimal("0.15"), Decimal("0.60"))


@pytest.mark.parametrize("spec", ["small", "small:1", ":1:2", "small:abc:1", "small:-1:2", "small:1:nan"])
def test_parse_model_rejects_bad_input(spec):
    with pytest.raises(ValueError):
        parse_model(spec)


def test_negative_volume_rejected():
    with pytest.raises(ValueError):
        estimate(parse_model("x:1:1"), 100, 100, requests_per_day=-5)


def test_money_formatting():
    assert money(Decimal("3150")) == "$3,150.00"
    assert money(Decimal("0.0105"), 6) == "$0.010500"
    assert money(Decimal("0")) == "$0.00"


def test_cli_compares_two_models(capsys):
    code = main([
        "--input-tokens", "1000", "--output-tokens", "500",
        "--requests-per-day", "10000",
        "--model", "small:0.15:0.60", "--model", "large:3:15",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "small" in out and "large" in out
    assert "$3,150.00" in out  # large, 30 days
    assert "$135.00" in out  # small, 30 days: (0.00015 + 0.0003) x 10,000 x 30
    assert "$0.010500" in out  # large, per request


def test_cli_bad_price_exits_2(capsys):
    code = main([
        "--input-tokens", "10", "--output-tokens", "10",
        "--requests-per-day", "1", "--model", "x:-1:1",
    ])
    assert code == 2
    assert "error" in capsys.readouterr().err
