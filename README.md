# GTM4Health Token Management System (TMS-QRcode)

A web-based Token Management and Queue Display System with QR code kiosk generation, multi-room support, and speech announcements.

## Features

- **📺 Main Display (`/` or `/display`)**: High-visibility waiting room display showing the current serving token, queue list, and voice announcements via Web Speech API.
- **🎫 Token Generation (`/token`)**: Web interface for patients to issue queue tickets for specific rooms and save/download tokens.
- **📢 Calling Console (`/next` or `/calling`)**: Operator/doctor dashboard to call the next token, recall the current token, or reset room queues.
- **📱 QR Code Kiosk (`/qr`)**: Instant QR code display for scanning and generating tokens from mobile devices.
- **🧭 Top-Right Navigation & Selection Menu**: Quickly switch between screens and change active rooms on the fly with state persistence.
- **🏥 Multi-Room Architecture**: Independent token queues, call counters, and announcements for Room 1, Room 2, Room 3, etc.

## Setup & Running

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server**:
   ```bash
   python tmsserver.py
   ```

3. **Access the application**:
   - Main Display: `http://<server-ip>:5000/`
   - Token Generation: `http://<server-ip>:5000/token`
   - Calling Console: `http://<server-ip>:5000/next`
   - QR Code: `http://<server-ip>:5000/qr`
