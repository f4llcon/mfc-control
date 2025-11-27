# MFC Control System

A Python application for controlling Bronkhorst Mass Flow Controllers (MFCs) in combustion experiments.

## Features

- **Dynamic MFC Management**: Add and remove MFCs at runtime without code changes
- **Calibration System**: Bidirectional conversion between MFC readings and real gas flow rates
- **Multiple Operating Modes**:
  - Manual: Direct control of individual gas flows
  - Volume: Specify total flow rate + equivalence ratio
  - Power: Specify thermal power output + equivalence ratio
- **Safety Features**: Purge sequences, emergency stop, deviation monitoring
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
mfc-cli --port COM1
```

### Python API

```python
from mfc_control import MFCController, MFC, Calibration

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
    com_port="COM1", 
    node_address=1,
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
│   ├── hardware/       # ProPar wrapper, mock devices
│   └── cli/            # Command-line interface
├── tests/              # Unit tests
├── data/calibrations/  # Calibration data files
└── docs/               # Documentation and manuals
```

## Hardware Requirements

- Bronkhorst MFCs with FLOW-BUS interface
- RS232 serial connection (USB-to-Serial adapter works)
- Windows PC (Linux support planned)

## Safety Notes

⚠️ **This software controls combustible gas flow. Always:**

1. Verify physical safety interlocks are in place
2. Test with mock mode before connecting to hardware
3. Keep manual shutoff valves accessible
4. Never leave unattended during operation

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest`
4. Submit a pull request
