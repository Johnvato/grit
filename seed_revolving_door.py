"""
Seed the revolving_door table with notable post-politics appointments
where the role indicates a potential conflict of interest during
the politician's time in office.

Run:  python3 seed_revolving_door.py
Re-seeding clears existing rows first.
"""

import sqlite3
import datetime

DB = "grit_cache.db"
TODAY = datetime.date.today().isoformat()

CASES = [
    {
        "name": "Andrew Robb",
        "party": "Liberal Party",
        "last_office": "Minister for Trade and Investment (2013–2016)",
        "left_office_year": 2016,
        "post_office_role": "Senior economic adviser",
        "employer": "Landbridge Group (Chinese-owned company)",
        "sector": "Foreign Investment / Infrastructure",
        "conflict_summary": (
            "As Trade Minister, Robb signed the China-Australia Free Trade Agreement "
            "and was in office when the 99-year lease of the Port of Darwin to Landbridge "
            "was approved. Within months of leaving parliament, he took an $880,000/year "
            "advisory role with Landbridge — the same company that leased the port."
        ),
        "portfolio_overlap": (
            "Trade Minister responsible for China trade relations → adviser to a Chinese-owned "
            "company that benefited from policy decisions made during his tenure."
        ),
        "cooling_off_months": 2,
        "source_url": "https://www.abc.net.au/news/2017-06-06/andrew-robb-defends-landbridge-role/8592308",
    },
    {
        "name": "Julie Bishop",
        "party": "Liberal Party",
        "last_office": "Minister for Foreign Affairs (2013–2018)",
        "left_office_year": 2019,
        "post_office_role": "Board member",
        "employer": "Palladium Group (international development contractor)",
        "sector": "Foreign Aid / Development",
        "conflict_summary": (
            "As Foreign Minister, Bishop oversaw DFAT and Australia's foreign aid program, "
            "which contracted companies like Palladium to deliver aid projects. After leaving "
            "parliament she joined Palladium's board — a major recipient of the contracts "
            "her department administered. She also took roles with ANU and multiple corporate boards."
        ),
        "portfolio_overlap": (
            "Foreign Minister overseeing aid contracts → board member of a company "
            "that is one of the largest recipients of those same aid contracts."
        ),
        "cooling_off_months": 6,
        "source_url": "https://www.theguardian.com/australia-news/2019/jul/18/julie-bishop-joins-board-of-aid-contractor-palladium",
    },
    {
        "name": "Christopher Pyne",
        "party": "Liberal Party",
        "last_office": "Minister for Defence (2018–2019)",
        "left_office_year": 2019,
        "post_office_role": "Consultant / lobbyist",
        "employer": "EY (Ernst & Young), then own lobbying firm GC Advisory",
        "sector": "Defence / Consulting",
        "conflict_summary": (
            "As Defence Minister, Pyne oversaw the $90 billion submarine program and major "
            "defence procurement contracts. Weeks after leaving parliament, he registered "
            "as a consultant with EY's defence practice and later established GC Advisory, "
            "lobbying on behalf of defence contractors. The NACC's predecessor (ACLEI) "
            "and multiple senators raised concerns about the speed of transition."
        ),
        "portfolio_overlap": (
            "Defence Minister overseeing $90B+ in procurement → consultant to companies "
            "bidding for the contracts he approved."
        ),
        "cooling_off_months": 1,
        "source_url": "https://www.abc.net.au/news/2019-07-22/christopher-pyne-ey-job-lobbying-rule-questions/11330284",
    },
    {
        "name": "Joe Hockey",
        "party": "Liberal Party",
        "last_office": "Treasurer (2013–2015), Ambassador to the US (2016–2020)",
        "left_office_year": 2020,
        "post_office_role": "Advisory board member / consultant",
        "employer": "Bondi Partners (own advisory firm), Oatly, multiple US/Australian boards",
        "sector": "Finance / International Trade",
        "conflict_summary": (
            "As Treasurer, Hockey made policy on foreign investment rules, banking regulation, "
            "and tax. As Ambassador to the US, he built relationships with American corporates "
            "and government. Upon return he launched Bondi Partners, a strategic advisory firm "
            "leveraging his political and diplomatic networks, advising firms on US-Australia "
            "business opportunities — monetising relationships built in public office."
        ),
        "portfolio_overlap": (
            "Treasurer + US Ambassador → consulting firm advising on Australia-US trade "
            "and investment, the exact intersection of his two public roles."
        ),
        "cooling_off_months": 0,
        "source_url": "https://www.afr.com/politics/federal/joe-hockey-launches-advisory-firm-after-ambassador-posting-20200120-p53t4m",
    },
    {
        "name": "Martin Ferguson",
        "party": "Australian Labor Party",
        "last_office": "Minister for Resources and Energy (2007–2013)",
        "left_office_year": 2013,
        "post_office_role": "Chairman",
        "employer": "APPEA (Australian Petroleum Production & Exploration Association)",
        "sector": "Mining / Oil & Gas",
        "conflict_summary": (
            "As Resources Minister, Ferguson was responsible for regulating the oil and gas "
            "industry and approving exploration permits. He was widely seen as a champion "
            "of the fossil fuel industry within the Labor caucus, opposing the mining tax "
            "within cabinet. After leaving parliament he became chairman of APPEA — "
            "the peak lobby group for the industry he had regulated."
        ),
        "portfolio_overlap": (
            "Resources Minister regulating the oil/gas industry → chairman of the "
            "industry's peak lobbying body."
        ),
        "cooling_off_months": 5,
        "source_url": "https://www.smh.com.au/politics/federal/martin-ferguson-to-chair-oil-and-gas-lobby-20140203-31xlf.html",
    },
    {
        "name": "Ian Macfarlane",
        "party": "Liberal Party",
        "last_office": "Minister for Industry and Science (2013–2015)",
        "left_office_year": 2016,
        "post_office_role": "Chief Executive",
        "employer": "Queensland Resources Council",
        "sector": "Mining / Resources",
        "conflict_summary": (
            "As Industry Minister, Macfarlane shaped policy affecting the mining and resources "
            "sector including energy policy and carbon reduction mechanisms. After leaving "
            "parliament he became CEO of the Queensland Resources Council — the peak body "
            "representing the mining companies his policies directly impacted."
        ),
        "portfolio_overlap": (
            "Industry Minister setting mining/energy policy → CEO of the mining "
            "industry's state peak body."
        ),
        "cooling_off_months": 3,
        "source_url": "https://www.afr.com/politics/federal/ian-macfarlane-to-lead-queensland-resources-council-20160419-go9hq5",
    },
    {
        "name": "Mark Vaile",
        "party": "National Party",
        "last_office": "Deputy Prime Minister / Trade Minister (2005–2007)",
        "left_office_year": 2008,
        "post_office_role": "Chairman",
        "employer": "Whitehaven Coal",
        "sector": "Mining / Coal",
        "conflict_summary": (
            "As Trade Minister and Deputy PM, Vaile shaped trade and agricultural policy "
            "affecting regional Australia and the resources sector. He also served as "
            "Agriculture Minister (1999–2005). After leaving parliament he became chairman "
            "of Whitehaven Coal, a major thermal and metallurgical coal producer whose "
            "operations intersect with trade, agriculture, and environmental policy."
        ),
        "portfolio_overlap": (
            "Trade/Agriculture/Deputy PM with resources policy influence → chairman "
            "of a major coal company."
        ),
        "cooling_off_months": 12,
        "source_url": "https://www.whitehavencoal.com.au",
    },
    {
        "name": "Peter Costello",
        "party": "Liberal Party",
        "last_office": "Treasurer (1996–2007)",
        "left_office_year": 2009,
        "post_office_role": "Chairman",
        "employer": "Nine Entertainment (now Nine), Future Fund (initial chairman)",
        "sector": "Media / Finance",
        "conflict_summary": (
            "As Treasurer for 11 years, Costello set media ownership laws, tax policy, "
            "and financial regulation. He created the Future Fund and was its inaugural "
            "chairman. He later became chairman of Nine Entertainment — one of Australia's "
            "largest media companies. His dual roles gave him influence over both the fund "
            "investing taxpayer money and a media company that covers political decisions."
        ),
        "portfolio_overlap": (
            "Treasurer who set media ownership and tax laws → chairman of Nine, a major "
            "media company directly affected by those laws."
        ),
        "cooling_off_months": 24,
        "source_url": "https://www.abc.net.au/news/2016-06-03/peter-costello-named-nine-entertainment-chairman/7475108",
    },
    {
        "name": "Mike Baird",
        "party": "Liberal Party",
        "last_office": "Premier of NSW (2014–2017)",
        "left_office_year": 2017,
        "post_office_role": "Senior executive",
        "employer": "National Australia Bank (NAB)",
        "sector": "Banking / Finance",
        "conflict_summary": (
            "As NSW Premier, Baird oversaw state financial regulation, the privatisation "
            "of the state electricity network ('Poles and Wires'), and state banking "
            "arrangements. He joined NAB as a senior executive shortly after resigning, "
            "raising questions about whether policy decisions during his premiership "
            "may have been influenced by future employment prospects. NAB was one of "
            "the banks involved in financing NSW privatisations."
        ),
        "portfolio_overlap": (
            "NSW Premier overseeing privatisation and state banking → senior executive "
            "at a major bank involved in financing those same privatisations."
        ),
        "cooling_off_months": 3,
        "source_url": "https://www.smh.com.au/business/banking-and-finance/mike-baird-named-nab-executive-20170414-gvl6g3.html",
    },
    {
        "name": "Steve Bracks",
        "party": "Australian Labor Party",
        "last_office": "Premier of Victoria (1999–2007)",
        "left_office_year": 2007,
        "post_office_role": "Consultant / board director",
        "employer": "KPMG, Jardine Lloyd Thompson, multiple boards",
        "sector": "Consulting / Insurance",
        "conflict_summary": (
            "As Victorian Premier, Bracks oversaw major infrastructure projects, state "
            "procurement, and insurance regulation (including WorkSafe and TAC reforms). "
            "After leaving politics he joined KPMG as a consultant and took board roles "
            "with companies in sectors his government regulated, including insurance "
            "and infrastructure."
        ),
        "portfolio_overlap": (
            "Premier overseeing state procurement and regulation → consultant at a firm "
            "that advises on government procurement."
        ),
        "cooling_off_months": 2,
        "source_url": "https://www.theaustralian.com.au/nation/politics/steve-bracks-joins-kpmg/news-story",
    },
    {
        "name": "Brendan Nelson",
        "party": "Liberal Party",
        "last_office": "Minister for Defence (2006–2007), Opposition Leader (2007–2008)",
        "left_office_year": 2009,
        "post_office_role": "President / Ambassador",
        "employer": "Boeing Australia, then Australian War Memorial director",
        "sector": "Defence / Aerospace",
        "conflict_summary": (
            "As Defence Minister, Nelson oversaw procurement decisions involving Boeing "
            "aircraft and weapons systems. He later became president of Boeing Australia — "
            "the local arm of a company that was a major beneficiary of the defence contracts "
            "approved during his tenure."
        ),
        "portfolio_overlap": (
            "Defence Minister approving Boeing contracts → president of Boeing's "
            "Australian operations."
        ),
        "cooling_off_months": 18,
        "source_url": "https://www.abc.net.au/news/2010-08-26/nelson-appointed-boeing-australia-president/2955842",
    },
    {
        "name": "Alexander Downer",
        "party": "Liberal Party",
        "last_office": "Minister for Foreign Affairs (1996–2007), High Commissioner to the UK (2014–2018)",
        "left_office_year": 2018,
        "post_office_role": "Consultant / board member",
        "employer": "Huawei (advisory board, earlier role), Woodside Energy board",
        "sector": "Telecommunications / Energy",
        "conflict_summary": (
            "As Australia's longest-serving Foreign Minister, Downer managed relationships "
            "with China and oversaw ASIS and intelligence operations. He sat on Huawei's "
            "Australian advisory board before Huawei was banned from 5G. He later joined "
            "Woodside Energy's board — a major LNG exporter whose projects span countries "
            "where he had diplomatic influence."
        ),
        "portfolio_overlap": (
            "Foreign Minister managing China relations → Huawei advisory board. "
            "Later joined Woodside board — an energy company operating in countries "
            "he dealt with diplomatically."
        ),
        "cooling_off_months": 6,
        "source_url": "https://www.smh.com.au/politics/federal/alexander-downer-joins-woodside-board-20200716-p55cqu.html",
    },
]


def seed(clear_first: bool = True):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS revolving_door (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            party               TEXT,
            last_office         TEXT,
            left_office_year    INTEGER,
            post_office_role    TEXT,
            employer            TEXT,
            sector              TEXT,
            conflict_summary    TEXT,
            portfolio_overlap   TEXT,
            cooling_off_months  INTEGER,
            source_url          TEXT,
            added_date          TEXT
        )
    ''')

    if clear_first:
        c.execute("DELETE FROM revolving_door")
        print("Cleared existing revolving door entries.")

    for r in CASES:
        c.execute('''
            INSERT INTO revolving_door
                (name, party, last_office, left_office_year, post_office_role,
                 employer, sector, conflict_summary, portfolio_overlap,
                 cooling_off_months, source_url, added_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r["name"], r.get("party", ""), r.get("last_office", ""),
            r.get("left_office_year"), r.get("post_office_role", ""),
            r.get("employer", ""), r.get("sector", ""),
            r.get("conflict_summary", ""), r.get("portfolio_overlap", ""),
            r.get("cooling_off_months"), r.get("source_url", ""),
            TODAY,
        ))

    conn.commit()
    conn.close()
    print(f"Seeded {len(CASES)} revolving door cases.")


if __name__ == "__main__":
    seed()
