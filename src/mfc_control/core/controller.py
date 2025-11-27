"""
MFC Controller - manages a collection of MFC devices.

Provides centralized management of multiple MFCs including:
- Dynamic addition/removal of devices
- Connection management with device discovery
- Coordinated operations (e.g., close all valves)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator, Any

from mfc_control.core.calibration import Calibration, get_default_calibration
from mfc_control.core.mfc import MFC, CoriFlowMeter, FlowDeviceBase
from mfc_control.core.safety import SafetyManager

if TYPE_CHECKING:
    from mfc_control.core.mfc import InstrumentProtocol
    from mfc_control.hardware.connection import DiscoveredDevice

logger = logging.getLogger(__name__)


@dataclass
class MFCController:
    """
    Central controller for managing multiple MFC devices.
    
    Handles device registration, connection management, and provides
    a unified interface for operations that span multiple devices.
    
    Attributes:
        use_mock: If True, use mock devices instead of real hardware
        safety: SafetyManager instance for emergency operations
        
    Example:
        >>> controller = MFCController()
        >>> 
        >>> # Discover devices on the network
        >>> devices = controller.discover("COM1")
        >>> for dev in devices:
        ...     print(f"Found: {dev}")
        >>> 
        >>> # Add MFCs
        >>> controller.add_mfc("CH4", "COM1", 1, "CH4")
        >>> controller.add_mfc("H2", "COM1", 7, "H2")
        >>> controller.connect_all()
        >>> 
        >>> ch4 = controller.get_mfc("CH4")
        >>> ch4.set_flow_real(0.2)
        >>> 
        >>> controller.close_all_valves()
        >>> controller.disconnect_all()
    """
    
    use_mock: bool = False
    _mfcs: dict[str, MFC] = field(default_factory=dict, repr=False)
    _cori_flows: dict[str, CoriFlowMeter] = field(default_factory=dict, repr=False)
    _connection_manager: Any = field(default=None, repr=False)
    _discovery_port: str | None = field(default=None, repr=False)
    safety: SafetyManager = field(init=False, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize safety manager after dataclass init."""
        self.safety = SafetyManager(self)
        
        # Initialize connection manager for real hardware
        if not self.use_mock:
            from mfc_control.hardware.connection import ConnectionManager
            self._connection_manager = ConnectionManager()
    
    # =========================================================================
    # Device Discovery
    # =========================================================================
    
    def discover(self, com_port: str) -> list["DiscoveredDevice"]:
        """
        Scan a COM port for connected MFC devices.
        
        This queries the FLOW-BUS network and returns information about
        all devices found, including their node addresses and types.
        
        Args:
            com_port: Serial port to scan (e.g., "COM1", "/dev/ttyUSB0")
            
        Returns:
            List of DiscoveredDevice objects with address, type, serial number
            
        Raises:
            ConnectionError: If cannot connect to port
            RuntimeError: If in mock mode (no real devices to discover)
            
        Example:
            >>> devices = controller.discover("COM1")
            >>> for dev in devices:
            ...     print(f"Node {dev.address}: {dev.device_type} ({dev.serial})")
            Node 1: F-201CV (M12345678A)
            Node 7: F-201CV (M12345679B)
        """
        if self.use_mock:
            raise RuntimeError(
                "Cannot discover devices in mock mode. "
                "Use MFCController(use_mock=False) for real hardware."
            )
        
        return self._connection_manager.discover_devices(com_port)
    
    def add_discovered_mfc(
        self,
        device: "DiscoveredDevice",
        name: str,
        gas_type: str,
        com_port: str,
        calibration: Calibration | None = None,
        auto_connect: bool = True,
    ) -> MFC:
        """
        Add an MFC from a discovered device.
        
        Convenience method to add a device that was found via discover().
        
        Args:
            device: DiscoveredDevice from discover()
            name: User-friendly name for this MFC
            gas_type: Type of gas ("CH4", "H2", "Air", etc.)
            com_port: COM port the device is on
            calibration: Calibration data, or None to use default
            auto_connect: If True, connect immediately
            
        Returns:
            The created MFC instance
        """
        return self.add_mfc(
            name=name,
            com_port=com_port,
            node_address=device.address,
            gas_type=gas_type,
            calibration=calibration,
            auto_connect=auto_connect,
        )
    
    # =========================================================================
    # Device Management
    # =========================================================================
    
    def add_mfc(
        self,
        name: str,
        com_port: str,
        node_address: int,
        gas_type: str,
        calibration: Calibration | None = None,
        auto_connect: bool = True,
    ) -> MFC:
        """
        Add a new MFC to the controller.
        
        Args:
            name: Unique identifier for this MFC
            com_port: Serial port (e.g., "COM1", "/dev/ttyUSB0")
            node_address: FLOW-BUS node address (1-127)
            gas_type: Type of gas ("CH4", "H2", "Air", etc.)
            calibration: Calibration data, or None to use default
            auto_connect: If True, connect immediately after adding
            
        Returns:
            The created MFC instance
            
        Raises:
            ValueError: If name already exists
        """
        if name in self._mfcs:
            raise ValueError(f"MFC with name '{name}' already exists")
        
        # Use default calibration if not provided
        if calibration is None:
            try:
                calibration = get_default_calibration(gas_type)
                logger.info(f"Using default calibration for {gas_type}")
            except KeyError:
                logger.warning(
                    f"No default calibration for {gas_type}, using identity calibration"
                )
                calibration = Calibration.identity(gas_type)
        
        mfc = MFC(
            name=name,
            com_port=com_port,
            node_address=node_address,
            gas_type=gas_type,
            calibration=calibration,
        )
        
        self._mfcs[name] = mfc
        logger.info(f"Added MFC '{name}' ({gas_type}) at {com_port}:{node_address}")
        
        if auto_connect:
            self._connect_device(mfc)
        
        return mfc
    
    def add_cori_flow(
        self,
        name: str,
        com_port: str,
        node_address: int,
        gas_type: str = "mixture",
        auto_connect: bool = True,
    ) -> CoriFlowMeter:
        """
        Add a Coriolis flow meter to the controller.
        
        Args:
            name: Unique identifier for this meter
            com_port: Serial port
            node_address: FLOW-BUS node address
            gas_type: Gas type (for identification only)
            auto_connect: If True, connect immediately
            
        Returns:
            The created CoriFlowMeter instance
        """
        if name in self._cori_flows:
            raise ValueError(f"CoriFlow with name '{name}' already exists")
        
        cori = CoriFlowMeter(
            name=name,
            com_port=com_port,
            node_address=node_address,
            gas_type=gas_type,
        )
        
        self._cori_flows[name] = cori
        logger.info(f"Added CoriFlow '{name}' at {com_port}:{node_address}")
        
        if auto_connect:
            self._connect_device(cori)
        
        return cori
    
    def remove_mfc(self, name: str) -> None:
        """
        Remove an MFC from the controller.
        
        The MFC is disconnected before removal.
        
        Args:
            name: Name of the MFC to remove
            
        Raises:
            KeyError: If MFC doesn't exist
        """
        if name not in self._mfcs:
            raise KeyError(f"MFC '{name}' not found")
        
        mfc = self._mfcs[name]
        if mfc.is_connected:
            mfc.close_valve()  # Safety: close before removing
            mfc.disconnect()
        
        del self._mfcs[name]
        logger.info(f"Removed MFC '{name}'")
    
    def remove_cori_flow(self, name: str) -> None:
        """Remove a CoriFlow meter from the controller."""
        if name not in self._cori_flows:
            raise KeyError(f"CoriFlow '{name}' not found")
        
        cori = self._cori_flows[name]
        if cori.is_connected:
            cori.disconnect()
        
        del self._cori_flows[name]
        logger.info(f"Removed CoriFlow '{name}'")
    
    def get_mfc(self, name: str) -> MFC:
        """
        Get an MFC by name.
        
        Args:
            name: Name of the MFC
            
        Returns:
            The MFC instance
            
        Raises:
            KeyError: If MFC doesn't exist
        """
        if name not in self._mfcs:
            available = ", ".join(self._mfcs.keys()) or "(none)"
            raise KeyError(f"MFC '{name}' not found. Available: {available}")
        return self._mfcs[name]
    
    def get_cori_flow(self, name: str) -> CoriFlowMeter:
        """Get a CoriFlow meter by name."""
        if name not in self._cori_flows:
            raise KeyError(f"CoriFlow '{name}' not found")
        return self._cori_flows[name]
    
    def list_mfcs(self) -> list[str]:
        """Get list of all MFC names."""
        return list(self._mfcs.keys())
    
    def list_cori_flows(self) -> list[str]:
        """Get list of all CoriFlow meter names."""
        return list(self._cori_flows.keys())
    
    @property
    def mfcs(self) -> Iterator[MFC]:
        """Iterate over all MFCs."""
        return iter(self._mfcs.values())

    def mfc_items(self) -> Iterator[tuple[str, MFC]]:
        """Iterate over all MFC name-value pairs."""
        return iter(self._mfcs.items())

    @property
    def all_devices(self) -> Iterator[FlowDeviceBase]:
        """Iterate over all devices (MFCs and CoriFlows)."""
        yield from self._mfcs.values()
        yield from self._cori_flows.values()
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    def _connect_device(self, device: FlowDeviceBase) -> None:
        """
        Connect a single device.
        
        Uses mock instruments in mock mode, or real propar instruments
        via ConnectionManager for real hardware.
        """
        if self.use_mock:
            from mfc_control.hardware.mock import MockInstrument
            instrument = MockInstrument(device.node_address)
        else:
            # Use connection manager for real hardware
            instrument = self._connection_manager.get_instrument(
                device.com_port, 
                device.node_address
            )
        
        device.connect(instrument)
    
    def connect_all(self) -> None:
        """Connect all registered devices."""
        for device in self.all_devices:
            if not device.is_connected:
                self._connect_device(device)
    
    def disconnect_all(self) -> None:
        """Disconnect all devices."""
        # Close valves first (safety)
        self.close_all_valves()
        
        for device in self.all_devices:
            if device.is_connected:
                device.disconnect()
        
        # Close connection manager
        if self._connection_manager is not None:
            self._connection_manager.close_all()
        
        logger.info("All devices disconnected")
    
    # =========================================================================
    # Coordinated Operations
    # =========================================================================
    
    def close_all_valves(self) -> None:
        """Close all MFC valves (set flows to zero)."""
        for mfc in self._mfcs.values():
            if mfc.is_connected:
                try:
                    mfc.close_valve()
                except Exception as e:
                    logger.error(f"Failed to close {mfc.name}: {e}")
        logger.info("All valves closed")
    
    def wink_all(self) -> None:
        """Make all devices blink for identification."""
        for device in self.all_devices:
            if device.is_connected:
                device.wink()
    
    def read_all_flows(self) -> dict[str, float]:
        """
        Read current flow from all MFCs.
        
        Returns:
            Dictionary mapping MFC name to flow rate (real units, l/min)
        """
        flows = {}
        for name, mfc in self._mfcs.items():
            if mfc.is_connected:
                try:
                    flows[name] = mfc.read_flow_real()
                except Exception as e:
                    logger.error(f"Failed to read {name}: {e}")
                    flows[name] = float("nan")
        return flows
    
    def check_all_deviations(self, threshold: float = 0.05) -> dict[str, tuple[bool, float]]:
        """
        Check setpoint deviation for all MFCs.
        
        Args:
            threshold: Maximum acceptable absolute deviation (l/min)
            
        Returns:
            Dictionary mapping MFC name to (is_ok, deviation) tuples
        """
        results = {}
        for name, mfc in self._mfcs.items():
            if mfc.is_connected:
                results[name] = mfc.check_deviation(threshold)
        return results
    
    def get_status_summary(self) -> dict:
        """
        Get a summary of all device statuses.
        
        Returns:
            Dictionary with status information for each device
        """
        status = {
            "mfcs": {},
            "cori_flows": {},
            "connected_count": 0,
            "total_count": 0,
        }
        
        for name, mfc in self._mfcs.items():
            status["mfcs"][name] = {
                "connected": mfc.is_connected,
                "gas_type": mfc.gas_type,
                "com_port": mfc.com_port,
                "node_address": mfc.node_address,
            }
            if mfc.is_connected:
                status["mfcs"][name]["flow_real"] = mfc.read_flow_real()
                status["mfcs"][name]["setpoint_real"] = mfc.read_setpoint_real()
                status["connected_count"] += 1
            status["total_count"] += 1
        
        for name, cori in self._cori_flows.items():
            status["cori_flows"][name] = {
                "connected": cori.is_connected,
                "gas_type": cori.gas_type,
            }
            if cori.is_connected:
                status["cori_flows"][name]["flow"] = cori.read_flow_mfc()
                status["connected_count"] += 1
            status["total_count"] += 1
        
        return status
    
    # =========================================================================
    # Context Manager
    # =========================================================================
    
    def __enter__(self) -> MFCController:
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - ensure cleanup."""
        self.disconnect_all()


# =============================================================================
# Factory function for common configurations
# =============================================================================

def create_standard_controller(
    com_port: str = "COM1",
    use_mock: bool = False,
) -> MFCController:
    """
    Create a controller with the standard lab MFC configuration.
    
    Sets up:
    - CH4 MFC at node 1
    - H2 MFC at node 7
    - Air MFC at node 10
    - Cori-Flow at node 6
    
    Args:
        com_port: Serial port for all devices
        use_mock: If True, use mock devices
        
    Returns:
        Configured MFCController
    """
    controller = MFCController(use_mock=use_mock)
    
    # Add MFCs with default calibrations
    controller.add_mfc("CH4", com_port, node_address=1, gas_type="CH4")
    controller.add_mfc("H2", com_port, node_address=7, gas_type="H2")
    controller.add_mfc("Air", com_port, node_address=10, gas_type="Air")
    
    # Add Cori-Flow meter
    controller.add_cori_flow("CoriFlow", com_port, node_address=6)
    
    return controller
