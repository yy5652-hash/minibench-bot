from datetime import date, timedelta

import numpy as np
import pandas as pd

from shelfcast.data import Dataset, event_key, generate_synthetic, load_m5, us_retail_holidays


def test_synthetic_is_reproducible(synthetic):
    again = generate_synthetic()
    for a, b in zip(synthetic.series, again.series):
        np.testing.assert_array_equal(np.nan_to_num(a.demand, nan=-1), np.nan_to_num(b.demand, nan=-1))


def test_synthetic_shape(synthetic):
    assert len(synthetic.series) == 20
    s = synthetic.get("BAK-001")
    assert s.n_weeks == 166
    assert s.week_starts[s.last_known_index()] == "2026-10-05"
    assert np.isnan(s.demand[-8:]).all() and not np.isnan(s.demand[:-8]).any()
    assert not np.isnan(s.price).any()
    future = dict(zip(s.week_starts[-8:], s.events[-8:]))
    assert future["2026-11-23"] == ["Holiday: Thanksgiving (Thu)"]
    assert future["2026-10-26"] == ["Holiday: Halloween (Sat)"]


def test_thanksgiving_lifts_pumpkin(synthetic):
    s = synthetic.get("BAK-001")
    tg = [i for i, e in enumerate(s.events)
          if any("Thanksgiving" in x for x in e) and not np.isnan(s.demand[i]) and i >= 8]
    assert len(tg) == 2
    for i in tg:
        assert s.demand[i] > 2 * np.median(s.demand[i - 8:i - 2])


def test_holiday_calendar():
    h = us_retail_holidays(2026)
    assert h[date(2026, 11, 26)] == "Thanksgiving"
    assert h[date(2026, 4, 5)] == "Easter"
    assert h[date(2026, 5, 25)] == "Memorial Day"
    assert h[date(2026, 2, 8)] == "Super Bowl"


def test_event_key():
    assert event_key("Holiday: Thanksgiving (Thu)") == "Holiday: Thanksgiving"
    assert event_key("Holiday: Christmas (Fri), store closed") == "Holiday: Christmas (Fri), store closed"
    assert event_key("Promotion: 20% off, featured in weekly ad") == "Promotion"
    assert event_key("SNAP benefit days: 3") == "SNAP"
    assert event_key("Cultural event: SuperBowl (Sun)") == "Cultural event: SuperBowl"


def test_save_load_roundtrip(tmp_path, synthetic):
    p = tmp_path / "ds.json"
    synthetic.save(p)
    back = Dataset.load(p)
    assert back.name == synthetic.name
    a, b = synthetic.series[3], back.series[3]
    assert a.events == b.events and a.week_starts == b.week_starts
    np.testing.assert_allclose(np.nan_to_num(a.demand, nan=-1), np.nan_to_num(b.demand, nan=-1))


def _fake_m5(root, n_weeks=120):
    days = n_weeks * 7 + 3  # a partial final week is dropped
    start = date(2011, 1, 29)  # a Saturday, as in M5
    dates = [start + timedelta(days=i) for i in range(days)]
    cal = pd.DataFrame({
        "date": [d.isoformat() for d in dates],
        "wm_yr_wk": [11101 + i // 7 for i in range(days)],
        "d": [f"d_{i + 1}" for i in range(days)],
        "event_name_1": [("SuperBowl" if i % 70 == 8 else None) for i in range(days)],
        "event_type_1": [("Sporting" if i % 70 == 8 else None) for i in range(days)],
        "event_name_2": [None] * days,
        "event_type_2": [None] * days,
        "snap_CA": [int(d.day <= 10) for d in dates],
        "snap_TX": [int(d.day <= 10) for d in dates],
        "snap_WI": [int(d.day <= 10) for d in dates],
    })
    rng = np.random.default_rng(0)
    rows = []
    for k, (cat, store) in enumerate([("FOODS", "CA_1"), ("FOODS", "TX_1"), ("HOBBIES", "CA_1"), ("HOUSEHOLD", "WI_1")]):
        item = f"{cat}_1_{k:03d}"
        sales = rng.poisson(8 if k != 3 else 0.2, size=days)
        rows.append({"id": f"{item}_{store}_evaluation", "item_id": item, "dept_id": f"{cat}_1", "cat_id": cat,
                     "store_id": store, "state_id": store[:2], **{f"d_{i + 1}": int(v) for i, v in enumerate(sales)}})
    sales = pd.DataFrame(rows)
    prices = pd.DataFrame([
        {"store_id": r["store_id"], "item_id": r["item_id"], "wm_yr_wk": 11101 + w, "sell_price": 2.5}
        for r in rows for w in range(n_weeks)
    ])
    sub = root / "m5" / "datasets"
    sub.mkdir(parents=True)
    cal.to_csv(sub / "calendar.csv", index=False)
    sales.to_csv(sub / "sales_train_evaluation.csv", index=False)
    prices.to_csv(sub / "sell_prices.csv", index=False)


def test_load_m5_weekly(tmp_path):
    _fake_m5(tmp_path)
    ds = load_m5(tmp_path, n_series=10, min_weekly_mean=20, min_weeks=100)
    # The near-zero HOUSEHOLD series fails the volume filter.
    assert {s.category.split(" / ")[0] for s in ds.series} == {"FOODS", "HOBBIES"}
    s = ds.series[0]
    assert s.n_weeks == 120 and s.week_starts[0] == "2011-01-29"
    assert s.demand.min() > 20 and np.all(s.price == 2.5)
    assert any(e.startswith("Sporting event: SuperBowl") for e in s.events[1])
    assert any(e.startswith("SNAP benefit days") for e in s.events[0])
