import io
import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import pymupdf
from design_backend.documents import decode_document, document_inputs
from design_backend.web_sources import TextParser

class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DATA_DIR': self.temp.name}); self.env.start()
    def tearDown(self): self.env.stop(); self.temp.cleanup()
    def test_image_is_vision_input(self):
        raw = io.BytesIO(); Image.new('RGB', (2400,1200), 'white').save(raw, format='PNG')
        meta = decode_document(raw.getvalue(), 'Plan coté.png')
        text, images = document_inputs('[document:' + meta['id'] + ']')
        self.assertIn('Plan coté.png', text); self.assertEqual(len(images),1)
        self.assertEqual(images[0].media_type,'image/jpeg')
    def test_pdf_text_and_page_images_limited(self):
        pdf=pymupdf.open()
        for i in range(8):
            page=pdf.new_page(); page.insert_text((50,60),f'Page {i+1}: dimension 35 mm')
        meta=decode_document(pdf.tobytes(),'dessin.pdf'); pdf.close()
        self.assertEqual(meta['pages'],8); self.assertEqual(meta['pages_read'],6)
        text,images=document_inputs('[document:' + meta['id'] + ']')
        self.assertIn('35 mm',text); self.assertEqual(len(images),6)
        self.assertNotIn('Page 7:',meta['text'])
    def test_invalid_and_oversize_files_rejected(self):
        for raw in (b'not an image', b'', b'x'*(12*1024*1024+1)):
            with self.assertRaises(Exception): decode_document(raw,'bad')
    def test_technical_assets_identified(self):
        parser=TextParser(); parser.feed('<img src="icon.png" alt><img src="logo.png"><img src="dimensions.png"><a href="drawing.pdf">Plan</a>')
        self.assertEqual(parser.assets,['dimensions.png','drawing.pdf'])
    def test_missing_reference_is_reported(self):
        text,images=document_inputs('[document:' + 'a'*24 + ']')
        self.assertIn('indisponible',text); self.assertEqual(images,[])
