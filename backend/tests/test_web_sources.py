import unittest
from unittest.mock import patch
from design_backend.web_sources import public_address, retrieve_sources, TextParser

class SourcesTests(unittest.TestCase):
    def test_private_addresses_rejected(self):
        for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '::1'):
            with patch('socket.getaddrinfo', return_value=[(2,1,6,'',(address,80))]):
                with self.assertRaises(ValueError): public_address('example.test',80)
    def test_public_address(self):
        with patch('socket.getaddrinfo', return_value=[(2,1,6,'',('93.184.216.34',443))]):
            self.assertEqual(public_address('example.test',443),'93.184.216.34')
    def test_limit_duplicates_and_failure(self):
        with patch('design_backend.web_sources.fetch_page', side_effect=ValueError('HTTP 403')) as fetch:
            sources=retrieve_sources('https://a.test https://a.test https://b.test https://c.test https://d.test')
            self.assertEqual(len(sources),3); self.assertEqual(fetch.call_count,3)
            self.assertTrue(all(s['status']=='indisponible' for s in sources))
    def test_hidden_scripts(self):
        parser=TextParser(); parser.feed('<h1>Dimensions</h1><script>evil()</script><p>35 mm</p>')
        self.assertEqual(parser.parts,['Dimensions','35 mm'])
