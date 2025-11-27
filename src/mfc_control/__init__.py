"""
MFC Control System

A Python application for controlling Bronkhorst Mass Flow Controllers
in combustion experiments.

Example usage:
    >>> from mfc_control import MFCController, Calibration
    >>> 
    >>> # Create controller for real hardware
    >>> controller = MFCController(use_mock=False)
    >>> 
    >>> # Discover devices on the network
    >>> devices = controller.discover("COM1")
    >>> for dev in devices:
    ...     print(f"Node {dev.address}: {dev.device_type}")
    >>> 
    >>> # Add MFCs
    >>> controller.add_mfc("CH4", "COM1", 1, "CH4")
    >>> controller.get_mfc("CH4").set_flow_real(0.2)
"""

from mfc_control.core.calibration import Calibration
from mfc_control.core.controller import MFCController
from mfc_control.core.mfc import MFC, CoriFlowMeter
from mfc_control.core.safety import SafetyManager
from mfc_control.combustion.properties import GasProperties, get_gas_properties
from mfc_control.combustion.calculations import (
    calculate_phi,
    calculate_power,
    solve_volume_mode,
    solve_power_mode,
)
from mfc_control.hardware.mock import MockMFC, MockCoriFlow
from mfc_control.hardware.connection import (
    ConnectionManager,
    DiscoveredDevice,
    PortInfo,
    discover_devices,
    list_available_ports,
)

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "MFC",
    "CoriFlowMeter", 
    "MFCController",
    "Calibration",
    "SafetyManager",
    # Combustion
    "GasProperties",
    "get_gas_properties",
    "calculate_phi",
    "calculate_power",
    "solve_volume_mode",
    "solve_power_mode",
    # Hardware/Mock
    "MockMFC",
    "MockCoriFlow",
    # Connection/Discovery
    "ConnectionManager",
    "DiscoveredDevice",
    "PortInfo",
    "discover_devices",
    "list_available_ports",
]
