from pathlib import Path
import unittest


class CompactEmbeddingTests(unittest.TestCase):
    def test_original_token_ids_and_embedding_directions_are_preserved(self):
        root=Path(__file__).resolve().parents[1]
        cache=root/'.model_cache'
        if not (cache/'sentencepiece.bpe.model').exists():self.skipTest('Local model assets are not installed')
        import numpy as np
        from fastembed import TextEmbedding
        from compact_embedding import CompactEmbedding
        original=TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            cache_dir=str(cache),local_files_only=True,threads=1,providers=['CPUExecutionProvider'])
        compact=CompactEmbedding(cache)
        for query in ['What is RAG?','recursive chunking kaise kaam karti hai?',
                      'रिकर्सिव चंकिंग क्या है?','راگ کیا ہے؟','<mask> test','AI '*200]:
            with self.subTest(query=query[:30]):
                self.assertEqual(original.model.tokenizer.encode(query).ids,compact.token_ids(query))
                a=next(original.query_embed([query])).astype(np.float32)
                b=next(compact.query_embed([query]))
                self.assertGreater(float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))),.99999)


if __name__=='__main__':unittest.main()
