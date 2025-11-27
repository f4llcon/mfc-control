"""Tests for MFC and MFCController classes."""

import pytest

from mfc_control.core.calibration import CH4_CALIBRATION, Calibration
from mfc_control.core.controller import MFCController, create_standard_controller
from mfc_control.core.mfc import MFC
from mfc_control.hardware.mock import MockInstrument


class TestMFCWithMock:
    """Tests for MFC class using mock instrument."""
    
    @pytest.fixture
    def mfc(self):
        """Create MFC with mock instrument."""
        mock_inst = MockInstrument(node_address=1)
        mfc = MFC(
            name="Test_CH4",
            com_port="COM1",
            node_address=1,
            gas_type="CH4",
            calibration=CH4_CALIBRATION,
        )
        mfc.connect(mock_inst)
        return mfc
    
    def test_initial_state(self, mfc):
        """Test MFC starts with zero flow."""
        assert mfc.is_connected
        assert mfc.read_flow_mfc() == pytest.approx(0.0, abs=0.01)
    
    def test_set_and_read_mfc_units(self, mfc):
        """Test setting and reading in MFC units."""
        # Speed up the mock for testing
        mfc.instrument.response_time = 0.1
        
        mfc.set_flow_mfc(0.5)
        
        # Wait for mock to stabilize
        import time
        time.sleep(0.3)
        
        flow = mfc.read_flow_mfc()
        # Allow for noise and response time
        assert 0.3 < flow < 0.7
    
    def test_set_real_units(self, mfc):
        """Test setting flow in real units applies calibration."""
        # 0.2 l/min real CH4 should convert to ~0.6 MFC
        mfc.set_flow_real(0.2)
        
        import time
        time.sleep(0.1)
        
        # Check the setpoint (not measured, which has delay)
        setpoint = mfc.read_setpoint_mfc()
        # From CH4 calibration: 0.2 real -> ~0.6 MFC (interpolated)
        assert 0.5 < setpoint < 0.7
    
    def test_close_valve(self, mfc):
        """Test closing valve sets flow to zero."""
        mfc.set_flow_mfc(0.5)
        mfc.close_valve()
        
        assert mfc.read_setpoint_mfc() == pytest.approx(0.0)
    
    def test_wink(self, mfc):
        """Test wink command doesn't raise error."""
        # Just verify it doesn't crash
        mfc.wink()
    
    def test_deviation_check(self, mfc):
        """Test deviation checking."""
        mfc.set_flow_mfc(0.0)
        import time
        time.sleep(0.1)
        
        is_ok, deviation = mfc.check_deviation(threshold=0.05)
        # At zero, deviation should be small
        assert is_ok is True


class TestMFCController:
    """Tests for MFCController class."""
    
    @pytest.fixture
    def controller(self):
        """Create controller in mock mode."""
        return MFCController(use_mock=True)
    
    def test_add_mfc(self, controller):
        """Test adding MFC to controller."""
        mfc = controller.add_mfc(
            name="CH4",
            com_port="COM1",
            node_address=1,
            gas_type="CH4",
        )
        
        assert "CH4" in controller.list_mfcs()
        assert mfc.is_connected
    
    def test_add_duplicate_name_raises(self, controller):
        """Test adding MFC with duplicate name raises error."""
        controller.add_mfc("CH4", "COM1", 1, "CH4")
        
        with pytest.raises(ValueError):
            controller.add_mfc("CH4", "COM1", 2, "CH4")
    
    def test_get_mfc(self, controller):
        """Test getting MFC by name."""
        controller.add_mfc("CH4", "COM1", 1, "CH4")
        
        mfc = controller.get_mfc("CH4")
        assert mfc.name == "CH4"
    
    def test_get_nonexistent_mfc_raises(self, controller):
        """Test getting non-existent MFC raises KeyError."""
        with pytest.raises(KeyError):
            controller.get_mfc("NonExistent")
    
    def test_remove_mfc(self, controller):
        """Test removing MFC from controller."""
        controller.add_mfc("CH4", "COM1", 1, "CH4")
        assert "CH4" in controller.list_mfcs()
        
        controller.remove_mfc("CH4")
        assert "CH4" not in controller.list_mfcs()
    
    def test_close_all_valves(self, controller):
        """Test closing all valves."""
        controller.add_mfc("CH4", "COM1", 1, "CH4")
        controller.add_mfc("H2", "COM1", 7, "H2")
        
        # Set some flows
        controller.get_mfc("CH4").set_flow_mfc(0.5)
        controller.get_mfc("H2").set_flow_mfc(0.5)
        
        # Close all
        controller.close_all_valves()
        
        # Check setpoints are zero
        assert controller.get_mfc("CH4").read_setpoint_mfc() == pytest.approx(0.0)
        assert controller.get_mfc("H2").read_setpoint_mfc() == pytest.approx(0.0)
    
    def test_read_all_flows(self, controller):
        """Test reading flows from all MFCs."""
        controller.add_mfc("CH4", "COM1", 1, "CH4")
        controller.add_mfc("H2", "COM1", 7, "H2")
        
        flows = controller.read_all_flows()
        
        assert "CH4" in flows
        assert "H2" in flows
    
    def test_context_manager(self):
        """Test controller as context manager."""
        with MFCController(use_mock=True) as controller:
            controller.add_mfc("CH4", "COM1", 1, "CH4")
            assert "CH4" in controller.list_mfcs()
        
        # After context, MFC should be disconnected
        # (Can't easily test this without reference)


class TestCreateStandardController:
    """Tests for create_standard_controller factory function."""
    
    def test_creates_standard_mfcs(self):
        """Test factory creates expected MFCs."""
        controller = create_standard_controller(use_mock=True)
        
        mfcs = controller.list_mfcs()
        assert "CH4" in mfcs
        assert "H2" in mfcs
        assert "Air" in mfcs
        
        coris = controller.list_cori_flows()
        assert "CoriFlow" in coris
    
    def test_mfcs_are_connected(self):
        """Test all MFCs are connected."""
        controller = create_standard_controller(use_mock=True)
        
        for name in controller.list_mfcs():
            mfc = controller.get_mfc(name)
            assert mfc.is_connected, f"{name} should be connected"
