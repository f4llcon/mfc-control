#!/usr/bin/env python3
"""
Diagnostic tools for debugging MFC communication issues.

Use this to troubleshoot when devices connect but don't respond.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def test_raw_communication(com_port: str, node_address: int, baudrate: int = 38400) -> dict[str, Any]:
    """
    Test raw communication with a device using high-level instrument API.

    Returns diagnostic information about what's working and what's not.
    """
    results = {
        'port': com_port,
        'node': node_address,
        'baudrate': baudrate,
        'port_opens': False,
        'instrument_created': False,
        'can_read_params': False,
        'errors': [],
        'data': {}
    }

    try:
        import propar
    except ImportError:
        results['errors'].append("propar library not installed")
        return results

    instrument = None
    # -------------------------------------------------------------
    # 1. Main TRY block for all operations that use 'master'
    # -------------------------------------------------------------
    try:
        # Step 1 & 2: Open Port, Create Master, and Start (Handled by instrument constructor)
        logger.info(f"Opening connection to {com_port} at {baudrate} baud...")
        instrument = propar.instrument(com_port, address=node_address, baudrate=baudrate)

        # If the line above succeeds, the port is open and master has started.
        results['port_opens'] = True
        results['master_starts'] = True 
        logger.info(f"✓ Port {com_port} opened and Master started successfully")

        # Step 3: Can we find nodes? (Use the instrument's master attribute)
        try:
            nodes = instrument.master.get_nodes(find_first=True)
            # ... (rest of Step 3 logic to set results['node_responds'] and check address) ...
            
        except Exception as e:
            results['errors'].append(f"Cannot scan for nodes: {e}")
            logger.error(f"✗ Node scan failed: {e}")

        # Step 4: Try to read parameters (Use the high-level instrument method)
        if results['node_responds'] and node_address in results['data'].get('found_nodes', []):
            try:
                # Use the high-level readParameter method that avoids the 'Zugriff verweigert' error
                test_params = {
                    'capacity': 21,
                    'measure': 205,
                    'device_tag': 115,
                }
                
                # Loop through test_params and use instrument.readParameter(param_num)
                # ... (Parameter reading logic goes here) ...
                
                results['can_read_params'] = True
                
            except Exception as e:
                results['errors'].append(f"Cannot read parameters: {e}")

        return results

    except Exception as e:
        results['errors'].append(f"Fatal connection or initialization error: {e}")
        return results

    # The final cleanup block is now essential and simple.
    finally:
        if instrument is not None and hasattr(instrument, 'master'):
            try:
                # Close the master (which was created implicitly by the instrument)
                instrument.master.stop()
                logger.debug(f"Closed connection to {com_port}")
            except Exception as e:
                logger.debug(f"Error during cleanup: {e}")

    return results

def test_multiple_baudrates(com_port: str, node_address: int) -> dict[int, dict]:
    """
    Test communication at different baud rates.

    MFCs might be configured for different baud rates than default 38400.
    """
    baudrates = [38400]
    results = {}

    logger.info(f"Testing {com_port}:{node_address} at multiple baud rates...")

    for baud in baudrates:
        logger.info(f"\n--- Testing {baud} baud ---")
        result = test_raw_communication(com_port, node_address, baudrate=baud)
        results[baud] = result

        if result['can_read_params']:
            logger.info(f"✓✓✓ SUCCESS at {baud} baud! ✓✓✓")
            return results  # Found working baud rate



def print_diagnostic_summary(results: dict[str, Any]) -> None:
    """Print human-readable diagnostic summary."""
    print("\n" + "="*60)
    print(f"DIAGNOSTIC RESULTS: {results['port']}:{results['node']} @ {results['baudrate']} baud")
    print("="*60)

    # Status checks
    checks = [
        ("Port Opens", results['port_opens']),
        ("Instrument Created", results['instrument_created']),
        ("Can Read Parameters", results['can_read_params']),
    ]

    for name, status in checks:
        symbol = "✓" if status else "✗"
        print(f"{symbol} {name}")

    # Parameters
    if 'parameters' in results['data']:
        print("\nParameter Reads:")
        for param, value in results['data']['parameters'].items():
            print(f"  {param}: {value}")

    # Errors
    if results['errors']:
        print("\nErrors:")
        for err in results['errors']:
            print(f"  • {err}")

    print("="*60 + "\n")


def diagnose_connection_issue(com_port: str, node_address: int = 1) -> str:
    """
    Run full diagnostics and return recommendation.
    """
    print(f"\nRunning diagnostics on {com_port}:{node_address}...\n")

    # Test at 38400 baud (standard for Bronkhorst)
    result = test_raw_communication(com_port, node_address, baudrate=38400)
    print_diagnostic_summary(result)

    if result['can_read_params']:
        return f"SUCCESS! Device is responding correctly at {result['baudrate']} baud."

    # Generate recommendation based on failure point
    if not result['port_opens']:
        return "PROBLEM: Cannot open port. Check Device Manager, close other programs using port."
    elif not result['master_starts']:
        return "PROBLEM: Port opens but master won't start. Check drivers/hardware."
    elif not result['node_responds']:
        return "PROBLEM: No nodes found on FLOW-BUS. Check: power, cables, termination resistors."
    elif result['node_responds'] and node_address not in result['data'].get('found_nodes', []):
        available = result['data'].get('found_nodes', [])
        # --- NEW LOGIC HERE ---
        if available:
            return f"PROBLEM: Node {node_address} not found. Found nodes: {available}\nRECOMMENDATION: Use the correct node address! Try running the diagnosis with address {available[0]}."
        else:
            return f"PROBLEM: Target node {node_address} not found, but scan saw no other nodes either."
    else:
        return "PROBLEM: Unknown issue. Check hardware connections and power."
