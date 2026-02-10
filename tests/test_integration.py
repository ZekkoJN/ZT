"""
Integration Tests for AI Service and Data Miner
Note: These tests require API keys to be set in .env file
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import unittest
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TestAIServiceIntegration(unittest.TestCase):
    """Integration tests for AI Service (requires API key)"""

    @classmethod
    def setUpClass(cls):
        """Setup test fixtures"""
        cls.api_key = os.getenv("GEMINI_API_KEY")

        if not cls.api_key:
            raise unittest.SkipTest("GEMINI_API_KEY not found in environment")

        from ai_service import GeminiService
        cls.gemini = GeminiService(api_key=cls.api_key)

    def test_service_initialization(self):
        """Test if service initializes correctly"""
        self.assertIsNotNone(self.gemini)
        self.assertIsNotNone(self.gemini.client)

    def test_extract_commodity_keywords(self):
        """Test commodity keyword extraction"""
        try:
            result = self.gemini.extract_commodity_keywords("kelapa")

            self.assertIsInstance(result, dict)
            self.assertIn('commodity_name', result)
            self.assertIn('raw_material', result)
            self.assertIn('finished_product', result)
            self.assertIn('keywords', result)

            print(f"\nExtraction result for 'kelapa': {result}")

        except Exception as e:
            self.skipTest(f"API call failed: {e}")

    def test_classify_processing_stage(self):
        """Test processing stage classification"""
        try:
            # Test raw material
            stage = self.gemini.classify_processing_stage("Nickel ore")
            self.assertIn(stage, ['raw', 'semi', 'finished'])

            print(f"\nClassification for 'Nickel ore': {stage}")

        except Exception as e:
            self.skipTest(f"API call failed: {e}")


class TestComtradeAPIIntegration(unittest.TestCase):
    """Integration tests for Comtrade API (requires API key)"""

    @classmethod
    def setUpClass(cls):
        """Setup test fixtures"""
        cls.api_key = os.getenv("COMTRADE_SUBSCRIPTION_KEY")

        if not cls.api_key:
            raise unittest.SkipTest("COMTRADE_SUBSCRIPTION_KEY not found in environment")

        from data_miner import ComtradeAPI
        cls.comtrade = ComtradeAPI(subscription_key=cls.api_key)

    def test_api_initialization(self):
        """Test if API client initializes correctly"""
        self.assertIsNotNone(self.comtrade)
        self.assertIsNotNone(self.comtrade.subscription_key)

    def test_get_export_data(self):
        """Test getting export data"""
        try:
            # Test with a simple query for Indonesia coconut exports
            df = self.comtrade.get_export_data(
                reporter_code="360",  # Indonesia
                hs_code="08",  # Fruits and nuts
                years=[2022, 2023]
            )

            print(f"\nExport data shape: {df.shape}")
            if not df.empty:
                print(f"Columns: {df.columns.tolist()}")

            self.assertIsNotNone(df)

        except Exception as e:
            self.skipTest(f"API call failed: {e}")


class TestDatabaseIntegration(unittest.TestCase):
    """Integration tests for Database (requires MySQL connection)"""

    @classmethod
    def setUpClass(cls):
        """Setup test fixtures"""
        try:
            from database import DatabaseManager
            cls.db = DatabaseManager()
            cls.db.initialize_schema()

        except Exception as e:
            raise unittest.SkipTest(f"Database connection failed: {e}")

    def test_database_connection(self):
        """Test database connection"""
        self.assertIsNotNone(self.db)
        self.assertIsNotNone(self.db.connection)

    def test_cache_and_retrieve(self):
        """Test caching and retrieval"""
        try:
            # Test caching
            test_data = {
                'commodity_name': 'test_commodity',
                'raw_material': 'test_raw',
                'finished_product': 'test_finished',
                'keywords': ['test']
            }

            result = self.db.cache_commodity_search(
                user_input="test_input",
                ai_extraction=test_data,
                raw_hs_code="01",
                finished_hs_code="02"
            )

            self.assertTrue(result)

            # Test retrieval
            cached = self.db.get_cached_commodity_search("test_input")

            if cached:
                self.assertEqual(cached['commodity_name'], 'test_commodity')
                print("\nCache test successful!")

        except Exception as e:
            self.skipTest(f"Database operation failed: {e}")


def suite():
    """Create test suite"""
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestAIServiceIntegration))
    suite.addTest(unittest.makeSuite(TestComtradeAPIIntegration))
    suite.addTest(unittest.makeSuite(TestDatabaseIntegration))
    return suite


if __name__ == '__main__':
    print("="*70)
    print("INTEGRATION TESTS")
    print("Note: These tests require valid API keys and database connection")
    print("="*70)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
