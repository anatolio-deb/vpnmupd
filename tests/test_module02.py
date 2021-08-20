from unittest import TestCase

from vpnmupd.core import Installer


class TestClass01(TestCase):
    """Checks dependencies' version updates and downloads them"""

    installer = Installer(verbose=False)

    def setUp(self) -> None:
        super().setUp()
        self.installer.set_updatable_dependencies()

    def test_case01(self):
        """Downloads updates on the clean filesystem"""
        self.assertTrue(
            all(dependency.updatable for dependency in self.installer.dependencies)
        )

        threads = self.installer.install_or_update()

        for thread, dependency in threads:
            self.assertEqual(thread.name, dependency.executable.filename)
            thread.join()

        self.assertTrue(
            all(
                dependency.executable.location.exists()
                for dependency in self.installer.dependencies
            )
        )
