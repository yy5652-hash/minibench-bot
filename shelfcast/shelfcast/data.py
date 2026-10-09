"""Weekly retail demand series: the data model, a synthetic store and an M5 loader.

Every series is weekly. ``demand`` holds units sold, with NaN for weeks that
have not happened yet. ``price`` and ``events`` are plans the retailer knows in
advance (shelf price, promotions, holidays), so they are filled for future
weeks too. Events are short strings with a stable prefix, for example
``"Holiday: Thanksgiving (Thu)"`` or ``"Promotion: 20% off"``; see
:func:`event_key`.
"""

from __future__ import annotations

import json
import math
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class Series:
    sku_id: str
    title: str
    category: str
    store: str
    week_starts: list[str]
    demand: np.ndarray
    price: np.ndarray
    events: list[list[str]]

    def __post_init__(self) -> None:
        self.demand = np.asarray(self.demand, dtype=float)
        self.price = np.asarray(self.price, dtype=float)
        n = len(self.week_starts)
        if not (len(self.demand) == len(self.price) == len(self.events) == n):
            raise ValueError(f"{self.sku_id}: week_starts, demand, price and events differ in length")

    @property
    def n_weeks(self) -> int:
        return len(self.week_starts)

    def last_known_index(self) -> int:
        """Index of the last week with observed demand (-1 if none)."""
        known = np.flatnonzero(~np.isnan(self.demand))
        return int(known[-1]) if known.size else -1

    def to_dict(self) -> dict:
        return {
            "sku_id": self.sku_id,
            "title": self.title,
            "category": self.category,
            "store": self.store,
            "week_starts": self.week_starts,
            "demand": [None if math.isnan(v) else round(float(v), 4) for v in self.demand],
            "price": [None if math.isnan(v) else round(float(v), 4) for v in self.price],
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Series":
        return cls(
            sku_id=d["sku_id"],
            title=d["title"],
            category=d["category"],
            store=d["store"],
            week_starts=list(d["week_starts"]),
            demand=np.array([np.nan if v is None else v for v in d["demand"]], dtype=float),
            price=np.array([np.nan if v is None else v for v in d["price"]], dtype=float),
            events=[list(e) for e in d["events"]],
        )


@dataclass
class Dataset:
    name: str
    source: str
    description: str
    series: list[Series]

    def get(self, sku_id: str) -> Series:
        for s in self.series:
            if s.sku_id == sku_id:
                return s
        raise KeyError(sku_id)

    def save(self, path: str | os.PathLike) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": self.name,
            "source": self.source,
            "description": self.description,
            "series": [s.to_dict() for s in self.series],
        }
        Path(path).write_text(json.dumps(payload, separators=(",", ":")))

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Dataset":
        d = json.loads(Path(path).read_text())
        return cls(
            name=d["name"],
            source=d["source"],
            description=d.get("description", ""),
            series=[Series.from_dict(s) for s in d["series"]],
        )


def event_key(event: str) -> str:
    """Stable key used to match an event against the same event in past years.

    ``"Holiday: Thanksgiving (Thu)"`` -> ``"Holiday: Thanksgiving"``;
    every promotion maps to ``"Promotion"``; SNAP day counts map to ``"SNAP"``.
    """
    if event.startswith("Promotion"):
        return "Promotion"
    if event.startswith("SNAP"):
        return "SNAP"
    return re.sub(r"\s*\([^)]*\)\s*$", "", event).strip()


# --------------------------------------------------------------------------- #
# Calendar helpers
# --------------------------------------------------------------------------- #


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th ``weekday`` (Mon=0) of a month; n=-1 is the last one."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + c + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1)


def us_retail_holidays(year: int) -> dict[date, str]:
    """US retail calendar used by the synthetic store."""
    return {
        date(year, 1, 1): "New Year's Day",
        _nth_weekday(year, 2, 6, 2): "Super Bowl",
        date(year, 2, 14): "Valentine's Day",
        _easter(year): "Easter",
        _nth_weekday(year, 5, 6, 2): "Mother's Day",
        _nth_weekday(year, 5, 0, -1): "Memorial Day",
        _nth_weekday(year, 6, 6, 3): "Father's Day",
        date(year, 7, 4): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        date(year, 10, 31): "Halloween",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving",
        date(year, 12, 25): "Christmas",
    }


# --------------------------------------------------------------------------- #
# Synthetic store
# --------------------------------------------------------------------------- #

# sku, title, category, list price, base units/week, seasonal amplitude,
# peak ISO week, holiday lifts, lifts in the week before, price elasticity,
# promotion rate, post-promotion dip.
_CATALOG: list[dict] = [
    dict(sku="SNK-001", title="Tortilla Chips 300g", cat="Snacks", price=3.49, base=140, amp=0.10, peak=28,
         lifts={"Super Bowl": 1.9, "Independence Day": 1.4, "Memorial Day": 1.25, "Labor Day": 1.25},
         elasticity=2.6, promo=0.10, dip=0.90),
    dict(sku="SNK-002", title="Salsa Dip 450g", cat="Snacks", price=2.99, base=70, amp=0.10, peak=28,
         lifts={"Super Bowl": 2.2, "Independence Day": 1.35}, elasticity=2.2, promo=0.08, dip=0.92),
    dict(sku="BEV-001", title="Craft Beer 6-pack", cat="Beverages", price=9.99, base=160, amp=0.25, peak=27,
         lifts={"Super Bowl": 1.5, "Independence Day": 1.7, "Memorial Day": 1.35, "Labor Day": 1.35},
         elasticity=1.8, promo=0.08, dip=0.93),
    dict(sku="BEV-002", title="Sparkling Water 12-pack", cat="Beverages", price=5.49, base=80, amp=0.30, peak=28,
         lifts={"Independence Day": 1.3}, elasticity=2.3, promo=0.10, dip=0.90),
    dict(sku="OUT-001", title="Charcoal Briquettes 8kg", cat="Outdoor", price=12.99, base=30, amp=0.85, peak=26,
         lifts={"Memorial Day": 1.9, "Independence Day": 2.3, "Labor Day": 1.7, "Father's Day": 1.4},
         elasticity=1.6, promo=0.06, dip=0.95),
    dict(sku="PER-001", title="Sunscreen SPF50", cat="Personal Care", price=11.49, base=24, amp=0.95, peak=27,
         lifts={"Memorial Day": 1.3, "Independence Day": 1.5}, elasticity=1.4, promo=0.05, dip=0.97),
    dict(sku="GRO-001", title="Hot Cocoa Mix", cat="Grocery", price=4.29, base=40, amp=0.70, peak=1,
         lifts={"Thanksgiving": 1.2, "Christmas": 1.5}, elasticity=2.0, promo=0.07, dip=0.93),
    dict(sku="BAK-001", title="Canned Pumpkin 425g", cat="Baking", price=2.49, base=14, amp=0.60, peak=46,
         lifts={"Thanksgiving": 3.8, "Halloween": 1.3, "Christmas": 1.6}, pre={"Thanksgiving": 1.8},
         elasticity=1.8, promo=0.05, dip=0.95),
    dict(sku="GRO-002", title="Cranberry Sauce", cat="Grocery", price=2.29, base=9, amp=0.30, peak=47,
         lifts={"Thanksgiving": 5.5, "Christmas": 2.8}, pre={"Thanksgiving": 1.6},
         elasticity=1.5, promo=0.04, dip=0.97),
    dict(sku="CAN-001", title="Chocolate Hearts Box", cat="Candy", price=8.99, base=7, amp=0.0, peak=1,
         lifts={"Valentine's Day": 7.0, "Mother's Day": 1.6}, pre={"Valentine's Day": 2.5},
         elasticity=1.5, promo=0.03, dip=0.97),
    dict(sku="CAN-002", title="Candy Corn Bag", cat="Candy", price=3.29, base=9, amp=0.40, peak=43,
         lifts={"Halloween": 5.0}, pre={"Halloween": 2.6}, elasticity=1.7, promo=0.04, dip=0.96),
    dict(sku="HOU-001", title="Paper Towels 6-roll", cat="Household", price=8.49, base=95, amp=0.0, peak=1,
         lifts={}, elasticity=3.0, promo=0.12, dip=0.85),
    dict(sku="HOU-002", title="AA Batteries 8-pack", cat="Household", price=9.49, base=32, amp=0.15, peak=51,
         lifts={"Christmas": 2.0, "Thanksgiving": 1.4}, elasticity=2.0, promo=0.07, dip=0.92),
    dict(sku="SEA-001", title="Gift Wrap Roll", cat="Seasonal", price=4.99, base=6, amp=0.30, peak=51,
         lifts={"Christmas": 6.0}, pre={"Christmas": 4.0}, elasticity=1.2, promo=0.03, dip=0.98),
    dict(sku="HEA-001", title="Cold & Flu Relief", cat="Health", price=10.99, base=30, amp=0.65, peak=3,
         lifts={}, elasticity=1.2, promo=0.05, dip=0.97),
    dict(sku="OFF-001", title="School Notebooks 5-pack", cat="Office", price=6.99, base=12, amp=0.0, peak=1,
         lifts={"Back-to-school season": 3.8}, elasticity=1.6, promo=0.05, dip=0.95),
    dict(sku="MEA-001", title="Whole Turkey (frozen)", cat="Meat", price=24.99, base=5, amp=0.30, peak=47,
         lifts={"Thanksgiving": 14.0, "Christmas": 3.5, "Easter": 1.6}, pre={"Thanksgiving": 3.0},
         elasticity=1.3, promo=0.03, dip=0.98),
    dict(sku="FRZ-001", title="Ice Cream 1.5L", cat="Frozen", price=5.99, base=85, amp=0.45, peak=29,
         lifts={"Independence Day": 1.35, "Memorial Day": 1.2}, elasticity=2.4, promo=0.10, dip=0.90),
    dict(sku="PRO-001", title="Bananas (per lb)", cat="Produce", price=0.59, base=420, amp=0.05, peak=20,
         lifts={}, elasticity=0.6, promo=0.0, dip=1.0),
    dict(sku="DAI-001", title="Whole Milk 1 gal", cat="Dairy", price=3.89, base=260, amp=0.05, peak=1,
         lifts={"Thanksgiving": 1.15, "Christmas": 1.1}, elasticity=0.7, promo=0.03, dip=0.98),
]


def generate_synthetic(
    start: date = date(2023, 10, 2),
    n_known: int = 158,
    n_future: int = 8,
    seed: int = 7,
) -> Dataset:
    """A reproducible single-store catalogue with holidays, promotions and noise.

    Defaults give observed weeks through the week of 2026-10-05 and eight
    planned weeks after it (Halloween and Thanksgiving 2026 included).
    """
    if start.weekday() != 0:
        raise ValueError("start must be a Monday")
    rng = np.random.default_rng(seed)
    n = n_known + n_future
    weeks = [start + timedelta(weeks=i) for i in range(n)]

    holidays: dict[date, str] = {}
    for y in range(start.year, weeks[-1].year + 2):
        holidays.update(us_retail_holidays(y))

    week_holidays: list[list[tuple[str, date]]] = []
    for w in weeks:
        hs = [(holidays[w + timedelta(days=k)], w + timedelta(days=k))
              for k in range(7) if w + timedelta(days=k) in holidays]
        if w.month == 8 and w.day <= 28:
            hs.append(("Back-to-school season", w))
        week_holidays.append(hs)

    series: list[Series] = []
    for item in _CATALOG:
        level0 = item["base"] * math.exp(rng.normal(0, 0.1))
        growth = rng.normal(0.0, 0.06)
        list_price = item["price"]
        price_steps = {}
        for i in range(26, n, 26):
            if rng.random() < 0.6:
                price_steps[i] = 1.0 + rng.uniform(0.02, 0.07)
        price = np.empty(n)
        demand = np.empty(n)
        events: list[list[str]] = []
        prev_promo = False
        for i, w in enumerate(weeks):
            if i in price_steps:
                list_price *= price_steps[i]
            ev: list[str] = []
            mult = 1.0
            woy = (w + timedelta(days=3)).isocalendar()[1]
            mult *= 1.0 + item["amp"] * math.cos(2 * math.pi * (woy - item["peak"]) / 52.0)
            mult *= math.exp(growth * i / 52.0)
            mult *= (list_price / item["price"]) ** (-0.5 * item["elasticity"])

            for name, day in week_holidays[i]:
                label = name if name == "Back-to-school season" else f"{name} ({WEEKDAYS[day.weekday()]})"
                ev.append(("Season: " if name == "Back-to-school season" else "Holiday: ") + label)
                mult *= item["lifts"].get(name, 1.0)
                if name == "Christmas":
                    ev[-1] += ", store closed"
                    mult *= 6.0 / 7.0
            if i + 1 < n:
                for name, _ in week_holidays[i + 1]:
                    mult *= item.get("pre", {}).get(name, 1.0)

            p = list_price
            if rng.random() < item["promo"]:
                disc = float(rng.choice([0.10, 0.15, 0.20, 0.25, 0.30]))
                feature = rng.random() < 0.35
                p = list_price * (1 - disc)
                mult *= (1 - disc) ** (-item["elasticity"]) * (1.2 if feature else 1.0)
                ev.append(f"Promotion: {int(disc * 100)}% off" + (", featured in weekly ad" if feature else ""))
                is_promo = True
            else:
                is_promo = False
            if prev_promo and not is_promo:
                mult *= item["dip"]
            prev_promo = is_promo

            # Shocks nobody announced: supply problems or a viral moment.
            if rng.random() < 0.015:
                mult *= rng.uniform(0.5, 0.7) if rng.random() < 0.5 else rng.uniform(1.4, 2.0)

            mu = max(level0 * mult, 0.05)
            k = 25.0
            demand[i] = rng.poisson(rng.gamma(k, mu / k))
            price[i] = round(p, 2)
            events.append(ev)
        demand[n_known:] = np.nan
        series.append(
            Series(
                sku_id=item["sku"],
                title=item["title"],
                category=item["cat"],
                store="Store #12 (Austin, TX)",
                week_starts=[w.isoformat() for w in weeks],
                demand=demand,
                price=price,
                events=events,
            )
        )
    return Dataset(
        name="synthetic-store",
        source="synthetic",
        description=(
            "Synthetic single-store catalogue (20 SKUs, weekly) with US holidays, planned "
            "promotions, price changes, post-promotion dips and unannounced shocks. "
            "Generated by shelfcast.data.generate_synthetic; not real sales."
        ),
        series=series,
    )


# --------------------------------------------------------------------------- #
# M5 (Walmart) loader
# --------------------------------------------------------------------------- #

M5_URL = "https://github.com/Nixtla/m5-forecasts/raw/main/datasets/m5.zip"
_M5_FILES = ("calendar.csv", "sell_prices.csv", "sales_train_evaluation.csv")


def _find_m5_files(data_dir: str | os.PathLike) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f in _M5_FILES and f not in found:
                found[f] = Path(root) / f
    return found


def download_m5(data_dir: str | os.PathLike, url: str = M5_URL) -> None:
    """Download and unzip the M5 files unless they are already present.

    The Kaggle copy (``kaggle competitions download -c m5-forecasting-accuracy``)
    works too: unzip it anywhere under ``data_dir``.
    """
    import urllib.request

    if len(_find_m5_files(data_dir)) == len(_M5_FILES):
        return
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    zpath = Path(data_dir) / "m5.zip"
    if not zpath.exists():
        print(f"Downloading M5 from {url} ...")
        with urllib.request.urlopen(url, timeout=120) as resp, open(zpath, "wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(data_dir)
    missing = set(_M5_FILES) - set(_find_m5_files(data_dir))
    if missing:
        raise FileNotFoundError(f"M5 archive is missing {sorted(missing)}")


def load_m5(
    data_dir: str | os.PathLike,
    n_series: int = 60,
    seed: int = 0,
    min_weekly_mean: float = 20.0,
    max_zero_share: float = 0.05,
    min_weeks: int = 104,
    holdout_weeks: int = 26,
) -> Dataset:
    """Weekly M5 series with calendar events, SNAP days and shelf prices.

    Picks ``n_series`` item-store series, spread evenly over the three
    categories, among those selling at least ``min_weekly_mean`` units a week
    over the last year, rarely selling zero and with ``min_weeks`` of history,
    judged on the weeks before the last ``holdout_weeks`` so the backtest window
    plays no part in choosing them. Weeks are Walmart weeks
    (Saturday to Friday); the partial final week is dropped.
    """
    import pandas as pd

    files = _find_m5_files(data_dir)
    missing = set(_M5_FILES) - set(files)
    if missing:
        raise FileNotFoundError(f"{sorted(missing)} not found under {data_dir}; run download_m5 first")

    cal = pd.read_csv(files["calendar.csv"])
    if "d" not in cal.columns:  # some mirrors drop it; rows are consecutive days from d_1
        cal["d"] = [f"d_{i + 1}" for i in range(len(cal))]
    sales = pd.read_csv(files["sales_train_evaluation.csv"])
    d_cols = [c for c in sales.columns if c.startswith("d_")]
    cal = cal.set_index("d").loc[d_cols].reset_index()

    # Contiguous Walmart weeks; keep only complete ones.
    wk = cal["wm_yr_wk"].to_numpy()
    starts = np.flatnonzero(np.r_[True, wk[1:] != wk[:-1]])
    lengths = np.diff(np.r_[starts, len(wk)])
    full = lengths == 7
    week_ids = wk[starts][full]
    week_dates = pd.to_datetime(cal["date"]).dt.date.to_numpy()[starts][full]

    daily = sales[d_cols].to_numpy(dtype=np.float32)
    weekly_all = np.add.reduceat(daily, starts, axis=1)[:, full].astype(float)

    seen = weekly_all[:, :-holdout_weeks] if holdout_weeks > 0 else weekly_all
    last_year = seen[:, -52:]
    ok = last_year.mean(axis=1) >= min_weekly_mean
    for r in np.flatnonzero(ok):
        row = seen[r]
        first = np.flatnonzero(row > 0)
        live = row[first[0]:] if first.size else row
        if (live == 0).mean() > max_zero_share or live.size < min_weeks:
            ok[r] = False
    candidates = sales.loc[ok, ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]]

    rng = np.random.default_rng(seed)
    cats = sorted(candidates["cat_id"].unique())
    picks: list[int] = []
    per_cat = max(1, n_series // len(cats))
    for c in cats:
        idx = candidates.index[candidates["cat_id"] == c].to_numpy()
        picks.extend(rng.choice(idx, size=min(per_cat, idx.size), replace=False).tolist())
    picks = sorted(picks)[:n_series]

    # Events and SNAP counts per week and state.
    week_events: list[list[str]] = []
    snap: dict[str, list[int]] = {s: [] for s in ("CA", "TX", "WI")}
    for s0, ln, is_full in zip(starts, lengths, full):
        if not is_full:
            continue
        evs: list[str] = []
        for _, row in cal.iloc[s0:s0 + ln].iterrows():
            day = WEEKDAYS[pd.Timestamp(row["date"]).weekday()]
            for n_col, t_col in (("event_name_1", "event_type_1"), ("event_name_2", "event_type_2")):
                if isinstance(row[n_col], str):
                    evs.append(f"{row[t_col]} event: {row[n_col]} ({day})")
        week_events.append(evs)
        for s in snap:
            snap[s].append(int(cal.iloc[s0:s0 + ln][f"snap_{s}"].sum()))

    prices = pd.read_csv(files["sell_prices.csv"])
    chosen = sales.loc[picks, ["item_id", "store_id"]]
    prices = prices.merge(chosen, on=["item_id", "store_id"])
    price_map = {
        key: dict(zip(g["wm_yr_wk"], g["sell_price"]))
        for key, g in prices.groupby(["item_id", "store_id"])
    }

    series: list[Series] = []
    for r in picks:
        meta = sales.loc[r]
        row = weekly_all[r]
        first = int(np.flatnonzero(row > 0)[0])
        pm = price_map[(meta["item_id"], meta["store_id"])]
        state = meta["state_id"]
        evs = []
        for i in range(first, len(row)):
            e = list(week_events[i])
            if snap[state][i]:
                e.append(f"SNAP benefit days: {snap[state][i]}")
            evs.append(e)
        series.append(
            Series(
                sku_id=meta["id"].replace("_evaluation", ""),
                title=f"{meta['item_id']} @ {meta['store_id']}",
                category=f"{meta['cat_id']} / {meta['dept_id']}",
                store=f"Walmart {meta['store_id']} ({state})",
                week_starts=[d.isoformat() for d in week_dates[first:]],
                demand=row[first:],
                price=np.array([pm.get(w, np.nan) for w in week_ids[first:]], dtype=float),
                events=evs,
            )
        )
    return Dataset(
        name=f"m5-{len(series)}",
        source="m5",
        description=(
            f"{len(series)} item-store series from the M5 (Walmart) competition data, aggregated "
            "to Walmart weeks, with calendar events, SNAP days and shelf prices."
        ),
        series=series,
    )
