"""System tools errors"""


class ContainerNotRunningException(Exception):
    """Container is not currently running"""


class CommandException(Exception):
    """Custom Exception raises if error occurs during command execution"""


class VirtualizationException(Exception):
    """Virtualization is not setting properly"""


class DependenciesException(Exception):
    """Dependency is not setting properly"""


class BusyPortException(Exception):
    """There is process in port"""
