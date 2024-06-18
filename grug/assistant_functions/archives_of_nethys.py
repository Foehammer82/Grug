"""AoN (Archives of Nethys) search functionality."""

from elasticsearch import Elasticsearch
from loguru import logger


def search_archives_of_nethys(search_string: str) -> list[dict]:
    """
    Searches the Elasticsearch index for entries matching the given search string within the
    [AON](https://2e.aonprd.com/) (Archives of Nethys) dataset.

    Args:
        search_string (str): The string to search for within the AON dataset.

    Returns:
        list[dict]: A list of dictionaries, each representing a cleaned-up search result. Each dictionary contains
        the keys:
            - name (str): The name of the entry.
            - type (str): The type of the entry (e.g., Ancestry, Class).
            - summary (str, optional): A summary of the entry, if available.
            - sources (list): The sources from which the entry is derived.
            - url (str): The URL to the detailed entry on the AON website.

    Note:
        This function requires the Elasticsearch Python client and assumes access to an Elasticsearch instance with
        the AON dataset indexed under the index named "aon".
    """
    logger.info(f"Searching AoN for: {search_string}")

    es = Elasticsearch("https://elasticsearch.aonprd.com/")

    es_response = es.search(
        index="aon",
        query={
            "function_score": {
                "query": {
                    "bool": {
                        "should": [
                            {"match_phrase_prefix": {"name.sayt": {"query": search_string}}},
                            {"match_phrase_prefix": {"text.sayt": {"query": search_string, "boost": 0.1}}},
                            {"term": {"name": search_string}},
                            {
                                "bool": {
                                    "must": [
                                        {
                                            "multi_match": {
                                                "query": word,
                                                "type": "best_fields",
                                                "fields": [
                                                    "name",
                                                    "text^0.1",
                                                    "trait_raw",
                                                    "type",
                                                ],
                                                "fuzziness": "auto",
                                            }
                                        }
                                        for word in search_string.split(" ")
                                    ]
                                }
                            },
                        ],
                        "must_not": [{"term": {"exclude_from_search": True}}],
                        "minimum_should_match": 1,
                    }
                },
                "boost_mode": "multiply",
                "functions": [
                    {"filter": {"terms": {"type": ["Ancestry", "Class"]}}, "weight": 1.1},
                    {"filter": {"terms": {"type": ["Trait"]}}, "weight": 1.05},
                ],
            }
        },
        sort=["_score", "_doc"],
        aggs={
            "group1": {
                "composite": {
                    "sources": [{"field1": {"terms": {"field": "type", "missing_bucket": True}}}],
                    "size": 10000,
                }
            }
        },
        source={"excludes": ["text"]},
    )

    results_raw = [hit["_source"] for hit in es_response.body["hits"]["hits"]]

    results_clean = [
        {
            "name": hit["name"],
            "type": hit["type"],
            "summary": hit["summary"] if "summary" in hit else None,
            # "overview_markdown": hit["markdown"] if "markdown" in hit else None,
            # "rarity": hit["rarity"] if "rarity" in hit else None,
            "sources": hit["source_raw"],
            "url": f"https://2e.aonprd.com{hit['url']}",
        }
        for hit in results_raw
    ]

    logger.info(
        f'Found {len(results_clean)} results from AoN for "{search_string}": '
        f'{[result["name"] for result in results_clean]}'
    )

    return results_clean


if __name__ == "__main__":
    wizard_search_results = search_archives_of_nethys("wizard")
    print(wizard_search_results)
