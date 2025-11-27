#!/usr/bin/env python3
"""Test script for new discovery features."""

from mfc_control.hardware.connection import list_available_ports, PortInfo

print("Testing list_available_ports()...")
try:
    ports = list_available_ports()
    print(f"Found {len(ports)} port(s):")
    for port in ports:
        print(f"  {port}")

    if not ports:
        print("  (No ports found - this is expected in Docker/VM)")

    print("\n✓ list_available_ports() works!")

except Exception as e:
    print(f"✗ Error: {e}")

print("\nTesting PortInfo class...")
try:
    test_port = PortInfo(
        device="COM3",
        description="USB Serial Port",
        manufacturer="FTDI"
    )
    print(f"  PortInfo: {test_port}")
    print("✓ PortInfo class works!")
except Exception as e:
    print(f"✗ Error: {e}")

print("\nAll tests completed!")
