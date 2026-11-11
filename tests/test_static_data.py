import unittest
from unittest.mock import patch
from riftmetrics.static_data import champion_image, item_image, readable_champion

class AssetTests(unittest.TestCase):
    def test_wukong_image_id(self):
        with patch('riftmetrics.static_data.champion_catalog', return_value={}):
            self.assertTrue(champion_image('Wukong', '16.22.1').endswith('/MonkeyKing.png'))
    def test_empty_items(self):
        self.assertIsNone(item_image(0, '16.22.1'))
        self.assertIsNone(item_image(None, '16.22.1'))
    def test_item_url(self):
        self.assertTrue(item_image(6653, '16.22.1').endswith('/6653.png'))
    def test_display(self):
        self.assertEqual(readable_champion('Chogath'), "Cho'Gath")

if __name__ == '__main__':
    unittest.main()
