# %% [markdown]
# # Fine Print: do LLM forecasters read the resolution criteria?
#
# Forecasting questions (Metaculus, Good Judgment, prediction markets) are decided by
# their resolution criteria, not by their headline. While running a forecasting bot in
# Metaculus' MiniBench I kept seeing the same failure: the model nails the news but
# answers the *headline*, not the fine print.
#
# This benchmark isolates that skill with **minimal pairs**. Each pair shares the same
# headline and the same confirmed facts; only one clause of the resolution criteria
# differs, and that clause flips the correct answer. All entities are fictional, so
# memorised world knowledge cannot help, and every question is already decided by the
# facts given, so the right probability is close to 0 or 1.
#
# * `control` variant: the fine print agrees with the plainest reading of the headline.
# * `trap` variant: the fine print quietly overrides it.
#
# **Main score: pair accuracy** - the share of pairs where the model gets *both*
# variants right. A model that ignores the fine print answers both variants the same
# way and scores 0%; a coin flip scores 25%.

# %%
import re

import pandas as pd

import kaggle_benchmarks as kbench

# %%
# Each pair: shared title/background/today, plus two resolution criteria.
# `control_yes` is the correct answer for the control variant; the trap variant is
# always the opposite.
PAIRS = [
    # ---------------------------------------------------------------- revision
    dict(
        family="data_vintage",
        today="2026-10-01",
        title="Will Northvale's Q2 2026 GDP growth exceed 2.0% (annualized)?",
        background=(
            "July 30, 2026: the Northvale Statistics Office (NSO) published its advance "
            "estimate - real GDP grew at a 2.3% annualized rate in Q2. Headlines called it "
            "'a strong quarter that beat expectations'. August 27: the NSO's second estimate "
            "revised Q2 growth to 1.9%. September 24: the third estimate put it at 1.8%."
        ),
        control=(
            "Resolves YES if the NSO's advance (first) estimate of Q2 2026 annualized real "
            "GDP growth is greater than 2.0%. Later revisions are ignored."
        ),
        trap=(
            "Resolves YES if the most recent NSO estimate of Q2 2026 annualized real GDP "
            "growth available on October 1, 2026 is greater than 2.0%."
        ),
        control_yes=True,
    ),
    dict(
        family="data_vintage",
        today="2026-10-06",
        title="Will Calderra's August 2026 unemployment rate be 4.0% or lower?",
        background=(
            "September 4, 2026: the Calderra Labour Bureau reported that unemployment rose "
            "to 4.2% in August ('unemployment ticks up to 4.2%'). October 2: with the "
            "September report, the Bureau revised the August rate down to 3.9%. The Bureau's "
            "online database now shows 3.9% for August 2026."
        ),
        control=(
            "Resolves YES if the first published Labour Bureau figure for the August 2026 "
            "unemployment rate is 4.0% or lower."
        ),
        trap=(
            "Resolves YES if the August 2026 unemployment rate shown in the Labour Bureau's "
            "database on October 5, 2026 is 4.0% or lower."
        ),
        control_yes=False,
    ),
    dict(
        family="data_vintage",
        today="2026-08-01",
        title="Will Pellandia's June 2026 CPI inflation be below 3.0%?",
        background=(
            "June 30, 2026: Pellandia's statistics agency published a flash estimate of "
            "2.8% year-on-year CPI inflation for June ('inflation falls below 3% for the "
            "first time since 2024'). July 17: the final estimate for June was published "
            "at 3.1%."
        ),
        control=(
            "Resolves YES if the flash estimate of June 2026 year-on-year CPI inflation is "
            "below 3.0%."
        ),
        trap=(
            "Resolves YES if the final (not flash) estimate of June 2026 year-on-year CPI "
            "inflation is below 3.0%."
        ),
        control_yes=True,
    ),
    dict(
        family="data_vintage",
        today="2026-10-01",
        title="Will Kestrel Motors report Q1 2026 revenue above $10.0 billion?",
        background=(
            "April 28, 2026: Kestrel Motors' Q1 earnings release reported revenue of $10.4 "
            "billion. August 12: after an internal accounting review, Kestrel restated Q1 "
            "2026 revenue to $9.7 billion in amended audited financial statements."
        ),
        control=(
            "Resolves YES if Q1 2026 revenue as stated in Kestrel's original Q1 earnings "
            "release is above $10.0 billion."
        ),
        trap=(
            "Resolves YES if Q1 2026 revenue in Kestrel's audited financial statements as "
            "of September 30, 2026, including any restatements, is above $10.0 billion."
        ),
        control_yes=True,
    ),
    dict(
        family="data_vintage",
        today="2026-10-01",
        title="Will turnout in the Marisol municipal referendum exceed 50%?",
        background=(
            "September 6, 2026 (election night): preliminary results put turnout at 48.7%; "
            "local media reported 'referendum misses 50% turnout mark'. September 20: after "
            "postal ballots were counted, the Marisol Electoral Board certified turnout of "
            "51.2%."
        ),
        control=(
            "Resolves YES if turnout in the preliminary results announced on election night "
            "exceeds 50%."
        ),
        trap=(
            "Resolves YES if turnout in the certified results published by the Marisol "
            "Electoral Board exceeds 50%."
        ),
        control_yes=False,
    ),
    # --------------------------------------------------------------- threshold
    dict(
        family="threshold_rounding",
        today="2026-07-10",
        title="Will Kestrel Motors deliver 500,000 vehicles in the first half of 2026?",
        background=(
            "July 2, 2026: Kestrel Motors reported 499,620 vehicle deliveries for January-"
            "June 2026. Its press release headline read 'Kestrel delivers nearly half a "
            "million vehicles in H1'."
        ),
        control=(
            "Resolves YES if Kestrel's reported H1 2026 deliveries are at least 500,000."
        ),
        trap=(
            "Resolves YES if Kestrel's reported H1 2026 deliveries, rounded to the nearest "
            "10,000, are at least 500,000."
        ),
        control_yes=False,
    ),
    dict(
        family="threshold_rounding",
        today="2026-09-20",
        title="Will Northvale's August 2026 annual inflation rate be above 3%?",
        background=(
            "September 15, 2026: the NSO published August 2026 CPI inflation of 3.0% "
            "year-on-year (headline figure, one decimal place). The NSO's published index "
            "levels imply an unrounded year-on-year change of 3.04%."
        ),
        control=(
            "Resolves YES if the headline figure published by the NSO, as reported to one "
            "decimal place, is greater than 3.0%."
        ),
        trap=(
            "Resolves YES if the unrounded year-on-year change computed from the NSO's "
            "published CPI index levels is greater than 3.00%."
        ),
        control_yes=False,
    ),
    dict(
        family="threshold_rounding",
        today="2026-10-01",
        title="Will the Calderra central bank cut its policy rate to 4% before October 2026?",
        background=(
            "September 17, 2026: the Calderra central bank cut its policy rate from 4.25% to "
            "4.00%. There were no other rate changes in 2026."
        ),
        control=(
            "Resolves YES if the policy rate is at or below 4.00% at any time between "
            "January 1 and September 30, 2026."
        ),
        trap=(
            "Resolves YES if the policy rate is strictly below 4.00% at any time between "
            "January 1 and September 30, 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="threshold_rounding",
        today="2026-08-05",
        title="Will the Mount Ilvar observatory record 40°C in July 2026?",
        background=(
            "The observatory's sensor recorded a July maximum of 39.96°C on July 22, 2026. "
            "The official July monthly bulletin, which reports to one decimal place, lists "
            "the monthly maximum as 40.0°C."
        ),
        control=(
            "Resolves YES if the observatory's official monthly bulletin reports a July "
            "2026 maximum of 40.0°C or higher."
        ),
        trap=(
            "Resolves YES if the observatory's raw sensor record (two decimal places) shows "
            "a July 2026 reading of 40.00°C or higher."
        ),
        control_yes=True,
    ),
    dict(
        family="threshold_rounding",
        today="2026-10-10",
        title="Will Northvale's unemployment rate rise by more than 10% in 2026?",
        background=(
            "Northvale's unemployment rate was 4.0% in December 2025 and 4.5% in September "
            "2026."
        ),
        control=(
            "Resolves YES if the September 2026 unemployment rate is more than 10% higher, "
            "in relative terms, than the December 2025 rate."
        ),
        trap=(
            "Resolves YES if the unemployment rate rises by more than 10 percentage points "
            "between December 2025 and September 2026."
        ),
        control_yes=True,
    ),
    # ---------------------------------------------------------------- deadline
    dict(
        family="deadline_timezone",
        today="2026-10-02",
        title="Will Kestrel Motors name a new CEO before October 1, 2026?",
        background=(
            "Kestrel Motors announced its new CEO in a press release at 9:15 PM Pacific "
            "Daylight Time on September 30, 2026."
        ),
        control=(
            "Resolves YES if Kestrel announces a new CEO before October 1, 2026, 00:00 "
            "Pacific Time."
        ),
        trap=(
            "Resolves YES if Kestrel announces a new CEO before October 1, 2026, 00:00 UTC."
        ),
        control_yes=True,
    ),
    dict(
        family="deadline_timezone",
        today="2026-09-20",
        title="Will the Vandor lander touch down on the Moon by September 15, 2026?",
        background=(
            "Mission control confirmed touchdown of the Vandor lander at 01:30 UTC on "
            "September 16, 2026 - 9:30 PM Eastern Daylight Time on September 15."
        ),
        control=(
            "Resolves YES if the landing occurs on or before September 15, 2026, US Eastern "
            "Time."
        ),
        trap=(
            "Resolves YES if the landing occurs on or before September 15, 2026, 23:59 UTC."
        ),
        control_yes=True,
    ),
    dict(
        family="deadline_timezone",
        today="2026-07-05",
        title="Will Pellandia's parliament pass the 2027 budget by June 30, 2026?",
        background=(
            "After an overnight session that began on June 30, Pellandia's parliament "
            "passed the 2027 budget at 00:40 local time (UTC+2) on July 1, 2026. Local "
            "media: 'Budget finally passes in the early hours of July 1'."
        ),
        control=(
            "Resolves YES if the budget passes its final vote by 23:59 on June 30, 2026, "
            "Pellandia local time."
        ),
        trap=(
            "Resolves YES if the budget passes its final vote by 23:59 UTC on June 30, 2026."
        ),
        control_yes=False,
    ),
    dict(
        family="deadline_timezone",
        today="2026-10-02",
        title="Will Kestrel Motors announce a vehicle recall in Q3 2026?",
        background=(
            "Kestrel announced a recall of 40,000 SUVs on the evening of June 30, 2026, US "
            "Eastern Time; the notice was timestamped 03:00 UTC, July 1, 2026. Kestrel "
            "announced no other recalls between June 30 and October 2, 2026."
        ),
        control=(
            "Resolves YES if Kestrel announces a recall between July 1 and September 30, "
            "2026, inclusive, US Eastern Time."
        ),
        trap=(
            "Resolves YES if Kestrel announces a recall between July 1 and September 30, "
            "2026, inclusive, UTC."
        ),
        control_yes=False,
    ),
    dict(
        family="deadline_timezone",
        today="2026-10-01",
        title="Will Calderra and Pellandia sign a trade agreement in 2026?",
        background=(
            "Calderra and Pellandia signed a bilateral trade agreement on September 12, 2026."
        ),
        control=(
            "Resolves YES if the two countries sign a trade agreement between January 1 and "
            "December 31, 2026."
        ),
        trap=(
            "Resolves YES only if the two countries sign a trade agreement on or before "
            "August 31, 2026; signings after that date do not count."
        ),
        control_yes=True,
    ),
    # ------------------------------------------------- announced vs effective
    dict(
        family="announced_vs_effective",
        today="2027-01-04",
        title="Will Pellandia raise its minimum wage in 2026?",
        background=(
            "September 20, 2026: Pellandia's president signed a law, passed by parliament "
            "the week before, raising the national minimum wage by 8%. The law takes effect "
            "on January 1, 2027. The minimum wage did not change during 2026."
        ),
        control=(
            "Resolves YES if a law raising the national minimum wage is signed into law "
            "during 2026."
        ),
        trap=(
            "Resolves YES only if a higher national minimum wage is legally in effect at "
            "any time during 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="announced_vs_effective",
        today="2026-10-01",
        title="Will Lorne Abaro become Prime Minister of Calderra before October 1, 2026?",
        background=(
            "Abaro's party won Calderra's general election on September 13, 2026. On "
            "September 15 the head of state formally designated Abaro as Prime Minister-"
            "designate. Abaro is scheduled to be sworn in on October 3, 2026."
        ),
        control=(
            "Resolves YES if Abaro is formally sworn in as Prime Minister before October 1, "
            "2026."
        ),
        trap=(
            "Resolves YES if, before October 1, 2026, the head of state officially "
            "designates or nominates Abaro to be Prime Minister, regardless of when the "
            "swearing-in takes place."
        ),
        control_yes=False,
    ),
    dict(
        family="announced_vs_effective",
        today="2027-01-05",
        title="Will Kestrel Motors complete its acquisition of Brightwell Batteries in 2026?",
        background=(
            "March 2, 2026: Kestrel and Brightwell signed a definitive merger agreement, "
            "approved by both boards. June: Brightwell shareholders approved the deal. "
            "September 28: regulators approved it. As of January 5, 2027 the deal has not "
            "closed; closing is scheduled for February 2027."
        ),
        control=(
            "Resolves YES if the acquisition legally closes on or before December 31, 2026."
        ),
        trap=(
            "Resolves YES if, during 2026, a definitive merger agreement for the acquisition "
            "is signed and approved by both companies' boards."
        ),
        control_yes=False,
    ),
    dict(
        family="announced_vs_effective",
        today="2027-01-03",
        title="Will Northvale ban single-use plastic bags in 2026?",
        background=(
            "May 14, 2026: Northvale's national ban on single-use plastic bags was signed "
            "into law. The ban becomes enforceable on July 1, 2027."
        ),
        control=(
            "Resolves YES if a national ban on single-use plastic bags is signed into law "
            "during 2026."
        ),
        trap=(
            "Resolves YES if a national ban on single-use plastic bags is in force "
            "(enforceable) at any time during 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="announced_vs_effective",
        today="2027-01-02",
        title="Will the Pellandia football league adopt video review in 2026?",
        background=(
            "August 2026: the Pellandia league board voted to adopt video assistant review, "
            "starting with the 2027-28 season. No league match in 2026 used video review."
        ),
        control=(
            "Resolves YES if the league officially approves the adoption of video review "
            "during 2026."
        ),
        trap=(
            "Resolves YES if video review is used in at least one official league match "
            "during 2026."
        ),
        control_yes=True,
    ),
    # ----------------------------------------------- any time vs on the date
    dict(
        family="status_vs_ever",
        today="2026-10-01",
        title="Will Aurelia Coin reach $100,000 in 2026?",
        background=(
            "August 14, 2026: Aurelia Coin traded as high as $100,420 on the Bravo exchange "
            "before closing the day at $98,900. Its highest daily close on Bravo between "
            "January 1 and September 30, 2026 was $99,610."
        ),
        control=(
            "Resolves YES if Aurelia Coin trades at or above $100,000 at any time, including "
            "intraday, on the Bravo exchange between January 1 and September 30, 2026."
        ),
        trap=(
            "Resolves YES if Aurelia Coin's daily closing price on the Bravo exchange is at "
            "or above $100,000 on any day between January 1 and September 30, 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="status_vs_ever",
        today="2026-10-01",
        title="Will Dana Orsell leave her role as CEO of Brightwell Batteries in 2026?",
        background=(
            "August 3, 2026: Brightwell's board removed Dana Orsell as CEO ('Brightwell "
            "ousts CEO Orsell'). August 21: after investor backlash, the board reinstated "
            "her. She has served as CEO continuously since August 21."
        ),
        control=(
            "Resolves YES if Orsell ceases to hold the CEO position at any point between "
            "January 1 and September 30, 2026, even temporarily."
        ),
        trap=(
            "Resolves YES if Orsell is not Brightwell's CEO on September 30, 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="status_vs_ever",
        today="2027-01-02",
        title="Will the Vela Tower be Calderra's tallest building in 2026?",
        background=(
            "March 2026: the Vela Tower topped out and became Calderra's tallest building. "
            "November 2026: the Orin Spire topped out taller than the Vela Tower and is now "
            "Calderra's tallest building."
        ),
        control=(
            "Resolves YES if the Vela Tower is Calderra's tallest building on December 31, "
            "2026."
        ),
        trap=(
            "Resolves YES if the Vela Tower is Calderra's tallest building at any point "
            "during 2026."
        ),
        control_yes=False,
    ),
    dict(
        family="status_vs_ever",
        today="2026-10-01",
        title="Will Kestrel Motors' market capitalization exceed $200 billion in 2026?",
        background=(
            "July 9, 2026: Kestrel closed with a market capitalization of $203 billion, its "
            "record high. September 30, 2026 (last trading day of September): it closed at "
            "$171 billion."
        ),
        control=(
            "Resolves YES if Kestrel's market capitalization at market close exceeds $200 "
            "billion on any trading day between January 1 and September 30, 2026."
        ),
        trap=(
            "Resolves YES if Kestrel's market capitalization at market close on the last "
            "trading day of September 2026 exceeds $200 billion."
        ),
        control_yes=True,
    ),
    dict(
        family="status_vs_ever",
        today="2026-10-01",
        title="Will the Tern border crossing between Northvale and Pellandia close in 2026?",
        background=(
            "The Tern crossing was closed to all traffic from May 15 to May 18, 2026 (about "
            "72 hours) because of protests. It reopened on May 18 and has been open since."
        ),
        control=(
            "Resolves YES if the Tern crossing is closed to traffic on September 30, 2026."
        ),
        trap=(
            "Resolves YES if the Tern crossing is closed to all traffic for at least 48 "
            "consecutive hours at any time between January 1 and September 30, 2026."
        ),
        control_yes=False,
    ),
    # ------------------------------------------------------------------ scope
    dict(
        family="definition_scope",
        today="2026-06-01",
        title="Will a Halvar Union country win the 2026 Continental Song Contest?",
        background=(
            "The 2026 Continental Song Contest was won by Norra's entry. Norra is a member "
            "of the Halvar Economic Area and the Halvar Customs Pact, but is not a member "
            "state of the Halvar Union itself."
        ),
        control=(
            "Resolves YES if the winning entry represents a member of the Halvar Economic "
            "Area."
        ),
        trap=(
            "Resolves YES if the winning entry represents a full member state of the Halvar "
            "Union."
        ),
        control_yes=True,
    ),
    dict(
        family="definition_scope",
        today="2026-10-01",
        title="Will a commercial flight land at Kessa International Airport before October 2026?",
        background=(
            "Kessa International Airport opened for cargo operations on September 10, 2026, "
            "when a commercial cargo flight landed ('first flight lands at Kessa'). The "
            "first scheduled passenger flights are planned for October 15, 2026."
        ),
        control=(
            "Resolves YES if any commercial flight, passenger or cargo, lands at Kessa "
            "International Airport before October 1, 2026."
        ),
        trap=(
            "Resolves YES only if a scheduled commercial flight carrying paying passengers "
            "lands at Kessa International Airport before October 1, 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="definition_scope",
        today="2027-01-04",
        title="Will Brightwell Batteries open a factory in Calderra in 2026?",
        background=(
            "June 2026: a joint venture owned 40% by Brightwell Batteries and 60% by Kestrel "
            "Motors opened a battery factory in Calderra ('Brightwell's Calderra plant "
            "opens'). Brightwell and its majority-owned subsidiaries opened no factories in "
            "Calderra in 2026."
        ),
        control=(
            "Resolves YES if Brightwell, any subsidiary, or any joint venture in which "
            "Brightwell holds an equity stake opens a factory in Calderra during 2026."
        ),
        trap=(
            "Resolves YES only if Brightwell itself or a subsidiary majority-owned by "
            "Brightwell opens a factory in Calderra during 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="definition_scope",
        today="2026-09-01",
        title="Will a Pellandian athlete win gold at the 2026 Coastal Championships?",
        background=(
            "Mira Toller, who was born and raised in Pellandia but has competed for Calderra "
            "since 2023, won gold in the 400m. No athlete competing for Pellandia won a gold "
            "medal at the 2026 Coastal Championships."
        ),
        control=(
            "Resolves YES if an athlete competing for (representing) Pellandia wins a gold "
            "medal."
        ),
        trap=(
            "Resolves YES if any gold medalist was born in Pellandia, regardless of the "
            "country they represent."
        ),
        control_yes=False,
    ),
    dict(
        family="definition_scope",
        today="2026-09-01",
        title="Will Northvale record a heatwave in summer 2026?",
        background=(
            "The capital's official Met Office station recorded five days above 35°C between "
            "June 1 and August 31, 2026, but never more than two in a row. The Met Office's "
            "official station in Eastport, Northvale, recorded four consecutive days above "
            "35°C (July 18-21)."
        ),
        control=(
            "Resolves YES if the Met Office's capital station records at least 3 "
            "consecutive days above 35°C between June 1 and August 31, 2026."
        ),
        trap=(
            "Resolves YES if any official Met Office station in Northvale records at least "
            "3 consecutive days above 35°C between June 1 and August 31, 2026."
        ),
        control_yes=False,
    ),
    # --------------------------------------------------------------- counting
    dict(
        family="counting_rules",
        today="2026-07-05",
        title="Will Vandor Aerospace conduct at least 3 orbital launches in H1 2026?",
        background=(
            "Vandor Aerospace attempted three orbital launches between January and June "
            "2026. The second launch failed to reach orbit; the other two succeeded."
        ),
        control=(
            "Resolves YES if Vandor makes at least 3 orbital launch attempts between "
            "January 1 and June 30, 2026, regardless of outcome."
        ),
        trap=(
            "Resolves YES if Vandor makes at least 3 orbital launches between January 1 and "
            "June 30, 2026. Only launches that successfully reach orbit count."
        ),
        control_yes=True,
    ),
    dict(
        family="counting_rules",
        today="2026-10-02",
        title="Will the film 'Glass Orchard' gross $1 billion worldwide by September 30, 2026?",
        background=(
            "As of September 30, 2026, BoxTally reports a worldwide gross of $1.004 billion "
            "for 'Glass Orchard' ('Glass Orchard crosses $1 billion'), including $12 million "
            "from a September re-release."
        ),
        control=(
            "Resolves YES if the worldwide gross reported by BoxTally reaches $1,000,000,000 "
            "by September 30, 2026."
        ),
        trap=(
            "Resolves YES if the worldwide gross reported by BoxTally, excluding any "
            "re-release grosses, reaches $1,000,000,000 by September 30, 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="counting_rules",
        today="2026-07-02",
        title="Will at least 5 states recognize Ostmark's independence by June 30, 2026?",
        background=(
            "By June 30, 2026, four UN member states had formally recognized Ostmark, and "
            "Varn, a partially recognized state that is not a UN member, had also formally "
            "recognized it."
        ),
        control=(
            "Resolves YES if at least 5 UN member states formally recognize Ostmark by June "
            "30, 2026."
        ),
        trap=(
            "Resolves YES if at least 5 states formally recognize Ostmark by June 30, 2026. "
            "Any sovereign or de facto state counts, including partially recognized states."
        ),
        control_yes=False,
    ),
    dict(
        family="counting_rules",
        today="2026-10-01",
        title="Will Kestrel Motors announce layoffs of at least 1,000 employees in 2026?",
        background=(
            "Kestrel announced 600 layoffs in March 2026 and a further 700 layoffs in August "
            "2026. It made no other layoff announcements between January 1 and September "
            "30, 2026."
        ),
        control=(
            "Resolves YES if Kestrel announces a single round of layoffs affecting at least "
            "1,000 employees between January 1 and September 30, 2026."
        ),
        trap=(
            "Resolves YES if layoffs announced by Kestrel between January 1 and September "
            "30, 2026 total at least 1,000 employees, summed across all announcements."
        ),
        control_yes=False,
    ),
    dict(
        family="counting_rules",
        today="2026-05-20",
        title="Will the 2026 Pellandia Cup final have more than 3 goals?",
        background=(
            "The 2026 Pellandia Cup final was 1-1 after 90 minutes and 2-2 after extra time. "
            "Rovers won the penalty shootout 4-3."
        ),
        control=(
            "Resolves YES if more than 3 goals are scored in the final, counting goals in "
            "regulation time and extra time but not in a penalty shootout."
        ),
        trap=(
            "Resolves YES if more than 3 goals are scored in the final. Only goals scored in "
            "regulation time (the first 90 minutes plus stoppage time) count."
        ),
        control_yes=True,
    ),
    # ----------------------------------------------------------------- source
    dict(
        family="resolution_source",
        today="2026-10-01",
        title="Will Sena Moro win Northvale's 2026 presidential election?",
        background=(
            "September 6, 2026: all three major national TV networks projected Sena Moro as "
            "the winner. After a court-ordered recount, the Northvale Electoral Commission "
            "certified her rival, Tavi Ren, as the winner on September 28."
        ),
        control=(
            "Resolves according to the Northvale Electoral Commission's certified result: "
            "YES if it certifies Moro as the winner."
        ),
        trap=(
            "Resolves YES if at least three major national news networks project Moro as the "
            "winner."
        ),
        control_yes=False,
    ),
    dict(
        family="resolution_source",
        today="2026-10-01",
        title="Will Calderra report more than 1,000 cases of Kessa fever in 2026?",
        background=(
            "As of September 30, 2026, Calderra's Ministry of Health reports 1,240 Kessa "
            "fever cases this year (confirmed plus suspected). The Global Health Agency "
            "reports 870 laboratory-confirmed cases in Calderra over the same period."
        ),
        control=(
            "Resolves YES if Calderra's Ministry of Health reports more than 1,000 cases in "
            "2026 as of September 30, 2026."
        ),
        trap=(
            "Resolves YES if the Global Health Agency's count of laboratory-confirmed cases "
            "in Calderra exceeds 1,000 for 2026 as of September 30, 2026."
        ),
        control_yes=True,
    ),
    dict(
        family="resolution_source",
        today="2026-10-01",
        title="Will Northvale's 2026 wheat harvest exceed 30 million tonnes?",
        background=(
            "September 20, 2026: Northvale's Agriculture Ministry estimated the 2026 wheat "
            "harvest at 31.2 million tonnes ('record harvest'). The independent Northvale "
            "Grain Council estimated 29.4 million tonnes."
        ),
        control=(
            "Resolves YES if the Agriculture Ministry's latest estimate as of October 1, 2026 "
            "exceeds 30 million tonnes."
        ),
        trap=(
            "Resolves YES if the Northvale Grain Council's latest estimate as of October 1, "
            "2026 exceeds 30 million tonnes."
        ),
        control_yes=True,
    ),
    dict(
        family="resolution_source",
        today="2026-09-01",
        title="Will the song 'Paper Lanterns' reach #1 in Pellandia in 2026?",
        background=(
            "'Paper Lanterns' spent two weeks at #1 on Spinlist, a streaming-only chart, in "
            "May 2026. On "
            "the Official Pellandia Singles Chart it peaked at #3. The chart run ended in "
            "August 2026."
        ),
        control=(
            "Resolves YES if 'Paper Lanterns' reaches #1 on the Official Pellandia Singles "
            "Chart between January 1 and August 31, 2026."
        ),
        trap=(
            "Resolves YES if 'Paper Lanterns' reaches #1 on either the Official Pellandia "
            "Singles Chart or Spinlist between January 1 and August 31, 2026."
        ),
        control_yes=False,
    ),
    dict(
        family="resolution_source",
        today="2026-10-01",
        title="Will the 2026 Mount Ilvar eruption be rated VEI 4 or higher?",
        background=(
            "The Calderra Volcano Observatory's initial assessment rated the June 2026 Mount "
            "Ilvar eruption VEI 4. The Global Volcanism Registry's entry, as of October 1, "
            "2026, rates it VEI 3."
        ),
        control=(
            "Resolves YES if the Calderra Volcano Observatory's initial assessment rates the "
            "eruption VEI 4 or higher."
        ),
        trap=(
            "Resolves YES if the Global Volcanism Registry's entry for the eruption, as of "
            "October 1, 2026, rates it VEI 4 or higher."
        ),
        control_yes=True,
    ),
]


def build_items(pairs: list[dict]) -> pd.DataFrame:
    rows = []
    for i, p in enumerate(pairs):
        for variant in ("control", "trap"):
            is_yes = p["control_yes"] if variant == "control" else not p["control_yes"]
            rows.append(
                dict(
                    pair_id=i,
                    family=p["family"],
                    variant=variant,
                    today=p["today"],
                    title=p["title"],
                    criteria=p[variant],
                    background=p["background"],
                    answer=int(is_yes),
                )
            )
    return pd.DataFrame(rows)


ITEMS = build_items(PAIRS)
print(f"{len(PAIRS)} pairs, {len(ITEMS)} items, {ITEMS.family.nunique()} families")
print(f"YES share: {ITEMS.answer.mean():.0%}")

# %%
PROMPT = """You are an expert forecaster on a forecasting platform. Today is {today}.

QUESTION: {title}

RESOLUTION CRITERIA:
{criteria}

BACKGROUND / LATEST NEWS (all facts below are confirmed and complete; nothing relevant \
remains to happen before this question resolves):
{background}

{instruction}What probability should be assigned to this question resolving YES?
End your answer with a final line in exactly this form:
PROBABILITY: <number between 0 and 1>"""

# Ablation: the "quote the deciding clause first" instruction that many bot prompts
# (including mine) approximate with "check the evidence against the resolution criteria".
QUOTE_FIRST = (
    "Before answering, quote verbatim the clause of the resolution criteria that decides "
    "this question, and check each fact against that clause, not against the question "
    "title.\n\n"
)

PROB_RE = re.compile(r"PROBABILITY\s*[:=]\s*\**\s*([0-9]*\.?[0-9]+)\s*(%?)", re.I)


def parse_probability(text: str) -> float | None:
    matches = PROB_RE.findall(text or "")
    if not matches:
        return None
    value, pct = matches[-1]
    p = float(value)
    if pct or p > 1:
        p /= 100
    return min(max(p, 0.0), 1.0)


# %%
@kbench.task(name="fine_print_item", store_task=False)
def fine_print_item(
    llm, pair_id, family, variant, today, title, criteria, background, answer, style
) -> dict:
    prompt = PROMPT.format(
        today=today,
        title=title,
        criteria=criteria,
        background=background,
        instruction=QUOTE_FIRST if style == "quote_first" else "",
    )
    try:
        response = llm.prompt(prompt)
    except Exception as e:  # keep one flaky call from sinking the whole run
        response = f"ERROR: {e}"
    p = parse_probability(response)
    parsed = p is not None
    if p is None:
        p = 0.5  # unparseable answers count as a shrug: wrong, Brier 0.25
    correct = p != 0.5 and (p > 0.5) == bool(answer)  # 0.5 is never "right"
    kbench.assertions.assert_true(
        correct,
        expectation=f"[{family}/{variant}] should resolve {'YES' if answer else 'NO'} "
        f"under the stated criteria (model gave {p:.2f}).",
    )
    return dict(
        pair_id=int(pair_id),
        family=family,
        variant=variant,
        answer=int(answer),
        p=p,
        parsed=parsed,
        correct=bool(correct),
        brier=(p - answer) ** 2,
        confidently_wrong=bool(abs(p - answer) >= 0.9),
    )


def run_items(llm, style: str = "plain", n_jobs: int = 8) -> pd.DataFrame:
    data = ITEMS.assign(style=style)
    with kbench.client.enable_cache():
        runs = fine_print_item.evaluate(
            llm=[llm],
            evaluation_data=data,
            n_jobs=n_jobs,
            timeout=300,
            max_attempts=1,
            remove_run_files=True,
        )
    results = [r for r in runs.as_dataframe().result if isinstance(r, dict)]
    return pd.DataFrame(results)


def md(df: pd.DataFrame, **kw) -> str:
    try:
        return df.to_markdown(floatfmt=".2f", **kw)
    except ImportError:  # tabulate not installed
        return df.round(2).to_string(**kw)


def summarize(res: pd.DataFrame) -> dict:
    pair_ok = res.groupby("pair_id").correct.all()
    by_variant = res.groupby("variant").correct.mean()
    return dict(
        pair_accuracy=float(pair_ok.mean()),
        item_accuracy=float(res.correct.mean()),
        control_accuracy=float(by_variant.get("control", float("nan"))),
        trap_accuracy=float(by_variant.get("trap", float("nan"))),
        brier=float(res.brier.mean()),
        confidently_wrong=float(res.confidently_wrong.mean()),
        parse_rate=float(res.parsed.mean()),
        n_items=int(len(res)),
    )


# %%
@kbench.task(
    name="fine_print_forecasting",
    description=(
        "Minimal pairs of forecasting questions where one clause of the resolution "
        "criteria flips the answer. Score = share of pairs with both variants right."
    ),
)
def fine_print_forecasting(llm) -> float:
    res = run_items(llm, style="plain")
    s = summarize(res)
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in s.items()})
    print(res.groupby("family").correct.mean().round(2).to_string())
    return s["pair_accuracy"]


fine_print_forecasting.run(kbench.llm)

# %% [markdown]
# ## Analysis for the write-up (optional)
#
# The leaderboard above uses "Evaluate More Models". The cells below re-run the item
# set for a handful of models inside this notebook so we can break results down by
# trap family and test the "quote the clause first" ablation. Pick model ids from
# `list(kbench.llms)`. Results are cached, so re-running is cheap.

# %%
print(sorted(kbench.llms) if hasattr(kbench.llms, "__iter__") else kbench.llms)

# %%
REPORT_MODELS: list[str] = []  # e.g. ["google/gemini-2.5-flash", ...]
RUN_ABLATION = True

all_results = []
for model_id in REPORT_MODELS:
    styles = ["plain", "quote_first"] if RUN_ABLATION else ["plain"]
    for style in styles:
        res = run_items(kbench.llms[model_id], style=style)
        all_results.append(res.assign(model=model_id, style=style))

if all_results:
    full = pd.concat(all_results, ignore_index=True)
    rows = []
    for (model, style), g in full.groupby(["model", "style"]):
        rows.append(dict(model=model, style=style, **summarize(g)))
    table = pd.DataFrame(rows).sort_values(["style", "pair_accuracy"], ascending=False)
    family_table = (
        full[full["style"] == "plain"]
        .pivot_table(index="family", columns="model", values="correct", aggfunc="mean")
        .round(2)
    )
    # Pairs answered the same way in both variants = the model ignored the clause.
    same_answer = (
        full.assign(says_yes=full.p > 0.5)
        .groupby(["model", "style", "pair_id"])
        .says_yes.nunique()
        .eq(1)
        .groupby(["model", "style"])
        .mean()
        .rename("fine_print_blind_pairs")
    )
    print(md(table, index=False))
    print()
    print(md(family_table))
    print()
    print(md(same_answer.to_frame()))
    full.to_csv("fine_print_results.csv", index=False)

# %%
# Keep only the main task and its latest run for the leaderboard.
# %choose fine_print_forecasting
