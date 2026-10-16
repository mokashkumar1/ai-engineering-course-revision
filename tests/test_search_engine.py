import unittest
from copy import deepcopy

from search_engine import chunks,terms,timing_status


class SearchTests(unittest.TestCase):
    def test_hindi_and_roman_queries_retain_technical_concepts(self):
        for query in ['मल्टी टेनेंट रैग कैसे काम करता है', 'multi tenant RAG kaise kaam karta hai']:
            result=terms(query)
            self.assertIn('rag',result)
            self.assertIn('multi',result)
            self.assertIn('tenant',result)

    def test_chunks_preserve_timestamps_and_do_not_modify_sources(self):
        source=[{'start':i*5,'end':i*5+5,'text':str(i)} for i in range(20)]
        original=deepcopy(source);result=list(chunks(source))
        self.assertEqual(source,original)
        self.assertEqual(result[0][0][0],0)
        self.assertEqual(result[1][0][0],result[0][-1][0])
        self.assertTrue(all(group[-1][1]['end']-group[0][1]['start']<=45 for group in result))
        self.assertEqual({i for group in result for i,_ in group},set(range(20)))

    def test_unreliable_and_out_of_range_times_are_not_presented(self):
        lecture={'duration':100,'timing_eligible':0}
        self.assertEqual(timing_status(lecture,10,20),'unreliable')
        lecture['timing_eligible']=1
        self.assertEqual(timing_status(lecture,10,20),'approximate')
        self.assertEqual(timing_status(lecture,90,110),'unavailable')


if __name__=='__main__':unittest.main()
