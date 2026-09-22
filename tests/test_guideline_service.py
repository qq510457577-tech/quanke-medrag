import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'medrag_backend'))
from app.services.guideline_service import GuidelineService, parse_guideline, parse_search, official_url
from app.services.llm_service import GuidelineLinks, ClinicalModelError


SEARCH = '<a href="/guidance/ng120">Test guideline (NG120)</a><a href="https://evil.test/guidance/ng9">Not official</a>'
PAGE = '''<h1>Test guideline</h1><time datetime="2020-01-01"></time><time datetime="2025-01-01"></time>
<article class="recommendation" id="ng120-1_1_1"><h4 class="recommendation__number">1.1.1</h4>
<div class="recommendation__body"><p>Do not assume that an unknown test result is normal.</p></div></article>'''
URL = 'https://www.nice.org.uk/guidance/ng120/chapter/recommendations'


class GuidelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        def handler(request):
            self.requests.append(request)
            return httpx.Response(200, headers={'content-type': 'text/html'},
                                  text=SEARCH if request.url.path == '/search' else PAGE)
        self.service = GuidelineService(httpx.MockTransport(handler))
        self.llm = AsyncMock()

    def citation(self, **changes):
        return {'diagnosis_index': 0, 'source_id': 'nice:ng120:ng120-1_1_1',
                'quote': 'Do not assume that an unknown test result is normal.',
                'translation': '不能将未知检查结果视为正常。', 'applicability': '检查结果未知',
                'limitations': '仅为测试条文', 'relation': 'evaluation', **changes}

    async def test_metadata_exact_quote_and_per_diagnosis_attachment(self):
        self.llm.link_guidelines.return_value = GuidelineLinks(citations=[self.citation()])
        report = {'diagnoses': [{'disease': '测试方向', 'guideline_query': 'acute cough'},
                                {'disease': '另一方向', 'guideline_query': ''}]}
        await self.service.annotate(report, {'patient': {'age': 42}}, self.llm)
        ref = report['diagnoses'][0]['references'][0]
        self.assertEqual(ref['quote'], self.citation()['quote'])
        self.assertEqual(ref['highlights'], [ref['quote']])
        self.assertEqual(ref['source_url'], URL + '#ng120-1_1_1')
        self.assertEqual(ref['updated_date'], '2025-01-01')
        self.assertEqual(report['diagnoses'][1]['references'], [])
        self.assertNotIn('42', str(self.requests[0].url))

    async def test_rejects_fabricated_quote_id_and_wrong_diagnosis(self):
        self.llm.link_guidelines.return_value = GuidelineLinks(citations=[
            self.citation(quote='All unknown test results are always normal.'),
            self.citation(source_id='made-up-id'), self.citation(diagnosis_index=1)])
        report = {'diagnoses': [{'guideline_query': 'acute cough'}, {'guideline_query': ''}]}
        await self.service.annotate(report, {}, self.llm)
        self.assertTrue(all(not d['references'] for d in report['diagnoses']))

    async def test_network_failure_does_not_fail_report_or_invent_reference(self):
        self.service.search = AsyncMock(side_effect=httpx.ConnectError('unavailable'))
        report = {'diagnoses': [{'guideline_query': 'acute cough', 'disease': '原报告'}]}
        await self.service.annotate(report, {}, self.llm)
        self.assertEqual(report['diagnoses'][0]['guideline_status'], 'unavailable')
        self.assertEqual(report['diagnoses'][0]['disease'], '原报告')
        self.llm.link_guidelines.assert_not_called()

    async def test_model_failure_does_not_fall_back_to_search_result(self):
        self.llm.link_guidelines.side_effect = ClinicalModelError('failed')
        report = {'diagnoses': [{'guideline_query': 'acute cough'}]}
        await self.service.annotate(report, {}, self.llm)
        self.assertEqual(report['diagnoses'][0]['references'], [])
        self.assertEqual(report['diagnoses'][0]['guideline_status'], 'unavailable')

    async def test_cache_and_redirect_boundaries(self):
        first = await self.service.search('acute cough')
        self.assertEqual(first, await self.service.search('acute cough'))
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(await self.service.search('患者病史'), [])
        def redirect(request):
            return httpx.Response(302, headers={'location': 'http://127.0.0.1/secret'})
        service = GuidelineService(httpx.MockTransport(redirect))
        with self.assertRaises(ValueError):
            await service.search('acute cough')

    def test_parser_ignores_foreign_urls_and_removed_guidelines(self):
        self.assertEqual(len(parse_search(SEARCH)), 1)
        self.assertFalse(official_url('https://www.nice.org.uk.evil.test/guidance/ng120'))
        self.assertFalse(official_url('https://www.nice.org.uk:123/guidance/ng120'))
        self.assertEqual(parse_guideline('<div class="alert">This guideline has been withdrawn</div>'+PAGE, URL, 'ng120'), [])


if __name__ == '__main__':
    unittest.main()
