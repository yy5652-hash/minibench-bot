"""Research and forecasting prompts.

The analysis rules (status-quo check, soft clocks, null search results, remaining
exposure, market reading) are adapted from No-Stream/metaculus-bot (MIT licence,
Copyright the metaculus-bot authors, https://github.com/No-Stream/metaculus-bot).
"""
from __future__ import annotations

SHARED_RULES = """
Rules for weighing evidence:
- Read the resolution criteria literally: the exact source, date, threshold and units decide the question, not the headline topic.
- Separate facts from opinion. Primary records and the named resolution source outrank wire services, which outrank aggregators, which outrank anonymous or social posts. Discount claims that serve the speaker's interest; a statement against the speaker's interest is strong evidence.
- A figure that is off by about an order of magnitude from other sources is probably an error. Flag it, do not anchor on it.
- A null search result only means evidence was not found. Silence from a comprehensive official database is weak-to-moderate evidence; silence from general web search on a poorly covered topic is almost none.
- A target date the responsible actor is not bound to (no statute, contract or schedule it has a record of meeting) shows that a target exists, not that it will hold. Price the chance it lands inside the window from that actor's record of slips.
- Rates apply to the exposure that remains: estimate the rate over the longest comparable history, then apply it only from today to the deadline. For "how many events in a period" questions, the pooled historical rate is the outside view; currently known candidates update it but do not replace it.
- Prediction markets: a deep liquid market on the same question is close to the best available estimate. A thin market is only a hint. A market at another date or threshold should be extrapolated, not discounted vaguely. Check that a listed market really measures this question before using it.
- You may use your own knowledge beyond the research; say when you do.
""".strip()

SCORING = (
    "Your forecast is scored with a log score against other expert forecasters at the moment the question "
    "closes, so overconfidence is punished heavily while honest calibrated numbers are rewarded. Go to the "
    "extremes (below 5% or above 95%) only when the outcome is essentially settled by the evidence."
)


def _question_block(question) -> str:
    return (
        f"Question:\n{question.question_text}\n\n"
        f"Background:\n{question.background_info}\n\n"
        f"Resolution criteria (these have not yet been satisfied):\n{question.resolution_criteria}\n\n"
        f"Fine print:\n{question.fine_print}"
    )


def research_prompt(question, today: str) -> str:
    return f"""You are the research assistant to a superforecaster. Today is {today} (UTC). Search the web now; do not rely on memory.

{_question_block(question)}

The question closes for forecasting at {question.close_time} and resolves around {question.scheduled_resolution_time}.

Report, with a publication date and a URL for each fact:
1. Resolution source: what the named source says now. The current observed value and how it has moved recently, with numbers.
2. What has already happened that bears on the criteria, separated from plans and announcements.
3. Historical base rate: past comparable cases, with counts, and how long such things usually take.
4. Scheduled events or releases between now and the resolution date.
5. Forecasts by experts, and prices on prediction markets (Polymarket, Kalshi, Manifold) on this or a closely related question.
6. The main ways the outcome could differ from the current trend.

Tag each fact with its source tier: [A] primary or official, [B] wire service or paper of record, [C] aggregator or single outlet, [D] anonymous or social. If you searched for something and did not find it, say so plainly. Never invent a citation or a value. Do not give a forecast. Keep it under 700 words."""


def gap_fill_prompt(question, research: str, today: str) -> str:
    return f"""You are checking a research brief for a forecasting question. Today is {today} (UTC).

{_question_block(question)}

Research brief so far:
{research}

Name the two or three missing or conflicting facts that would most change a forecast of this question, for example the latest value from the resolution source, a contradiction between sources, or a missing base rate. Search the web for exactly those facts now and report what you find, with a publication date and URL for each. If the search finds nothing, say so. Do not give a forecast. Keep it under 300 words."""


def binary_prompt(question, research: str, today: str, conditional_note: str = "") -> str:
    return f"""You are a senior forecaster. {SCORING}

{_question_block(question)}

Research from your assistants:
{research}

Today is {today} (UTC). The question closes at {question.close_time} and resolves around {question.scheduled_resolution_time}.

{SHARED_RULES}
{conditional_note}

Work through these steps in order, briefly:
0. Status quo: this question is open and unresolved today. If nothing changed before resolution, how would it resolve? Check whether the evidence already settles it. If the criteria contain several conditions, list them.
1. Outside view: name the best reference class and give a base rate with numbers, before weighing the news. For a recurring event, compute the chance of it occurring in the time that remains.
2. Inside view: list the specific evidence for and against, with how far each item moves you from the base rate. Multiply through any separate conditions.
3. Red team: give the strongest case that your number is wrong in each direction, and adjust if it holds up.

The last line of your answer must be exactly: Probability: ZZ%"""


def multiple_choice_prompt(question, research: str, today: str, conditional_note: str = "") -> str:
    return f"""You are a senior forecaster. {SCORING}

{_question_block(question)}

The options are: {question.options}

Research from your assistants:
{research}

Today is {today} (UTC). The question closes at {question.close_time} and resolves around {question.scheduled_resolution_time}.

{SHARED_RULES}
{conditional_note}

Work through these steps in order, briefly:
0. Status quo: if nothing changed before resolution, which option would resolve?
1. Outside view: base rates for each option from a named reference class, with numbers.
2. Inside view: evidence for and against each option, with how far it moves you.
3. Red team: what surprise would make the likely option wrong? Leave real probability on options the evidence has not ruled out, and never give an option 0%.

End with your final probabilities for all options, in this order {question.options}, one per line:
Option_A: Probability_A
Option_B: Probability_B
...
Option_N: Probability_N"""


def numeric_prompt(question, research: str, today: str, lower_message: str, upper_message: str,
                   conditional_note: str = "") -> str:
    units = question.unit_of_measure or "Not stated (please infer this)"
    return f"""You are a senior forecaster. {SCORING}

{_question_block(question)}

Units for the answer: {units}

Research from your assistants:
{research}

Today is {today} (UTC). The question closes at {question.close_time} and resolves around {question.scheduled_resolution_time}.

{SHARED_RULES}
{conditional_note}

{lower_message}
{upper_message}

Work through these steps in order, briefly:
0. Check the resolution metric: exactly which series, date and units are named? State the latest observed value of that same series, and check it is on the same scale as the units above.
1. Outside view: the outcome if nothing changed and if the trend continued. For a market price or time series, compute a spread from its recent volatility over the time remaining. For a count, use the historical rate over the remaining period.
2. Inside view: scheduled events, expert and market expectations, and what they shift.
3. Tails: name a surprise that gives a low outcome and one that gives a high outcome. Past forecasters have been too narrow far more often than too wide, so make the 5th to 95th percentile range cover those surprises.

Give values in the requested units, never in scientific notation, strictly increasing from lowest to highest percentile.

End with your final answer in exactly this form:
Percentile 5: XX
Percentile 10: XX
Percentile 20: XX
Percentile 40: XX
Percentile 60: XX
Percentile 80: XX
Percentile 90: XX
Percentile 95: XX"""


def date_prompt(question, research: str, today: str, lower_message: str, upper_message: str,
                conditional_note: str = "") -> str:
    return f"""You are a senior forecaster. {SCORING}

{_question_block(question)}

Research from your assistants:
{research}

Today is {today} (UTC). The question closes at {question.close_time} and resolves around {question.scheduled_resolution_time}.

{SHARED_RULES}
{conditional_note}

{lower_message}
{upper_message}

Work through these steps in order, briefly:
0. Which binding clock, if any, fixes this date? Compute the date from it and name the clock.
1. Outside view: how long comparable cases took, with numbers, applied to the time that remains.
2. Inside view: scheduled events, the actor's record of slips, and expert expectations.
3. Tails: name a surprise that makes it early and one that makes it late, and cover both.

Give dates in chronological order, in the form YYYY-MM-DD.

End with your final answer in exactly this form:
Percentile 5: YYYY-MM-DD
Percentile 10: YYYY-MM-DD
Percentile 20: YYYY-MM-DD
Percentile 40: YYYY-MM-DD
Percentile 60: YYYY-MM-DD
Percentile 80: YYYY-MM-DD
Percentile 90: YYYY-MM-DD
Percentile 95: YYYY-MM-DD"""
