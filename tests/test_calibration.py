"""Tests for calibration module."""

import numpy as np
import pytest

from mfc_control.core.calibration import (
    Calibration,
    CH4_CALIBRATION,
    H2_CALIBRATION,
    AIR_CALIBRATION,
    get_default_calibration,
)


class TestCalibration:
    """Tests for Calibration class."""
    
    def test_basic_interpolation(self):
        """Test basic MFC to real conversion."""
        cal = Calibration(
            mfc_values=[0.0, 1.0],
            real_values=[0.0, 0.5],
            gas_type="Test"
        )
        
        assert cal.mfc_to_real(0.0) == pytest.approx(0.0)
        assert cal.mfc_to_real(1.0) == pytest.approx(0.5)
        assert cal.mfc_to_real(0.5) == pytest.approx(0.25)
    
    def test_reverse_interpolation(self):
        """Test real to MFC conversion."""
        cal = Calibration(
            mfc_values=[0.0, 1.0],
            real_values=[0.0, 0.5],
            gas_type="Test"
        )
        
        assert cal.real_to_mfc(0.0) == pytest.approx(0.0)
        assert cal.real_to_mfc(0.5) == pytest.approx(1.0)
        assert cal.real_to_mfc(0.25) == pytest.approx(0.5)
    
    def test_roundtrip(self):
        """Test that mfc_to_real and real_to_mfc are inverses."""
        cal = CH4_CALIBRATION
        
        for mfc_val in [0.0, 0.3, 0.5, 0.7, 1.0]:
            real_val = cal.mfc_to_real(mfc_val)
            recovered = cal.real_to_mfc(real_val)
            assert recovered == pytest.approx(mfc_val, rel=1e-4)
    
    def test_properties(self):
        """Test calibration properties."""
        cal = CH4_CALIBRATION
        
        assert cal.min_mfc_value == 0.0
        assert cal.max_mfc_value == 1.0
        assert cal.min_real_flow == 0.0
        assert cal.max_real_flow == pytest.approx(0.325)
    
    def test_range_checking(self):
        """Test is_in_range methods."""
        cal = CH4_CALIBRATION
        
        assert cal.is_mfc_in_range(0.5) is True
        assert cal.is_mfc_in_range(1.5) is False
        
        assert cal.is_real_in_range(0.2) is True
        assert cal.is_real_in_range(0.5) is False
    
    def test_identity_calibration(self):
        """Test identity calibration (no conversion)."""
        cal = Calibration.identity("N2")
        
        assert cal.mfc_to_real(1.0) == pytest.approx(1.0)
        assert cal.real_to_mfc(1.0) == pytest.approx(1.0)
    
    def test_invalid_calibration(self):
        """Test that invalid calibrations raise errors."""
        # Different lengths
        with pytest.raises(ValueError):
            Calibration(mfc_values=[1, 2, 3], real_values=[1, 2])
        
        # Too few points
        with pytest.raises(ValueError):
            Calibration(mfc_values=[1], real_values=[1])
    
    def test_get_default_calibration(self):
        """Test getting default calibrations."""
        assert get_default_calibration("CH4") == CH4_CALIBRATION
        assert get_default_calibration("H2") == H2_CALIBRATION
        assert get_default_calibration("Air") == AIR_CALIBRATION
        
        with pytest.raises(KeyError):
            get_default_calibration("UnknownGas")


class TestDefaultCalibrations:
    """Tests for the default calibration data."""
    
    def test_ch4_calibration_values(self):
        """Verify CH4 calibration matches MATLAB values."""
        cal = CH4_CALIBRATION
        
        # Check some known points from MATLAB
        assert cal.mfc_to_real(1.0) == pytest.approx(0.325, rel=1e-3)
        assert cal.mfc_to_real(0.5) == pytest.approx(0.151, rel=1e-3)
        assert cal.mfc_to_real(0.0) == pytest.approx(0.0, abs=1e-6)
    
    def test_h2_calibration_values(self):
        """Verify H2 calibration matches MATLAB values."""
        cal = H2_CALIBRATION
        
        assert cal.mfc_to_real(2.0) == pytest.approx(2.019, rel=1e-3)
        assert cal.mfc_to_real(1.0) == pytest.approx(1.005, rel=1e-3)
        assert cal.mfc_to_real(0.0) == pytest.approx(0.0, abs=1e-6)
    
    def test_air_calibration_values(self):
        """Verify Air calibration matches MATLAB values."""
        cal = AIR_CALIBRATION
        
        assert cal.mfc_to_real(1.4) == pytest.approx(1.826, rel=1e-3)
        assert cal.mfc_to_real(1.0) == pytest.approx(1.307, rel=1e-3)
        assert cal.mfc_to_real(0.0) == pytest.approx(0.0, abs=1e-6)
