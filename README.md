# MFC Control System

Python application for controlling Bronkhorst Mass Flow Controllers (MFCs) in combustion experiments.

## Features

- **Dynamic Port Discovery**: Automatically scan and detect MFC devices on all COM ports
- **Dynamic MFC Management**: Add and remove MFCs at runtime
- **Calibration System**: Bidirectional conversion between MFC readings and real gas flow rates
- **Multiple Operating Modes**:
  - Manual: Direct control of individual gas flows
  - Volume: Specify total flow rate + equivalence ratio
  - Power: Specify thermal power output + equivalence ratio
- **Safety Features**: Purge sequences, emergency stop, deviation monitoring
- **Diagnostics**: Built-in tools for troubleshooting hardware communication
- **Mock Mode**: Full testing without hardware connection

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/mfc-control.git
cd mfc-control

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # On Windows

# Install in development mode
pip install -e ".[dev]"
```

## Quick Start

### Testing without hardware (Mock Mode)

```bash
mfc-cli --mock
```

### Connecting to real MFCs

```bash
# Auto-discover devices on all ports
mfc-cli
mfc> autosetup

# Or scan a specific port
mfc> scan COM6
mfc> add helium 5 He
mfc> set helium 2.5
mfc> status
```

### CLI Commands

- `ports` - List all available COM ports
- `scan [port]` - Scan for MFC devices (all ports or specific port)
- `diagnose <port> <node>` - Test communication with a device
- `autosetup` - Interactive device discovery and configuration
- `add <name> <node> <gas>` - Add an MFC (uses last scanned port)
- `remove <name>` - Remove an MFC
- `set <name> <flow>` - Set flow rate in l/min
- `read <name>` - Read current flow
- `status` - Show all devices
- `reset` - Close all port connections
- `help` - Show all commands

### Python API

```python
from mfc_control import MFCController, Calibration

# Create controller
controller = MFCController()

# Define calibration for CH4
ch4_cal = Calibration(
    mfc_values=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0],
    real_values=[0.325, 0.286, 0.251, 0.215, 0.182, 0.151, 0.120, 0.089, 0.058, 0.028, 0]
)

# Add MFC
controller.add_mfc(
    name="CH4_main",
    com_port="COM6",
    node_address=5,
    gas_type="CH4",
    calibration=ch4_cal
)

# Set flow in real units (l/min)
controller.get_mfc("CH4_main").set_flow_real(0.2)

# Read back
measured = controller.get_mfc("CH4_main").read_flow_real()
print(f"Measured: {measured:.3f} l/min")

# Clean up
controller.disconnect_all()
```

## Project Structure

```
mfc-control/
├── src/mfc_control/
│   ├── core/           # MFC, Controller, Calibration, Safety
│   ├── combustion/     # Gas properties, calculations
│   ├── hardware/       # ProPar wrapper, connection manager, mock devices
│   └── cli/            # Command-line interface, diagnostics
├── tests/              # Unit tests (use mock devices)
├── data/calibrations/  # Calibration data files
└── docs/               # Documentation and manuals
```

## Hardware Requirements

- Bronkhorst MFCs with FLOW-BUS interface (RS232/RS485)
- RS232 serial connection (USB-to-Serial adapter supported)
- Windows PC (tested on Windows 10/11)

## How It Works

### FLOW-BUS Protocol

Multiple MFC devices can share a single COM port using the FLOW-BUS protocol (RS485 multidrop):
- Each device has a unique node address (1-127)
- Example: COM6 might have nodes 1, 5, 7, 10 for different gases
- Communication at 38400 baud (standard for Bronkhorst)

### Calibration

MFCs are factory-calibrated for nitrogen. For other gases, calibration tables convert between:
- MFC readings (device units, 0-1)
- Real flow rates (l/min)

Default calibrations provided for CH4, H2, Air, and Cori-Flow meters.

### Testing

Tests use mock devices (no hardware required):

```bash
pytest  # Run all tests
pytest tests/test_mfc.py -v  # Run specific test file
```

All tests pass without hardware. They verify:
- Calibration math
- Gas property calculations
- MFC API logic
- Safety sequences

## Safety Notes

⚠️ **This software controls combustible gas flow. Always:**

1. Verify physical safety interlocks are in place
2. Test with mock mode before connecting to hardware
3. Keep manual shutoff valves accessible
4. Never leave unattended during operation

## Troubleshooting

### Port Access Errors

If you see "Zugriff verweigert" or "Access denied":
1. Run `reset` command to close stuck connections
2. Close other programs using the port (PuTTY, Arduino IDE, etc.)
3. Check Windows Device Manager for port conflicts

### Device Not Responding

If `diagnose` shows "Cannot read parameters":
1. Verify device is powered on
2. Check node address matches device configuration
3. Verify wiring (RX/TX, ground)
4. Check termination resistors on FLOW-BUS

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest`
4. Submit a pull request
