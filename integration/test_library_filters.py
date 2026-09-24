import unittest
from library_filters import select_rows


class LibraryFiltersTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'name': 'Zebra', 'type': 'movie', 'genres': ['Drama'], '_ctime': '2025'},
                     {'name': 'Alpha', 'type': 'series', 'genres': ['Comedy'], '_ctime': '2026'},
                     {'name': 'Beta', 'type': 'movie'}]

    def test_combined_filters(self):
        self.assertEqual([r['name'] for r in select_rows(self.rows, 'movie', 'az', 'Drama')], ['Zebra'])

    def test_sorts(self):
        self.assertEqual(select_rows(self.rows)[0]['name'], 'Alpha')
        self.assertEqual(select_rows(self.rows, sort='za')[0]['name'], 'Zebra')

    def test_unknown_genres_stay_in_all(self):
        self.assertEqual(len(select_rows(self.rows)), 3)
        self.assertEqual(len(select_rows(self.rows, genre='Missing')), 0)
