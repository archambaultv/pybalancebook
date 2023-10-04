import unittest

from balancebook.csv import CsvFile, CsvConfig, load_csv
import balancebook.errors as bberr

class TestAccount(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", encoding="utf-8-sig")

    def test_errors(self):
        csv_file = CsvFile("tests/csv/wrongdate.csv", self.config)
        with self.assertRaises(bberr.InvalidDateFormat):
            load_csv(csv_file, [("Date", "date", True, True)])

        csv_file = CsvFile("tests/csv/wrongamount.csv", self.config)
        with self.assertRaises(bberr.InvalidAmount):
            load_csv(csv_file, [("Amount", "amount", True, True)])

        csv_file = CsvFile("tests/csv/wrongint.csv", self.config)
        with self.assertRaises(bberr.InvalidInt):
            load_csv(csv_file, [("Id", "int", True, True)]) 

        csv_file = CsvFile("tests/csv/wrongint.csv", self.config)
        with self.assertRaises(bberr.RequiredColumnMissing):
            load_csv(csv_file, [("Toto", "int", True, True)]) 

        csv_file = CsvFile("tests/csv/wrongrequired.csv", self.config)
        with self.assertRaises(bberr.RequiredValueEmpty):
            load_csv(csv_file, [("Amount", "int", True, True)]) 