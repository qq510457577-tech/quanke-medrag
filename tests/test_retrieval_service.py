import unittest

from medrag_backend.app.config import REFERENCE_DIR
from medrag_backend.app.services.retrieval_service import LocalVectorRetriever


class RetrievalServiceTest(unittest.TestCase):
    def test_vector_store_files_exist_after_build(self) -> None:
        retriever = LocalVectorRetriever()
        self.assertTrue(REFERENCE_DIR.exists())
        self.assertTrue(retriever.ready)

    def test_retrieve_references(self) -> None:
        retriever = LocalVectorRetriever()
        results = retriever.retrieve_as_references("胸痛 胸闷 急性冠脉综合征 心电图", top_k=3)
        self.assertTrue(results)
        self.assertTrue(any(item.get("evidence_paragraphs") for item in results))


if __name__ == "__main__":
    unittest.main()

