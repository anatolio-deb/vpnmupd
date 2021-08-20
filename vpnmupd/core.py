"""A module to check vpnm's and reated dependecies version updates"""

from __future__ import annotations

import json
import pathlib
import subprocess
import threading
import zipfile
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union
from urllib.request import Request, urlopen

from anyd import logging

from vpnmupd import versions


class GitHubRelease:
    """Gets an asset from the latest release in the given GitHub repository"""

    api_request_template = "https://api.github.com/repos/{}/{}/releases/latest"
    headers: Dict = {"User-Agent": "Mozilla/5.0"}
    browser_download_url: str = ""
    version: str = ""

    def __init__(self, filename: str, github_user: str, github_repo: str) -> None:
        self.filename = filename
        self.api_request_url = self.api_request_template.format(
            github_user, github_repo
        )

    def _get_json_response(self) -> Dict:
        request = Request(self.api_request_url, headers={"User-Agent": "Mozilla/5.0"})

        with urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_version(self) -> Any:
        """Get the version of a GitHub Releases asset's tag name

        Returns:
            [str]: a tag of version
        """
        response = self._get_json_response()

        for asset in response["assets"]:
            if asset["name"] == self.filename:
                self.version = versions.extract_version(response["tag_name"])
                self.browser_download_url = asset["browser_download_url"]

        if self.version:
            return versions.get_version_power(self.version)
        return self.version


class AbstractBaseFile(ABC):
    """Represents a downloaded file"""

    def __init__(self, filename: str) -> None:
        self.location: pathlib.Path = self.container / filename
        self.filename: str = filename

    @property
    @abstractmethod
    def container(self):
        """A directory containing the file"""


class DataFile(AbstractBaseFile):
    """Represents a data file in the archive"""

    container = pathlib.Path("/usr/local/bin")

    def chmod(self) -> subprocess.CompletedProcess:
        """Makes file readable after extraction from a ZIP archive"""
        proc = subprocess.run(
            ["chmod", "ugo+r", self.location], check=False, capture_output=True
        )
        return proc


class Executable(DataFile):
    """Represents a downloaded executable file"""

    version: str = ""

    def get_version(self) -> Any:
        """Gets a version of a local dependency software

        Raises:
            subprocess.CalledProcessError: An executable does not exist

        Returns:
            [str]: a version of an executable
        """
        try:
            if self.location.exists():
                proc = subprocess.run(
                    [self.location.as_posix(), "--version"],
                    check=True,
                    capture_output=True,
                )
            else:
                raise FileNotFoundError()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self.version
        else:
            self.version = versions.extract_version(proc.stdout.decode())
            return versions.get_version_power(self.version)

    def chmod(self) -> subprocess.CompletedProcess:
        """Makes a file executable

        Returns:
            subprocess.CompletedProcess: To check the returncode on the client
        """
        proc = subprocess.run(
            ["chmod", "ugo+x", self.location], check=False, capture_output=True
        )
        return proc


class Acrhive(AbstractBaseFile):
    """Represents a downloaded ZIP arhive"""

    container = pathlib.Path("/tmp")
    results: List[subprocess.CompletedProcess] = []

    def __init__(
        self, filename: str, extractables: List[Union[Executable, DataFile]]
    ) -> None:
        super().__init__(filename)
        self.extractables = extractables

    def extract(self) -> List[subprocess.CompletedProcess]:
        """Extract extractables from a ZIP archive

        Returns:
            [List[subprocess.CompletedProcess]]: A completed processes of chmod
            command for each of extractables
        """
        with zipfile.ZipFile(self.location, "r") as zip_ref:
            for member in zip_ref.infolist():
                for extractable in self.extractables:
                    if member.filename == extractable.filename:
                        zip_ref.extract(member, extractable.container)
                        self.results.append(extractable.chmod())
        return self.results


class Dependency:
    """Represents a dependency software from GitHub"""

    acrhive: Acrhive | None = None
    extractables: List[Union[Executable, DataFile]] = []
    updatable: bool = False
    results: List[subprocess.CompletedProcess] = []
    content_length: int = 0

    def __init__(
        self, github_release: GitHubRelease, executable: Executable, verbose: bool
    ) -> None:
        if github_release.filename != executable.filename:
            self.extractables.append(executable)

            if github_release.filename == "v2ray-linux-64.zip":
                self.extractables.extend(
                    [DataFile("geoip.dat"), DataFile("geosite.dat")]
                )

            self.acrhive = Acrhive(github_release.filename, self.extractables)

        self.github_release = github_release
        self.executable = executable
        self.verbose = verbose

    def check(self) -> None:
        """Check dependency's version and mark it as updatable or not"""
        latest_release_version = self.github_release.get_version()
        local_version = self.executable.get_version()

        if latest_release_version and local_version:

            if latest_release_version > local_version:
                self.updatable = True

        if not local_version:
            self.updatable = True

    def download(self) -> None:
        """Download a new version of dependency software

        Returns:
            List[subprocess.CompletedProcess]: completed processes of chmod commands
        """
        request = Request(
            self.github_release.browser_download_url, headers=GitHubRelease.headers
        )

        with urlopen(request) as response:
            self.content_length = response.headers["Content-Length"]

            while True:
                try:
                    if self.acrhive:
                        with open(self.acrhive.location, "wb") as file:
                            file.write(response.read())

                        self.results = self.acrhive.extract()
                    else:

                        with open(self.executable.location, "wb") as file:
                            file.write(response.read())

                        self.results.append(self.executable.chmod())
                except OSError:
                    proc = subprocess.run(
                        ["pkill", self.executable.filename],
                        check=True,
                        capture_output=True,
                    )

                    if self.verbose and proc.stdout:
                        print(proc.stdout.decode())
                else:
                    break


class SystemdUnit(AbstractBaseFile):
    # TODO: create a library with transient decorator
    container = pathlib.Path("/etc/systemd/system")
    content: str = ""

    def __init__(self, executable: Executable, verbose: bool) -> None:
        super().__init__(f"{executable.filename}.service")
        self.content = f"""[Unit]
Description={executable.filename}
After=network-online.target
Wants=network-online.target

[Service]
Restart=on-failure
ExecStart={executable.location.as_posix()}

[Install]
WantedBy=multi-user.target"""
        self.verbose = verbose
        self.executable = executable

    def start(self) -> bool:
        if not self.is_active():
            try:
                proc = subprocess.run(
                    ["systemctl", "enable", "--now", self.filename],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as ex:
                logging.exception(ex)
            else:
                if self.verbose and proc.stdout:
                    logging.info(proc.stdout.decode())
        return self.is_active()

    def stop(self) -> bool:
        if self.is_active():
            try:
                proc = subprocess.run(
                    ["systemctl", "disable", "--now", self.filename],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as ex:
                logging.exception(ex)
            else:
                if self.verbose and proc.stdout:
                    logging.info(proc.stdout.decode())
        return self.is_active()

    def remove(self) -> bool:
        if self.is_active():
            self.stop()

        if self.location.exists():
            self.location.unlink()

        return self.location.exists()

    def is_active(self) -> bool:
        try:
            proc = subprocess.run(
                ["systemctl", "is-active", self.filename],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            return False

        if "active" in proc.stdout.decode():
            return True
        return False

    def dump(self) -> bool:
        if not self.location.exists():
            with open(self.location, "w") as file:
                file.write(self.content)

            try:
                proc = subprocess.run(
                    ["systemctl", "daemon-reload"], check=True, capture_output=True
                )
            except subprocess.CalledProcessError as ex:
                logging.exception(ex)
            else:
                if self.verbose and proc.stdout:
                    logging.info(proc.stdout.decode())
        return self.location.exists()


class Installer:
    """Updates vpnm's dependencies"""

    metadata = [
        ("tun2socks-linux-amd64.zip", "xjasonlyu", "tun2socks"),
        ("v2ray-linux-64.zip", "v2fly", "v2ray-core"),
        ("cloudflared-linux-amd64", "cloudflare", "cloudflared"),
        ("vpnmd", "anatolio-deb", "vpnmd"),
        ("vpnm", "anatolio-deb", "vpnm"),
    ]
    releases: List[GitHubRelease] = [
        GitHubRelease(filename, github_user, github_repo)
        for filename, github_user, github_repo in metadata
    ]
    executables: List[Executable] = [
        Executable(filename)
        for filename in ["tun2socks-linux-amd64", "v2ray"]
        + [filename[0] for filename in metadata[2:]]
    ]
    dependencies: List[Dependency] = []
    unit: SystemdUnit | None = None

    def __init__(self, verbose: bool) -> None:
        self.verbose = verbose
        self.dependencies = [
            Dependency(release, executable, verbose)
            for release, executable in zip(self.releases, self.executables)
        ]

    def get_updatable_dependencies(self):
        return [dependency for dependency in self.dependencies if dependency.updatable]

    def set_updatable_dependencies(self) -> None:
        """Checks new versions of a software dependencies"""
        for dependency in self.dependencies:
            dependency.check()

    def install_or_update(self, force: bool = False) -> List[Dependency]:
        """Downloads new versions of a software dependencies

        Returns:
            List[Tuple[threading.Thread, Dependency]]: A downloading thread
            and the dependency being downloaded
        """
        dependencies: List[Dependency] = []

        for dependency in self.dependencies:
            if dependency.updatable or force:
                thread = threading.Thread(
                    target=dependency.download, name=dependency.executable.filename
                )

                if dependency.executable.filename is self.metadata[3][0]:
                    self.unit = SystemdUnit(dependency.executable, self.verbose)
                    self.unit.stop()

                thread.start()
                dependencies.append(dependency)

        return dependencies

    def uninstall(self):
        for dependency in self.dependencies:
            if dependency.executable.location.exists():

                if dependency.executable.filename is self.metadata[3][0]:
                    self.unit = SystemdUnit(dependency.executable, self.verbose)
                    self.unit.stop()
                    self.unit.remove()

                while True:
                    try:
                        dependency.executable.location.unlink()
                    except OSError:
                        proc = subprocess.run(
                            ["pkill", dependency.executable.filename],
                            check=True,
                            capture_output=True,
                        )

                        if self.verbose and proc.stdout:
                            print(proc.stdout.decode())
                    else:
                        break
