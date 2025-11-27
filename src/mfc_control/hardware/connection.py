"""
Hardware connection management for Bronkhorst MFCs.

Provides:
- Device discovery (scan FLOW-BUS network)
- Connection pooling (share master across devices on same port)
- Real hardware communication via bronkhorst-propar
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """
    Information about a device found during network scan.
    
    Attributes:
        address: FLOW-BUS node address (1-127)
        device_type: Device type string (e.g., "F-201CV", "mini CORI-FLOW")
        serial: Serial number
        channels: Number of channels (usually 1)
        id_string: Raw identification string
    """
    address: int
    device_type: str
    serial: str
    channels: int = 1
    id_string: str = ""
    
    def __str__(self) -> str:
        return f"Node {self.address:3d}: {self.device_type} (S/N: {self.serial})"


class ConnectionManager:
    """
    Manages serial connections to MFC networks.
    
    Handles:
    - Creating and reusing master connections per COM port
    - Device discovery/scanning
    - Clean shutdown
    
    Example:
        >>> manager = ConnectionManager()
        >>> devices = manager.discover_devices("COM1")
        >>> for dev in devices:
        ...     print(dev)
        Node   1: F-201CV (S/N: M12345678A)
        Node   7: F-201CV (S/N: M12345679B)
        Node  10: F-201CV (S/N: M12345680C)
        
        >>> instrument = manager.get_instrument("COM1", node_address=1)
        >>> instrument.readParameter(205)  # Read flow
    """
    
    def __init__(self, baudrate: int = 38400):
        """
        Initialize connection manager.
        
        Args:
            baudrate: Serial baudrate (default 38400 for FLOW-BUS)
        """
        self.baudrate = baudrate
        self._masters: dict[str, Any] = {}  # COM port -> master object
        self._instruments: dict[str, Any] = {}  # "COMx:addr" -> instrument object
    
    def _get_master(self, com_port: str) -> Any:
        """
        Get or create a master connection for a COM port.
        
        The master handles the low-level FLOW-BUS protocol.
        Multiple instruments on the same port share one master.
        """
        if com_port not in self._masters:
            try:
                import propar
            except ImportError:
                raise ImportError(
                    "bronkhorst-propar not installed. "
                    "Install with: pip install bronkhorst-propar"
                )
            
            logger.info(f"Opening connection to {com_port} at {self.baudrate} baud")
            master = propar.master(com_port, baudrate=self.baudrate)
            master.start()
            self._masters[com_port] = master
        
        return self._masters[com_port]
    
    def discover_devices(self, com_port: str) -> list[DiscoveredDevice]:
        """
        Scan the FLOW-BUS network and return all connected devices.
        
        Args:
            com_port: Serial port to scan (e.g., "COM1")
            
        Returns:
            List of DiscoveredDevice objects
            
        Raises:
            ConnectionError: If cannot connect to port
            ImportError: If bronkhorst-propar not installed
        """
        master = self._get_master(com_port)
        
        logger.info(f"Scanning for devices on {com_port}...")
        
        try:
            nodes = master.get_nodes(find_first=True)
        except Exception as e:
            raise ConnectionError(f"Failed to scan {com_port}: {e}")
        
        devices = []
        for node in nodes:
            dev = DiscoveredDevice(
                address=node.get("address", 0),
                device_type=str(node.get("type", "Unknown")),
                serial=str(node.get("serial", "")),
                channels=node.get("channels", 1),
                id_string=str(node.get("id", "")),
            )
            devices.append(dev)
            logger.info(f"  Found: {dev}")
        
        logger.info(f"Found {len(devices)} device(s) on {com_port}")
        return devices
    
    def get_instrument(self, com_port: str, node_address: int) -> Any:
        """
        Get an instrument connection for a specific device.
        
        Args:
            com_port: Serial port
            node_address: FLOW-BUS node address (1-127)
            
        Returns:
            propar.instrument object for communicating with device
        """
        key = f"{com_port}:{node_address}"
        
        if key not in self._instruments:
            try:
                import propar
            except ImportError:
                raise ImportError(
                    "bronkhorst-propar not installed. "
                    "Install with: pip install bronkhorst-propar"
                )
            
            logger.debug(f"Creating instrument connection to {key}")
            instrument = propar.instrument(
                com_port, 
                address=node_address,
                baudrate=self.baudrate
            )
            self._instruments[key] = instrument
        
        return self._instruments[key]
    
    def close_all(self) -> None:
        """Close all connections."""
        for com_port, master in self._masters.items():
            try:
                master.stop()
                logger.info(f"Closed connection to {com_port}")
            except Exception as e:
                logger.error(f"Error closing {com_port}: {e}")
        
        self._masters.clear()
        self._instruments.clear()
    
    def __enter__(self) -> "ConnectionManager":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close_all()


# Global connection manager instance (optional convenience)
_default_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get the default global connection manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ConnectionManager()
    return _default_manager


def discover_devices(com_port: str) -> list[DiscoveredDevice]:
    """
    Convenience function to discover devices on a COM port.
    
    Args:
        com_port: Serial port to scan
        
    Returns:
        List of discovered devices
    """
    return get_connection_manager().discover_devices(com_port)
