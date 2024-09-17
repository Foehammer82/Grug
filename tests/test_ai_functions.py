from grug.ai_functions import search_archives_of_nethys


def test_aon():
    wizard_search_results = search_archives_of_nethys("wizard")
    assert len(wizard_search_results) > 0
