"""Tests for combustion calculations."""

import pytest

from mfc_control.combustion.calculations import (
    calculate_phi,
    calculate_power,
    calculate_stoichiometric_air,
    solve_power_mode,
    solve_volume_mode,
)
from mfc_control.combustion.properties import AIR_TO_O2_RATIO


class TestStoichiometry:
    """Tests for stoichiometric calculations."""
    
    def test_h2_stoichiometric_air(self):
        """Test stoichiometric air for H2."""
        # H2 + 0.5 O2 -> H2O
        # Air/O2 ratio is 4.762
        # So 1 l/min H2 needs 0.5 * 4.762 = 2.381 l/min air
        v_h2 = 1.0
        air = calculate_stoichiometric_air(v_h2=v_h2)
        assert air == pytest.approx(0.5 * AIR_TO_O2_RATIO)
    
    def test_ch4_stoichiometric_air(self):
        """Test stoichiometric air for CH4."""
        # CH4 + 2 O2 -> CO2 + 2 H2O
        # So 1 l/min CH4 needs 2 * 4.762 = 9.524 l/min air
        v_ch4 = 1.0
        air = calculate_stoichiometric_air(v_ch4=v_ch4)
        assert air == pytest.approx(2.0 * AIR_TO_O2_RATIO)
    
    def test_mixed_fuel_stoichiometric_air(self):
        """Test stoichiometric air for H2+CH4 mixture."""
        v_h2 = 1.0
        v_ch4 = 1.0
        air = calculate_stoichiometric_air(v_h2=v_h2, v_ch4=v_ch4)
        expected = AIR_TO_O2_RATIO * (0.5 * v_h2 + 2.0 * v_ch4)
        assert air == pytest.approx(expected)


class TestPhi:
    """Tests for equivalence ratio calculation."""
    
    def test_stoichiometric_h2(self):
        """Test phi = 1 for stoichiometric H2-air."""
        v_h2 = 1.0
        v_air = 0.5 * AIR_TO_O2_RATIO  # Stoichiometric
        phi = calculate_phi(v_h2=v_h2, v_air=v_air)
        assert phi == pytest.approx(1.0)
    
    def test_lean_mixture(self):
        """Test phi < 1 for lean mixture."""
        v_h2 = 1.0
        v_air = 1.0 * AIR_TO_O2_RATIO  # Double stoichiometric air
        phi = calculate_phi(v_h2=v_h2, v_air=v_air)
        assert phi == pytest.approx(0.5)
    
    def test_rich_mixture(self):
        """Test phi > 1 for rich mixture."""
        v_h2 = 1.0
        v_air = 0.25 * AIR_TO_O2_RATIO  # Half stoichiometric air
        phi = calculate_phi(v_h2=v_h2, v_air=v_air)
        assert phi == pytest.approx(2.0)
    
    def test_zero_air(self):
        """Test phi = 0 when no air."""
        phi = calculate_phi(v_h2=1.0, v_air=0.0)
        assert phi == 0.0
    
    def test_zero_fuel(self):
        """Test phi = 0 when no fuel."""
        phi = calculate_phi(v_h2=0.0, v_ch4=0.0, v_air=1.0)
        assert phi == 0.0


class TestPower:
    """Tests for thermal power calculation."""
    
    def test_h2_power(self):
        """Test power calculation for H2."""
        # H2: density = 0.0899 kg/m³, LHV = 120 MJ/kg
        # 1 l/min = 1/60000 m³/s
        # Power = 1/60000 * 0.0899 * 120 * 1e6 = 179.8 W
        power = calculate_power(v_h2=1.0)
        assert power == pytest.approx(179.8, rel=0.01)
    
    def test_ch4_power(self):
        """Test power calculation for CH4."""
        # CH4: density = 0.7175 kg/m³, LHV = 50.013 MJ/kg
        # Power = 1/60000 * 0.7175 * 50.013 * 1e6 = 598.0 W
        power = calculate_power(v_ch4=1.0)
        assert power == pytest.approx(598.0, rel=0.01)
    
    def test_zero_fuel(self):
        """Test zero power with no fuel."""
        power = calculate_power(v_h2=0.0, v_ch4=0.0)
        assert power == 0.0


class TestVolumeModeH2:
    """Tests for volume mode solver (H2-Air)."""
    
    def test_stoichiometric(self):
        """Test volume mode at phi = 1."""
        solution = solve_volume_mode(v_total=5.0, phi=1.0, fuel="H2")
        
        # Check phi is correct
        assert solution.phi == pytest.approx(1.0)
        
        # Check total volume
        assert solution.v_total == pytest.approx(5.0)
        
        # Check no CH4
        assert solution.v_ch4 == 0.0
    
    def test_lean(self):
        """Test volume mode with lean mixture."""
        solution = solve_volume_mode(v_total=5.0, phi=0.5, fuel="H2")
        assert solution.phi == pytest.approx(0.5)
        assert solution.v_total == pytest.approx(5.0)
    
    def test_rich(self):
        """Test volume mode with rich mixture."""
        solution = solve_volume_mode(v_total=5.0, phi=2.0, fuel="H2")
        assert solution.phi == pytest.approx(2.0)
        assert solution.v_total == pytest.approx(5.0)
    
    def test_invalid_volume(self):
        """Test error on invalid volume."""
        with pytest.raises(ValueError):
            solve_volume_mode(v_total=-1.0, phi=1.0)
    
    def test_invalid_phi(self):
        """Test error on invalid phi."""
        with pytest.raises(ValueError):
            solve_volume_mode(v_total=5.0, phi=0.0)


class TestPowerModeH2:
    """Tests for power mode solver (H2-Air)."""
    
    def test_stoichiometric(self):
        """Test power mode at phi = 1."""
        solution = solve_power_mode(power_target=500, phi=1.0, fuel="H2")
        
        # Check phi is correct
        assert solution.phi == pytest.approx(1.0)
        
        # Check power is approximately correct
        assert solution.power == pytest.approx(500, rel=0.01)
    
    def test_lean(self):
        """Test power mode with lean mixture."""
        solution = solve_power_mode(power_target=500, phi=0.5, fuel="H2")
        assert solution.phi == pytest.approx(0.5)
        assert solution.power == pytest.approx(500, rel=0.01)
    
    def test_invalid_power(self):
        """Test error on invalid power."""
        with pytest.raises(ValueError):
            solve_power_mode(power_target=-100, phi=1.0)
