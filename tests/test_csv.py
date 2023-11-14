import unittest

from balancebook.csv import CsvFile, CsvConfig, load_csv, CsvColumn
import balancebook.errors as bberr

class TestAccount(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", encoding="utf-8-sig")

    def test_errors(self):
        csv_file = CsvFile("tests/csv/wrongdate.csv", self.config)
        with self.assertRaises(bberr.InvalidDateFormat):
            load_csv(csv_file, [CsvColumn("Date", "date", True, True)])

        csv_file = CsvFile("tests/csv/wrongamount.csv", self.config)
        with self.assertRaises(bberr.InvalidAmount):
            load_csv(csv_file, [CsvColumn("Amount", "amount", True, True)])

        csv_file = CsvFile("tests/csv/wrongint.csv", self.config)
        with self.assertRaises(bberr.InvalidInt):
            load_csv(csv_file, [CsvColumn("Id", "int", True, True)]) 

        csv_file = CsvFile("tests/csv/wrongint.csv", self.config)
        with self.assertRaises(bberr.MissingRequiredColumn):
            load_csv(csv_file, [CsvColumn("Toto", "int", True, True)]) 

        csv_file = CsvFile("tests/csv/wrongrequired.csv", self.config)
        with self.assertRaises(bberr.RequiredValueEmpty):
            load_csv(csv_file, [CsvColumn("Amount", "int", True, True)]) 