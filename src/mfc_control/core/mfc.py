"""
MFC (Mass Flow Controller) classes.

Provides the MFC class for controlling Bronkhorst mass flow controllers
and the CoriFlowMeter class for read-only Coriolis flow meters.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from mfc_control.core.calibration import Calibration

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Bronkhorst Parameter Constants (DDE numbers)
# =============================================================================

class MFCParameter:
    """Bronkhorst MFC parameter numbers (DDE)."""
    
    WINK = 1            # LED control (write: 2=slow, 9=long blink)
    MEASURE = 205       # Measured flow (fMeasure, float)
    SETPOINT = 206      # Setpoint (fSetpoint, float)
    CAPACITY = 21       # Maximum flow capacity
    DEVICE_TAG = 115    # Device name string


class WinkMode:
    """Wink (LED blink) modes for device identification."""
    
    SLOW = "2"    # 0.2s on/off - subtle blink
    LONG = "9"    # 2.0s on/off - obvious blink


# =============================================================================
# Protocol for hardware abstraction
# =============================================================================

class InstrumentProtocol(Protocol):
    """Protocol defining the interface for MFC instrument communication."""
    
    def readParameter(self, parameter: int) -> Any:
        """Read a parameter from the device."""
        ...
    
    def writeParameter(self, parameter: int, value: Any) -> None:
        """Write a parameter to the device."""
        ...


# =============================================================================
# Base class for flow devices
# =============================================================================

@dataclass
class FlowDeviceBase(ABC):
    """
    Abstract base class for flow measurement/control devices.
    
    Attributes:
        name: User-defined name for this device
        com_port: Serial port (e.g., "COM1")
        node_address: FLOW-BUS node address
        gas_type: Type of gas flowing through device
        instrument: The underlying communication object
    """
    
    name: str
    com_port: str
    node_address: int
    gas_type: str
    instrument: InstrumentProtocol | None = field(default=None, repr=False)
    _connected: bool = field(default=False, repr=False)
    
    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self.instrument is not None
    
    def connect(self, instrument: InstrumentProtocol) -> None:
        """
        Attach an instrument connection to this device.
        
        Args:
            instrument: ProPar instrument object or mock
        """
        self.instrument = instrument
        self._connected = True
        logger.info(f"Connected {self.name} at {self.com_port}:{self.node_address}")
    
    def disconnect(self) -> None:
        """Disconnect from the device."""
        self.instrument = None
        self._connected = False
        logger.info(f"Disconnected {self.name}")
    
    def _require_connection(self) -> InstrumentProtocol:
        """Get instrument, raising error if not connected."""
        if not self.is_connected or self.instrument is None:
            raise ConnectionError(f"{self.name} is not connected")
        return self.instrument
    
    @abstractmethod
    def read_flow_mfc(self) -> float:
        """Read flow in MFC units (raw device reading)."""
        ...
    
    def read_device_tag(self) -> str:
        """Read the device identification tag."""
        inst = self._require_connection()
        tag = inst.readParameter(MFCParameter.DEVICE_TAG)
        return str(tag) if tag else ""

    def read_capacity(self) -> float:
        """
        Read the device's maximum flow capacity.

        Raises:
            ValueError: If device returns invalid data
        """
        inst = self._require_connection()
        value = inst.readParameter(MFCParameter.CAPACITY)
        if value is None:
            raise ValueError(f"{self.name}: Device returned no capacity data")
        return float(value)
    
    def wink(self, mode: str = WinkMode.LONG) -> None:
        """
        Make the device blink its LED for identification.
        
        Args:
            mode: WinkMode.SLOW (subtle) or WinkMode.LONG (obvious)
        """
        inst = self._require_connection()
        inst.writeParameter(MFCParameter.WINK, mode)
        logger.info(f"{self.name} winking (mode={mode})")


# =============================================================================
# MFC Class (read/write flow control)
# =============================================================================

@dataclass
class MFC(FlowDeviceBase):
    """
    Mass Flow Controller with calibration support.
    
    Controls gas flow rate through a Bronkhorst MFC. Handles conversion
    between MFC units (device-native) and real units (actual gas flow)
    using calibration data.
    
    Attributes:
        calibration: Calibration data for gas conversion (optional)
        
    Example:
        >>> mfc = MFC(
        ...     name="CH4_main",
        ...     com_port="COM1",
        ...     node_address=1,
        ...     gas_type="CH4",
        ...     calibration=ch4_calibration
        ... )
        >>> mfc.connect(instrument)
        >>> mfc.set_flow_real(0.2)  # Set 0.2 l/min actual CH4 flow
        >>> print(mfc.read_flow_real())  # Read actual flow
    """
    
    calibration: Calibration | None = None
    _last_setpoint_mfc: float = field(default=0.0, repr=False)
    
    # -------------------------------------------------------------------------
    # Reading flow
    # -------------------------------------------------------------------------
    
    def read_flow_mfc(self) -> float:
        """
        Read measured flow in MFC units (raw device reading).

        Returns:
            Flow rate as displayed by MFC (l/min in MFC units)

        Raises:
            ValueError: If device returns invalid data
        """
        inst = self._require_connection()
        value = inst.readParameter(MFCParameter.MEASURE)
        if value is None:
            raise ValueError(f"{self.name}: Device returned no data (check communication)")
        return float(value)
    
    def read_flow_real(self) -> float:
        """
        Read measured flow in real gas units.
        
        If calibration is set, converts from MFC units to actual flow.
        Without calibration, returns raw MFC reading.
        
        Returns:
            Actual gas flow rate (l/min)
        """
        mfc_value = self.read_flow_mfc()
        if self.calibration is not None:
            return self.calibration.mfc_to_real(mfc_value)
        return mfc_value
    
    def read_setpoint_mfc(self) -> float:
        """
        Read current setpoint in MFC units.

        Returns:
            Setpoint as understood by MFC (l/min in MFC units)

        Raises:
            ValueError: If device returns invalid data
        """
        inst = self._require_connection()
        value = inst.readParameter(MFCParameter.SETPOINT)
        if value is None:
            raise ValueError(f"{self.name}: Device returned no data (check communication)")
        return float(value)
    
    def read_setpoint_real(self) -> float:
        """
        Read current setpoint in real gas units.
        
        Returns:
            Setpoint in actual gas flow (l/min)
        """
        mfc_value = self.read_setpoint_mfc()
        if self.calibration is not None:
            return self.calibration.mfc_to_real(mfc_value)
        return mfc_value
    
    # -------------------------------------------------------------------------
    # Setting flow
    # -------------------------------------------------------------------------
    
    def set_flow_mfc(self, mfc_value: float) -> None:
        """
        Set flow directly in MFC units (no calibration conversion).
        
        Args:
            mfc_value: Setpoint in MFC units (l/min)
            
        Warning:
            Use set_flow_real() for normal operation. This bypasses calibration.
        """
        if mfc_value < 0:
            raise ValueError(f"Flow cannot be negative: {mfc_value}")
        
        inst = self._require_connection()
        inst.writeParameter(MFCParameter.SETPOINT, mfc_value)
        self._last_setpoint_mfc = mfc_value
        logger.debug(f"{self.name}: setpoint = {mfc_value:.4f} l/min (MFC units)")
    
    def set_flow_real(self, real_value: float) -> None:
        """
        Set flow in real gas units.
        
        Converts the desired real flow to MFC units using calibration,
        then sends to device.
        
        Args:
            real_value: Desired actual gas flow rate (l/min)
            
        Raises:
            ValueError: If flow is negative
            
        Warning:
            If calibration is not set, value is sent directly to MFC.
        """
        if real_value < 0:
            raise ValueError(f"Flow cannot be negative: {real_value}")
        
        if self.calibration is not None:
            # Warn if outside calibration range
            if not self.calibration.is_real_in_range(real_value):
                logger.warning(
                    f"{self.name}: requested flow {real_value:.4f} l/min is outside "
                    f"calibrated range [{self.calibration.min_real_flow:.4f}, "
                    f"{self.calibration.max_real_flow:.4f}] - extrapolating"
                )
            mfc_value = self.calibration.real_to_mfc(real_value)
        else:
            mfc_value = real_value
        
        self.set_flow_mfc(mfc_value)
        logger.info(f"{self.name}: set {real_value:.4f} l/min real ({mfc_value:.4f} MFC)")
    
    def close_valve(self) -> None:
        """Close the valve (set flow to zero)."""
        self.set_flow_mfc(0.0)
        logger.info(f"{self.name}: valve closed")
    
    # -------------------------------------------------------------------------
    # Deviation checking
    # -------------------------------------------------------------------------
    
    def check_deviation(self, threshold: float = 0.05) -> tuple[bool, float]:
        """
        Check if measured flow deviates from setpoint.
        
        Args:
            threshold: Maximum acceptable absolute deviation (l/min)
            
        Returns:
            Tuple of (is_ok, deviation) where is_ok is True if within threshold
        """
        setpoint = self.read_setpoint_mfc()
        measured = self.read_flow_mfc()
        deviation = abs(setpoint - measured)
        is_ok = deviation <= threshold
        
        if not is_ok:
            logger.warning(
                f"{self.name}: deviation {deviation:.4f} l/min exceeds "
                f"threshold {threshold:.4f} l/min"
            )
        
        return is_ok, deviation


# =============================================================================
# CoriFlowMeter Class (read-only)
# =============================================================================

@dataclass  
class CoriFlowMeter(FlowDeviceBase):
    """
    Coriolis Flow Meter (read-only).
    
    A high-precision reference flow meter. Unlike MFCs, this device
    only measures flow - it cannot control it.
    
    Coriolis meters measure mass flow directly (not volume) and are
    insensitive to gas composition, making them ideal as reference
    instruments.
    
    Example:
        >>> cori = CoriFlowMeter(
        ...     name="Cori_ref",
        ...     com_port="COM1",
        ...     node_address=6,
        ...     gas_type="mixture"
        ... )
        >>> cori.connect(instrument)
        >>> print(cori.read_flow_mfc())  # Read current flow
    """
    
    def read_flow_mfc(self) -> float:
        """
        Read measured flow from Cori-Flow meter.

        Returns:
            Flow rate (l/min or as configured on device)

        Raises:
            ValueError: If device returns invalid data
        """
        inst = self._require_connection()
        value = inst.readParameter(MFCParameter.MEASURE)
        if value is None:
            raise ValueError(f"{self.name}: Device returned no data (check communication)")
        return float(value)
    
    # CoriFlowMeter has no calibration - it measures true mass flow
    def read_flow_real(self) -> float:
        """
        Read measured flow (same as read_flow_mfc for Cori-Flow).
        
        Coriolis meters measure true mass flow independent of gas type,
        so no calibration conversion is needed.
        
        Returns:
            Flow rate (l/min or as configured)
        """
        return self.read_flow_mfc()
