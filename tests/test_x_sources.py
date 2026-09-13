from app.services.news_collector import build_all_sources, build_x_sources, parse_extra_feeds


def test_build_x_sources_makes_rsshub_urls():
    sources = build_x_sources("Reuters, @elonmusk , bad-handle!", "https://rsshub.app")
    assert [(s.name, s.url) for s in sources] == [
        ("X @Reuters", "https://rsshub.app/twitter/user/Reuters"),
        ("X @elonmusk", "https://rsshub.app/twitter/user/elonmusk"),
    ]


def test_parse_extra_feeds_skips_bad_entries():
    sources = parse_extra_feeds(
        "My Blog|https://example.com/feed;bad-entry;X @NASA|https://rsshub.app/twitter/user/NASA"
    )
    assert [(s.name, s.url) for s in sources] == [
        ("My Blog", "https://example.com/feed"),
        ("X @NASA", "https://rsshub.app/twitter/user/NASA"),
    ]


def test_build_all_sources_includes_20_plus_x():
    sources = build_all_sources("Reuters", "https://rsshub.app", "")
    assert len(sources) == 21
    assert sources[-1].name == "X @Reuters"
