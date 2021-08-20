import argparse
import threading
import time

import schedule
from anyd import Appd

from vpnmupd import utils
from vpnmupd.core import Executable, Installer, SystemdUnit

parser = argparse.ArgumentParser(
    prog="vpnmupd", description="An update daemon for vpnm"
)
parser.add_argument(
    "-uninstall",
    action="store_true",
    default=False,
    help="Uninstall vpnm and dependencies",
)
parser.add_argument(
    "-update",
    action="store_true",
    default=False,
    help="Install vpnm or update an existing installation",
)
parser.add_argument("--verbose", action="store_true", default=False)

args = parser.parse_args()
installer = Installer(args.verbose)

if args.update:
    # TODO: Welcome message
    installer.set_updatable_dependencies()
    dependencies = installer.install_or_update()

    for dependency in dependencies:
        utils.start_dependency_download_thread(dependency)

    executable = Executable("vpnmupd")
    unit = SystemdUnit(executable, verbose=False)
    unit.content = unit.content.replace(
        unit.executable.location.as_posix(),
        f"python3 -m {executable.filename}",
    )
    if unit.dump():
        if not unit.start():
            raise RuntimeError(f"{unit.filename} is not started")
    else:
        raise FileNotFoundError(unit.location.as_posix())
elif args.uninstall:
    installer.uninstall()
else:
    address = ("localhost", 3445)
    appd = Appd(address)

    schedule.every().day.do(installer.set_updatable_dependencies)

    def job():
        """Cheks updates daily"""
        while True:
            schedule.run_pending()
            time.sleep(1)

    thread = threading.Thread(target=job)
    thread.start()

    @appd.api
    def check():
        """API endpoint to check updates"""
        return installer.get_updatable_dependencies()

    @appd.api
    def install():
        """API endpoint to install updates"""
        return installer.install_or_update()

    @appd.api
    def restart_vpnmd():
        if installer.unit:
            if installer.unit.dump():
                started = installer.unit.start()
            installer.unit = None
            return started
        return True

    appd.start()
