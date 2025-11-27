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
    Test raw communication with a device at various levels.

    Returns diagnostic information about what's working and what's not.
    """
    results = {
        'port': com_port,
        'node': node_address,
        'baudrate': baudrate,
        'port_opens': False,
        'master_starts': False,
        'node_responds': False,
        'can_read_params': False,
        'errors': [],
        'data': {}
    }

    try:
        import propar
    except ImportError:
        results['errors'].append("propar library not installed")
        return results

    # Step 1: Can we open the port?
    try:
        master = propar.master(com_port, baudrate=baudrate)
        results['port_opens'] = True
        logger.info(f"✓ Port {com_port} opened successfully")
    except Exception as e:
        results['errors'].append(f"Cannot open port: {e}")
        return results

    # Step 2: Can we start the master?
    try:
        master.start()
        results['master_starts'] = True
        logger.info(f"✓ Master started on {com_port}")
    except Exception as e:
        results['errors'].append(f"Cannot start master: {e}")
        return results

    # Step 3: Can we find nodes?
    try:
        nodes = master.get_nodes(find_first=True)
        if nodes:
            results['node_responds'] = True
            results['data']['found_nodes'] = [n.get('address') for n in nodes]
            logger.info(f"✓ Found {len(nodes)} node(s): {results['data']['found_nodes']}")

            # Check if our target node is in the list
            if node_address in results['data']['found_nodes']:
                logger.info(f"✓ Target node {node_address} found!")
            else:
                logger.warning(f"✗ Target node {node_address} NOT found. Available: {results['data']['found_nodes']}")
        else:
            results['errors'].append("No nodes found on FLOW-BUS")
            logger.warning(f"✗ No nodes responded on {com_port}")
    except Exception as e:
        results['errors'].append(f"Cannot scan for nodes: {e}")
        logger.error(f"✗ Node scan failed: {e}")

    # Step 4: Try to read parameters from target node
    if results['node_responds']:
        try:
            instrument = propar.instrument(com_port, address=node_address, baudrate=baudrate)

            # Try reading common parameters
            test_params = {
                'capacity': 21,
                'measure': 205,
                'setpoint': 206,
                'device_tag': 115,
            }

            results['data']['parameters'] = {}
            for name, param_num in test_params.items():
                try:
                    value = instrument.readParameter(param_num)
                    results['data']['parameters'][name] = value
                    if value is not None:
                        logger.info(f"✓ Read {name} (param {param_num}): {value}")
                        results['can_read_params'] = True
                    else:
                        logger.warning(f"✗ Read {name} (param {param_num}): None (no response)")
                except Exception as e:
                    logger.error(f"✗ Failed to read {name}: {e}")
                    results['data']['parameters'][name] = f"ERROR: {e}"

        except Exception as e:
            results['errors'].append(f"Cannot create instrument: {e}")

    # Cleanup
    try:
        master.stop()
    except:
        pass

    return results


def test_multiple_baudrates(com_port: str, node_address: int) -> dict[int, dict]:
    """
    Test communication at different baud rates.

    MFCs might be configured for different baud rates than default 38400.
    """
    baudrates = [9600, 19200, 38400, 57600, 115200]
    results = {}

    logger.info(f"Testing {com_port}:{node_address} at multiple baud rates...")

    for baud in baudrates:
        logger.info(f"\n--- Testing {baud} baud ---")
        result = test_raw_communication(com_port, node_address, baudrate=baud)
        results[baud] = result

        if result['can_read_params']:
            logger.info(f"✓✓✓ SUCCESS at {baud} baud! ✓✓✓")
            return results  # Found working baud rate

    return results


def print_diagnostic_summary(results: dict[str, Any]) -> None:
    """Print human-readable diagnostic summary."""
    print("\n" + "="*60)
    print(f"DIAGNOSTIC RESULTS: {results['port']}:{results['node']} @ {results['baudrate']} baud")
    print("="*60)

    # Status checks
    checks = [
        ("Port Opens", results['port_opens']),
        ("Master Starts", results['master_starts']),
        ("Node Responds", results['node_responds']),
        ("Can Read Parameters", results['can_read_params']),
    ]

    for name, status in checks:
        symbol = "✓" if status else "✗"
        print(f"{symbol} {name}")

    # Found nodes
    if 'found_nodes' in results['data']:
        print(f"\nNodes found: {results['data']['found_nodes']}")

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

    # First try default baudrate
    result = test_raw_communication(com_port, node_address)
    print_diagnostic_summary(result)

    if result['can_read_params']:
        return f"SUCCESS! Device is responding correctly at {result['baudrate']} baud."

    # If that didn't work, try other baud rates
    if result['port_opens'] and result['master_starts']:
        print("\nTrying different baud rates...")
        baud_results = test_multiple_baudrates(com_port, node_address)

        for baud, res in baud_results.items():
            if res['can_read_params']:
                return f"SUCCESS! Device responds at {baud} baud (not default {result['baudrate']}).\nUse: mfc-cli --baudrate {baud}"

    # Generate recommendation
    if not result['port_opens']:
        return "PROBLEM: Cannot open port. Check Device Manager, close other programs using port."
    elif not result['master_starts']:
        return "PROBLEM: Port opens but master won't start. Check drivers/hardware."
    elif not result['node_responds']:
        return "PROBLEM: No nodes found on FLOW-BUS. Check: power, cables, termination resistors."
    elif result['node_responds'] and node_address not in result['data'].get('found_nodes', []):
        available = result['data'].get('found_nodes', [])
        return f"PROBLEM: Node {node_address} not found. Found nodes: {available}\nUse correct node address!"
    else:
        return "PROBLEM: Nodes found but parameters return None. Check: baud rate, FLOW-BUS protocol, firmware."
