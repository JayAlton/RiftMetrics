import tempfile
import unittest
from pathlib import Path
from riftmetrics.storage import connect, stored_ids

class StorageTest(unittest.TestCase):
    def test_empty_database(self):
        with tempfile.TemporaryDirectory() as folder:
            with connect(str(Path(folder) / 'test.db')) as db:
                self.assertEqual(stored_ids(db), set())
                self.assertEqual(db.execute('SELECT COUNT(*) FROM matches').fetchone()[0], 0)

if __name__ == '__main__':
    unittest.main()
