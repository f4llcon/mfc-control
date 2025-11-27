"""
Combustion calculations for fuel-air mixtures.

Provides functions for:
- Calculating equivalence ratio (phi) from flow rates
- Calculating thermal power from fuel flows
- Solving for flows given target phi and total volume/power

References:
    Equivalence ratio (φ) = (fuel/air)_actual / (fuel/air)_stoichiometric
    φ = 1: stoichiometric (complete combustion)
    φ < 1: lean (excess air)
    φ > 1: rich (excess fuel)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mfc_control.combustion.properties import (
    AIR_TO_O2_RATIO,
    GasProperties,
    get_gas_properties,
)


# =============================================================================
# Basic Calculations
# =============================================================================

def calculate_stoichiometric_air(
    v_h2: float = 0.0,
    v_ch4: float = 0.0,
) -> float:
    """
    Calculate stoichiometric air requirement for given fuel flows.
    
    Based on combustion reactions:
    - H2 + 0.5 O2 → H2O
    - CH4 + 2 O2 → CO2 + 2 H2O
    
    Args:
        v_h2: Hydrogen flow rate (l/min)
        v_ch4: Methane flow rate (l/min)
        
    Returns:
        Required air flow for stoichiometric combustion (l/min)
        
    Note:
        Uses ideal gas assumption (equal molar volumes at same T, P).
        AIR_TO_O2_RATIO (4.762) accounts for N2 in air.
    """
    # Moles O2 needed = 0.5 * mol_H2 + 2 * mol_CH4
    # Since volumes are proportional to moles (ideal gas): V_O2 = 0.5*V_H2 + 2*V_CH4
    # Air needed = V_O2 * 4.762
    return AIR_TO_O2_RATIO * (0.5 * v_h2 + 2.0 * v_ch4)


def calculate_phi(
    v_h2: float = 0.0,
    v_ch4: float = 0.0,
    v_air: float = 0.0,
) -> float:
    """
    Calculate equivalence ratio (φ) from flow rates.
    
    φ = stoichiometric_air / actual_air
    
    Args:
        v_h2: Hydrogen flow rate (l/min)
        v_ch4: Methane flow rate (l/min)
        v_air: Air flow rate (l/min)
        
    Returns:
        Equivalence ratio (dimensionless)
        Returns 0 if no air flow (undefined)
        
    Examples:
        >>> calculate_phi(v_h2=1.0, v_air=2.381)  # Stoichiometric H2
        1.0
        >>> calculate_phi(v_ch4=1.0, v_air=9.524)  # Stoichiometric CH4
        1.0
    """
    if v_air <= 0:
        return 0.0
    
    air_stoich = calculate_stoichiometric_air(v_h2, v_ch4)
    if air_stoich <= 0:
        return 0.0
    
    return air_stoich / v_air


def calculate_power(
    v_h2: float = 0.0,
    v_ch4: float = 0.0,
) -> float:
    """
    Calculate thermal power output from fuel flows.
    
    Power = Σ (V_fuel × density × LHV)
    
    Args:
        v_h2: Hydrogen flow rate (l/min)
        v_ch4: Methane flow rate (l/min)
        
    Returns:
        Thermal power (W)
        
    Note:
        Uses lower heating value (LHV). Assumes complete combustion.
    """
    power = 0.0
    
    h2_props = get_gas_properties("H2")
    ch4_props = get_gas_properties("CH4")
    
    # Convert l/min to m³/s: divide by 60 and 1000
    # V (m³/s) = V (l/min) * (1/60) * (1/1000) = V / 60000
    
    if v_h2 > 0 and h2_props.lhv is not None:
        # Power = V (m³/s) × density (kg/m³) × LHV (MJ/kg) × 10^6 (W/MW)
        power += v_h2 / 60000.0 * h2_props.density * h2_props.lhv * 1e6
    
    if v_ch4 > 0 and ch4_props.lhv is not None:
        power += v_ch4 / 60000.0 * ch4_props.density * ch4_props.lhv * 1e6
    
    return power


# =============================================================================
# Mode Solvers
# =============================================================================

@dataclass
class FlowSolution:
    """
    Result of a flow calculation.
    
    Attributes:
        v_h2: Hydrogen flow rate (l/min)
        v_ch4: Methane flow rate (l/min)
        v_air: Air flow rate (l/min)
        phi: Equivalence ratio (computed)
        power: Thermal power in W (computed)
        v_total: Total volume flow (l/min)
    """
    v_h2: float
    v_ch4: float
    v_air: float
    phi: float
    power: float
    
    @property
    def v_total(self) -> float:
        """Total volume flow rate (l/min)."""
        return self.v_h2 + self.v_ch4 + self.v_air


def solve_volume_mode(
    v_total: float,
    phi: float,
    fuel: str = "H2",
) -> FlowSolution:
    """
    Solve for individual flows given total volume and equivalence ratio.
    
    This matches the MATLAB "Vorgabemodus Volumen" functionality.
    Currently only supports single-fuel operation (H2 or CH4 with Air).
    
    Args:
        v_total: Desired total volume flow (l/min)
        phi: Desired equivalence ratio
        fuel: Fuel type ("H2" or "CH4")
        
    Returns:
        FlowSolution with calculated flows
        
    Raises:
        ValueError: If fuel type not supported or parameters invalid
        
    Theory:
        For H2-Air:
            V_H2 + V_Air = V_total
            φ = (0.5 × 4.762 × V_H2) / V_Air
            
        Solving:
            V_Air = V_total / (1 + φ/(0.5 × 4.762))
            V_H2 = V_total - V_Air
    """
    if v_total <= 0:
        raise ValueError("Total volume must be positive")
    if phi <= 0:
        raise ValueError("Equivalence ratio must be positive")
    
    if fuel == "H2":
        # For H2: stoich ratio is 0.5 mol O2 per mol H2
        stoich_factor = 0.5 * AIR_TO_O2_RATIO  # = 2.381
        
        # Solve system:
        # V_H2 + V_Air = V_total
        # phi = stoich_factor * V_H2 / V_Air
        # => V_Air = stoich_factor * V_H2 / phi
        # => V_H2 + stoich_factor * V_H2 / phi = V_total
        # => V_H2 * (1 + stoich_factor / phi) = V_total
        # => V_H2 = V_total / (1 + stoich_factor / phi)
        
        v_h2 = v_total / (1.0 + stoich_factor / phi)
        v_air = v_total - v_h2
        v_ch4 = 0.0
        
    elif fuel == "CH4":
        # For CH4: stoich ratio is 2 mol O2 per mol CH4
        stoich_factor = 2.0 * AIR_TO_O2_RATIO  # = 9.524
        
        v_ch4 = v_total / (1.0 + stoich_factor / phi)
        v_air = v_total - v_ch4
        v_h2 = 0.0
        
    else:
        raise ValueError(f"Unsupported fuel type: {fuel}. Use 'H2' or 'CH4'.")
    
    # Calculate actual phi and power for verification
    actual_phi = calculate_phi(v_h2=v_h2, v_ch4=v_ch4, v_air=v_air)
    power = calculate_power(v_h2=v_h2, v_ch4=v_ch4)
    
    return FlowSolution(
        v_h2=v_h2,
        v_ch4=v_ch4,
        v_air=v_air,
        phi=actual_phi,
        power=power,
    )


def solve_power_mode(
    power_target: float,
    phi: float,
    fuel: str = "H2",
) -> FlowSolution:
    """
    Solve for individual flows given target power and equivalence ratio.
    
    This matches the MATLAB "Vorgabemodus Leistung" functionality.
    Currently only supports single-fuel operation (H2 or CH4 with Air).
    
    Args:
        power_target: Desired thermal power (W)
        phi: Desired equivalence ratio
        fuel: Fuel type ("H2" or "CH4")
        
    Returns:
        FlowSolution with calculated flows
        
    Raises:
        ValueError: If fuel type not supported or parameters invalid
        
    Theory:
        Power = V_fuel × (1/60000) × density × LHV × 10^6
        => V_fuel = Power / ((1/60000) × density × LHV × 10^6)
        
        Then use stoichiometry to find V_Air from V_fuel and phi.
    """
    if power_target <= 0:
        raise ValueError("Power must be positive")
    if phi <= 0:
        raise ValueError("Equivalence ratio must be positive")
    
    if fuel == "H2":
        props = get_gas_properties("H2")
        stoich_factor = 0.5 * AIR_TO_O2_RATIO
        
        # V_H2 (l/min) from power
        # Power = V_H2 / 60000 * density * LHV * 1e6
        # V_H2 = Power * 60000 / (density * LHV * 1e6)
        v_h2 = power_target * 60000.0 / (props.density * props.lhv * 1e6)
        
        # V_Air from stoichiometry and phi
        # phi = stoich_factor * V_H2 / V_Air
        # V_Air = stoich_factor * V_H2 / phi
        v_air = stoich_factor * v_h2 / phi
        v_ch4 = 0.0
        
    elif fuel == "CH4":
        props = get_gas_properties("CH4")
        stoich_factor = 2.0 * AIR_TO_O2_RATIO
        
        v_ch4 = power_target * 60000.0 / (props.density * props.lhv * 1e6)
        v_air = stoich_factor * v_ch4 / phi
        v_h2 = 0.0
        
    else:
        raise ValueError(f"Unsupported fuel type: {fuel}. Use 'H2' or 'CH4'.")
    
    # Calculate actual phi and power for verification
    actual_phi = calculate_phi(v_h2=v_h2, v_ch4=v_ch4, v_air=v_air)
    actual_power = calculate_power(v_h2=v_h2, v_ch4=v_ch4)
    
    return FlowSolution(
        v_h2=v_h2,
        v_ch4=v_ch4,
        v_air=v_air,
        phi=actual_phi,
        power=actual_power,
    )
