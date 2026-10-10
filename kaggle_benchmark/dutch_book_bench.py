# %% [markdown]
# # Dutch Book Bench: can you arbitrage an LLM forecaster?
#
# LLM forecasting bots (like the ones in Metaculus' AI benchmark tournaments) usually ask the model
# **one question at a time, in a fresh context**. A bot asked "Will X happen?" and later
# "Will X *not* happen?" can easily answer 60% and 55%. A bookmaker can then sell it both contracts and make a
# guaranteed profit, whatever happens. That is a *Dutch book*, and a probabilistic forecaster that allows one is
# **incoherent**: its numbers cannot all be probabilities.
#
# Measuring coherence does **not** need ground truth. So this benchmark can use genuinely open questions about
# 2027-2050, which no model can have memorised, without waiting for them to resolve.
#
# **Method**
# * 37 *question families*. Each family is a set of statements over the same small set of possible worlds
#   ("atoms"). The families come in six types:
#   `negation` (A / not-A), `threshold` (P(X > t) for rising t, which is how Metaculus builds numeric CDFs),
#   `deadline` (happens by 2030 / 2035 / ...), `partition` (mutually exclusive, exhaustive bins, as in
#   multiple-choice questions), `conjunction` (A, B, A and B, A or B) and `story` (A versus A plus a plausible
#   detail: the Linda problem).
# * 28 families are about the real, uncertain future. 9 are **controls** (dice, coins, cards) with exact answers,
#   which separate "can't do probability" from "is incoherent under uncertainty".
# * Each statement is asked **in isolation**, in a fresh chat. Separately, each whole family is asked **jointly** in
#   a single prompt.
# * For each family we compute the **guaranteed Dutch-book profit**: the most a bookie can be sure of winning by
#   trading at most $1 of each contract at the model's prices. By de Finetti's theorem and LP duality, this equals
#   the L1 distance from the model's probability vector to the coherent polytope (the convex hull of the atoms'
#   truth vectors). A coherent forecaster has 0.
#
# **Leaderboard score**: the **arbitrage-free rate**, the percentage of families (asked in isolation, the way bots
# work) where a bookie can guarantee at most 5¢. Higher is better. A model that fails to answer 10% or more of the
# families (API errors or no parseable number) is not scored at all, so a dropped call never counts as incoherence.

# %%
import os

os.environ.setdefault("RENDER_SUBRUNS", "False")

import datetime
import itertools
import json
import math
import random
import re
import time
from fractions import Fraction

import numpy as np
import pandas as pd

import kaggle_benchmarks as kbench

TODAY = datetime.date.today().isoformat()
ARB_TOL = 0.05  # dollars of guaranteed bookie profit per family still counted as "arbitrage-free"
N_JOBS = 8
TIMEOUT_S = 600
MAX_API_ATTEMPTS = 6  # per call; rate limits are retried with exponential backoff
# Kaggle's model proxy reserves quota up front from max_tokens (the default reservation is >$3 per call on big models,
# which fails under concurrency), so every call sets an explicit cap and halves it on a failed attempt.
MAX_OUTPUT_TOKENS = 2500
# Reasoning effort requested from models that support it. The answers are short, and thinking tokens are what
# make a 160-call suite expensive on the Kaggle proxy; models that reject the parameter are retried without it.
REASONING = "low"
MIN_OUTPUT_TOKENS = 1500
MIN_COVERAGE = 0.9  # a model must answer >= 90% of families or the task fails instead of scoring
OUT_DIR = "/kaggle/working" if os.path.isdir("/kaggle/working") else "."

# %% [markdown]
# ## 1. Question families
#
# Every family lists its statements and, for each one, the set of atoms (possible worlds) in which it is true.
# Control families also carry the exact probability, computed below by enumeration.

# %%
FAMILIES: list[dict] = []


def _family(fid, ftype, domain, n_atoms, questions, note=""):
    FAMILIES.append(
        dict(
            fid=fid,
            ftype=ftype,
            domain=domain,
            n_atoms=n_atoms,
            note=note,
            questions=[
                dict(qid=f"{fid}.{i}", text=text, atoms=sorted(atoms), exact=exact)
                for i, (text, atoms, exact) in enumerate(questions)
            ],
        )
    )


def negation(fid, a, not_a, domain="uncertain", p_exact=None):
    q = None if p_exact is None else float(p_exact)
    _family(
        fid, "negation", domain, 2,
        [(a, {0}, q), (not_a, {1}, None if q is None else 1 - q)],
    )


def threshold(fid, template, thresholds, direction="above", domain="uncertain", cdf_exact=None):
    """P(X > t) (direction='above') or P(X < t) ('below') for increasing t.

    Atom j is the interval between consecutive thresholds (k thresholds -> k+1 atoms).
    """
    k = len(thresholds)
    qs = []
    for i, t in enumerate(thresholds):
        atoms = set(range(i + 1, k + 1)) if direction == "above" else set(range(0, i + 1))
        exact = None if cdf_exact is None else float(cdf_exact(t))
        qs.append((template.format(t=t), atoms, exact))
    _family(fid, "threshold", domain, k + 1, qs)


def deadline(fid, template, dates, domain="uncertain"):
    """'X happens by d_i' for increasing d_i. Atom j = first happens in period j; atom k = not by the last date."""
    k = len(dates)
    qs = [(template.format(d=d), set(range(0, i + 1)), None) for i, d in enumerate(dates)]
    _family(fid, "deadline", domain, k + 1, qs)


def partition(fid, statements, domain="uncertain", exact=None):
    qs = [
        (s, {i}, None if exact is None else float(exact[i]))
        for i, s in enumerate(statements)
    ]
    _family(fid, "partition", domain, len(statements), qs)


def conjunction(fid, a, b, a_and_b, a_or_b, domain="uncertain", exact=None):
    # atoms: 0 = A&B, 1 = A&~B, 2 = ~A&B, 3 = ~A&~B
    e = exact or {}
    _family(
        fid, "conjunction", domain, 4,
        [
            (a, {0, 1}, e.get("a")),
            (b, {0, 2}, e.get("b")),
            (a_and_b, {0}, e.get("ab")),
            (a_or_b, {0, 1, 2}, e.get("aorb")),
        ],
    )


def story(fid, a, a_with_detail, domain="uncertain"):
    # atoms: 0 = A with the detail, 1 = A without it, 2 = not A
    _family(fid, "story", domain, 3, [(a, {0, 1}, None), (a_with_detail, {0}, None)])


# %% [markdown]
# ### Uncertain, real-world families (2027-2050)

# %%
# --- negation: the complement is phrased as a positive statement, not "it is not the case that ..."
negation(
    "neg_gistemp",
    "NASA GISTEMP reports a global mean surface temperature anomaly for calendar year 2028 above 1.30°C (relative to the 1951-1980 baseline).",
    "NASA GISTEMP reports a global mean surface temperature anomaly for calendar year 2028 of 1.30°C or less (relative to the 1951-1980 baseline).",
)
negation(
    "neg_unemployment",
    "The US unemployment rate (U-3, seasonally adjusted) for December 2027, as first published by the BLS, is 5.0% or higher.",
    "The US unemployment rate (U-3, seasonally adjusted) for December 2027, as first published by the BLS, is below 5.0%.",
)
negation(
    "neg_apple_msft",
    "At the close of trading on 29 December 2028, Apple's market capitalization is larger than Microsoft's.",
    "At the close of trading on 29 December 2028, Microsoft's market capitalization is larger than or equal to Apple's.",
)
negation(
    "neg_moon",
    "At least one human walks on the surface of the Moon before 1 January 2029.",
    "No human walks on the surface of the Moon between now and 1 January 2029.",
)
negation(
    "neg_worldcup_europe",
    "The 2030 FIFA World Cup final is won by a national team from UEFA (Europe).",
    "The 2030 FIFA World Cup final is won by a national team from outside UEFA (outside Europe).",
)
negation(
    "neg_brent",
    "The Brent crude oil spot price on 31 December 2027 (EIA daily series) is above $70 per barrel.",
    "The Brent crude oil spot price on 31 December 2027 (EIA daily series) is $70 per barrel or lower.",
)

# --- threshold (a numeric question's CDF, asked one threshold at a time)
threshold(
    "thr_bitcoin",
    "The price of Bitcoin on 31 December 2028 (CoinMarketCap daily close, USD) is above ${t:,}.",
    [50_000, 100_000, 150_000, 250_000],
)
threshold(
    "thr_sp500",
    "The S&P 500 index closes above {t:,} on the last trading day of 2028.",
    [5_000, 6_500, 8_000, 10_000],
)
threshold(
    "thr_ev_share",
    "Electric cars (BEV + PHEV) make up more than {t}% of global new passenger car sales in 2030, according to the IEA Global EV Outlook.",
    [30, 40, 50, 60],
)
threshold(
    "thr_sea_ice",
    "The September 2030 Arctic sea ice minimum extent reported by NSIDC is below {t} million km².",
    [3.0, 3.5, 4.0, 4.5],
    direction="below",
)
threshold(
    "thr_treasury",
    "The US 10-year Treasury constant-maturity yield on 29 December 2028 (FRED series DGS10) is above {t}%.",
    [3.0, 4.0, 5.0, 6.0],
)

# --- deadline (cumulative probability over time must not decrease)
deadline(
    "ddl_mars",
    "A human sets foot on the surface of Mars on or before 31 December {d}.",
    [2030, 2035, 2040, 2050],
)
deadline(
    "ddl_fusion",
    "A fusion power plant delivers electricity to a commercial power grid on or before 31 December {d}.",
    [2030, 2035, 2040, 2050],
)
deadline(
    "ddl_population",
    "The US Census Bureau's World Population Clock first shows a world population of at least 8.5 billion on or before 31 December {d}.",
    [2028, 2030, 2032, 2035],
)
deadline(
    "ddl_robotaxi_london",
    "A fully driverless robotaxi service (no safety driver on board) is open to the general public in London on or before 31 December {d}.",
    [2027, 2028, 2030, 2035],
)

# --- partition (mutually exclusive and exhaustive outcomes, asked one bin at a time)
partition(
    "par_us2028",
    [
        "The 2028 US presidential election is won by the Democratic Party's nominee.",
        "The 2028 US presidential election is won by the Republican Party's nominee.",
        "The 2028 US presidential election is won by a candidate who is neither the Democratic nor the Republican nominee.",
    ],
)
partition(
    "par_storms2028",
    [
        "The 2028 Atlantic hurricane season has 12 or fewer named storms (per NOAA's final count).",
        "The 2028 Atlantic hurricane season has between 13 and 16 named storms inclusive (per NOAA's final count).",
        "The 2028 Atlantic hurricane season has between 17 and 20 named storms inclusive (per NOAA's final count).",
        "The 2028 Atlantic hurricane season has 21 or more named storms (per NOAA's final count).",
    ],
)
partition(
    "par_la2028_gold",
    [
        "The United States wins the most gold medals at the 2028 Los Angeles Summer Olympics (ties broken by total medals, then alphabetically).",
        "China wins the most gold medals at the 2028 Los Angeles Summer Olympics (ties broken by total medals, then alphabetically).",
        "A country other than the United States and China wins the most gold medals at the 2028 Los Angeles Summer Olympics (ties broken by total medals, then alphabetically).",
    ],
)
partition(
    "par_warmest_year",
    [
        f"Of the four years 2027, 2028, 2029 and 2030, {y} has the highest annual global temperature anomaly in NASA GISTEMP (ties go to the earlier year)."
        for y in (2027, 2028, 2029, 2030)
    ],
)
partition(
    "par_worldcup2030",
    [
        f"{team} wins the 2030 FIFA World Cup."
        for team in ("Spain", "France", "Brazil", "Argentina", "England")
    ]
    + ["A team other than Spain, France, Brazil, Argentina and England wins the 2030 FIFA World Cup."],
)

# --- conjunction (A, B, A and B, A or B)
conjunction(
    "con_btc_sp",
    "The price of Bitcoin on 31 December 2028 (CoinMarketCap daily close, USD) is above $150,000.",
    "The S&P 500 index closes above 8,000 on the last trading day of 2028.",
    "Both of these happen: Bitcoin's 31 December 2028 CoinMarketCap daily close is above $150,000, and the S&P 500 closes above 8,000 on the last trading day of 2028.",
    "At least one of these happens: Bitcoin's 31 December 2028 CoinMarketCap daily close is above $150,000, or the S&P 500 closes above 8,000 on the last trading day of 2028.",
)
conjunction(
    "con_moon_race",
    "NASA lands astronauts on the Moon before 1 January 2031.",
    "China lands astronauts (taikonauts) on the Moon before 1 January 2031.",
    "Both NASA and China land astronauts on the Moon before 1 January 2031.",
    "NASA or China (or both) land astronauts on the Moon before 1 January 2031.",
)
conjunction(
    "con_ipos",
    "OpenAI's shares (or the shares of a holding company that owns it) are publicly listed on a stock exchange before 1 January 2029.",
    "SpaceX's shares are publicly listed on a stock exchange before 1 January 2029.",
    "Both OpenAI (directly or via a holding company) and SpaceX have publicly listed shares on a stock exchange before 1 January 2029.",
    "At least one of OpenAI (directly or via a holding company) and SpaceX has publicly listed shares on a stock exchange before 1 January 2029.",
)
conjunction(
    "con_climate",
    "NASA GISTEMP reports a global mean surface temperature anomaly for calendar year 2028 above 1.30°C (relative to 1951-1980).",
    "The September 2028 Arctic sea ice minimum extent reported by NSIDC is below 4.0 million km².",
    "Both: NASA GISTEMP's 2028 global anomaly is above 1.30°C (relative to 1951-1980), and NSIDC's September 2028 Arctic sea ice minimum is below 4.0 million km².",
    "At least one: NASA GISTEMP's 2028 global anomaly is above 1.30°C (relative to 1951-1980), or NSIDC's September 2028 Arctic sea ice minimum is below 4.0 million km².",
)
conjunction(
    "con_quake",
    "An earthquake of magnitude 7.0 or greater (USGS) has its epicenter in California between now and 31 December 2035.",
    "An earthquake of magnitude 7.0 or greater (USGS) has its epicenter in Japan's Kanto region between now and 31 December 2035.",
    "Between now and 31 December 2035, there is both an M7.0+ earthquake (USGS) with its epicenter in California and an M7.0+ earthquake with its epicenter in Japan's Kanto region.",
    "Between now and 31 December 2035, there is an M7.0+ earthquake (USGS) with its epicenter in California, or one in Japan's Kanto region, or both.",
)

# --- story (conjunction fallacy: adding a plausible detail can only lower the probability)
story(
    "sty_hurricane",
    "A Category 4 or 5 hurricane makes landfall in the United States during 2028.",
    "A Category 4 or 5 hurricane makes landfall in the United States during 2028 and causes more than $50 billion in damage.",
)
story(
    "sty_tesla",
    "Tesla delivers more than 3 million vehicles in calendar year 2028.",
    "Tesla starts selling a new vehicle priced under $30,000 before the end of 2028 and delivers more than 3 million vehicles in calendar year 2028.",
)
story(
    "sty_mars",
    "A human sets foot on the surface of Mars before 1 January 2040.",
    "A human sets foot on the surface of Mars before 1 January 2040, having travelled there aboard a SpaceX Starship.",
)

# %% [markdown]
# ### Control families (exact answers by enumeration)

# %%
DIE = range(1, 7)
two_dice = list(itertools.product(DIE, DIE))
three_dice = list(itertools.product(DIE, DIE, DIE))


def p_of(outcomes, pred):
    return Fraction(sum(1 for o in outcomes if pred(o)), len(outcomes))


negation(
    "ctl_neg_dice",
    "Two fair six-sided dice are rolled once. Their sum is 9 or more.",
    "Two fair six-sided dice are rolled once. Their sum is 8 or less.",
    domain="control",
    p_exact=p_of(two_dice, lambda o: sum(o) >= 9),
)
_distinct_ranks = Fraction(math.comb(13, 5) * 4**5, math.comb(52, 5))
negation(
    "ctl_neg_cards",
    "Five cards are dealt from a well-shuffled standard 52-card deck. At least two of the five cards have the same rank.",
    "Five cards are dealt from a well-shuffled standard 52-card deck. All five cards have different ranks.",
    domain="control",
    p_exact=1 - _distinct_ranks,
)
threshold(
    "ctl_thr_coins",
    "A fair coin is flipped 10 times. It lands heads more than {t} times.",
    [3, 5, 6, 8],
    domain="control",
    cdf_exact=lambda t: Fraction(sum(math.comb(10, k) for k in range(t + 1, 11)), 2**10),
)
threshold(
    "ctl_thr_3dice",
    "Three fair six-sided dice are rolled once. Their sum is greater than {t}.",
    [8, 10, 12, 14],
    domain="control",
    cdf_exact=lambda t: p_of(three_dice, lambda o: sum(o) > t),
)
partition(
    "ctl_par_max",
    [
        "Two fair six-sided dice are rolled once. The larger of the two values is 1 or 2.",
        "Two fair six-sided dice are rolled once. The larger of the two values is 3 or 4.",
        "Two fair six-sided dice are rolled once. The larger of the two values is exactly 5.",
        "Two fair six-sided dice are rolled once. The larger of the two values is exactly 6.",
    ],
    domain="control",
    exact=[p_of(two_dice, lambda o, lo=lo, hi=hi: lo <= max(o) <= hi) for lo, hi in ((1, 2), (3, 4), (5, 5), (6, 6))],
)
_aces = [Fraction(math.comb(4, k) * math.comb(48, 5 - k), math.comb(52, 5)) for k in range(5)]
partition(
    "ctl_par_aces",
    [
        "Five cards are dealt from a well-shuffled standard 52-card deck. The hand contains no aces.",
        "Five cards are dealt from a well-shuffled standard 52-card deck. The hand contains exactly one ace.",
        "Five cards are dealt from a well-shuffled standard 52-card deck. The hand contains exactly two aces.",
        "Five cards are dealt from a well-shuffled standard 52-card deck. The hand contains three or more aces.",
    ],
    domain="control",
    exact=[_aces[0], _aces[1], _aces[2], _aces[3] + _aces[4]],
)
conjunction(
    "ctl_con_card",
    "One card is drawn from a well-shuffled standard 52-card deck. It is a heart.",
    "One card is drawn from a well-shuffled standard 52-card deck. It is a face card (jack, queen or king).",
    "One card is drawn from a well-shuffled standard 52-card deck. It is a face card (jack, queen or king) of hearts.",
    "One card is drawn from a well-shuffled standard 52-card deck. It is a heart, or a face card (jack, queen or king), or both.",
    domain="control",
    exact=dict(a=1 / 4, b=12 / 52, ab=3 / 52, aorb=22 / 52),
)
conjunction(
    "ctl_con_dice",
    "Two fair six-sided dice, one red and one blue, are rolled once. The red die shows an even number.",
    "Two fair six-sided dice, one red and one blue, are rolled once. The sum of the two dice is 8 or more.",
    "Two fair six-sided dice, one red and one blue, are rolled once. The red die shows an even number and the sum is 8 or more.",
    "Two fair six-sided dice, one red and one blue, are rolled once. The red die shows an even number, or the sum is 8 or more, or both.",
    domain="control",
    exact=dict(
        a=float(p_of(two_dice, lambda o: o[0] % 2 == 0)),
        b=float(p_of(two_dice, lambda o: sum(o) >= 8)),
        ab=float(p_of(two_dice, lambda o: o[0] % 2 == 0 and sum(o) >= 8)),
        aorb=float(p_of(two_dice, lambda o: o[0] % 2 == 0 or sum(o) >= 8)),
    ),
)
story(
    "ctl_sty_dice",
    "A fair six-sided die is rolled 4 times. At least one roll is a 6.",
    "A fair six-sided die is rolled 4 times. At least one roll is a 6, and the first roll is odd.",
    domain="control",
)
# exact answers for the control story family
FAMILIES[-1]["questions"][0]["exact"] = 1 - (5 / 6) ** 4
FAMILIES[-1]["questions"][1]["exact"] = float(
    p_of(list(itertools.product(DIE, repeat=4)), lambda o: 6 in o and o[0] % 2 == 1)
)

FAMILY_BY_ID = {f["fid"]: f for f in FAMILIES}
QUESTIONS = pd.DataFrame(
    [dict(qid=q["qid"], fid=f["fid"], ftype=f["ftype"], domain=f["domain"], text=q["text"]) for f in FAMILIES for q in f["questions"]]
)
print(f"{len(FAMILIES)} families ({sum(f['domain'] == 'uncertain' for f in FAMILIES)} uncertain, "
      f"{sum(f['domain'] == 'control' for f in FAMILIES)} control), {len(QUESTIONS)} isolated questions")
print(QUESTIONS.groupby(["domain", "ftype"]).fid.nunique().unstack(fill_value=0))

# %% [markdown]
# ## 2. Self-checks on the family definitions
# The control families must be exactly coherent, and each atom must be a genuinely different world.

# %%
def guaranteed_arbitrage(probs, atom_sets, n_atoms):
    """Max guaranteed bookie profit (in $) with stakes of at most $1 per contract.

    Equals min ||p - q||_1 over coherent q = convex hull of the atoms' truth vectors (LP duality).
    The objective is convex and piecewise linear in the atom weights, so the minimum sits where n_atoms - 1 of
    the "kink" hyperplanes (q_i = p_i, or weight_j = 0) meet. The families are tiny, so we enumerate those points
    exactly with numpy alone (the Kaggle benchmark image has no scipy).
    """
    p = np.asarray(probs, dtype=float)
    n = len(p)
    V = np.array([[1.0 if a in s else 0.0 for a in range(n_atoms)] for s in atom_sets])  # questions x atoms
    rows = [(V[i], p[i]) for i in range(n)] + [(np.eye(n_atoms)[j], 0.0) for j in range(n_atoms)]
    best = float(np.abs(V @ np.full(n_atoms, 1 / n_atoms) - p).sum())
    ones = np.ones(n_atoms)
    for combo in itertools.combinations(range(len(rows)), n_atoms - 1):
        A = np.vstack([ones] + [rows[k][0] for k in combo])
        b = np.array([1.0] + [rows[k][1] for k in combo])
        if abs(np.linalg.det(A)) < 1e-10:
            continue
        lam = np.linalg.solve(A, b)
        if lam.min() < -1e-9:
            continue
        best = min(best, float(np.abs(V @ lam - p).sum()))
    return best


for f in FAMILIES:
    sets = [tuple(q["atoms"]) for q in f["questions"]]
    assert len(set(sets)) == len(sets), f["fid"]
    if f["domain"] == "control":
        exact = [q["exact"] for q in f["questions"]]
        assert all(e is not None for e in exact), f["fid"]
        assert guaranteed_arbitrage(exact, [q["atoms"] for q in f["questions"]], f["n_atoms"]) < 1e-9, f["fid"]

# Sanity: the textbook Dutch book (A at 0.60 and not-A at 0.55) earns the bookie exactly 15 cents.
assert abs(guaranteed_arbitrage([0.60, 0.55], [[0], [1]], 2) - 0.15) < 1e-9
# A non-monotone CDF: P(X>1)=0.5 < P(X>2)=0.7 earns 20 cents.
assert abs(guaranteed_arbitrage([0.5, 0.7], [[1, 2], [2]], 3) - 0.20) < 1e-9
print("family definitions OK")

# %% [markdown]
# ## 3. Prompts and parsing

# %%
ISOLATED_PROMPT = """You are an expert, well-calibrated forecaster. Today's date is {today}.

Estimate the probability that the following statement is (or will turn out to be) true:

"{statement}"

Think briefly (at most 4 sentences), then end your reply with a final line in exactly this format:
Probability: <a number between 0 and 1>"""

JOINT_PROMPT = """You are an expert, well-calibrated forecaster. Today's date is {today}.

For each statement below, estimate the probability that it is (or will turn out to be) true.

{statements}

Think briefly (at most 6 sentences in total), then end your reply with one line per statement in exactly this format:
{format_lines}"""

_NUM = r"[~≈]?\s*([0-9]*\.?[0-9]+)\s*(%?)"


def _to_prob(num: str, pct: str) -> float | None:
    try:
        x = float(num)
    except ValueError:
        return None
    if pct or 1 < x <= 100:
        x /= 100
    return x if 0 <= x <= 1 else None


def parse_probability(text: str) -> float | None:
    matches = re.findall(r"probability\**\s*[:=]\s*\**\s*" + _NUM, text or "", flags=re.I)
    return _to_prob(*matches[-1]) if matches else None


def parse_joint(text: str, n: int) -> list[float | None]:
    out: list[float | None] = [None] * n
    for idx, num, pct in re.findall(r"\bQ\s*(\d+)\s*\**\s*[:=]\s*\**\s*" + _NUM, text or "", flags=re.I):
        i = int(idx) - 1
        if 0 <= i < n:
            out[i] = _to_prob(num, pct)  # the last occurrence wins, i.e. the final answer block
    return out


assert parse_probability("blah\nProbability: 0.35") == 0.35
assert parse_probability("**Probability:** 35%") == 0.35
assert parse_probability("Probability: 0.2 ... final Probability: 0.25") == 0.25
assert parse_probability("Probability: ~0.35") == 0.35
assert parse_probability("I cannot say.") is None
assert parse_joint("Q1: 0.1\nQ2: 20%\nQ3: 0.7", 3) == [0.1, 0.2, 0.7]


def isolated_prompt(qid: str) -> str:
    fid = qid.rsplit(".", 1)[0]
    text = next(q["text"] for q in FAMILY_BY_ID[fid]["questions"] if q["qid"] == qid)
    return ISOLATED_PROMPT.format(today=TODAY, statement=text)


def joint_prompt(fid: str) -> str:
    qs = FAMILY_BY_ID[fid]["questions"]
    return JOINT_PROMPT.format(
        today=TODAY,
        statements="\n".join(f"Q{i + 1}. {q['text']}" for i, q in enumerate(qs)),
        format_lines="\n".join(f"Q{i + 1}: <probability>" for i in range(len(qs))),
    )


print(isolated_prompt("neg_apple_msft.1"))

# %% [markdown]
# ## 4. Tasks
# `ask_isolated` runs once per statement. Each run is a fresh chat, so the model never sees the sibling questions.
# `ask_joint` shows the model a whole family at once.

# %%
def _ask(llm, message: str, attempts: int = MAX_API_ATTEMPTS) -> str:
    """llm.prompt with retries. The Kaggle proxy rate-limits bigger models under concurrency, and a dropped call
    must not be mistaken for an incoherent (or unparseable) answer."""
    delay = 2.0
    max_tokens = MAX_OUTPUT_TOKENS
    reasoning = REASONING
    for attempt in range(1, attempts + 1):
        try:
            return str(llm.prompt(message, temperature=0, reasoning=reasoning,
                                  extra_api_params={"max_tokens": max_tokens}))
        except Exception as e:  # noqa: BLE001 - we re-raise after the last attempt
            if attempt == attempts:
                raise
            if reasoning is not None and "reasoning" in str(e).lower():
                reasoning = None  # the model does not take a reasoning parameter; retry without it
                continue
            time.sleep(delay + random.random())
            delay = min(delay * 2, 40)
            max_tokens = max(MIN_OUTPUT_TOKENS, max_tokens // 2)


@kbench.task(name="dbb_ask_isolated", store_task=False)
def ask_isolated(llm, qid: str, attempts: int = MAX_API_ATTEMPTS) -> dict:
    reply = _ask(llm, isolated_prompt(qid), attempts=attempts)
    return dict(qid=qid, p=parse_probability(reply), raw=reply[-600:])


@kbench.task(name="dbb_ask_joint", store_task=False)
def ask_joint(llm, fid: str) -> dict:
    n = len(FAMILY_BY_ID[fid]["questions"])
    reply = _ask(llm, joint_prompt(fid))
    return dict(fid=fid, ps=parse_joint(reply, n), raw=reply[-1200:])


def _collect(task, llm, df, **grid) -> tuple[list[dict], list[str]]:
    with kbench.client.enable_cache():
        runs = task.evaluate(
            llm=[llm],
            evaluation_data=df,
            n_jobs=N_JOBS,
            timeout=TIMEOUT_S,
            max_attempts=1,
            on_failure="continue",
            remove_run_files=True,
            **{k: [v] for k, v in grid.items()},
        )
    results = [r.result for r in runs.completed_runs if isinstance(r.result, dict)]
    errors = [
        (str(getattr(r, "error_message", "") or "unknown error").strip().splitlines() or ["unknown error"])[-1][:300]
        for r in runs.errored_runs
    ]
    return results, errors


def score_families(prob_by_qid: dict) -> pd.DataFrame:
    rows = []
    for f in FAMILIES:
        qs = f["questions"]
        ps = [prob_by_qid.get(q["qid"]) for q in qs]
        parsed = all(p is not None for p in ps)
        arb = guaranteed_arbitrage(ps, [q["atoms"] for q in qs], f["n_atoms"]) if parsed else np.nan
        brier = (
            float(np.mean([(p - q["exact"]) ** 2 for p, q in zip(ps, qs)]))
            if parsed and f["domain"] == "control" else np.nan
        )
        rows.append(dict(
            fid=f["fid"], ftype=f["ftype"], domain=f["domain"], n_q=len(qs), parsed=parsed,
            arbitrage=arb, arbitrage_free=bool(parsed and arb <= ARB_TOL + 1e-9), brier=brier,
            probs=json.dumps([None if p is None else round(p, 4) for p in ps]),
        ))
    return pd.DataFrame(rows)


# model name -> detailed results, for the analysis section. Kept across re-runs of the notebook in the same
# interactive kernel so a fix in a later cell does not force every model to be re-evaluated.
RESULTS: dict[str, dict] = globals().get("RESULTS") or {}
SKIPPED: dict[str, str] = globals().get("SKIPPED") or {}  # model name -> why it could not be evaluated

CACHE_NAME = "dbb_results.json"


def save_cache(path: str = f"{OUT_DIR}/{CACHE_NAME}") -> None:
    """Write RESULTS/SKIPPED to JSON so a later session (or a reader) can reuse them without re-spending quota."""
    payload = {
        "results": {
            m: dict(model=r["model"], score=r["score"], api_errors=r.get("api_errors", 0),
                    families=r["families"].to_dict("records"), raw_isolated=r["raw_isolated"])
            for m, r in RESULTS.items()
        },
        "skipped": SKIPPED,
    }
    with open(path, "w") as fh:
        json.dump(payload, fh)


def load_cache() -> int:
    """Load cached results from an attached input (or the working dir). Returns how many models were loaded."""
    import glob

    paths = glob.glob(f"/kaggle/input/**/{CACHE_NAME}", recursive=True) + glob.glob(f"{OUT_DIR}/{CACHE_NAME}")
    n = 0
    for path in paths:
        with open(path) as fh:
            payload = json.load(fh)
        for m, r in payload.get("results", {}).items():
            if m not in RESULTS:
                RESULTS[m] = dict(model=r["model"], score=r["score"], api_errors=r.get("api_errors", 0),
                                  families=pd.DataFrame(r["families"]), raw_isolated=r["raw_isolated"])
                n += 1
        # "skipped" reasons are session-specific (quota, outages), so they are reported but never reloaded.
    return n


print(f"loaded {load_cache()} cached model result(s)")


def run_suite(llm) -> dict:
    name = getattr(llm, "name", str(llm))
    if name in RESULTS:
        return RESULTS[name]
    # Probe before spending ~160 calls: one call, then a burst of N_JOBS concurrent calls without retries. A model
    # this account cannot use, or a quota that is nearly exhausted (the proxy reserves each call's cost up front,
    # so single calls can pass while concurrent ones fail), fails fast here and is recorded in SKIPPED.
    try:
        _ask(llm, isolated_prompt(QUESTIONS.qid.iloc[0]), attempts=3)
    except Exception as e:  # noqa: BLE001
        SKIPPED[name] = f"{type(e).__name__}: {str(e)[:300]}"
        raise RuntimeError(f"{name}: probe call failed, skipping. {SKIPPED[name]}") from e
    burst, burst_errors = _collect(ask_isolated, llm, QUESTIONS[["qid"]].head(N_JOBS), attempts=1)
    if len(burst_errors) > N_JOBS // 4:
        SKIPPED[name] = f"{len(burst_errors)}/{N_JOBS} concurrent calls failed: {burst_errors[:1]}"
        raise RuntimeError(f"{name}: burst probe failed, skipping. {SKIPPED[name]}")
    iso, iso_errors = _collect(ask_isolated, llm, QUESTIONS[["qid"]])
    iso_p = {r["qid"]: r["p"] for r in iso}
    joint, joint_errors = _collect(ask_joint, llm, pd.DataFrame({"fid": [f["fid"] for f in FAMILIES]}))
    joint_p = {}
    for r in joint:
        for q, p in zip(FAMILY_BY_ID[r["fid"]]["questions"], r["ps"]):
            joint_p[q["qid"]] = p
    isolated_df = score_families(iso_p).assign(mode="isolated")
    joint_df = score_families(joint_p).assign(mode="joint")
    coverage = float(isolated_df.parsed.mean())
    if coverage < MIN_COVERAGE:
        unparsed = [r["raw"][-200:] for r in iso if r["p"] is None][:2]
        SKIPPED[name] = f"{coverage:.0%} answered; {len(iso_errors)} API errors; sample: {iso_errors[:1]} {unparsed}"
        raise RuntimeError(
            f"{name}: only {coverage:.0%} of families answered ({len(iso_errors)} API errors, "
            f"{sum(r['p'] is None for r in iso)} unparseable replies). Not scoring. "
            f"Sample error: {iso_errors[:1]} Sample reply: {unparsed}"
        )
    raw = {r["qid"]: r["raw"] for r in iso}
    SKIPPED.pop(name, None)
    RESULTS[name] = dict(
        model=name,
        families=pd.concat([isolated_df, joint_df], ignore_index=True),
        raw_isolated=raw,
        api_errors=len(iso_errors) + len(joint_errors),
        # Score over the families the model actually answered. Unparseable replies are reported separately.
        score=100 * float(isolated_df[isolated_df.parsed].arbitrage_free.mean()),
    )
    return RESULTS[name]


@kbench.task(
    name="dutch_book_bench",
    description=(
        "Can you Dutch-book an LLM forecaster? 37 families of related probability questions (28 about 2027-2050, "
        "9 dice/card controls), each statement asked in a fresh chat. Score = % of families on which a bookie "
        "trading <=$1 per contract cannot lock in more than 5 cents of risk-free profit."
    ),
)
def dutch_book_bench(llm) -> float:
    # The leaderboard run must be a real one: in a batch (saved-version / "Evaluate More Models") run, ignore any
    # cached result for this model so the run file carries the model's actual conversations.
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE", "").lower() == "batch":
        RESULTS.pop(getattr(llm, "name", str(llm)), None)
    res = run_suite(llm)
    fam = res["families"]
    iso = fam[fam["mode"] == "isolated"]
    print(f"{res['model']}: arbitrage-free rate {res['score']:.1f}% "
          f"| mean guaranteed arbitrage {100 * iso.arbitrage.mean():.1f}¢/family "
          f"| parse failures {int((~iso.parsed).sum())} | API errors {res['api_errors']}")
    return res["score"]


# ==== RUN ====
# %% [markdown]
# ## 5. Run on the default model (the leaderboard task)

# %%
main_run = dutch_book_bench.run(kbench.llm)
main_run

# %% [markdown]
# ## 6. Cross-model analysis (for the write-up)
# The leaderboard gets its other models from **"Evaluate More Models"** on the task page. To compare models side by
# side in this notebook, list them below. Each model costs about 160 calls.
#
# This section runs only in an interactive session. Saved-version and "Evaluate More Models" runs execute in batch
# mode and skip it, so they don't re-run every model each time.

# %%
INTERACTIVE = os.environ.get("KAGGLE_KERNEL_RUN_TYPE", "").lower() != "batch"
print("Available models:", sorted(kbench.llms))

# Kaggle's model proxy has a daily quota (about $10) and reserves each call's worst-case cost up front, so the order
# matters: cheap models from as many providers as possible first, the most expensive last. Models that are not on
# the roster are skipped; models already in RESULTS (this session or the cache) are not re-run.
PRIORITY = [
    # cheap, non-thinking, many providers
    "openai/gpt-5.4-nano-2026-03-17", "openai/gpt-5.4-mini-2026-03-17", "google/gemma-4-26b-a4b", "google/gemma-4-31b",
    "qwen/qwen3-235b-a22b-instruct-2507", "openai/gpt-oss-20b", "xai/grok-4.20-0309-non-reasoning", "zai/glm-5",
    "google/gemini-3.5-flash-lite", "google/gemini-3.1-flash-lite-preview", "qwen/qwen3-next-80b-a3b-instruct",
    "openai/gpt-oss-120b", "qwen/qwen3-coder-480b-a35b-instruct", "anthropic/claude-haiku-5-5",
    # mid-price
    "google/gemini-3.5-flash", "google/gemini-3.6-flash", "google/gemini-3.8-flash", "google/gemini-3-flash-preview",
    "google/gemini-2.5-flash", "anthropic/claude-haiku-4-5@20251001", "openai/gpt-5.5-2026-04-23",
    "openai/gpt-5.6-luna", "openai/gpt-5.6-sol", "openai/gpt-5.6-terra", "xai/grok-4.6", "xai/grok-4.5-0708",
    # thinking-heavy or expensive
    "qwen/qwen3-next-80b-a3b-thinking", "deepseek-ai/deepseek-r1-0528", "xai/grok-4.20-0309-reasoning",
    "anthropic/claude-sonnet-5-5@default", "anthropic/claude-sonnet-5@default", "anthropic/claude-sonnet-4-6@default",
    "openai/gpt-6-luna", "openai/gpt-6-sol", "openai/gpt-6-astra", "openai/gpt-6.1-sol", "openai/gpt-5.4-2026-03-05",
    "google/gemini-2.5-pro", "google/gemini-3.1-pro-preview", "anthropic/claude-opus-4-5@20251101",
    "anthropic/claude-opus-4-6@default", "anthropic/claude-opus-4-7@default", "anthropic/claude-opus-4-8@default",
    "anthropic/claude-opus-5@default", "anthropic/claude-opus-5-5@default",
]
ordered = [m for m in PRIORITY if m in kbench.llms] + sorted(set(kbench.llms) - set(PRIORITY))
ANALYSIS_MODELS = ordered if INTERACTIVE else []

for model_name in ANALYSIS_MODELS:
    if model_name in RESULTS:
        print(f"{model_name:45s} {RESULTS[model_name]['score']:5.1f}%  (cached)")
        continue
    try:
        r = run_suite(kbench.llms[model_name])
        print(f"{model_name:45s} {r['score']:5.1f}%")
    except Exception as e:  # keep going if one model is unavailable
        print(f"{model_name:45s} FAILED: {e!r}"[:400])
    save_cache()

if SKIPPED:
    print(f"\n{len(SKIPPED)} model(s) could not be evaluated from this account:")
    for k, v in SKIPPED.items():
        print(f"  {k:45s} {v[:160]}")

# %%
def summarize(results: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_fam = pd.concat([r["families"].assign(model=m) for m, r in results.items()], ignore_index=True)
    iso = all_fam[all_fam["mode"] == "isolated"]
    jnt = all_fam[all_fam["mode"] == "joint"]

    def agg(df):
        # Rates are over the families that were answered; parse failures are reported in their own column.
        return df.groupby("model").agg(
            arb_free=("arbitrage_free", lambda s: s[df.loc[s.index, "parsed"]].mean()),
            mean_arb_cents=("arbitrage", lambda s: 100 * s.mean()),
            parse_fail=("parsed", lambda s: int((~s).sum())),
        )

    a, b = agg(iso), agg(jnt)
    summary = pd.DataFrame({
        "score (arbitrage-free %, isolated)": 100 * a.arb_free,
        "mean arbitrage ¢/family (isolated)": a.mean_arb_cents,
        "uncertain-only ¢/family": iso[iso.domain == "uncertain"].groupby("model").arbitrage.mean() * 100,
        "control-only ¢/family": iso[iso.domain == "control"].groupby("model").arbitrage.mean() * 100,
        "control Brier": iso[iso.domain == "control"].groupby("model").brier.mean(),
        "arbitrage-free % (joint)": 100 * b.arb_free,
        "mean arbitrage ¢/family (joint)": b.mean_arb_cents,
        "parse failures (iso/joint)": a.parse_fail.astype(str) + "/" + b.parse_fail.astype(str),
    }).sort_values("score (arbitrage-free %, isolated)", ascending=False)
    by_type = (iso.groupby(["model", "ftype"]).arbitrage.mean() * 100).unstack().reindex(summary.index)
    return summary.round(3), by_type.round(1)


def worst_examples(results: dict, k: int = 8) -> pd.DataFrame:
    rows = []
    for m, r in results.items():
        fam = r["families"]
        for _, row in fam[(fam["mode"] == "isolated") & fam.parsed].iterrows():
            f = FAMILY_BY_ID[row.fid]
            probs = json.loads(row.probs)
            rows.append(dict(
                model=m, fid=row.fid, ftype=row.ftype, arbitrage_cents=round(100 * row.arbitrage, 1),
                answers=" | ".join(f"{p:.2f} ← {q['text']}" for p, q in zip(probs, f["questions"])),
            ))
    df = pd.DataFrame(rows)
    return df.sort_values("arbitrage_cents", ascending=False).head(k) if len(df) else df


if RESULTS:
    summary, by_type = summarize(RESULTS)
    worst = worst_examples(RESULTS)
    pd.set_option("display.max_colwidth", 400)
    display(summary)
    display(by_type)
    display(worst)

# %%
try:
    import matplotlib.pyplot as plt
except ImportError:  # charts are optional
    plt = None

if RESULTS and plt is not None:
    fig, axes = plt.subplots(1, 2, figsize=(15, max(4, 0.45 * len(summary) + 1.5)))
    s = summary.iloc[::-1]
    axes[0].barh(s.index, s["score (arbitrage-free %, isolated)"], color="#4C72B0", label="isolated (one question per chat)")
    axes[0].scatter(s["arbitrage-free % (joint)"], s.index, color="#DD8452", zorder=3, label="joint (whole family in one prompt)")
    axes[0].set_xlim(0, 100)
    axes[0].set_xlabel("% of question families that cannot be Dutch-booked for more than 5¢")
    axes[0].set_title("Coherence: isolated vs joint")
    axes[0].legend(loc="lower right")

    im = axes[1].imshow(by_type.iloc[::-1].values, aspect="auto", cmap="Reds")
    axes[1].set_xticks(range(len(by_type.columns)), by_type.columns, rotation=30)
    axes[1].set_yticks(range(len(by_type)), by_type.index[::-1])
    for (i, j), v in np.ndenumerate(by_type.iloc[::-1].values):
        if not np.isnan(v):
            axes[1].text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8)
    axes[1].set_title("Mean guaranteed arbitrage (¢ per family), isolated")
    fig.colorbar(im, ax=axes[1], shrink=0.8)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/dutch_book_bench.png", dpi=160)
    plt.show()

# %%
# Write a Markdown block (tables plus the most-arbitrageable examples) that can be pasted into the DEV post.
if RESULTS:
    def md_table(df):
        try:
            return df.to_markdown()
        except ImportError:  # tabulate is not installed
            return "```\n" + df.to_string() + "\n```"

    lines = [
        f"_Run date: {TODAY}. Isolated = each statement in a fresh chat; joint = whole family in one prompt. "
        f"Arbitrage-free = a bookie trading at most $1 per contract can lock in at most {100 * ARB_TOL:.0f}¢._",
        "",
        "### Leaderboard",
        md_table(summary),
        "",
        "### Guaranteed arbitrage by family type (¢ per family, isolated)",
        md_table(by_type),
        "",
        "### The most Dutch-bookable answers",
    ]
    for _, w in worst.iterrows():
        lines.append(f"- **{w.model}**, `{w.fid}` ({w.ftype}): **{w.arbitrage_cents}¢** risk-free")
        for part in w.answers.split(" | "):
            lines.append(f"  - {part}")
    with open(f"{OUT_DIR}/results.md", "w") as fh:
        fh.write("\n".join(lines))
    all_rows = pd.concat([r["families"].assign(model=m) for m, r in RESULTS.items()], ignore_index=True)
    all_rows.to_csv(f"{OUT_DIR}/family_results.csv", index=False)
    print("\n".join(lines))

# %% [markdown]
# ## 7. Pick the leaderboard task
# This must be the last cell. It keeps only `dutch_book_bench`'s task file and its latest run.

# %%
# CHOOSE: dutch_book_bench
