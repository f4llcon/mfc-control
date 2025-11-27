"""
Gas properties for combustion calculations.

Contains physical properties of common gases used in combustion experiments.
All values are at standard temperature and pressure (STP: 0°C, 1 atm).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GasProperties:
    """
    Physical properties of a gas.
    
    Attributes:
        name: Gas name/identifier
        density: Density at STP (kg/m³)
        molar_mass: Molar mass (g/mol)
        lhv: Lower heating value (MJ/kg), None for non-fuels
        dynamic_viscosity: Dynamic viscosity at STP (Pa·s), optional
        stoich_o2_ratio: Moles of O2 needed per mole of fuel for complete combustion
    """
    
    name: str
    density: float  # kg/m³
    molar_mass: float  # g/mol
    lhv: Optional[float] = None  # MJ/kg (None for non-fuels like Air)
    dynamic_viscosity: Optional[float] = None  # Pa·s
    stoich_o2_ratio: Optional[float] = None  # mol O2 / mol fuel
    
    @property
    def is_fuel(self) -> bool:
        """Check if this gas is a fuel (has heating value)."""
        return self.lhv is not None and self.lhv > 0


# =============================================================================
# Standard gas properties (at STP: 0°C, 1 atm)
# =============================================================================

HYDROGEN = GasProperties(
    name="H2",
    density=0.0899,  # kg/m³
    molar_mass=2.02,  # g/mol
    lhv=120.0,  # MJ/kg (lower heating value)
    dynamic_viscosity=8.377e-6,  # Pa·s
    stoich_o2_ratio=0.5,  # H2 + 0.5 O2 -> H2O
)

METHANE = GasProperties(
    name="CH4",
    density=0.7175,  # kg/m³
    molar_mass=16.04,  # g/mol
    lhv=50.013,  # MJ/kg
    dynamic_viscosity=1.03945e-5,  # Pa·s
    stoich_o2_ratio=2.0,  # CH4 + 2 O2 -> CO2 + 2 H2O
)

AIR = GasProperties(
    name="Air",
    density=1.293,  # kg/m³
    molar_mass=28.96,  # g/mol
    lhv=None,  # Not a fuel
    dynamic_viscosity=1.722e-5,  # Pa·s
    stoich_o2_ratio=None,
)

NITROGEN = GasProperties(
    name="N2",
    density=1.2506,  # kg/m³
    molar_mass=28.01,  # g/mol
    lhv=None,  # Not a fuel
    dynamic_viscosity=1.663e-5,  # Pa·s
    stoich_o2_ratio=None,
)

OXYGEN = GasProperties(
    name="O2",
    density=1.429,  # kg/m³
    molar_mass=32.00,  # g/mol
    lhv=None,  # Not a fuel (it's the oxidizer)
    dynamic_viscosity=1.919e-5,  # Pa·s
    stoich_o2_ratio=None,
)

# Dictionary of all available gases
GAS_PROPERTIES: dict[str, GasProperties] = {
    "H2": HYDROGEN,
    "CH4": METHANE,
    "Air": AIR,
    "N2": NITROGEN,
    "O2": OXYGEN,
}


def get_gas_properties(gas_type: str) -> GasProperties:
    """
    Get properties for a gas type.
    
    Args:
        gas_type: Gas identifier ("H2", "CH4", "Air", etc.)
        
    Returns:
        GasProperties instance
        
    Raises:
        KeyError: If gas type not found
    """
    if gas_type not in GAS_PROPERTIES:
        available = ", ".join(GAS_PROPERTIES.keys())
        raise KeyError(f"Unknown gas '{gas_type}'. Available: {available}")
    return GAS_PROPERTIES[gas_type]


def register_gas(properties: GasProperties) -> None:
    """
    Register a new gas type.
    
    Args:
        properties: GasProperties instance for the new gas
    """
    GAS_PROPERTIES[properties.name] = properties


# =============================================================================
# Air composition constants
# =============================================================================

# Molar ratio of air to oxygen (accounting for N2 dilution)
# Air is approximately 21% O2, 79% N2 by volume
# So 1 mol O2 requires 1/0.21 ≈ 4.762 mol air
AIR_TO_O2_RATIO = 4.762
