"""
Mock MFC classes for testing without hardware.

Provides simulated MFC behavior for development and testing.
The mock devices maintain internal state and simulate realistic
response characteristics.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

from mfc_control.core.mfc import MFCParameter

logger = logging.getLogger(__name__)


@dataclass
class MockInstrument:
    """
    Mock instrument that simulates Bronkhorst ProPar communication.
    
    Maintains internal state for parameters and simulates realistic
    MFC behavior including:
    - Gradual flow changes (not instant)
    - Small measurement noise
    - Device identification
    
    Attributes:
        node_address: Simulated node address
        response_time: Time constant for flow changes (seconds)
        noise_level: Standard deviation of measurement noise (fraction)
    """
    
    node_address: int
    response_time: float = 0.5  # seconds to reach setpoint
    noise_level: float = 0.01  # 1% measurement noise
    
    # Internal state
    _parameters: dict[int, Any] = field(default_factory=dict, repr=False)
    _setpoint: float = field(default=0.0, repr=False)
    _actual_flow: float = field(default=0.0, repr=False)
    _last_update: float = field(default_factory=time.time, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize default parameter values."""
        self._parameters = {
            MFCParameter.DEVICE_TAG: f"MOCK_MFC_{self.node_address}",
            MFCParameter.CAPACITY: 5.0,  # 5 l/min capacity
            MFCParameter.SETPOINT: 0.0,
            MFCParameter.MEASURE: 0.0,
            MFCParameter.WINK: 0,
        }
    
    def _update_flow(self) -> None:
        """Update simulated flow based on time elapsed."""
        now = time.time()
        dt = now - self._last_update
        self._last_update = now
        
        # Simple exponential approach to setpoint
        # flow(t) = setpoint + (flow(0) - setpoint) * exp(-t/tau)
        if self.response_time > 0:
            alpha = 1.0 - (0.5 ** (dt / self.response_time))
        else:
            alpha = 1.0
        
        self._actual_flow += alpha * (self._setpoint - self._actual_flow)
    
    def readParameter(self, parameter: int) -> Any:
        """
        Read a parameter from the mock device.
        
        Args:
            parameter: DDE parameter number
            
        Returns:
            Parameter value (type depends on parameter)
        """
        self._update_flow()
        
        if parameter == MFCParameter.MEASURE:
            # Add realistic noise to measurement
            noise = random.gauss(0, self.noise_level * max(0.01, abs(self._actual_flow)))
            return max(0.0, self._actual_flow + noise)
        
        elif parameter == MFCParameter.SETPOINT:
            return self._setpoint
        
        elif parameter in self._parameters:
            return self._parameters[parameter]
        
        else:
            logger.warning(f"Mock: Unknown parameter {parameter}, returning 0")
            return 0
    
    def writeParameter(self, parameter: int, value: Any) -> None:
        """
        Write a parameter to the mock device.
        
        Args:
            parameter: DDE parameter number
            value: Value to write
        """
        self._update_flow()
        
        if parameter == MFCParameter.SETPOINT:
            self._setpoint = float(value)
            self._parameters[MFCParameter.SETPOINT] = self._setpoint
            logger.debug(f"Mock node {self.node_address}: setpoint = {self._setpoint}")
        
        elif parameter == MFCParameter.WINK:
            logger.info(f"Mock node {self.node_address}: WINK (mode={value})")
            self._parameters[MFCParameter.WINK] = value
        
        else:
            self._parameters[parameter] = value
            logger.debug(f"Mock node {self.node_address}: param {parameter} = {value}")


@dataclass
class MockMFC:
    """
    High-level mock MFC for testing.
    
    This is a complete mock that can be used in place of a real MFC
    for testing the full control flow including calibration.
    
    Example:
        >>> mock = MockMFC(name="CH4_test", gas_type="CH4")
        >>> mock.set_flow_real(0.2)
        >>> print(mock.read_flow_real())
        0.198  # Approximately, with noise
    """
    
    name: str
    gas_type: str = "N2"
    capacity: float = 5.0  # l/min
    
    _instrument: MockInstrument = field(init=False, repr=False)
    _calibration: Any = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize mock instrument."""
        self._instrument = MockInstrument(node_address=0)
        self._instrument._parameters[MFCParameter.CAPACITY] = self.capacity
        self._instrument._parameters[MFCParameter.DEVICE_TAG] = self.name
    
    def set_calibration(self, calibration) -> None:
        """Set calibration for real unit conversion."""
        self._calibration = calibration
    
    def read_flow_mfc(self) -> float:
        """Read flow in MFC units."""
        return self._instrument.readParameter(MFCParameter.MEASURE)
    
    def read_flow_real(self) -> float:
        """Read flow in real units (if calibrated)."""
        mfc_value = self.read_flow_mfc()
        if self._calibration is not None:
            return self._calibration.mfc_to_real(mfc_value)
        return mfc_value
    
    def set_flow_mfc(self, value: float) -> None:
        """Set flow in MFC units."""
        self._instrument.writeParameter(MFCParameter.SETPOINT, value)
    
    def set_flow_real(self, value: float) -> None:
        """Set flow in real units (if calibrated)."""
        if self._calibration is not None:
            mfc_value = self._calibration.real_to_mfc(value)
        else:
            mfc_value = value
        self.set_flow_mfc(mfc_value)
    
    def close_valve(self) -> None:
        """Close valve (set to zero)."""
        self.set_flow_mfc(0.0)
    
    def wink(self) -> None:
        """Make LED blink."""
        self._instrument.writeParameter(MFCParameter.WINK, "9")


@dataclass
class MockCoriFlow:
    """
    Mock Coriolis flow meter for testing.
    
    Simulates a read-only flow meter that tracks "actual" flow
    in the system.
    """
    
    name: str
    _flow: float = field(default=0.0, repr=False)
    _noise_level: float = 0.005  # 0.5% noise
    
    def set_simulated_flow(self, flow: float) -> None:
        """
        Set the simulated flow for testing.
        
        In real use, this would be the actual measured flow.
        For testing, you set it manually to simulate conditions.
        """
        self._flow = flow
    
    def read_flow(self) -> float:
        """Read flow with simulated noise."""
        noise = random.gauss(0, self._noise_level * max(0.01, abs(self._flow)))
        return max(0.0, self._flow + noise)
