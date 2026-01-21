# PetWALK Local API Integratio

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
![Release](https://img.shields.io/github/v/release/Dav41K9/newhapetwalk)

Control your PetWALK smart door **locally** via REST API (port 8080) – no cloud required.

## Requirements
- PetWALK.control module firmware ≥ 1.1
- REST API enabled (PetWALK app → Advanced → REST API)

## Installation (HACS – recommended)
1. Add this repository to HACS (Custom repositories)
2. Install "PetWALK"
3. Restart Home Assistant
4. Settings → Devices & Services → Add Integration → PetWALK

## Configuration
- IP address (same used in the official app)
- Username / Password (same as app)
- Port (default 8080)
- Flag “Include all door events” to create pet sensors/trackers

## Entities provided
- **Cover**: Door open / close
- **Switches**: Brightness sensor, Motion IN/OUT, RFID, Time, System
- **Device Tracker**: one per pet (if enabled)
- **Sensor**: last event timestamp per pet (if enabled)

## Support
[GitHub Issues](https://github.com/Dav41K9/hapetwalk/issues)

