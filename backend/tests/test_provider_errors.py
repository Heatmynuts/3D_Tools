import unittest
from unittest.mock import patch
import httpx
from design_backend.llm.base import LLMError, LLMRequest
from design_backend.llm.openai_compat_provider import OpenAICompatProvider

class ProviderErrorTests(unittest.TestCase):
    def test_rate_limit_preserves_actionable_message(self):
        provider=OpenAICompatProvider('https://example.test','test-model',None)
        response=httpx.Response(429,request=httpx.Request('POST','https://example.test/chat/completions'))
        with patch('design_backend.llm.openai_compat_provider.httpx.post',return_value=response):
            with self.assertRaisesRegex(LLMError,'temporairement limité'): provider.complete(LLMRequest('interview','system','user'))
    def test_stream_style_error_in_success_response(self):
        provider=OpenAICompatProvider('https://example.test','test-model',None)
        response=httpx.Response(200,json={'error':{'code':429,'message':'temporarily rate-limited upstream'}}, request=httpx.Request('POST','https://example.test'))
        with patch('design_backend.llm.openai_compat_provider.httpx.post',return_value=response):
            with self.assertRaisesRegex(LLMError,'concept est conservé'): provider.complete(LLMRequest('interview','system','user'))
