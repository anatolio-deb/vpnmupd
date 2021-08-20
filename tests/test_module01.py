from datetime import datetime
from unittest import TestCase

from vpnmupd import versions


class TestClass01(TestCase):
    """Software dependency versions compared"""

    def setUp(self) -> None:
        super().setUp()
        self.any_string = "Some string containing v1.1.1"

    def test_case01(self):
        """Version extraction"""
        version = versions.extract_version(self.any_string)
        self.assertEqual(version, "1.1.1")

    def test_case02(self):
        """Version power calculation"""
        version = versions.get_version_power("1.1.1")
        self.assertEqual(version, 111)

    def test_case03(self):
        """Version power calculation compared"""
        version1 = versions.get_version_power("1.1.1")
        version2 = versions.get_version_power("0.2.1")
        self.assertGreater(version1, version2)

    def test_case04(self):
        """Datetime version"""
        version = versions.get_version_power("2021.1.1")
        self.assertTrue(isinstance(version, datetime))

    def test_case05(self):
        """Datetime versions compare"""
        version = versions.get_version_power("2020.1.1")
        version2 = versions.get_version_power("2021.1.1")
        self.assertGreater(version2, version)
