"""
Unit Tests for utils.py
Tests HS code cleaning and helper functions
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import unittest
from utils import (
    clean_hs_code,
    extract_hs_codes_from_ai,
    get_best_hs_code,
    get_hs_code_description,
    calculate_cagr,
    calculate_value_added,
    format_currency,
    validate_hscode
)


class TestHSCodeCleaning(unittest.TestCase):
    """Test HS Code cleaning from AI extraction"""

    def test_clean_hs_code_with_dots(self):
        """Test cleaning HS codes with dots"""
        self.assertEqual(clean_hs_code("0801.12"), "080112")
        self.assertEqual(clean_hs_code("1513.11"), "151311")
        self.assertEqual(clean_hs_code("3401.11"), "340111")

    def test_clean_hs_code_with_long_format(self):
        """Test cleaning HS codes longer than 6 digits"""
        self.assertEqual(clean_hs_code("1704.10.00"), "170410")
        self.assertEqual(clean_hs_code("0801.12.00"), "080112")

    def test_clean_hs_code_already_clean(self):
        """Test cleaning already clean HS codes"""
        self.assertEqual(clean_hs_code("080112"), "080112")
        self.assertEqual(clean_hs_code("151311"), "151311")

    def test_clean_hs_code_short_code(self):
        """Test cleaning short HS codes (pad with zeros)"""
        self.assertEqual(clean_hs_code("0801"), "080100")
        self.assertEqual(clean_hs_code("08"), "080000")

    def test_clean_hs_code_invalid(self):
        """Test cleaning invalid HS codes"""
        self.assertIsNone(clean_hs_code(""))
        self.assertIsNone(clean_hs_code(None))
        self.assertIsNone(clean_hs_code("abc"))

    def test_extract_hs_codes_from_ai(self):
        """Test extracting HS codes from AI result"""
        ai_result = {
            "raw_hs_codes": [
                {"code": "0801.12", "description": "Coconuts"},
                {"code": "0801.19", "description": "Coconuts, other"}
            ],
            "semi_hs_codes": [
                {"code": "1513.11", "description": "Coconut oil, crude"}
            ],
            "finished_hs_codes": [
                {"code": "3401.11", "description": "Soap"}
            ]
        }

        raw_codes = extract_hs_codes_from_ai(ai_result, 'raw')
        self.assertEqual(len(raw_codes), 2)
        self.assertEqual(raw_codes[0], "080112")
        self.assertEqual(raw_codes[1], "080119")

        semi_codes = extract_hs_codes_from_ai(ai_result, 'semi')
        self.assertEqual(len(semi_codes), 1)
        self.assertEqual(semi_codes[0], "151311")

    def test_get_best_hs_code(self):
        """Test getting best (first) HS code from AI result"""
        ai_result = {
            "raw_hs_codes": [
                {"code": "0801.12", "description": "Coconuts"},
            ],
            "semi_hs_codes": [],
            "finished_hs_codes": [
                {"code": "3401.11", "description": "Soap"}
            ]
        }

        self.assertEqual(get_best_hs_code(ai_result, 'raw'), "080112")
        self.assertIsNone(get_best_hs_code(ai_result, 'semi'))
        self.assertEqual(get_best_hs_code(ai_result, 'finished'), "340111")

    def test_get_hs_code_description(self):
        """Test getting HS code description from AI result"""
        ai_result = {
            "raw_hs_codes": [
                {"code": "0801.12", "description": "Coconuts, in the inner shell"}
            ]
        }

        desc = get_hs_code_description(ai_result, 'raw', "080112")
        self.assertEqual(desc, "Coconuts, in the inner shell")

        desc_missing = get_hs_code_description(ai_result, 'raw', "999999")
        self.assertEqual(desc_missing, "N/A")


class TestCalculationFunctions(unittest.TestCase):
    """Test calculation helper functions"""

    def test_calculate_cagr_positive_growth(self):
        """Test CAGR calculation with positive growth"""
        cagr = calculate_cagr(100, 150, 3)
        self.assertGreater(cagr, 0)
        self.assertAlmostEqual(cagr, 14.47, places=1)

    def test_calculate_cagr_negative_growth(self):
        """Test CAGR calculation with negative growth"""
        cagr = calculate_cagr(150, 100, 3)
        self.assertLess(cagr, 0)

    def test_calculate_cagr_zero_values(self):
        """Test CAGR with zero values"""
        cagr = calculate_cagr(0, 100, 3)
        self.assertEqual(cagr, 0.0)

    def test_calculate_value_added(self):
        """Test value added calculation"""
        value_added = calculate_value_added(100, 200)
        self.assertEqual(value_added, 100.0)

        value_added = calculate_value_added(50, 75)
        self.assertEqual(value_added, 50.0)

    def test_calculate_value_added_zero_raw(self):
        """Test value added with zero raw price"""
        value_added = calculate_value_added(0, 100)
        self.assertEqual(value_added, 0.0)


class TestFormattingFunctions(unittest.TestCase):
    """Test formatting helper functions"""

    def test_format_currency_usd(self):
        """Test USD currency formatting"""
        formatted = format_currency(1234567.89, "USD")
        self.assertIn("$", formatted)
        self.assertIn("1,234,567.89", formatted)

    def test_format_currency_other(self):
        """Test other currency formatting"""
        formatted = format_currency(1000, "EUR")
        self.assertIn("EUR", formatted)
        self.assertIn("1,000.00", formatted)

    def test_validate_hscode_valid(self):
        """Test HS code validation with valid codes"""
        self.assertTrue(validate_hscode("01"))
        self.assertTrue(validate_hscode("0101"))
        self.assertTrue(validate_hscode("010101"))

    def test_validate_hscode_invalid(self):
        """Test HS code validation with invalid codes"""
        self.assertFalse(validate_hscode(""))
        self.assertFalse(validate_hscode("1"))
        self.assertFalse(validate_hscode("0101011"))
        self.assertFalse(validate_hscode("ABC"))
        self.assertFalse(validate_hscode("01AB"))


def suite():
    """Create test suite"""
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestHSCodeCleaning))
    suite.addTest(unittest.makeSuite(TestCalculationFunctions))
    suite.addTest(unittest.makeSuite(TestFormattingFunctions))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
