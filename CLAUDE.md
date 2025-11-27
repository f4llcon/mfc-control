# MFC Control System

## Project Overview

Python application to control Bronkhorst Mass Flow Controllers (MFCs) for combustion experiments. This replaces an existing MATLAB application with improved, class-based architecture that supports dynamic MFC management.

## Quick Start

```bash
# Install in development mode
pip install -e ".[dev]"

# Run with mock MFCs (no hardware needed)
mfc-cli --mock

# Run tests
pytest
```

## Key Resources

- `docs/manuals/` - Bronkhorst MFC technical documentation (PDFs)
- `docs/matlab/` - Original MATLAB implementation for reference
- `docs/requirements_spec.md` - Detailed requirements document

## Hardware Configuration

- **Protocol**: FLOW-BUS over RS232
- **Library**: `bronkhorst-propar` (pip install bronkhorst-propar)
- **Default node addresses**: CH4=1, H2=7, Air=10, Cori-Flow=6
- **Default COM port**: COM1 (configurable)

## Key Technical Details

### MFC Parameters (DDE numbers used by bronkhorst-propar)

| Parameter | DDE | Type  | Description                           |
|-----------|-----|-------|---------------------------------------|
| Wink      | 1   | Write | LED control: 2=slow blink, 9=long     |
| Capacity  | 21  | Read  | Max flow rating (l/min)               |
| Device Tag| 115 | Read  | Device name string                    |
| fMeasure  | 205 | Read  | Current measured flow (l/min)         |
| fSetpoint | 206 | R/W   | Target setpoint (l/min)               |

### Calibration System

MFCs are factory-calibrated for nitrogen. Different gases require correction via lookup tables that map MFC readings to actual flow rates. The calibration works bidirectionally:

- `real_to_mfc(flow)`: Convert desired real flow → MFC setpoint
- `mfc_to_real(reading)`: Convert MFC reading → actual flow

### Combustion Calculations

```
Stoichiometric air = 4.762 × (0.5 × V_H2 + 2 × V_CH4)
Equivalence ratio φ = Stoichiometric_air / Actual_air
Thermal power (W) = V_fuel (l/min) × (1/60000) × density (kg/m³) × LHV (MJ/kg) × 10⁶
```

### Gas Properties (at STP)

| Gas | Density (kg/m³) | Molar Mass (g/mol) | LHV (MJ/kg) |
|-----|-----------------|-------------------|-------------|
| H2  | 0.0899          | 2.02              | 120.0       |
| CH4 | 0.7175          | 16.04             | 50.013      |
| Air | 1.293           | 28.96             | —           |

## Architecture

```
src/mfc_control/
├── core/
│   ├── mfc.py          # MFC and CoriFlowMeter classes
│   ├── controller.py   # MFCController - manages MFC collection
│   ├── calibration.py  # Calibration interpolation
│   └── safety.py       # Safety manager (purge, e-stop)
├── combustion/
│   ├── properties.py   # Gas properties
│   └── calculations.py # Phi, power, volume solvers
├── hardware/
│   ├── connection.py   # ProPar wrapper
│   └── mock.py         # Mock MFC for testing
└── cli/
    └── main.py         # Command-line interface
```

## Development Guidelines

1. **Always test with MockMFC first** before connecting to real hardware
2. **Safety features are critical** - purge sequence must work reliably
3. **Calibration tables are sacred** - don't modify without physical verification
4. **Type hints everywhere** - this is lab equipment, correctness matters

## Current Constraints

- NO Cantera integration yet (planned for future phase)
- Keep hardcoded calibration tables for now
- Target platform: Windows with Python 3.10+
- GUI is secondary priority - CLI must work first

## Common Tasks

### Adding a new gas type

1. Add properties to `src/mfc_control/combustion/properties.py`
2. Create calibration data file in `data/calibrations/`
3. Update stoichiometry in `calculations.py` if it's a fuel

### Adding a new MFC to the system

```python
controller.add_mfc(
    name="N2_purge",
    com_port="COM1",
    node_address=12,
    gas_type="N2",
    calibration=my_calibration  # or None if gas matches MFC calibration
)
```

### Running safety purge

```python
controller.safety.purge()  # High air flow, then close all
controller.safety.emergency_stop()  # Immediate close all valves
```
