import asyncio
import io
import unittest
import openpyxl
from fastapi import UploadFile, HTTPException
from comparison import match_details, dimensions, materials, compare_row, reprice, PAN_HOME_BENCHMARK
from main import compare_file, export_excel, CompareItem, ExportRequest
import json
from pathlib import Path

# Rules are tested against a fixed catalog, so refreshing src/benchmark.json from Pan Home
# does not break them. Same fixture as the frontend tests.
FIXTURE = Path(__file__).resolve().parents[2] / 'tests/fixtures/benchmark.test.json'
_LIVE_CATALOG = dict(PAN_HOME_BENCHMARK)

def setUpModule():
    PAN_HOME_BENCHMARK.clear()
    PAN_HOME_BENCHMARK.update(json.loads(FIXTURE.read_text(encoding='utf-8'))['products'])

def tearDownModule():
    PAN_HOME_BENCHMARK.clear()
    PAN_HOME_BENCHMARK.update(_LIVE_CATALOG)

class ComparisonTests(unittest.TestCase):
    def test_classification(self):
        for desc,material,category in [('Planter','Poly Rattan','Planter'),('Wall décor','Rattan','Wall Decor'),
                                       ('Paper Tray','Paper','Tray'),('Paper storage','Paper','Storage')]:
            result=match_details(desc,material,'30x30x60cm')
            self.assertEqual(result['category'],category)
            self.assertIsNone(result['product'])

    def test_dimensions_and_material(self):
        self.assertEqual(dimensions('45 × 45 x H 50 cm'),[45,45,50])
        self.assertIsNone(dimensions('D30/36 x H63 cm'))
        self.assertEqual(materials('Poly Rattan'),['poly_rattan'])
        self.assertEqual(materials('Julte / Bamboo'),['jute','bamboo','natural_fiber'])

    def test_size_rounding_tolerance(self):
        ok=match_details('Lamp full with Uno Shade set;\nFull size:36x36xH60 cm','Bamboo Capiz','36x36xH59.5cm')
        self.assertEqual(ok['match_status'],'candidate')
        bad=match_details('Lamp full with Uno Shade set;\nFull size:36x36xH62 cm','Bamboo Capiz','36x36xH59.5cm')
        self.assertEqual(bad['match_status'],'review')

    def test_natural_fiber_group(self):
        result=match_details('Lamp full with Uno Shade set;\nFull size:47x47xH146 cm','rattan, color natural','47x47xH146cm')
        self.assertEqual(result['product']['title'],PAN_HOME_BENCHMARK['FLOOR_LAMP_OKRA_TALL']['title'])

    def test_reprice(self):
        item=compare_row(dict(ref='A',desc='Table lamp',mat_color='Bamboo Capiz',size='30x30x60cm',fob_price=10),0,3.6725)
        self.assertEqual(reprice([item],4)['items'][0]['retail_usd'],82.75)
        with self.assertRaises(ValueError): reprice([item],0)

    def test_import_and_export_unmatched(self):
        async def run():
            book=openpyxl.Workbook();sheet=book.active
            for row in [['','Ref','Description','Material','Size','FOB'],
                        ['','A','Planter','Rattan','30x30x60cm',20],
                        ['','B','Planter','Rattan','30x30x60cm','12 USD'],
                        ['','C','Planter','Rattan','30x30x60cm',0],
                        ['','D','Planter','Rattan','30x30x60cm',-5]]: sheet.append(row)
            stream=io.BytesIO();book.save(stream)
            result=await compare_file(UploadFile(file=io.BytesIO(stream.getvalue())),3.6725)
            self.assertEqual(len(result['items']),1)
            self.assertIsNone(result['items'][0]['retail_aed'])
            self.assertEqual(len(result['warnings']),3)
            with self.assertRaises(HTTPException): await compare_file(UploadFile(file=io.BytesIO(stream.getvalue())),0)
            response=export_excel(ExportRequest(items=[CompareItem(**result['items'][0])]))
            data=b''.join([chunk async for chunk in response.body_iterator])
            output=openpyxl.load_workbook(io.BytesIO(data))
            self.assertIsNone(output.active['I5'].value)
            self.assertIsNone(output.active['J5'].value)
            self.assertIsNone(output.active['K5'].value)
            self.assertEqual(output.active['N5'].value,'Chưa có đối chiếu')
        asyncio.run(run())

if __name__=='__main__': unittest.main()
