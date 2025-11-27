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
    try:
        logger.info(f"Opening connection to {com_port} at {baudrate} baud...")
        instrument = propar.instrument(com_port, address=node_address, baudrate=baudrate)
        results['port_opens'] = True
        results['instrument_created'] = True
        logger.info(f"✓ Instrument created for node {node_address} on {com_port}")

        test_params = {
            'capacity': 21,
            'measure': 205,
            'setpoint': 206,
            'device_tag': 115,
        }

        results['data']['parameters'] = {}
        params_read = 0

        for name, param_num in test_params.items():
            try:
                value = instrument.readParameter(param_num)
                results['data']['parameters'][name] = value
                if value is not None:
                    logger.info(f"✓ Read {name} (param {param_num}): {value}")
                    params_read += 1
                else:
                    logger.warning(f"✗ Read {name} (param {param_num}): None (no response)")
            except Exception as e:
                logger.error(f"✗ Failed to read {name}: {e}")
                results['data']['parameters'][name] = f"ERROR: {e}"
                results['errors'].append(f"Cannot read {name}: {e}")

        if params_read > 0:
            results['can_read_params'] = True

    except Exception as e:
        results['errors'].append(f"Cannot create instrument: {e}")
        logger.error(f"✗ Failed to create instrument: {e}")

    finally:
        if instrument is not None:
            try:
                if hasattr(instrument, 'master') and hasattr(instrument.master, 'stop'):
                    instrument.master.stop()
                    logger.debug(f"Closed connection to {com_port}")
                elif hasattr(instrument, 'close'):
                    instrument.close()
                    logger.debug(f"Closed connection to {com_port}")
            except Exception as e:
                logger.debug(f"Error during cleanup: {e}")

    return results




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
    elif not result['instrument_created']:
        return "PROBLEM: Port opens but instrument creation failed. Check drivers/hardware."
    elif result['instrument_created'] and not result['can_read_params']:
        return f"""PROBLEM: Instrument created but cannot read parameters. Possible causes:
1. Wrong node address (tried {node_address}) - use 'scan {com_port}' to find available nodes
2. Device not powered on
3. FLOW-BUS wiring issue (check RX/TX, termination resistors)
4. Device firmware not responding to FLOW-BUS protocol"""
    else:
        return "PROBLEM: Unknown issue. Check hardware connections and power."
