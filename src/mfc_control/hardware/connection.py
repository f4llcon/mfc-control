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

try:
    import serial.tools.list_ports
    SERIAL_TOOLS_AVAILABLE = True
except ImportError:
    SERIAL_TOOLS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PortInfo:
    """Information about an available COM port."""
    device: str
    description: str
    manufacturer: str = ""

    def __str__(self) -> str:
        if self.manufacturer:
            return f"{self.device}: {self.description} [{self.manufacturer}]"
        return f"{self.device}: {self.description}"


def list_available_ports() -> list[PortInfo]:
    """
    List all available COM/serial ports on the system.

    Returns:
        List of PortInfo objects describing available ports

    Raises:
        ImportError: If pyserial is not installed
    """
    if not SERIAL_TOOLS_AVAILABLE:
        raise ImportError(
            "pyserial not installed. Install with: pip install pyserial"
        )

    ports = []
    for p in serial.tools.list_ports.comports():
        ports.append(PortInfo(
            device=p.device,
            description=p.description or "Unknown",
            manufacturer=p.manufacturer or "",
        ))

    return ports


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

            try:
                master = propar.master(com_port, baudrate=self.baudrate)
                self._masters[com_port] = master
            except Exception as e:
                # Provide helpful error message with available ports
                error_msg = f"Failed to open port '{com_port}': {e}"

                try:
                    available = list_available_ports()
                    if available:
                        port_list = ", ".join(p.device for p in available)
                        error_msg += f"\n\nAvailable COM ports: {port_list}"
                        error_msg += f"\n\nCommon causes:"
                        error_msg += f"\n  1. Another program has {com_port} open"
                        error_msg += f"\n  2. Wrong port number (check Device Manager)"
                        error_msg += f"\n  3. Device not connected or powered off"
                    else:
                        error_msg += "\n\nNo COM ports found on system"
                except:
                    pass  # If we can't list ports, just show original error

                raise ConnectionError(error_msg)

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

    def discover_all_ports(self) -> dict[str, list[DiscoveredDevice]]:
        """
        Scan ALL available COM ports for MFC devices.

        This method automatically enumerates all serial ports on the system
        and attempts to discover MFC devices on each one.

        Returns:
            Dictionary mapping port name -> list of devices found on that port
            Only ports with MFC devices are included in the result.

        Raises:
            ImportError: If pyserial is not installed

        Example:
            >>> manager = ConnectionManager()
            >>> results = manager.discover_all_ports()
            >>> for port, devices in results.items():
            ...     print(f"{port}: {len(devices)} device(s)")
            ...     for dev in devices:
            ...         print(f"  - {dev}")
            COM3: 2 device(s)
              - Node   1: F-201CV (S/N: M12345678A)
              - Node   7: F-201CV (S/N: M12345679B)
        """
        available_ports = list_available_ports()

        if not available_ports:
            logger.warning("No COM ports found on system")
            return {}

        logger.info(f"Scanning {len(available_ports)} available port(s) for MFC devices...")

        results = {}
        errors = []
        for port_info in available_ports:
            try:
                logger.debug(f"Checking {port_info.device}...")
                devices = self.discover_devices(port_info.device)
                if devices:
                    results[port_info.device] = devices
                    logger.info(f"{port_info.device}: Found {len(devices)} device(s)")
                else:
                    logger.debug(f"{port_info.device}: No devices found")
            except ConnectionError as e:
                # Connection errors indicate port access issues
                error_msg = str(e).split('\n')[0]  # Get first line only
                logger.warning(f"{port_info.device}: {error_msg}")
                errors.append((port_info.device, error_msg))
            except ValueError as e:
                # ValueError often means non-MFC device (e.g., "bytes must be in range(0, 256)")
                if "bytes must be in range" in str(e) or "byte" in str(e).lower():
                    logger.info(f"{port_info.device}: Not an MFC device (incompatible protocol)")
                    # Don't add to errors list - this is expected for non-MFC ports
                else:
                    logger.warning(f"{port_info.device}: {e}")
                    errors.append((port_info.device, str(e)))
            except Exception as e:
                # Other errors (timeouts, protocol errors, etc.)
                logger.debug(f"Could not scan {port_info.device}: {e}")
                errors.append((port_info.device, str(e)))
            finally:
                # IMPORTANT: Close the port after checking to prevent "access denied" on subsequent ports
                self.close_port(port_info.device)

        if not results:
            if errors:
                logger.warning(f"No MFC devices found. {len(errors)} port(s) had issues (check logs for details)")
            else:
                logger.info("No MFC devices found on any port")
        else:
            total_devices = sum(len(devs) for devs in results.values())
            logger.info(f"Discovery complete: {total_devices} device(s) on {len(results)} port(s)")

        return results

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
    
    def close_port(self, com_port: str) -> None:
        """
        Close connection to a specific port.

        Args:
            com_port: Port to close (e.g., "COM6")
        """
        if com_port in self._masters:
            try:
                self._masters[com_port].stop()
                logger.debug(f"Closed connection to {com_port}")
                del self._masters[com_port]
            except Exception as e:
                logger.error(f"Error closing {com_port}: {e}")

        # Also remove any instruments on this port
        instruments_to_remove = [key for key in self._instruments if key.startswith(f"{com_port}:")]
        for key in instruments_to_remove:
            del self._instruments[key]

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
