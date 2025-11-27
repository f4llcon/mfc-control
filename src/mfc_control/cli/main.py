#!/usr/bin/env python3
"""
Command-line interface for MFC Control System.

Provides an interactive shell for controlling MFCs, either connected
to real hardware or in mock mode for testing.

Usage:
    mfc-cli --mock           # Use mock devices (no hardware)
    mfc-cli --port COM1      # Connect to real hardware
    mfc-cli --help           # Show help
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from mfc_control.core.calibration import get_default_calibration
from mfc_control.core.controller import MFCController, create_standard_controller
from mfc_control.combustion.calculations import (
    calculate_phi,
    calculate_power,
    solve_power_mode,
    solve_volume_mode,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_banner() -> None:
    """Print welcome banner."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║             MFC Control System v0.1.0                     ║
║         Bronkhorst Mass Flow Controller Interface         ║
╚═══════════════════════════════════════════════════════════╝
    """)


def print_help() -> None:
    """Print available commands."""
    print("""
Available Commands:
-------------------------------------------------------------------
  status                 Show status of all devices
  list                   List all registered MFCs

  ports                  List all available COM ports on system
  scan [port]            Scan for MFC devices (all ports or specific port, e.g., scan COM6)
  discover               Scan specific port for devices (uses --port from startup)
  diagnose <port> [node] Deep diagnostic test (e.g., diagnose COM6 1)
  reset                  Close all connections (fixes "port already open" errors)
  autosetup              Auto-discover and interactively add devices

  read <name>            Read current flow from MFC
  set <name> <flow>      Set flow rate (real units, l/min)
  close <name>           Close valve (set flow to 0)
  closeall               Close all valves

  add <name> <node> <gas>   Add MFC dynamically (e.g., add CH4 1 CH4)
  remove <name>          Remove MFC from controller

  wink <name>            Make MFC blink its LED
  winkall                Make all devices blink

  phi                    Calculate phi from current flows
  power                  Calculate power from current flows

  volume <V> <phi>       Solve volume mode (H2-Air)
  pmode <P> <phi>        Solve power mode (H2-Air)

  purge                  Execute purge sequence
  estop                  Emergency stop (close all immediately)

  help                   Show this help
  quit / exit            Exit the program
-------------------------------------------------------------------
""")


def cmd_status(controller: MFCController) -> None:
    """Show status of all devices."""
    print("\nDevice Status:")
    print("─" * 60)
    
    for name in controller.list_mfcs():
        mfc = controller.get_mfc(name)
        status = "CONNECTED" if mfc.is_connected else "DISCONNECTED"
        
        if mfc.is_connected:
            try:
                flow = mfc.read_flow_real()
                setpoint = mfc.read_setpoint_real()
                print(f"  {name:12} [{status:12}] {mfc.gas_type:4} "
                      f"Flow: {flow:6.3f} l/min  Setpoint: {setpoint:6.3f} l/min")
            except Exception as e:
                print(f"  {name:12} [{status:12}] {mfc.gas_type:4} Error: {e}")
        else:
            print(f"  {name:12} [{status:12}] {mfc.gas_type:4}")
    
    for name in controller.list_cori_flows():
        cori = controller.get_cori_flow(name)
        status = "CONNECTED" if cori.is_connected else "DISCONNECTED"
        
        if cori.is_connected:
            try:
                flow = cori.read_flow_mfc()
                print(f"  {name:12} [{status:12}] CORI Flow: {flow:6.3f} l/min")
            except Exception as e:
                print(f"  {name:12} [{status:12}] CORI Error: {e}")
        else:
            print(f"  {name:12} [{status:12}] CORI")
    
    print()


def cmd_read(controller: MFCController, name: str) -> None:
    """Read flow from specified MFC."""
    try:
        mfc = controller.get_mfc(name)
        flow_real = mfc.read_flow_real()
        flow_mfc = mfc.read_flow_mfc()
        print(f"  {name}: {flow_real:.4f} l/min (real), {flow_mfc:.4f} l/min (MFC)")
    except KeyError:
        print(f"  Error: MFC '{name}' not found")
    except Exception as e:
        print(f"  Error reading {name}: {e}")


def cmd_set(controller: MFCController, name: str, flow: float) -> None:
    """Set flow for specified MFC."""
    try:
        mfc = controller.get_mfc(name)
        mfc.set_flow_real(flow)
        print(f"  {name}: Set to {flow:.4f} l/min (real)")
    except KeyError:
        print(f"  Error: MFC '{name}' not found")
    except ValueError as e:
        print(f"  Error: {e}")
    except Exception as e:
        print(f"  Error setting {name}: {e}")


def cmd_phi(controller: MFCController) -> None:
    """Calculate current equivalence ratio."""
    flows = controller.read_all_flows()
    
    v_h2 = flows.get("H2", 0.0)
    v_ch4 = flows.get("CH4", 0.0)
    v_air = flows.get("Air", 0.0)
    
    phi = calculate_phi(v_h2=v_h2, v_ch4=v_ch4, v_air=v_air)
    power = calculate_power(v_h2=v_h2, v_ch4=v_ch4)
    
    print(f"\n  Current Conditions:")
    print(f"    H2:    {v_h2:.4f} l/min")
    print(f"    CH4:   {v_ch4:.4f} l/min")
    print(f"    Air:   {v_air:.4f} l/min")
    print(f"    ─────────────────────")
    print(f"    φ:     {phi:.4f}")
    print(f"    Power: {power:.1f} W")
    print()


def cmd_volume_mode(controller: MFCController, v_total: float, phi: float) -> None:
    """Solve and optionally apply volume mode."""
    try:
        solution = solve_volume_mode(v_total, phi, fuel="H2")
        
        print(f"\n  Volume Mode Solution:")
        print(f"    Target: V_total={v_total:.3f} l/min, φ={phi:.3f}")
        print(f"    ─────────────────────")
        print(f"    H2:    {solution.v_h2:.4f} l/min")
        print(f"    Air:   {solution.v_air:.4f} l/min")
        print(f"    Power: {solution.power:.1f} W")
        
        response = input("\n  Apply these setpoints? [y/N]: ").strip().lower()
        if response == "y":
            controller.get_mfc("H2").set_flow_real(solution.v_h2)
            controller.get_mfc("Air").set_flow_real(solution.v_air)
            print("  Setpoints applied.")
        else:
            print("  Cancelled.")
        print()
        
    except ValueError as e:
        print(f"  Error: {e}")
    except KeyError as e:
        print(f"  Error: Required MFC not found: {e}")


def cmd_power_mode(controller: MFCController, power: float, phi: float) -> None:
    """Solve and optionally apply power mode."""
    try:
        solution = solve_power_mode(power, phi, fuel="H2")
        
        print(f"\n  Power Mode Solution:")
        print(f"    Target: Power={power:.1f} W, φ={phi:.3f}")
        print(f"    ─────────────────────")
        print(f"    H2:      {solution.v_h2:.4f} l/min")
        print(f"    Air:     {solution.v_air:.4f} l/min")
        print(f"    V_total: {solution.v_total:.4f} l/min")
        
        response = input("\n  Apply these setpoints? [y/N]: ").strip().lower()
        if response == "y":
            controller.get_mfc("H2").set_flow_real(solution.v_h2)
            controller.get_mfc("Air").set_flow_real(solution.v_air)
            print("  Setpoints applied.")
        else:
            print("  Cancelled.")
        print()
        
    except ValueError as e:
        print(f"  Error: {e}")
    except KeyError as e:
        print(f"  Error: Required MFC not found: {e}")


def run_interactive(controller: MFCController) -> None:
    """Run interactive command loop."""
    print_help()
    
    while True:
        try:
            line = input("mfc> ").strip()
            if not line:
                continue
            
            parts = line.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            # ─────────────────────────────────────────────────────────────
            # Navigation commands
            # ─────────────────────────────────────────────────────────────
            if cmd in ("quit", "exit", "q"):
                print("Shutting down...")
                break
            
            elif cmd in ("help", "h", "?"):
                print_help()
            
            # ─────────────────────────────────────────────────────────────
            # Status commands
            # ─────────────────────────────────────────────────────────────
            elif cmd == "status":
                cmd_status(controller)
            
            elif cmd == "list":
                print(f"  MFCs: {', '.join(controller.list_mfcs()) or '(none)'}")
                print(f"  CoriFlows: {', '.join(controller.list_cori_flows()) or '(none)'}")

            # ─────────────────────────────────────────────────────────────
            # Discovery commands
            # ─────────────────────────────────────────────────────────────
            elif cmd == "ports":
                try:
                    from mfc_control.hardware.connection import list_available_ports
                    ports = list_available_ports()
                    if ports:
                        print(f"  Available COM ports ({len(ports)}):")
                        for port in ports:
                            print(f"    {port}")
                    else:
                        print("  No COM ports found on system")
                except ImportError as e:
                    print(f"  Error: {e}")
                except Exception as e:
                    print(f"  Error listing ports: {e}")

            elif cmd == "scan":
                if controller.use_mock:
                    print("  Error: Cannot scan ports in mock mode")
                else:
                    scanned_port = None
                    try:
                        # Check if specific port was provided
                        if len(args) > 0:
                            # Scan specific port
                            specific_port = args[0]
                            scanned_port = specific_port
                            print(f"  Scanning {specific_port} for MFC devices...\n")
                            devices = controller._connection_manager.discover_devices(specific_port)

                            if devices:
                                # Remember this port for the add command
                                controller._discovery_port = specific_port
                                print(f"  ✓ Found {len(devices)} device(s) on {specific_port}:\n")
                                for dev in devices:
                                    print(f"    - Node {dev.address:3d}: {dev.device_type} (S/N: {dev.serial})")
                                print(f"\n  Use 'add <name> <node_address> <gas>' to add devices")
                            else:
                                print(f"  ✗ No MFC devices found on {specific_port}")
                                print("\n  Troubleshooting:")
                                print("    1. Check that devices are powered on")
                                print("    2. Verify correct baud rate (default: 38400)")
                                print("    3. Check physical connections")
                                print("    4. Try a different port with 'ports' command")
                        else:
                            # Scan all ports
                            print("  Scanning all COM ports for MFC devices...")
                            print("  (Check log messages above for port-specific errors)\n")
                            results = controller._connection_manager.discover_all_ports()

                            if results:
                                print(f"\n  ✓ Found devices on {len(results)} port(s):\n")
                                for port, devices in results.items():
                                    print(f"  {port}:")
                                    for dev in devices:
                                        print(f"    - Node {dev.address:3d}: {dev.device_type} (S/N: {dev.serial})")
                                print(f"\n  Use 'add <name> <node> <gas>' to add devices")
                                print(f"  Or use 'autosetup' for interactive configuration")
                            else:
                                print("\n  ✗ No MFC devices found on any port")
                                print("\n  Troubleshooting:")
                                print("    1. Check that devices are powered on")
                                print("    2. Close other programs using the ports (Device Manager, serial terminals)")
                                print("    3. Try unplugging and replugging USB connections")
                                print("    4. Check Windows Device Manager for port issues")
                                print("    5. Verify the device is a Bronkhorst MFC with FLOW-BUS protocol")
                    except Exception as e:
                        print(f"  Error during scan: {e}")
                    finally:
                        if scanned_port:
                            try:
                                controller._connection_manager.close_port(scanned_port)
                            except Exception as e:
                                logger.debug(f"Error closing port {scanned_port}: {e}")
                        else:
                            try:
                                controller._connection_manager.close_all()
                            except Exception as e:
                                logger.debug(f"Error closing ports: {e}")

            elif cmd == "autosetup":
                if controller.use_mock:
                    print("  Error: Cannot auto-setup in mock mode")
                else:
                    try:
                        print("  Auto-discovering MFC devices...\n")
                        results = controller._connection_manager.discover_all_ports()

                        if not results:
                            print("  No MFC devices found on any port")
                        else:
                            added_count = 0
                            for port, devices in results.items():
                                print(f"\n  Port: {port}")
                                for dev in devices:
                                    print(f"\n  Found: {dev.device_type} at node {dev.address}")
                                    print(f"  Serial: {dev.serial}")

                                    name = input(f"    Enter name (or press Enter to skip): ").strip()
                                    if name:
                                        if name in controller.list_mfcs():
                                            print(f"    Warning: '{name}' already exists, skipping")
                                            continue

                                        gas = input(f"    Enter gas type (CH4/H2/Air/N2/O2): ").strip()
                                        if not gas:
                                            print(f"    Skipping (no gas type provided)")
                                            continue

                                        try:
                                            controller.add_mfc(name, port, dev.address, gas, auto_connect=True)
                                            print(f"    ✓ Added '{name}' ({gas})")
                                            added_count += 1
                                        except Exception as e:
                                            print(f"    ✗ Error: {e}")

                            print(f"\n  Setup complete: {added_count} device(s) added")

                    except Exception as e:
                        print(f"  Error during auto-setup: {e}")

            elif cmd == "discover":
                if controller.use_mock:
                    print("  Error: Cannot discover devices in mock mode")
                else:
                    try:
                        # Use the COM port from startup or default
                        com_port = getattr(controller, '_discovery_port', 'COM1')
                        print(f"  Scanning {com_port} for devices...")
                        devices = controller.discover(com_port)
                        if devices:
                            print(f"  Found {len(devices)} device(s):")
                            for dev in devices:
                                print(f"    Node {dev.address:3d}: {dev.device_type} (S/N: {dev.serial})")
                        else:
                            print("  No devices found")
                    except Exception as e:
                        print(f"  Error: {e}")

            elif cmd == "diagnose":
                if controller.use_mock:
                    print("  Error: Cannot diagnose in mock mode")
                elif len(args) < 1:
                    print("  Usage: diagnose <port> [node_address]")
                    print("  Example: diagnose COM6 1")
                else:
                    try:
                        from mfc_control.cli.diagnostics import diagnose_connection_issue
                        port = args[0]
                        node = int(args[1]) if len(args) > 1 else 1

                        recommendation = diagnose_connection_issue(port, node)
                        print(f"\n{recommendation}\n")
                    except Exception as e:
                        print(f"  Error during diagnostics: {e}")
                        logger.exception("Diagnostic error")

            elif cmd == "reset":
                if controller.use_mock:
                    print("  (Mock mode - no connections to reset)")
                else:
                    try:
                        if controller._connection_manager is not None:
                            controller._connection_manager.close_all()
                            print("  ✓ All connections closed")
                            print("  You can now scan/diagnose ports again")
                        else:
                            print("  No connection manager to reset")
                    except Exception as e:
                        print(f"  Error resetting connections: {e}")

            # ─────────────────────────────────────────────────────────────
            # Dynamic MFC management
            # ─────────────────────────────────────────────────────────────
            elif cmd == "add":
                if len(args) < 3:
                    print("  Usage: add <name> <node_address> <gas_type>")
                    print("  Example: add CH4 1 CH4")
                else:
                    name = args[0]
                    try:
                        node = int(args[1])
                        gas = args[2]
                        com_port = getattr(controller, '_discovery_port', 'COM1')
                        controller.add_mfc(name, com_port, node, gas, auto_connect=True)
                        print(f"  Added MFC '{name}' at node {node} for {gas}")
                    except ValueError:
                        print(f"  Error: Invalid node address '{args[1]}'")
                    except Exception as e:
                        print(f"  Error: {e}")
            
            elif cmd == "remove":
                if len(args) < 1:
                    print("  Usage: remove <name>")
                else:
                    try:
                        controller.remove_mfc(args[0])
                        print(f"  Removed MFC '{args[0]}'")
                    except KeyError:
                        print(f"  Error: MFC '{args[0]}' not found")
            
            # ─────────────────────────────────────────────────────────────
            # Individual MFC commands
            # ─────────────────────────────────────────────────────────────
            elif cmd == "read":
                if len(args) < 1:
                    print("  Usage: read <mfc_name>")
                else:
                    cmd_read(controller, args[0])
            
            elif cmd == "set":
                if len(args) < 2:
                    print("  Usage: set <mfc_name> <flow_l_min>")
                else:
                    try:
                        flow = float(args[1])
                        cmd_set(controller, args[0], flow)
                    except ValueError:
                        print(f"  Error: Invalid flow value '{args[1]}'")
            
            elif cmd == "close":
                if len(args) < 1:
                    print("  Usage: close <mfc_name>")
                else:
                    try:
                        mfc = controller.get_mfc(args[0])
                        mfc.close_valve()
                        print(f"  {args[0]}: Valve closed")
                    except KeyError:
                        print(f"  Error: MFC '{args[0]}' not found")
            
            elif cmd == "closeall":
                controller.close_all_valves()
                print("  All valves closed")
            
            elif cmd == "wink":
                if len(args) < 1:
                    print("  Usage: wink <mfc_name>")
                else:
                    try:
                        mfc = controller.get_mfc(args[0])
                        mfc.wink()
                        print(f"  {args[0]}: Winking...")
                    except KeyError:
                        print(f"  Error: MFC '{args[0]}' not found")
            
            elif cmd == "winkall":
                controller.wink_all()
                print("  All devices winking...")
            
            # ─────────────────────────────────────────────────────────────
            # Calculation commands
            # ─────────────────────────────────────────────────────────────
            elif cmd == "phi":
                cmd_phi(controller)
            
            elif cmd == "power":
                cmd_phi(controller)  # Shows both phi and power
            
            elif cmd == "volume":
                if len(args) < 2:
                    print("  Usage: volume <total_flow_l_min> <phi>")
                else:
                    try:
                        v_total = float(args[0])
                        phi = float(args[1])
                        cmd_volume_mode(controller, v_total, phi)
                    except ValueError:
                        print("  Error: Invalid numeric values")
            
            elif cmd == "pmode":
                if len(args) < 2:
                    print("  Usage: pmode <power_W> <phi>")
                else:
                    try:
                        power = float(args[0])
                        phi = float(args[1])
                        cmd_power_mode(controller, power, phi)
                    except ValueError:
                        print("  Error: Invalid numeric values")
            
            # ─────────────────────────────────────────────────────────────
            # Safety commands
            # ─────────────────────────────────────────────────────────────
            elif cmd == "purge":
                print("  Starting purge sequence...")
                controller.safety.purge()
                print("  Purge complete")
            
            elif cmd == "estop":
                print("  EMERGENCY STOP!")
                controller.safety.emergency_stop()
            
            # ─────────────────────────────────────────────────────────────
            # Unknown command
            # ─────────────────────────────────────────────────────────────
            else:
                print(f"  Unknown command: {cmd}")
                print("  Type 'help' for available commands")
        
        except KeyboardInterrupt:
            print("\n  Use 'quit' to exit")
        
        except EOFError:
            print("\nShutting down...")
            break
        
        except Exception as e:
            print(f"  Error: {e}")
            logger.exception("Unhandled error in CLI")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MFC Control System - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mfc-cli --mock              Run with simulated MFCs (for testing)
  mfc-cli --port COM1         Connect to MFCs on COM1
  mfc-cli --port COM1 --debug Enable debug logging
        """,
    )
    
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock MFCs (no hardware required)",
    )
    parser.add_argument(
        "--port",
        type=str,
        default="COM1",
        help="Serial port for MFC connection (default: COM1)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--empty",
        action="store_true",
        help="Start with no MFCs (use 'add' command to add dynamically)",
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print_banner()
    
    # Create controller
    if args.mock:
        print("Starting in MOCK mode (no hardware)\n")
        if args.empty:
            controller = MFCController(use_mock=True)
            print("Empty controller - use 'add' command to add MFCs\n")
        else:
            controller = create_standard_controller(com_port=args.port, use_mock=True)
    else:
        print(f"Connecting to MFCs on {args.port}...\n")
        try:
            if args.empty:
                controller = MFCController(use_mock=False)
                controller._discovery_port = args.port  # Store for discover command
                print("Empty controller - use 'discover' to find devices, 'add' to add MFCs\n")
            else:
                controller = create_standard_controller(com_port=args.port, use_mock=False)
                controller._discovery_port = args.port
        except ImportError as e:
            print(f"Error: {e}")
            print("\nInstall bronkhorst-propar: pip install bronkhorst-propar")
            print("Or use --mock for testing without hardware")
            return 1
        except ConnectionError as e:
            print(f"Connection error: {e}")
            print("\nCheck that:")
            print(f"  1. MFCs are powered on")
            print(f"  2. Serial cable is connected to {args.port}")
            print(f"  3. No other software is using {args.port}")
            print("\nOr use --mock for testing without hardware")
            return 1
    
    try:
        run_interactive(controller)
    finally:
        controller.disconnect_all()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
