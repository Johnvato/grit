"""
Seed media_profiles table with ownership, funding, political leaning,
and trustworthiness data for Australian media outlets.

Trust score: 1-10 scale based on:
  - Editorial independence from owner
  - Transparency of funding/corrections
  - Track record of accuracy (ACMA rulings, Press Council adjudications)
  - Diversity of sources and viewpoints

Run:  python3 seed_media_profiles.py
"""

import sqlite3
import datetime

DB = "grit_cache.db"
TODAY = datetime.date.today().isoformat()

PROFILES = [
    {
        "source_name": "The Australian",
        "owner": "Rupert Murdoch / Lachlan Murdoch",
        "parent_company": "News Corp Australia",
        "funding_model": "Subscriptions + advertising (paywall)",
        "political_leaning": "Centre-right to right",
        "trust_score": 5,
        "trust_method": "Mixed. Strong investigative journalism but editorial page has a well-documented conservative agenda. Campaigns openly on policy issues (climate scepticism, nuclear energy, immigration). Press Council complaints upheld on several occasions.",
        "ownership_notes": (
            "Part of Rupert Murdoch's global media empire. News Corp owns ~65% of Australian "
            "metropolitan newspaper circulation. The Murdoch family's political influence in "
            "Australia is unparalleled — former PM Kevin Rudd led a parliamentary petition "
            "(500,000+ signatures) calling for a Royal Commission into media concentration. "
            "News Corp publications have endorsed the Coalition at every federal election "
            "since 2007 (except selected mastheads in 2022)."
        ),
        "political_interests": (
            "Consistently campaigns against: climate action, the ABC, union power, "
            "immigration, and Labor governments. Consistently campaigns for: lower taxes, "
            "deregulation, nuclear energy, defence spending. The editorial line closely "
            "tracks the interests of resource companies (major advertisers) and the "
            "Coalition parties."
        ),
        "source_url": "https://www.theaustralian.com.au",
    },
    {
        "source_name": "Sky News Australia",
        "owner": "Rupert Murdoch / Lachlan Murdoch",
        "parent_company": "News Corp Australia (Foxtel/Fox Sports)",
        "funding_model": "Pay TV (Foxtel) + free YouTube/social media + advertising",
        "political_leaning": "Right to far-right (opinion programming)",
        "trust_score": 3,
        "trust_method": "News bulletins are generally factual, but prime-time opinion programming (after 6pm) routinely platforms misinformation, conspiracy theories, and partisan commentary. YouTube channel has been temporarily suspended for COVID misinformation. ACMA has investigated multiple broadcasts.",
        "ownership_notes": (
            "Same Murdoch/News Corp ownership as The Australian but operates as a TV/digital "
            "channel. Evening opinion hosts (Bolt, Credlin, Murray, Kenny) are former political "
            "operatives or party-aligned commentators. The channel's free YouTube strategy gives "
            "it outsized influence — it is the most-watched Australian news channel on YouTube "
            "despite low Foxtel subscriber numbers."
        ),
        "political_interests": (
            "The most overtly partisan major media outlet in Australia. Evening programming "
            "functions as advocacy for the Coalition and against Labor, the Greens, and the "
            "crossbench. Has campaigned against: climate policy, Indigenous Voice referendum, "
            "COVID lockdowns, renewable energy. Regular platform for One Nation and UAP positions."
        ),
        "source_url": "https://www.skynews.com.au",
    },
    {
        "source_name": "news.com.au",
        "owner": "Rupert Murdoch / Lachlan Murdoch",
        "parent_company": "News Corp Australia",
        "funding_model": "Free (advertising-funded, high-volume clickbait model)",
        "political_leaning": "Centre-right (news), tabloid sensationalism",
        "trust_score": 4,
        "trust_method": "Aggregation-heavy, often repackages News Corp wire copy and tabloid content. Prioritises engagement over accuracy. Less ideologically driven than The Australian but inherits News Corp editorial framing on major issues.",
        "ownership_notes": (
            "News Corp's free digital portal — the most visited news website in Australia. "
            "Serves as the top of the Murdoch funnel, driving audiences toward paywalled "
            "News Corp mastheads."
        ),
        "political_interests": (
            "Inherits News Corp's centre-right framing but is primarily driven by clicks "
            "rather than ideology. Political coverage tends to favour drama and personality "
            "over policy analysis."
        ),
        "source_url": "https://www.news.com.au",
    },
    {
        "source_name": "Australian Broadcasting Corporation",
        "owner": "Australian Government (independent statutory authority)",
        "parent_company": "ABC (Australian Broadcasting Corporation)",
        "funding_model": "Government-funded (taxpayer, no advertising)",
        "political_leaning": "Centre (perceived centre-left by some studies)",
        "trust_score": 8,
        "trust_method": "Highest trust rating among Australian media in multiple surveys (Reuters Digital News Report, Essential Poll). Independent editorial board. Subject to ACMA oversight. Corrections policy is transparent. Regularly criticised by both sides of politics, which is often cited as evidence of balance.",
        "ownership_notes": (
            "Publicly funded, editorially independent statutory authority. Governed by a "
            "board appointed by the government — leading to periodic accusations of political "
            "stacking. Funding has been cut in real terms by successive governments (both "
            "Labor and Coalition). The ABC is structurally insulated from advertiser pressure "
            "but vulnerable to political funding threats."
        ),
        "political_interests": (
            "No commercial owner with political interests. However, its reliance on government "
            "funding creates an indirect vulnerability — governments that cut ABC funding "
            "(Coalition govts have made $783M in cumulative cuts since 2014) may influence "
            "editorial caution on issues affecting the government of the day. The ABC's "
            "charter requires balance and impartiality."
        ),
        "source_url": "https://www.abc.net.au",
    },
    {
        "source_name": "SBS Australia",
        "owner": "Australian Government (independent statutory authority)",
        "parent_company": "SBS (Special Broadcasting Service)",
        "funding_model": "Government-funded + limited advertising",
        "political_leaning": "Centre",
        "trust_score": 7,
        "trust_method": "High trust in multicultural and international reporting. Smaller newsroom than ABC means less original political journalism. Limited commercial pressure. Subject to ACMA oversight.",
        "ownership_notes": (
            "Publicly funded with a mandate to serve multicultural Australia. Carries limited "
            "advertising (unlike the ABC). Smaller political bureau means less original "
            "investigative work but strong international and immigration coverage."
        ),
        "political_interests": (
            "No commercial owner. Charter focuses on multicultural representation. "
            "Less likely to be targeted by political funding pressure than the ABC."
        ),
        "source_url": "https://www.sbs.com.au",
    },
    {
        "source_name": "The Guardian",
        "owner": "Scott Trust Limited (UK)",
        "parent_company": "Guardian Media Group",
        "funding_model": "Reader contributions (voluntary) + advertising (no paywall)",
        "political_leaning": "Centre-left to left",
        "trust_score": 7,
        "trust_method": "Strong original reporting, particularly on climate, Indigenous affairs, and politics. Transparent funding model (reader-supported). Open corrections policy. Criticised by the right for progressive editorial stance. No billionaire owner with commercial interests.",
        "ownership_notes": (
            "Owned by the Scott Trust, a UK entity whose sole purpose is to secure the "
            "financial and editorial independence of The Guardian in perpetuity. No individual "
            "shareholder or billionaire owner. The Australian edition launched in 2013 and has "
            "become the third most-read quality news site in Australia."
        ),
        "political_interests": (
            "Editorially progressive. Campaigns on: climate action, Indigenous rights, "
            "government transparency, workers' rights. Critical of both major parties but "
            "more sympathetic to Labor and the Greens on policy. The ownership structure "
            "means editorial decisions are not influenced by a proprietor's business interests."
        ),
        "source_url": "https://www.theguardian.com/australia-news",
    },
    {
        "source_name": "SMH.com.au",
        "owner": "Nine Entertainment",
        "parent_company": "Nine Entertainment Co. (chaired by Peter Costello until 2024)",
        "funding_model": "Subscriptions + advertising (paywall)",
        "political_leaning": "Centre to centre-left (historically), shifting centre-right under Nine",
        "trust_score": 6,
        "trust_method": "Strong investigative journalism tradition (Age/SMH have broken major stories). Editorial independence has been questioned since the Nine merger and Peter Costello's appointment as chairman. Some veteran journalists have departed citing editorial pressure.",
        "ownership_notes": (
            "The Sydney Morning Herald and The Age were historically owned by Fairfax Media — "
            "a family-controlled company with a tradition of editorial independence. In 2018, "
            "Fairfax merged with Nine Entertainment (a TV network). Former Liberal Treasurer "
            "Peter Costello became Nine's chairman, raising concerns about political influence "
            "over what were traditionally centre-left mastheads. Costello resigned as chairman "
            "in 2024 after a physical altercation with a journalist."
        ),
        "political_interests": (
            "Under Nine ownership, editorial direction has shifted. The mastheads' opinion pages "
            "have become more centrist/centre-right. Nine's commercial interests in broadcasting "
            "and streaming may influence coverage of media policy. The Costello chairmanship "
            "represented a direct link between a former senior Liberal politician and editorial "
            "oversight of two major mastheads."
        ),
        "source_url": "https://www.smh.com.au",
    },
    {
        "source_name": "The Age",
        "owner": "Nine Entertainment",
        "parent_company": "Nine Entertainment Co.",
        "funding_model": "Subscriptions + advertising (paywall)",
        "political_leaning": "Centre to centre-left",
        "trust_score": 6,
        "trust_method": "Same ownership and trust profile as SMH. Melbourne-based. Strong state politics coverage.",
        "ownership_notes": "Same Nine/ex-Fairfax ownership as SMH. See SMH entry for details.",
        "political_interests": "Same as SMH — see SMH entry.",
        "source_url": "https://www.theage.com.au",
    },
    {
        "source_name": "afr.com",
        "owner": "Nine Entertainment",
        "parent_company": "Nine Entertainment Co.",
        "funding_model": "Subscriptions + advertising (premium paywall)",
        "political_leaning": "Centre-right (pro-business)",
        "trust_score": 6,
        "trust_method": "Australia's premier business/financial newspaper. Strong on economic and corporate reporting. Editorial stance is consistently pro-market, pro-deregulation. Reliable on factual reporting; opinion pages skew right.",
        "ownership_notes": (
            "Same Nine ownership as SMH/The Age. The AFR was always the most conservative "
            "Fairfax masthead. Its audience — business executives, investors, politicians — "
            "creates a natural pro-market editorial orientation."
        ),
        "political_interests": (
            "Editorially supports: lower taxes, deregulation, free trade, smaller government. "
            "Sceptical of: union power, welfare expansion, industry subsidies (though less so "
            "for mining). The AFR's political coverage is policy-heavy and generally reliable, "
            "but its framing consistently privileges business perspectives."
        ),
        "source_url": "https://www.afr.com",
    },
    {
        "source_name": "Crikey",
        "owner": "Private Media Pty Ltd (Eric Beecher)",
        "parent_company": "Private Media",
        "funding_model": "Subscriptions (paywall, no major advertising)",
        "political_leaning": "Centre-left to left (independent)",
        "trust_score": 7,
        "trust_method": "Small but editorially independent. Known for media criticism and political analysis. Subscriber-funded model reduces commercial pressure. Limited resources mean less original reporting but strong commentary and accountability journalism.",
        "ownership_notes": (
            "Owned by Private Media, controlled by Eric Beecher — a former editor of the "
            "SMH. Small team but fiercely independent. No major corporate or political "
            "affiliations. The subscriber-only model means no advertiser influence."
        ),
        "political_interests": (
            "Consistently critical of media concentration (particularly Murdoch), political "
            "spin, and both major parties. Independent media watchdog role. No corporate "
            "owner with policy interests to protect."
        ),
        "source_url": "https://www.crikey.com.au",
    },
    {
        "source_name": "The Conversation",
        "owner": "The Conversation Media Group (non-profit)",
        "parent_company": "Non-profit academic publisher",
        "funding_model": "University funding + philanthropic grants (free, no advertising)",
        "political_leaning": "Centre (academic/evidence-based)",
        "trust_score": 9,
        "trust_method": "All articles written by academics with peer review and editorial oversight. Transparent author disclosures (funding, affiliations). No advertising. Corrections are prominent. Highest factual accuracy rating of any Australian outlet in independent assessments.",
        "ownership_notes": (
            "Non-profit funded by Australian universities and philanthropic organisations. "
            "No commercial owner. Authors are required to disclose all conflicts of interest. "
            "Articles undergo editorial and academic review."
        ),
        "political_interests": (
            "No owner with political interests. The evidence-based model means coverage "
            "follows research rather than editorial ideology. Criticised by some on the right "
            "as reflecting an academic 'groupthink' on climate and social issues."
        ),
        "source_url": "https://theconversation.com/au",
    },
    {
        "source_name": "9News",
        "owner": "Nine Entertainment",
        "parent_company": "Nine Entertainment Co.",
        "funding_model": "Free-to-air television + digital advertising",
        "political_leaning": "Centre",
        "trust_score": 5,
        "trust_method": "Mainstream commercial TV news. Prioritises brevity, visuals, and audience ratings over depth. Generally factual but shallow on policy. Same Nine ownership concerns as SMH.",
        "ownership_notes": "Nine Entertainment — see SMH entry for ownership details.",
        "political_interests": "Commercial TV news is driven by ratings more than ideology. Coverage tends to follow polling and personality rather than policy substance.",
        "source_url": "https://www.9news.com.au",
    },
    {
        "source_name": "7NEWS",
        "owner": "Kerry Stokes",
        "parent_company": "Seven West Media",
        "funding_model": "Free-to-air television + digital advertising",
        "political_leaning": "Centre to centre-right",
        "trust_score": 5,
        "trust_method": "Commercial TV news — same ratings-driven model as Nine. Kerry Stokes' personal relationships with political figures (including close friendship with various PMs) raise questions about editorial independence on certain stories.",
        "ownership_notes": (
            "Controlled by billionaire Kerry Stokes through Seven Group Holdings. Stokes "
            "has extensive mining and industrial interests (through SGH's stake in WesCEF, "
            "Beach Energy, and Boral). His personal relationships with political leaders "
            "across both parties are well-documented."
        ),
        "political_interests": (
            "Stokes' mining and industrial interests create potential conflicts when Seven "
            "covers resources policy, energy, and environmental regulation. His support for "
            "Ben Roberts-Smith's defamation case against Nine (at a cost of tens of millions) "
            "demonstrated willingness to use corporate resources in matters adjacent to media coverage."
        ),
        "source_url": "https://7news.com.au",
    },
    {
        "source_name": "The Canberra Times",
        "owner": "Australian Community Media (ACM)",
        "parent_company": "ACM (formerly Fairfax regional, now owned by Antony Catalano)",
        "funding_model": "Subscriptions + advertising",
        "political_leaning": "Centre",
        "trust_score": 6,
        "trust_method": "Strong federal politics coverage due to Canberra location. Reliable on factual reporting. Reduced resources since separation from Fairfax/Nine.",
        "ownership_notes": (
            "Owned by Antony Catalano's Australian Community Media, which purchased the "
            "former Fairfax regional mastheads. Smaller newsroom than when it was part of Fairfax."
        ),
        "political_interests": "No major political agenda. Proximity to Parliament House makes it a useful source for federal politics coverage.",
        "source_url": "https://www.canberratimes.com.au",
    },
    {
        "source_name": "The Saturday Paper",
        "owner": "Morry Schwartz",
        "parent_company": "Schwartz Media",
        "funding_model": "Subscriptions (paywall)",
        "political_leaning": "Centre-left",
        "trust_score": 7,
        "trust_method": "Long-form investigative journalism. Small team but high editorial standards. Subscriber-funded. Known for breaking political stories and detailed policy analysis.",
        "ownership_notes": (
            "Owned by Morry Schwartz, a property developer and philanthropist who also "
            "publishes The Monthly and Quarterly Essay. Schwartz has stated he does not "
            "interfere with editorial decisions. The publications are understood to operate "
            "at a loss, subsidised by Schwartz's other business interests."
        ),
        "political_interests": (
            "Editorially independent despite single-owner structure. Progressive editorial "
            "stance. Strong on: government accountability, Indigenous affairs, environment. "
            "Schwartz's property interests have not visibly influenced coverage."
        ),
        "source_url": "https://www.thesaturdaypaper.com.au",
    },
]


def seed(clear_first: bool = True):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS media_profiles (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name         TEXT    NOT NULL UNIQUE,
            owner               TEXT,
            parent_company      TEXT,
            funding_model       TEXT,
            political_leaning   TEXT,
            trust_score         INTEGER,
            trust_method        TEXT,
            ownership_notes     TEXT,
            political_interests TEXT,
            source_url          TEXT,
            added_date          TEXT
        )
    ''')

    if clear_first:
        c.execute("DELETE FROM media_profiles")
        print("Cleared existing media profiles.")

    for p in PROFILES:
        c.execute('''
            INSERT OR REPLACE INTO media_profiles
                (source_name, owner, parent_company, funding_model,
                 political_leaning, trust_score, trust_method,
                 ownership_notes, political_interests, source_url, added_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            p["source_name"], p.get("owner", ""), p.get("parent_company", ""),
            p.get("funding_model", ""), p.get("political_leaning", ""),
            p.get("trust_score"), p.get("trust_method", ""),
            p.get("ownership_notes", ""), p.get("political_interests", ""),
            p.get("source_url", ""), TODAY,
        ))

    conn.commit()
    conn.close()
    print(f"Seeded {len(PROFILES)} media profiles.")


if __name__ == "__main__":
    seed()
