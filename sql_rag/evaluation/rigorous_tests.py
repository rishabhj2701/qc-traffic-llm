import sys
import os
import unittest
import pandas as pd

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_rag.retrieval.query_router import QueryRouter
from sql_rag.models import RouteType

class TestAnalyticalEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router = QueryRouter("traffic_data.db")

    def test_use_case_1_nl_query(self):
        """Test Use Case 1: Natural Language Query Interface"""
        print("\nTesting Use Case 1: NL Query...")
        question = "What is the average volume for Station 725 in September 2019?"
        response = self.router.route_query(question)
        self.assertIn(response.route, [RouteType.SQL, RouteType.CLARIFICATION])
        print(f"Result: {response.answer[:100]}...")

    def test_use_case_2_data_quality(self):
        """Test Use Case 2: Automated Data Quality Narratives"""
        print("\nTesting Use Case 2: Data Quality...")
        question = "Identify any tables with missing values or zero volume outliers for Station 725."
        response = self.router.route_query(question)
        self.assertNotEqual(response.route, RouteType.ERROR)
        print(f"Audit Answer: {response.answer[:100]}...")

    def test_use_case_3_pattern_detection(self):
        """Test Use Case 3: Contextual Pattern Detection"""
        print("\nTesting Use Case 3: Pattern Detection...")
        question = "Analyze the peak hour trends for Station 725 and explain the morning surge."
        response = self.router.route_query(question)
        self.assertNotEqual(response.route, RouteType.ERROR)
        print(f"Pattern Answer: {response.answer[:100]}...")

    def test_global_query(self):
        """Test Global Overview capability"""
        print("\nTesting Global Query...")
        question = "How many unique stations are in the dataset?"
        response = self.router.route_query(question)
        self.assertEqual(response.route, RouteType.SQL)
        print(f"Global Answer: {response.answer}")

if __name__ == "__main__":
    unittest.main()
