import json
import tempfile
import unittest
from pathlib import Path

from benchmark_export import build_catalog, dimensions_from_name, export_benchmark, materials_for
from models import ProductItem, load_config
from network_parser import parse_products
from output import OutputWriter

HERE = Path(__file__).resolve().parent


def product(**kw):
    base = dict(sku='181ATO9901024', name='Bistro E27 Rattan Floor Lamp Dia 45x146cm - Natural',
                product_url='https://www.panhomestores.com/uae_en/bistro', regular_price=649, final_price=325,
                app_category='Floor Lamp', filter_materials=['Rattan'], app_materials=['rattan'],
                sources=['listing'], scraped_at_utc='2026-11-06T09:00:00+00:00')
    base.update(kw)
    return ProductItem(**base)


class ExportTests(unittest.TestCase):
    def test_dimensions_from_name(self):
        self.assertEqual(dimensions_from_name('Cerah E27 Abaca Table Lamp Dia 35x53cm - Natural'), [35, 35, 53])
        self.assertEqual(dimensions_from_name('Brooklyn E27 Table Lamp 24x24x40.5cm - White'), [24, 24, 40.5])
        self.assertEqual(dimensions_from_name('Dowan E14 Table Lamp Dia14.2x24.5cm - Off White'), [14.2, 14.2, 24.5])
        self.assertEqual(dimensions_from_name('Levin Led Mini Table Lamp 5w 13x28cm - Black'), [13, 13, 28])
        self.assertIsNone(dimensions_from_name('Rattan Basket - Natural'))

    def test_title_materials_are_added(self):
        # Ceramic lamp listed under the Bamboo filter must not look bamboo-only.
        p = product(name='Ashanti E27 Hand Painted Ceramic Table Lamp 46x53cm - Green', app_materials=['bamboo'])
        self.assertEqual(materials_for(p), ['bamboo', 'ceramic'])
        self.assertEqual(materials_for(product(name='Poly Rattan Planter 40x60cm', app_materials=[])), ['poly_rattan'])

    def test_catalog_entry_keeps_both_prices_and_date(self):
        catalog, skipped = build_catalog([product(), product(sku='X1', name='Rattan Basket - Natural')])
        entry = catalog['181ATO9901024']
        self.assertEqual(entry['price_aed'], 649)
        self.assertEqual(entry['sale_price_aed'], 325)
        self.assertEqual(entry['price_checked_at'], '2026-11-06')
        self.assertEqual(entry['dimensions'], [45, 45, 146])
        self.assertEqual(entry['scope'], 'complete')
        self.assertEqual(len(skipped), 1)

    def test_not_comparable_products_are_left_out(self):
        names = ['Barley Beach Bag 38x36cm-brown', 'Khalari 3-light E27 Rattan Floor Lamp 66x150cm - Natural',
                 'Ajax 3 Tier Planter Stand 50.5x28x75cm- Natural', 'Trevoss Handcrafted Jute Hanging Planter 37x91cm',
                 'Natura 3-piece Trouser Hanger Set 33x16.5x1.2cm', 'Calida 4-tier Bamboo Shoe Rack 68.5x26x75.5cm']
        catalog, skipped = build_catalog([product(sku=f'S{i}', name=n) for i, n in enumerate(names)])
        self.assertEqual(catalog, {})
        self.assertEqual(len(skipped), len(names))
        keep = ['Catelyn Water Hyacinth Laundry Hamper 49x38x58cm', 'Enya Jute Wall Hanging 120x180cm',
                'Bistro E27 Rattan Floor Lamp Dia 45x146cm']
        catalog, _ = build_catalog([product(sku=f'K{i}', name=n) for i, n in enumerate(keep)])
        self.assertEqual(len(catalog), 3)

    def test_export_keeps_tolerances(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = OutputWriter(tmp)
            out.save_products([product()])
            bench = Path(tmp, 'benchmark.json')
            bench.write_text(json.dumps({'dimensionTolerance': 0.2, 'sizeRoundingToleranceCm': 1, 'products': {}}))
            result = export_benchmark(out.products_json, bench, Path(tmp, 'gen.json'))
            data = json.loads(Path(tmp, 'gen.json').read_text(encoding='utf-8'))
            self.assertEqual(result['exported'], 1)
            self.assertEqual(data['dimensionTolerance'], 0.2)
            self.assertIn('181ATO9901024', data['products'])
            self.assertTrue(Path(tmp, 'products_output.csv').read_text(encoding='utf-8-sig').startswith('sku,name'))

    def test_network_parser_reads_magento_graphql(self):
        payload = {'data': {'products': {'items': [{
            'sku': '181ato9900131', 'name': 'Okra E27 Table Lamp 30x60cm - Natural', 'url_key': 'okra',
            'stock_status': 'IN_STOCK', 'small_image': {'url': 'https://img/okra.jpg'},
            'price_range': {'minimum_price': {'regular_price': {'value': 331, 'currency': 'AED'},
                                              'final_price': {'value': 166, 'currency': 'AED'}}}}]}}}
        [item] = parse_products(payload, 'https://www.panhomestores.com/uae_en/')
        self.assertEqual((item.sku, item.regular_price, item.final_price, item.stock_status),
                         ('181ATO9900131', 331, 166, 'IN_STOCK'))

    def test_config_loads(self):
        config = load_config(HERE / 'scrape_config.json')
        self.assertTrue(any(t.name == 'Planter' for t in config.targets))
        self.assertEqual(config.material_aliases['poly wicker'], 'poly_rattan')


if __name__ == '__main__':
    unittest.main()
