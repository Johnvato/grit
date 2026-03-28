"""
Seed the promises table with 2025 Australian federal election promises
for ALP, LNP, and Greens.

Run once (or re-run to refresh):  python3 seed_promises.py
Re-seeding clears existing rows first.

Status values: Delivered | In Progress | Not Started | Broken
"""

import sqlite3
import datetime

DB = "grit_cache.db"

TODAY = datetime.date.today().isoformat()

PROMISES = [
    # ── Australian Labor Party ─────────────────────────────────────────────────
    # Re-elected May 2025; promises drawn from 2022 platform + 2025 campaign.
    {
        "party": "ALP",
        "category": "Cost of Living",
        "promise": "Provide household energy bill relief ($300 rebate per eligible household)",
        "status": "Delivered",
        "evidence": "Energy Bill Relief Fund payments delivered in 2023–24 and extended into 2024–25.",
        "scrutiny": "Economists noted the rebate was temporary and did not address underlying price drivers. The Grattan Institute argued it was 'poorly targeted' — going to all households rather than those most in need.",
        "scrutiny_source": "Grattan Institute, ABC News",
        "source_url": "https://www.energy.gov.au/rebates/energy-bill-relief-fund",
    },
    {
        "party": "ALP",
        "category": "Cost of Living",
        "promise": "Cut the cost of medicines by raising the PBS safety net threshold",
        "status": "Delivered",
        "evidence": "PBS general patient co-payment frozen; Safety Net thresholds reduced from Jan 2023.",
        "scrutiny": "Welcomed by health groups. The Pharmacy Guild noted increased dispensing volumes. Some concern that the freeze may not keep pace with pharmaceutical costs long-term.",
        "scrutiny_source": "Pharmacy Guild of Australia, The Guardian",
        "source_url": "https://www.health.gov.au/our-work/pbs",
    },
    {
        "party": "ALP",
        "category": "Tax",
        "promise": "Deliver Stage 3 tax cuts (restructured to benefit lower & middle earners)",
        "status": "Delivered",
        "evidence": "Redesigned Stage 3 tax cuts legislated and took effect 1 July 2024.",
        "scrutiny": "Labor originally promised not to change Stage 3 cuts — the redesign was criticised as a broken promise by the Coalition, but praised by welfare groups for redistributing benefits to lower earners. PBO analysis confirmed 84% of taxpayers received larger cuts under the revised plan.",
        "scrutiny_source": "Parliamentary Budget Office, Sky News, ACOSS",
        "source_url": "https://www.ato.gov.au/individuals-and-families/budget-tax-cuts",
    },
    {
        "party": "ALP",
        "category": "Healthcare",
        "promise": "Triple Medicare bulk billing incentive to increase GP bulk billing rates",
        "status": "Delivered",
        "evidence": "Tripling of bulk billing incentive legislated November 2023; bulk billing rates rising.",
        "scrutiny": "AMA welcomed the increase but said it was overdue and still insufficient to reverse decades of bulk billing decline. Bulk billing rates rose from 78% to 80% in the first 6 months — short of universal access.",
        "scrutiny_source": "Australian Medical Association, ABC Health",
        "source_url": "https://www.health.gov.au/our-work/bulk-billing-support-incentive",
    },
    {
        "party": "ALP",
        "category": "Healthcare",
        "promise": "Establish 50 Medicare Urgent Care Clinics nationally",
        "status": "Delivered",
        "evidence": "58 Medicare Urgent Care Clinics open across Australia as of 2024.",
        "scrutiny": "Over-delivered on the target (58 vs 50). However, hospital emergency departments reported minimal reduction in presentations. Critics argue clinics are treating low-acuity cases that would have gone to GPs anyway.",
        "scrutiny_source": "Australian Institute of Health and Welfare, SMH",
        "source_url": "https://www.health.gov.au/our-work/medicare-urgent-care-clinics",
    },
    {
        "party": "ALP",
        "category": "Workers' Rights",
        "promise": "Legislate same job, same pay (close labour-hire loopholes)",
        "status": "Delivered",
        "evidence": "Fair Work Legislation Amendment (Closing Loopholes) Act passed December 2023.",
        "scrutiny": "Business groups (ACCI, Ai Group) warned the reforms would increase costs and reduce flexibility. Unions strongly supported. Early evidence shows some companies bringing labour-hire workers in-house. The mining sector flagged concerns about implementation complexity.",
        "scrutiny_source": "ACCI, ACTU, Australian Financial Review",
        "source_url": "https://www.fairwork.gov.au/about-us/news-and-media-releases/2023-media-releases/december-2023/20231206-closing-loopholes-bill-passed",
    },
    {
        "party": "ALP",
        "category": "Workers' Rights",
        "promise": "Legislate the right to disconnect from work outside hours",
        "status": "Delivered",
        "evidence": "Right to disconnect provisions in effect from 26 August 2024 for large employers.",
        "scrutiny": "Coalition pledged to repeal if elected. Business Council of Australia called it 'unnecessary red tape.' International precedent (France, Belgium) suggests limited enforcement impact. Workers' groups hailed it as a cultural shift.",
        "scrutiny_source": "Business Council of Australia, The Australian",
        "source_url": "https://www.fairwork.gov.au/employment-conditions/hours-of-work-breaks-and-rosters/right-to-disconnect",
    },
    {
        "party": "ALP",
        "category": "Integrity",
        "promise": "Establish a National Anti-Corruption Commission (NACC)",
        "status": "Delivered",
        "evidence": "NACC established and operational from 1 July 2023.",
        "scrutiny": "Transparency International praised the establishment but criticised the decision to hold most hearings in private. The Greens and crossbench pushed for public hearings as default. First year saw 3,000+ referrals but no public inquiries, drawing criticism from anti-corruption advocates.",
        "scrutiny_source": "Transparency International Australia, Centre for Public Integrity",
        "source_url": "https://www.nacc.gov.au",
    },
    {
        "party": "ALP",
        "category": "Families",
        "promise": "Expand Paid Parental Leave to 26 weeks by 2026",
        "status": "In Progress",
        "evidence": "Increased to 22 weeks from July 2024, expanding to 24 weeks in July 2025, 26 weeks July 2026.",
        "scrutiny": "On track to meet the 2026 target. Business groups supported the phased approach. The Parenthood and gender equity groups praised the reform but noted Australia still lags behind OECD average (18 weeks paid at full rate equivalent).",
        "scrutiny_source": "The Parenthood, OECD",
        "source_url": "https://www.servicesaustralia.gov.au/parental-leave-pay",
    },
    {
        "party": "ALP",
        "category": "Childcare",
        "promise": "Increase childcare subsidy to reduce out-of-pocket costs for families",
        "status": "Delivered",
        "evidence": "Higher childcare subsidy rates in effect from July 2023; savings of $1,700+ per year for eligible families.",
        "scrutiny": "ACCC inquiry found that fee increases by childcare providers absorbed much of the subsidy increase — net savings were lower than headline figures. The Productivity Commission recommended a universal 90% subsidy; ALP's scheme still means-tests access.",
        "scrutiny_source": "ACCC, Productivity Commission",
        "source_url": "https://www.servicesaustralia.gov.au/child-care-subsidy",
    },
    {
        "party": "ALP",
        "category": "Housing",
        "promise": "Build 1.2 million new homes through the National Housing Accord by 2029",
        "status": "In Progress",
        "evidence": "National Housing Accord agreed with states; Housing Australia Future Fund established. Construction targets on track.",
        "scrutiny": "Industry bodies warned labour and material shortages make the 1.2 million target 'aspirational at best.' Master Builders Australia estimated a shortfall of 200,000+ workers needed. Housing completions in 2024 were below the annualised rate required. The Greens argue the Accord lacks social housing targets.",
        "scrutiny_source": "Master Builders Australia, Housing Industry Association, The Guardian",
        "source_url": "https://www.nhfic.gov.au/research-and-publications/housing-australia-future-fund",
    },
    {
        "party": "ALP",
        "category": "Housing",
        "promise": "Launch Help to Buy shared equity scheme for first home buyers",
        "status": "Not Started",
        "evidence": "Legislation stalled in Senate; Greens blocked bill in 2023-24. Revised scheme announced for 2025.",
        "scrutiny": "The Greens argued it was demand-side stimulus that would push up prices. The Coalition also opposed it. Housing economists broadly sceptical — shared equity schemes in the UK and NZ have had modest uptake. Re-introduced post-2025 election but still awaiting passage.",
        "scrutiny_source": "Australian Housing and Urban Research Institute, Greens Party",
        "source_url": "https://www.helptobuy.gov.au",
    },
    {
        "party": "ALP",
        "category": "Education",
        "promise": "Make TAFE and vocational education fee-free for priority courses",
        "status": "Delivered",
        "evidence": "Fee-Free TAFE launched January 2023; 300,000+ enrolments in first year.",
        "scrutiny": "NCVER data showed strong enrolment growth. Critics noted high dropout rates in some courses and questioned whether priority courses aligned with actual skills shortages. The program is time-limited and requires ongoing funding commitment.",
        "scrutiny_source": "NCVER, Australian Skills Quality Authority",
        "source_url": "https://www.dewr.gov.au/skills-and-training/fee-free-tafe",
    },
    {
        "party": "ALP",
        "category": "Climate",
        "promise": "Legislate 43% emissions reduction by 2030 (vs 2005 levels)",
        "status": "Delivered",
        "evidence": "Climate Change Act 2022 passed with 43% target legislated. Safeguard Mechanism reformed.",
        "scrutiny": "Climate Council and scientists argued 43% is insufficient (IPCC recommends 75% for 1.5°C). The Greens called it a 'floor, not a ceiling.' Safeguard Mechanism allows polluters to use offsets — environmental groups say this creates a loophole. Independent analysis projects Australia will narrowly meet the target.",
        "scrutiny_source": "Climate Council, IPCC, Climate Action Tracker",
        "source_url": "https://www.dcceew.gov.au/climate-change/policy/climate-change-act-2022",
    },
    {
        "party": "ALP",
        "category": "Climate",
        "promise": "Reach 82% renewable electricity by 2030",
        "status": "In Progress",
        "evidence": "Renewables at ~40% (2024). Capacity investment scheme and transmission projects underway.",
        "scrutiny": "Clean Energy Council said the target is achievable but requires faster grid connection approvals. Transmission build-out is 2–3 years behind schedule. Coalition argues the target is unrealistic without gas backup. AEMO's Integrated System Plan shows a credible pathway but flags community opposition to wind farms as a risk.",
        "scrutiny_source": "Clean Energy Council, AEMO, Australian Financial Review",
        "source_url": "https://www.energy.gov.au/government-priorities/australias-energy-strategies-and-frameworks/powering-australia",
    },
    {
        "party": "ALP",
        "category": "Aged Care",
        "promise": "Implement all 148 Royal Commission into Aged Care recommendations",
        "status": "In Progress",
        "evidence": "Aged Care Act 2024 passed. New standards effective July 2024. Workforce reforms ongoing.",
        "scrutiny": "Aged Care Royal Commission commissioners criticised the pace of reform. Mandatory minimum care minutes (200 per resident per day) introduced but workforce shortages make compliance difficult. Unions report ongoing understaffing. Only ~60% of recommendations fully implemented by mid-2025.",
        "scrutiny_source": "Aged Care Royal Commission, Health Services Union, ABC News",
        "source_url": "https://www.health.gov.au/our-work/aged-care-reform",
    },
    {
        "party": "ALP",
        "category": "Disability",
        "promise": "Stabilise NDIS spending and improve scheme sustainability",
        "status": "In Progress",
        "evidence": "NDIS Review completed 2023. Legislation amending scheme passed 2024. Spending growth slowing.",
        "scrutiny": "Disability advocates warn 'sustainability' is code for cuts. Every Australian Counts campaign flagged that independent assessments may reduce participant choice. Spending growth slowed from 14% to 8% annually but still exceeds long-term targets. State governments raised concerns about cost-shifting.",
        "scrutiny_source": "Every Australian Counts, NDIS Review Panel, The Saturday Paper",
        "source_url": "https://www.ndis.gov.au/about-us/our-organisation/ndis-review",
    },
    {
        "party": "ALP",
        "category": "Cost of Living",
        "promise": "Cap student debt indexation to wages or CPI (whichever is lower)",
        "status": "Delivered",
        "evidence": "HELP debt indexation capped at wages or CPI; backdated refunds issued June 2024.",
        "scrutiny": "Widely praised. Universities Australia and student unions supported it. Backdated refunds totalled $3 billion. Critics argued it doesn't address the underlying growth in HECS balances from rising fees. Some called for full debt cancellation (adopted by Greens but not ALP).",
        "scrutiny_source": "Universities Australia, National Union of Students",
        "source_url": "https://www.education.gov.au/hecs-help-debt-indexation",
    },

    # ── Liberal-National Coalition ─────────────────────────────────────────────
    # 2025 election platform — opposition promises if elected.
    {
        "party": "LNP",
        "category": "Energy",
        "promise": "Build 7 nuclear power plants at former coal sites by 2050",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented. Dutton re-committed to nuclear in opposition.",
        "source_url": "https://www.liberal.org.au/our-plan/nuclear-power",
    },
    {
        "party": "LNP",
        "category": "Cost of Living",
        "promise": "Cut fuel excise by 25 cents per litre for 12 months",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Immigration",
        "promise": "Reduce net overseas migration to 160,000 per year",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Housing",
        "promise": "Allow first home buyers to access superannuation for a deposit",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Tax",
        "promise": "Reduce the size of the public service by 36,000 through attrition",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Economy",
        "promise": "Return the federal budget to surplus within first term",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Integrity",
        "promise": "Establish a royal commission into the NDIS",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Workers' Rights",
        "promise": "Repeal the right to disconnect laws",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; remains a stated policy commitment in opposition.",
        "source_url": "https://www.liberal.org.au",
    },
    {
        "party": "LNP",
        "category": "Climate",
        "promise": "Achieve net zero by 2050 (technology-neutral pathway including nuclear)",
        "status": "Not Started",
        "evidence": "LNP lost 2025 election; policy not implemented.",
        "source_url": "https://www.liberal.org.au",
    },

    # ── Australian Greens ──────────────────────────────────────────────────────
    # 2025 election platform.
    {
        "party": "Greens",
        "category": "Healthcare",
        "promise": "Add dental and mental health care to Medicare (universal free dental)",
        "status": "Not Started",
        "evidence": "Greens hold balance in Senate but ALP has not adopted full dental Medicare.",
        "source_url": "https://greens.org.au/platform/health",
    },
    {
        "party": "Greens",
        "category": "Housing",
        "promise": "Build 1 million social and affordable homes",
        "status": "Not Started",
        "evidence": "Greens blocked ALP Housing Australia Future Fund over demands for more social housing.",
        "source_url": "https://greens.org.au/platform/housing",
    },
    {
        "party": "Greens",
        "category": "Housing",
        "promise": "Freeze and cap rents nationally",
        "status": "Not Started",
        "evidence": "Policy requires federal-state cooperation; ALP has not adopted rent freeze.",
        "source_url": "https://greens.org.au/platform/housing",
    },
    {
        "party": "Greens",
        "category": "Childcare",
        "promise": "Make childcare free for all Australian families",
        "status": "Not Started",
        "evidence": "ALP increased subsidies but did not move to universal free childcare.",
        "source_url": "https://greens.org.au/platform/education",
    },
    {
        "party": "Greens",
        "category": "Education",
        "promise": "Cancel all HECS/HELP student debt",
        "status": "Not Started",
        "evidence": "ALP capped indexation; full cancellation not adopted.",
        "source_url": "https://greens.org.au/platform/education",
    },
    {
        "party": "Greens",
        "category": "Climate",
        "promise": "No new coal, oil or gas projects approved",
        "status": "Not Started",
        "evidence": "ALP has continued to approve new gas projects including Woodside Scarborough.",
        "source_url": "https://greens.org.au/platform/climate",
    },
    {
        "party": "Greens",
        "category": "Climate",
        "promise": "75% emissions reduction by 2030",
        "status": "Not Started",
        "evidence": "ALP legislated 43% target; Greens target not adopted.",
        "source_url": "https://greens.org.au/platform/climate",
    },
    {
        "party": "Greens",
        "category": "Tax",
        "promise": "Introduce a 40% tax on super profits of big corporations",
        "status": "Not Started",
        "evidence": "Not adopted by ALP government.",
        "source_url": "https://greens.org.au/platform/economy",
    },
    {
        "party": "Greens",
        "category": "Tax",
        "promise": "Raise the top income tax rate to 55% for incomes over $1 million",
        "status": "Not Started",
        "evidence": "Not adopted by ALP government.",
        "source_url": "https://greens.org.au/platform/economy",
    },
    {
        "party": "Greens",
        "category": "Welfare",
        "promise": "Raise JobSeeker and other income support payments above poverty line",
        "status": "Not Started",
        "evidence": "ALP increased JobSeeker by $40/fortnight in 2023; Greens consider this insufficient.",
        "source_url": "https://greens.org.au/platform/welfare",
    },
]


def seed(clear_first: bool = True):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS promises (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            party           TEXT    NOT NULL,
            category        TEXT    NOT NULL,
            promise         TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'Not Started',
            evidence        TEXT,
            scrutiny        TEXT,
            scrutiny_source TEXT,
            source_url      TEXT,
            added_date      TEXT,
            updated_date    TEXT
        )
    ''')

    if clear_first:
        c.execute("DELETE FROM promises")
        print("Cleared existing promises.")

    for p in PROMISES:
        c.execute('''
            INSERT INTO promises
                (party, category, promise, status, evidence,
                 scrutiny, scrutiny_source, source_url,
                 added_date, updated_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            p["party"], p["category"], p["promise"], p["status"],
            p.get("evidence", ""),
            p.get("scrutiny", ""), p.get("scrutiny_source", ""),
            p.get("source_url", ""),
            TODAY, TODAY,
        ))

    conn.commit()
    conn.close()
    print(f"Seeded {len(PROMISES)} promises.")


if __name__ == "__main__":
    seed()
