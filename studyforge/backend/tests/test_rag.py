import tempfile

from app.rag.chunking import PageText, chunk_pages
from app.rag.vector_store import UserVectorStore


def test_chunking_respects_size_and_overlap():
    long_text = " ".join(f"word{i}" for i in range(500))
    pages = [PageText(page_number=1, text=long_text, source_method="text")]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 100
        assert c.page_number == 1


def test_chunking_rejects_bad_overlap():
    import pytest

    with pytest.raises(ValueError):
        chunk_pages([PageText(1, "text", "text")], chunk_size=50, overlap=50)


def test_chunking_skips_empty_pages():
    pages = [
        PageText(page_number=1, text="   ", source_method="text"),
        PageText(page_number=2, text="Real content here.", source_method="text"),
    ]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].page_number == 2


def test_vector_store_retrieves_relevant_chunk():
    with tempfile.TemporaryDirectory() as tmp:
        store = UserVectorStore(tmp, user_id=1)
        corpus = [
            "Photosynthesis converts light energy into chemical energy in plants.",
            "The mitochondria organelle produces cellular energy through respiration.",
            "Newton's second law relates force, mass, and acceleration.",
        ]
        store.rebuild(corpus)

        results = store.search("Which organelle produces cellular energy through respiration?", top_k=1)
        assert len(results) == 1
        assert results[0].row_index == 1  # the mitochondria sentence


def test_vector_store_empty_corpus_returns_no_results():
    with tempfile.TemporaryDirectory() as tmp:
        store = UserVectorStore(tmp, user_id=2)
        store.rebuild([])
        assert store.search("anything", top_k=3) == []


def test_vector_store_persists_across_instances():
    with tempfile.TemporaryDirectory() as tmp:
        store1 = UserVectorStore(tmp, user_id=3)
        store1.rebuild(["apples and oranges", "cars and trucks"])

        store2 = UserVectorStore(tmp, user_id=3)  # fresh instance, same directory
        results = store2.search("apples", top_k=1)
        assert len(results) == 1


def test_topic_clustering_groups_similar_chunks():
    with tempfile.TemporaryDirectory() as tmp:
        store = UserVectorStore(tmp, user_id=4)
        corpus = [
            "Python variables store data values.",
            "Python functions group reusable code.",
            "The French Revolution began in 1789.",
            "The French Revolution ended the monarchy.",
        ]
        store.rebuild(corpus)
        labels = store.cluster_topics(n_clusters=2)

        assert len(labels) == 4
        assert labels[0] == labels[1]  # both Python sentences cluster together
        assert labels[2] == labels[3]  # both history sentences cluster together
        assert labels[0] != labels[2]
