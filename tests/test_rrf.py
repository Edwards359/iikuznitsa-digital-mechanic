from app.rag import rrf_fusion


def test_rrf_prefers_consensus() -> None:
    bm25 = [0, 1, 2, 3]
    dense = [1, 0, 5, 2]
    merged = rrf_fusion([bm25, dense], k=60, limit=10)
    top_two = [index for index, _ in merged[:2]]
    assert 0 in top_two and 1 in top_two


def test_rrf_single_list() -> None:
    merged = rrf_fusion([[2, 0, 1]], k=10, limit=3)
    assert [index for index, _ in merged] == [2, 0, 1]