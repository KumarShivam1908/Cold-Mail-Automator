from yc_scraper.parser import parse_company_links, parse_company_page


def test_parse_company_links_deduplicates_profiles():
    html = '<a href="/companies/acme">Acme</a><a href="/companies/acme">Acme again</a>'
    assert parse_company_links(html) == ["https://www.ycombinator.com/companies/acme"]


def test_parse_company_page_extracts_founders_and_linkedin():
    html = """
    <html><head><title>Acme: Build tools. | Y Combinator</title></head>
    <body>
      <h1>Build tools.</h1><p>Company description.</p>
      <span>Summer 2026</span><a href="https://acme.example">Website</a>
      <a href="/companies?industry=B2B">B2B</a>
      <section><h3>Jane Doe</h3><a href="https://www.linkedin.com/in/janedoe">LinkedIn</a></section>
    </body></html>
    """
    company = parse_company_page(html, "https://www.ycombinator.com/companies/acme")
    assert company.name == "Acme"
    assert company.batch == "Summer 2026"
    assert company.industries == ["B2B"]
    assert company.founders[0].name == "Jane Doe"


def test_parse_company_page_extracts_founder_name_from_profile_card_context():
    html = """
    <html><head><title>Deel: Payroll infra. | Y Combinator</title></head>
    <body>
      <section>
        <div>Alex Bouaziz</div>
        <div>Founder/CEO</div>
        <div>Co-founder & CEO @Deel</div>
        <a href="https://x.com/alexbouaziz">X</a>
        <a href="https://www.linkedin.com/in/alexbouaziz">LinkedIn</a>
      </section>
    </body></html>
    """
    company = parse_company_page(html, "https://www.ycombinator.com/companies/deel")
    assert company.founders[0].name == "Alex Bouaziz"


def test_parse_company_page_prefers_founded_by_names_and_deduplicates_linkedin_variants():
    html = """
    <html><head><title>Ralo: AI-Native Mortgage Broker | Y Combinator</title>
    <meta name="description" content="AI-Native Mortgage Broker. Founded in 2025 by Arjun Lalwani and Helly Shah, Ralo has 2 employees based in New York City.">
    </head>
    <body>
      <h1>AI-Native Mortgage Broker</h1>
      <a href="https://www.linkedin.com/in/arjun-lalwani">LinkedIn</a>
      <a href="https://www.linkedin.com/in/hellyshah">LinkedIn</a>
      <a href="https://www.linkedin.com/in/arjun-lalwani/">LinkedIn</a>
      <a href="https://www.linkedin.com/in/hellyshah/?trk=foo">LinkedIn</a>
    </body></html>
    """
    company = parse_company_page(html, "https://www.ycombinator.com/companies/ralo")
    assert [founder.name for founder in company.founders] == ["Arjun Lalwani", "Helly Shah"]
    assert [founder.linkedin for founder in company.founders] == [
        "https://www.linkedin.com/in/arjun-lalwani",
        "https://www.linkedin.com/in/hellyshah",
    ]
