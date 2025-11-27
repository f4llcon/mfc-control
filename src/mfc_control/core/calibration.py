"""
Calibration handling for MFC gas conversion.

MFCs are factory-calibrated for nitrogen. When flowing different gases,
the readings must be corrected using calibration data (lookup tables).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np


@dataclass
class Calibration:
    """
    Handles bidirectional conversion between MFC readings and real gas flow rates.
    
    MFCs display values based on their nitrogen calibration. This class uses
    interpolation on measured calibration data to convert between:
    - MFC units (what the device displays/accepts)
    - Real units (actual gas flow rate)
    
    Attributes:
        mfc_values: Array of MFC readings from calibration (l/min)
        real_values: Array of corresponding real flow rates (l/min)
        gas_type: Name of the gas this calibration is for
        
    Example:
        >>> cal = Calibration(
        ...     mfc_values=[1.0, 0.5, 0.0],
        ...     real_values=[0.325, 0.151, 0.0],
        ...     gas_type="CH4"
        ... )
        >>> cal.real_to_mfc(0.2)  # What MFC setpoint for 0.2 l/min real?
        0.55  # approximately
        >>> cal.mfc_to_real(0.8)  # What's real flow when MFC shows 0.8?
        0.251  # approximately
    """
    
    mfc_values: np.ndarray = field(repr=False)
    real_values: np.ndarray = field(repr=False)
    gas_type: str = "Unknown"
    
    def __init__(
        self,
        mfc_values: Sequence[float],
        real_values: Sequence[float],
        gas_type: str = "Unknown",
    ):
        """
        Initialize calibration with matched arrays of MFC and real values.
        
        Args:
            mfc_values: MFC readings from calibration measurements
            real_values: Corresponding actual flow rates
            gas_type: Name of the gas (for identification)
            
        Raises:
            ValueError: If arrays have different lengths or are too short
        """
        self.mfc_values = np.array(mfc_values, dtype=float)
        self.real_values = np.array(real_values, dtype=float)
        self.gas_type = gas_type
        
        if len(self.mfc_values) != len(self.real_values):
            raise ValueError(
                f"mfc_values ({len(self.mfc_values)}) and real_values "
                f"({len(self.real_values)}) must have same length"
            )
        if len(self.mfc_values) < 2:
            raise ValueError("Need at least 2 calibration points for interpolation")
            
        # Sort by MFC values for consistent interpolation
        sort_idx = np.argsort(self.mfc_values)
        self.mfc_values = self.mfc_values[sort_idx]
        self.real_values = self.real_values[sort_idx]
    
    def mfc_to_real(self, mfc_value: float) -> float:
        """
        Convert MFC reading to real gas flow rate.
        
        Args:
            mfc_value: Value displayed by MFC (l/min)
            
        Returns:
            Actual gas flow rate (l/min)
            
        Note:
            Uses linear interpolation. Values outside calibration range
            are extrapolated (use with caution).
        """
        return float(np.interp(mfc_value, self.mfc_values, self.real_values))
    
    def real_to_mfc(self, real_value: float) -> float:
        """
        Convert real gas flow rate to MFC setpoint.
        
        Args:
            real_value: Desired actual flow rate (l/min)
            
        Returns:
            MFC setpoint to achieve that flow (l/min)
            
        Note:
            Uses linear interpolation. Values outside calibration range
            are extrapolated (use with caution).
        """
        # Need to sort by real values for this direction
        sort_idx = np.argsort(self.real_values)
        sorted_real = self.real_values[sort_idx]
        sorted_mfc = self.mfc_values[sort_idx]
        return float(np.interp(real_value, sorted_real, sorted_mfc))
    
    @property
    def max_real_flow(self) -> float:
        """Maximum calibrated real flow rate (l/min)."""
        return float(np.max(self.real_values))
    
    @property
    def min_real_flow(self) -> float:
        """Minimum calibrated real flow rate (l/min)."""
        return float(np.min(self.real_values))
    
    @property
    def max_mfc_value(self) -> float:
        """Maximum calibrated MFC value (l/min)."""
        return float(np.max(self.mfc_values))
    
    @property
    def min_mfc_value(self) -> float:
        """Minimum calibrated MFC value (l/min)."""
        return float(np.min(self.mfc_values))
    
    def is_real_in_range(self, real_value: float) -> bool:
        """Check if a real flow value is within calibrated range."""
        return self.min_real_flow <= real_value <= self.max_real_flow
    
    def is_mfc_in_range(self, mfc_value: float) -> bool:
        """Check if an MFC value is within calibrated range."""
        return self.min_mfc_value <= mfc_value <= self.max_mfc_value
    
    @classmethod
    def from_csv(cls, filepath: str | Path, gas_type: str = "Unknown") -> Calibration:
        """
        Load calibration from CSV file.
        
        Expected format: two columns (mfc_value, real_value) with header row.
        
        Args:
            filepath: Path to CSV file
            gas_type: Name of the gas
            
        Returns:
            Calibration instance
        """
        data = np.loadtxt(filepath, delimiter=",", skiprows=1)
        return cls(
            mfc_values=data[:, 0],
            real_values=data[:, 1],
            gas_type=gas_type,
        )
    
    @classmethod
    def from_numpy(cls, filepath: str | Path, gas_type: str = "Unknown") -> Calibration:
        """
        Load calibration from NumPy .npy file.
        
        Expected format: 2D array with shape (N, 2) where columns are
        [mfc_value, real_value].
        
        Args:
            filepath: Path to .npy file
            gas_type: Name of the gas
            
        Returns:
            Calibration instance
        """
        data = np.load(filepath)
        return cls(
            mfc_values=data[:, 0],
            real_values=data[:, 1],
            gas_type=gas_type,
        )
    
    @classmethod
    def identity(cls, gas_type: str = "N2") -> Calibration:
        """
        Create an identity calibration (no conversion needed).
        
        Use this when the gas matches the MFC's factory calibration (nitrogen),
        or when no calibration data is available.
        
        Args:
            gas_type: Name of the gas
            
        Returns:
            Calibration where MFC values equal real values
        """
        # Linear identity from 0 to 10 l/min
        values = np.linspace(0, 10, 11)
        return cls(mfc_values=values, real_values=values, gas_type=gas_type)
    
    def to_csv(self, filepath: str | Path) -> None:
        """Save calibration to CSV file."""
        data = np.column_stack([self.mfc_values, self.real_values])
        np.savetxt(
            filepath, 
            data, 
            delimiter=",", 
            header="mfc_value,real_value",
            comments=""
        )
    
    def __repr__(self) -> str:
        return (
            f"Calibration(gas_type={self.gas_type!r}, "
            f"points={len(self.mfc_values)}, "
            f"real_range=[{self.min_real_flow:.3f}, {self.max_real_flow:.3f}] l/min)"
        )


# =============================================================================
# Default calibration data from MATLAB implementation
# =============================================================================

# CH4 calibration data
CH4_CALIBRATION = Calibration(
    mfc_values=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0],
    real_values=[0.325, 0.286, 0.251, 0.215, 0.182, 0.151, 0.120, 0.089, 0.058, 0.028, 0.0],
    gas_type="CH4",
)

# H2 calibration data
H2_CALIBRATION = Calibration(
    mfc_values=[2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0],
    real_values=[2.019, 1.802, 1.602, 1.405, 1.201, 1.005, 0.899, 0.795, 0.703, 0.595, 0.493, 0.393, 0.291, 0.197, 0.111, 0.0],
    gas_type="H2",
)

# Air calibration data
AIR_CALIBRATION = Calibration(
    mfc_values=[1.4, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05, 0.0],
    real_values=[1.826, 1.566, 1.307, 1.176, 1.046, 0.916, 0.783, 0.654, 0.525, 0.460, 0.395, 0.330, 0.265, 0.200, 0.135, 0.069, 0.0],
    gas_type="Air",
)

# Dictionary of default calibrations
DEFAULT_CALIBRATIONS: dict[str, Calibration] = {
    "CH4": CH4_CALIBRATION,
    "H2": H2_CALIBRATION,
    "Air": AIR_CALIBRATION,
}


def get_default_calibration(gas_type: str) -> Calibration:
    """
    Get the default calibration for a gas type.
    
    Args:
        gas_type: Name of the gas ("CH4", "H2", "Air", etc.)
        
    Returns:
        Calibration instance
        
    Raises:
        KeyError: If no default calibration exists for the gas type
    """
    if gas_type not in DEFAULT_CALIBRATIONS:
        available = ", ".join(DEFAULT_CALIBRATIONS.keys())
        raise KeyError(
            f"No default calibration for '{gas_type}'. "
            f"Available: {available}. "
            f"Use Calibration.identity() or provide custom calibration."
        )
    return DEFAULT_CALIBRATIONS[gas_type]
