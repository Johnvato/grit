"""
Seed the controversial_bills table with notable Australian legislation
where the stated purpose masks provisions that unfairly favour specific groups.

Run:  python3 seed_controversial_bills.py
Re-seeding clears existing rows first.
"""

import sqlite3
import datetime

DB = "grit_cache.db"
TODAY = datetime.date.today().isoformat()

BILLS = [
    # ── Electoral / Donations ──────────────────────────────────────────────────
    {
        "title": "Electoral Legislation Amendment (Electoral Funding and Disclosure Reform) Bill 2024",
        "short_name": "Donation caps bill",
        "category": "Electoral Reform",
        "year": 2024,
        "status": "Passed",
        "official_purpose": (
            "Cap political donations at $20,000 per donor per party to reduce "
            "the influence of money in politics and increase transparency."
        ),
        "hidden_impact": (
            "The cap applies per donor per party — but major parties have dozens of state "
            "and federal branches that count as separate entities. A single donor can give "
            "$20,000 to the federal ALP, $20,000 to each state branch, $20,000 to each "
            "associated entity — effectively multiplying their cap many times over. "
            "Independents, with only one entity, are limited to $20,000 per donor total. "
            "The bill also bans donations above $20,000 from being split across affiliated "
            "organisations that independents rely on (like community campaign groups), "
            "while unions and business associations affiliated with major parties continue "
            "to donate separately. This structurally entrenches the fundraising advantage "
            "of established parties."
        ),
        "who_benefits": "ALP, Liberal Party, National Party — any party with multiple state/federal branches",
        "who_loses": (
            "Independent candidates and small parties with a single organisational entity. "
            "Community-backed independents like the 'teal' movement face severe fundraising constraints "
            "compared to their major-party opponents."
        ),
        "key_provisions": (
            "1. $20,000 annual cap per donor per political entity. "
            "2. Major parties' state branches count as separate entities. "
            "3. Affiliated bodies (unions, business groups) can donate separately to their aligned party. "
            "4. Spending caps introduced but set high enough to favour incumbents with existing war chests."
        ),
        "criticism": (
            "The crossbench labelled it 'the incumbent protection act.' Senator David Pocock and "
            "multiple teal independents argued the bill was designed to look like reform while "
            "structurally disadvantaging their movement. The Grattan Institute noted the branch "
            "loophole made the caps 'largely cosmetic' for major parties. International observers "
            "pointed out that genuine donation caps (as in Canada) apply per donor across ALL "
            "branches of a party."
        ),
        "criticism_source": (
            "Senator David Pocock, Grattan Institute, The Centre for Public Integrity, "
            "Voices of Indi, The Guardian, The Saturday Paper"
        ),
        "criticism_urls": (
            "PS News — independents criticise donation reform|https://psnews.com.au/major-party-stitch-up-independents-criticise-federal-donation-law-reform-move/149265/||"
            "The Conversation — donation caps rushed through|https://www.theconversation.com/government-aims-to-pass-political-donation-and-spending-caps-within-a-fortnight-after-in-principle-deal-with-opposition-243708||"
            "Grattan Institute — where the money came from|https://grattan.edu.au/news/election-2025-where-the-money-came-from/"
        ),
        "defence": (
            "The government argued the bill represented the most significant donation reform in "
            "decades and that perfect should not be the enemy of good. The ALP said the branch "
            "structure reflects the federal nature of Australian politics and that the bill "
            "dramatically improves transparency compared to the prior regime."
        ),
        "source_url": "https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/Bills_Search_Results/Result?bId=r7236",
    },

    # ── Mining / Resources ─────────────────────────────────────────────────────
    {
        "title": "Safeguard Mechanism (Crediting) Amendment Bill 2023",
        "short_name": "Safeguard Mechanism reform",
        "category": "Mining / Energy",
        "year": 2023,
        "status": "Passed",
        "official_purpose": (
            "Reduce emissions from Australia's 215 highest-polluting industrial facilities "
            "by requiring them to cut emissions by 4.9% per year toward net zero by 2050."
        ),
        "hidden_impact": (
            "The bill allows facilities to meet their obligations by purchasing carbon offsets "
            "rather than making actual emissions reductions. Australian Carbon Credit Units (ACCUs) "
            "have been widely criticised as unreliable — a 2022 whistleblower review found that "
            "up to 80% of credits from some methods did not represent genuine abatement. "
            "The bill also includes 'trade-exposed' exemptions that allow the most carbon-intensive "
            "exporters (LNG, coal) to receive government-funded Safeguard Mechanism Credits, "
            "effectively subsidising polluters. New fossil fuel projects can still be approved "
            "and enter the scheme with generous baselines."
        ),
        "who_benefits": (
            "Major LNG exporters (Woodside, Santos, Chevron), coal miners, and the carbon offset "
            "industry. Companies can continue polluting at current levels while purchasing cheap "
            "offsets to claim compliance."
        ),
        "who_loses": (
            "The climate. Communities near polluting facilities. Renewable energy competitors who "
            "don't receive equivalent subsidies. Taxpayers funding the offset credits."
        ),
        "key_provisions": (
            "1. 4.9% annual decline in baselines for covered facilities. "
            "2. Unlimited use of ACCUs (carbon offsets) to meet obligations. "
            "3. Trade-exposed exemptions for export-oriented polluters. "
            "4. New fossil fuel projects can still enter the scheme. "
            "5. Government-funded Safeguard Mechanism Credits for hardship cases."
        ),
        "criticism": (
            "Professor Andrew Macintosh (former chair of the Emissions Reduction Assurance Committee) "
            "called the offset system 'largely a sham.' The Greens secured amendments banning "
            "the use of some offset types but could not remove the loophole entirely. "
            "Climate Analytics estimated the scheme would allow Australia's emissions to continue "
            "rising until 2030 despite the stated 43% reduction target."
        ),
        "criticism_source": (
            "Professor Andrew Macintosh, Climate Analytics, The Australia Institute, "
            "Australian Conservation Foundation, The Guardian"
        ),
        "criticism_urls": (
            "The Conversation — carbon credits could blow up climate policy|https://theconversation.com/the-unsafe-safeguard-mechanism-how-carbon-credits-could-blow-up-australias-main-climate-policy-213874||"
            "ABC News — research questions offset integrity|https://www.abc.net.au/news/2024-03-26/safeguard-mechanism-accu-challenge/103636382||"
            "ABC News — insider blows whistle on offsets|https://www.abc.net.au/news/2022-03-24/insider-blows-whistle-on-greenhouse-gas-reduction-schemes/100933186"
        ),
        "defence": (
            "Climate Change Minister Chris Bowen argued the mechanism represents the first "
            "legally binding emissions reduction obligation on heavy industry in Australian history "
            "and that offsets provide necessary flexibility during the transition."
        ),
        "source_url": "https://www.legislation.gov.au/C2023B00058",
    },
    {
        "title": "Future Gas Strategy 2024",
        "short_name": "Future Gas Strategy",
        "category": "Mining / Energy",
        "year": 2024,
        "status": "Policy (non-legislative)",
        "official_purpose": (
            "Ensure reliable and affordable gas supply during Australia's energy transition "
            "by positioning gas as a 'transition fuel' to complement renewables."
        ),
        "hidden_impact": (
            "The strategy explicitly states gas will remain part of Australia's energy mix "
            "'beyond 2050' — contradicting the IEA's finding that no new gas fields are "
            "compatible with net zero by 2050. It provides political cover for approving "
            "new gas projects (including Woodside's Scarborough and Browse fields) worth "
            "billions in export revenue. The strategy was developed with extensive gas industry "
            "consultation — FOI requests revealed that gas lobbyists had more meetings with "
            "the Resources Minister than renewable energy advocates by a ratio of 5:1."
        ),
        "who_benefits": (
            "Gas producers (Woodside, Santos, Shell), the APPEA lobby group, and export-dependent "
            "states (WA, QLD). The strategy protects billions in planned gas investments."
        ),
        "who_loses": (
            "Domestic gas consumers (most Australian gas is exported, keeping domestic prices high). "
            "Climate targets — the strategy makes 43% by 2030 harder to achieve. Renewable energy "
            "projects competing for grid connection and investment."
        ),
        "key_provisions": (
            "1. Gas designated a 'transition fuel' with no end date. "
            "2. Government support for new gas exploration and development. "
            "3. No domestic reservation policy (most gas continues to be exported). "
            "4. Gas infrastructure eligible for government concessional finance."
        ),
        "criticism": (
            "The Climate Council called it 'a gift to the fossil fuel industry dressed up as "
            "climate policy.' The IEA's 2021 Net Zero Roadmap explicitly states no new gas "
            "fields should be approved for 1.5-degree alignment. FOI documents revealed "
            "disproportionate gas industry influence in drafting the strategy."
        ),
        "criticism_source": (
            "Climate Council, International Energy Agency, The Australia Institute, "
            "Greenpeace Australia Pacific, Michael West Media"
        ),
        "criticism_urls": (
            "Climate Council — Future Gas Strategy critique|https://www.climatecouncil.org.au/resources/a-future-gas-strategy-that-sends-us-back-to-the-future/||"
            "Australia Institute — through the looking glass|https://australiainstitute.org.au/post/future-gas-strategy-takes-australians-through-the-looking-glass/||"
            "IEEFA — questions over gas strategy|https://ieefa.org/resources/australian-government-has-questions-answer-over-future-gas-strategy"
        ),
        "defence": (
            "Resources Minister Madeleine King argued gas is essential for energy security, "
            "manufacturing, and firming intermittent renewables. The government noted Australia's "
            "gas export industry supports 80,000 jobs and that an abrupt exit would cause "
            "economic disruption in regional communities."
        ),
        "source_url": "https://www.industry.gov.au/publications/future-gas-strategy",
    },
    {
        "title": "Treasury Laws Amendment (Foreign Ownership) Bill 2024",
        "short_name": "Foreign ownership screening (mining carve-out)",
        "category": "Mining / Energy",
        "year": 2024,
        "status": "Passed",
        "official_purpose": (
            "Strengthen foreign investment screening to protect Australia's national interest, "
            "particularly for critical minerals and strategic assets."
        ),
        "hidden_impact": (
            "While tightening rules for residential property and agricultural land, "
            "the bill maintained generous exemptions for mining and LNG projects. "
            "Foreign state-owned enterprises can still acquire major stakes in "
            "Australian gas and coal projects without the same scrutiny applied to "
            "farmland purchases. The bill's 'national interest' test for mining is "
            "interpreted narrowly — focusing on security, not environmental or "
            "community impact."
        ),
        "who_benefits": (
            "Foreign-backed mining and gas companies. State-owned enterprises from "
            "major trading partners investing in Australian resources."
        ),
        "who_loses": (
            "Local communities affected by mining expansion. Australian-owned competitors "
            "who face different regulatory burdens. The inconsistency between strict farmland "
            "rules and lax mining rules suggests agricultural communities are protected "
            "while mining communities are not."
        ),
        "key_provisions": (
            "1. Stricter screening for agricultural land and residential property. "
            "2. Mining and LNG projects assessed primarily on security grounds. "
            "3. 'National interest' test does not include environmental or community impact for mining. "
            "4. Higher penalties for non-compliance with screening."
        ),
        "criticism": (
            "The Australia Institute argued the bill created a 'two-tier system' where "
            "farming families face more scrutiny than multinational miners. Crossbench senators "
            "pushed for mining to face equivalent scrutiny without success."
        ),
        "criticism_source": "The Australia Institute, Senate crossbench, ABC Rural",
        "criticism_urls": (
            "APH — Foreign Investment Bill digest|https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/bd/bd2324a/24bd047a||"
            "DLA Piper — foreign investment reforms|https://www.dlapiper.com/en-au/insights/publications/2024/05/upcoming-reforms-to-australia-foreign-investment-regime-seeking-to-refocus-and-streamline-approvals"
        ),
        "defence": (
            "Treasurer Jim Chalmers argued the reforms balanced national security with "
            "Australia's need for foreign investment in mining and critical minerals "
            "essential for the energy transition."
        ),
        "source_url": "https://www.legislation.gov.au/C2024B00094",
    },
    {
        "title": "Fuel and Petroleum Standards Amendment 2024",
        "short_name": "Fuel quality standards delay",
        "category": "Mining / Energy",
        "year": 2024,
        "status": "Passed",
        "official_purpose": (
            "Update Australia's fuel quality standards to align with international norms, "
            "including the introduction of Euro 6/VI equivalent vehicle emission standards."
        ),
        "hidden_impact": (
            "Australia's fuel sulfur standards have been among the worst in the OECD for over "
            "a decade. The bill set a compliance date of 2027 for 10ppm sulfur fuel — three "
            "years later than health experts recommended. This delay benefits the four "
            "domestic refineries (Viva, Ampol, and others) that would need to invest in "
            "desulfurisation equipment. During the delay, Australians continue breathing "
            "dirtier air. High-sulfur fuel also prevents modern emission-control technologies "
            "(like gasoline particulate filters) from working properly, meaning even new cars "
            "pollute more in Australia than identical models in Europe or Japan."
        ),
        "who_benefits": (
            "Domestic fuel refineries avoiding immediate capital expenditure. Fuel importers "
            "who can continue sourcing cheaper high-sulfur fuel."
        ),
        "who_loses": (
            "Public health — the delayed standard is linked to an estimated 1,700 premature "
            "deaths per year from vehicle pollution. Car manufacturers who cannot deploy their "
            "cleanest engine technologies in Australia."
        ),
        "key_provisions": (
            "1. 10ppm sulfur standard mandated — but not until 2027. "
            "2. No interim tightening of the current 150ppm standard. "
            "3. No financial penalties for refineries that delay compliance."
        ),
        "criticism": (
            "The Australian Medical Association called the timeline 'unconscionable' given the "
            "known health impacts. The FCAI (Federal Chamber of Automotive Industries) had been "
            "lobbying for earlier implementation since 2016. International comparison: Europe "
            "adopted 10ppm sulfur in 2009."
        ),
        "criticism_source": (
            "Australian Medical Association, FCAI, Lung Foundation Australia, "
            "Doctors for the Environment"
        ),
        "criticism_urls": (
            "ABC News — fuel standards eased explainer|https://abc.gov.au/news/2026-03-14/australian-fuel-standards-eased-explainer-what-is-dirty-fuel/106450074||"
            "Petrolmate — dirty fuel reputation|https://petrolmate.com.au/blog/2026-01-10-australia-finally-ditches-dirty-fuel-reputation"
        ),
        "defence": (
            "The government argued the 2027 timeline was necessary to allow domestic refineries "
            "to invest in upgrades without risking closure, which would leave Australia entirely "
            "dependent on imported fuel — a national security concern."
        ),
        "source_url": "https://www.legislation.gov.au/C2024B00065",
    },

    # ── Social / Privacy ───────────────────────────────────────────────────────
    {
        "title": "Online Safety Amendment (Social Media Minimum Age) Bill 2024",
        "short_name": "Social media age ban",
        "category": "Digital / Privacy",
        "year": 2024,
        "status": "Passed",
        "official_purpose": (
            "Protect children by banning social media access for users under 16, "
            "requiring platforms to implement age verification."
        ),
        "hidden_impact": (
            "To verify age, platforms will need to collect government-issued ID or biometric data "
            "from all Australians — not just children. This creates a de facto national online "
            "identity verification system without the privacy safeguards that would normally "
            "accompany such a scheme. The bill was rushed through Parliament in under a week "
            "with minimal committee scrutiny. Digital rights groups warned the infrastructure "
            "could be repurposed for broader online surveillance or content censorship. "
            "The bill also shifts responsibility from platforms to parents — if verification "
            "fails, it's the user's problem, not the platform's."
        ),
        "who_benefits": (
            "Government (gains age-verification infrastructure applicable beyond social media). "
            "Incumbent media organisations competing with social media for advertising revenue. "
            "Age-verification technology vendors."
        ),
        "who_loses": (
            "All Australians who must submit identity documents or biometrics to use social media. "
            "Children in unsafe home environments who use social media as a support network. "
            "Digital privacy. Small platforms unable to build compliant verification systems."
        ),
        "key_provisions": (
            "1. Minimum age of 16 for social media access. "
            "2. Platforms must take 'reasonable steps' to prevent underage access. "
            "3. Age verification method left to platforms (likely ID or biometrics). "
            "4. Penalties up to $50 million for non-compliant platforms. "
            "5. Passed with less than one week of parliamentary debate."
        ),
        "criticism": (
            "The Human Rights Law Centre warned the bill was 'a Trojan horse for mass surveillance.' "
            "Digital Rights Watch noted that no age verification technology exists that doesn't "
            "compromise privacy. Former eSafety Commissioner Toby Walsh called the timeline "
            "'reckless.' The bill passed with bipartisan support and almost no dissent, "
            "raising concerns about performative populism overriding careful policy design."
        ),
        "criticism_source": (
            "Human Rights Law Centre, Digital Rights Watch, Electronic Frontiers Australia, "
            "Reset Australia, Professor Toby Walsh"
        ),
        "criticism_urls": (
            "HRLC — social media ban not the answer|https://hrlc.org.au/news/social-media-ban||"
            "AHRC — social media ban explainer (PDF)|https://humanrights.gov.au/sites/default/files/2024-11/AHRC_Social-Media-Ban-Explainer.pdf"
        ),
        "defence": (
            "Both ALP and Coalition argued the mental health of children must take priority "
            "and that platforms have failed to self-regulate. The government committed to "
            "reviewing the age-verification approach within 12 months of implementation."
        ),
        "source_url": "https://www.legislation.gov.au/C2024B00219",
    },
]


def seed(clear_first: bool = True):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS controversial_bills (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            short_name      TEXT,
            category        TEXT    NOT NULL,
            year            INTEGER,
            status          TEXT,
            official_purpose TEXT,
            hidden_impact   TEXT,
            who_benefits    TEXT,
            who_loses       TEXT,
            key_provisions  TEXT,
            criticism       TEXT,
            criticism_source TEXT,
            criticism_urls  TEXT,
            defence         TEXT,
            source_url      TEXT,
            added_date      TEXT
        )
    ''')

    if clear_first:
        c.execute("DELETE FROM controversial_bills")
        print("Cleared existing controversial bills.")

    for b in BILLS:
        c.execute('''
            INSERT INTO controversial_bills
                (title, short_name, category, year, status,
                 official_purpose, hidden_impact, who_benefits, who_loses,
                 key_provisions, criticism, criticism_source, defence,
                 source_url, added_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            b["title"], b.get("short_name", ""), b["category"],
            b.get("year"), b.get("status", ""),
            b.get("official_purpose", ""), b.get("hidden_impact", ""),
            b.get("who_benefits", ""), b.get("who_loses", ""),
            b.get("key_provisions", ""), b.get("criticism", ""),
            b.get("criticism_source", ""), b.get("defence", ""),
            b.get("source_url", ""), TODAY,
        ))

    conn.commit()
    conn.close()
    print(f"Seeded {len(BILLS)} controversial bills.")


if __name__ == "__main__":
    seed()
