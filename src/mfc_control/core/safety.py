"""
Safety Manager for MFC system.

Handles emergency operations like purge sequences and emergency stops.
Critical for combustion safety.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mfc_control.core.controller import MFCController

logger = logging.getLogger(__name__)


@dataclass
class SafetyManager:
    """
    Manages safety operations for the MFC system.
    
    Provides methods for:
    - Emergency stop (immediate valve closure)
    - Purge sequence (blow out flame with air, then close)
    - Safe disconnect procedure
    
    Attributes:
        controller: The MFCController this safety manager is attached to
        air_mfc_name: Name of the air MFC for purge operations
        purge_flow: Air flow rate during purge (l/min, MFC units)
        purge_duration: Duration of air purge (seconds)
        
    Warning:
        This is safety-critical code. Test thoroughly before use with
        real combustion systems.
    """
    
    controller: "MFCController"
    air_mfc_name: str = "Air"
    purge_flow: float = 30.0  # High air flow for extinguishing (MFC units)
    purge_duration: float = 10.0  # Seconds of air purge
    
    def emergency_stop(self) -> None:
        """
        Immediately close all valves.
        
        Use in emergency situations. Does not perform purge sequence -
        just closes everything as fast as possible.
        """
        logger.critical("EMERGENCY STOP ACTIVATED")
        self.controller.close_all_valves()
        logger.critical("All valves closed")
    
    def purge(self, air_mfc_name: str | None = None) -> None:
        """
        Execute purge sequence to safely extinguish flame.
        
        Sequence:
        1. Close all fuel valves (H2, CH4)
        2. Open air valve to high flow
        3. Wait for purge duration
        4. Close air valve
        
        Args:
            air_mfc_name: Name of air MFC (uses default if not specified)
        """
        air_name = air_mfc_name or self.air_mfc_name
        
        logger.warning("Starting purge sequence")

        # Step 1: Close fuel valves
        for name, mfc in self.controller.mfc_items():
            if name != air_name and mfc.is_connected:
                try:
                    mfc.close_valve()
                    logger.info(f"Closed {name}")
                except Exception as e:
                    logger.error(f"Failed to close {name}: {e}")
        
        # Step 2: Open air valve high
        try:
            air_mfc = self.controller.get_mfc(air_name)
            if air_mfc.is_connected:
                # Use MFC units directly for purge (bypass calibration)
                air_mfc.set_flow_mfc(self.purge_flow)
                logger.info(f"Air purge started at {self.purge_flow} l/min (MFC units)")
        except KeyError:
            logger.error(f"Air MFC '{air_name}' not found - cannot purge!")
            # Still try to close everything
            self.controller.close_all_valves()
            return
        except Exception as e:
            logger.error(f"Failed to start air purge: {e}")
            self.controller.close_all_valves()
            return
        
        # Step 3: Wait
        logger.info(f"Purging for {self.purge_duration} seconds...")
        time.sleep(self.purge_duration)
        
        # Step 4: Close air
        try:
            air_mfc.close_valve()
            logger.info("Air valve closed")
        except Exception as e:
            logger.error(f"Failed to close air valve: {e}")
        
        logger.warning("Purge sequence complete")
    
    def safe_disconnect(self) -> None:
        """
        Safely disconnect all devices.
        
        Performs purge sequence before disconnecting to ensure
        flame is extinguished.
        """
        logger.info("Starting safe disconnect procedure")
        self.purge()
        self.controller.disconnect_all()
        logger.info("Safe disconnect complete")
    
    def check_all_flows_zero(self, threshold: float = 0.01) -> bool:
        """
        Verify all MFC flows are at or near zero.
        
        Args:
            threshold: Maximum flow to consider as "zero" (l/min)
            
        Returns:
            True if all flows are below threshold
        """
        all_zero = True
        for name, mfc in self.controller.mfc_items():
            if mfc.is_connected:
                try:
                    flow = mfc.read_flow_mfc()
                    if abs(flow) > threshold:
                        logger.warning(f"{name} flow is {flow:.4f}, not zero")
                        all_zero = False
                except Exception as e:
                    logger.error(f"Failed to read {name}: {e}")
                    all_zero = False
        return all_zero
