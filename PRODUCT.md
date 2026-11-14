# PRODUCT.md
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Municipal traffic enforcement officers, smart-city surveillance operators, and roadway audit supervisors monitoring high-density vehicle intersections.

## Product Purpose
Sentinel Vanguard (TVDR - Traffic Violation Detection & Recognition) delivers automated real-time CCTV and video analysis for detecting moving traffic infractions including Signal Jumping (Red Light Violations), Unprotected Riders (No Helmet), Overcrowded Two-Wheelers (Triple Riding), and Wrong-Way Motion.

## Positioning
An offline-capable, local-first deep learning surveillance workstation providing transparent video calibration, zero-latency inference, and automated forensic evidence folder archiving without requiring third-party cloud analytics.

## Operating Context
Surveillance control rooms, audit workstations, and live automated review feeds monitoring high-density intersections.

## Capabilities and Constraints
- **Capabilities**: Precision video markup (stop lines, traffic signal ROI color detection, direction vectors), real-time deep learning inference, forensic evidentiary snapshot capture into session-isolated folders, and incident review.
- **Constraints**: Runs locally on macOS / Linux via PyTorch CPU/GPU and Flask web server at `http://localhost:5001`.

## Brand Commitments
- High-contrast Obsidian Command Center design language.
- Professional, mission-critical, authoritative operator interface.
- Zero-yellow design aesthetic: Emerald (`#10b981`), Electric Violet (`#8b5cf6`), and Crimson (`#ef4444`).

## Evidence on Hand
- Full-pipeline computer vision models with custom YOLOv5 weights in `models/best.pt`.
- Test surveillance video assets in project root and Downloads directory.
- Complete interactive web application running live at `http://localhost:5001`.

## Product Principles
1. Uncompromising operator clarity and high data density.
2. Mission-critical reliability: no silent failures during video surveillance streams.
3. Transparent calibration: operators can visually inspect and fine-tune detection zones and signal status in real time.
4. Non-destructive evidence handling with immutable session-based folder archiving.

## Accessibility & Inclusion
Strict adherence to WCAG AA contrast standards for dark-mode command center interfaces.
