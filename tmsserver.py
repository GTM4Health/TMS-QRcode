from flask import Flask, request, jsonify, Response, send_from_directory, send_file
from datetime import datetime
from io import BytesIO
import socket
import uuid
import qrcode

app = Flask(__name__)

PORT = 5000
LOGO_FILE = "logo.png"


# ============================================================
# TOKEN DATA
# ============================================================

rooms = {
    1: {
        "last_token": 0,
        "current_token": None,
        "pending": [],
        "completed": [],
        "token_records": {},
        "announcement_id": 0
    }
}


def get_room(room_number=1):
    room_number = int(room_number)

    if room_number not in rooms:
        rooms[room_number] = {
            "last_token": 0,
            "current_token": None,
            "pending": [],
            "completed": [],
            "token_records": {},
            "announcement_id": 0
        }

    return rooms[room_number]


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


# ============================================================
# LOGO
# Put logo.png in the same folder as this file.
# ============================================================

@app.route("/logo.png")
def logo():
    return send_from_directory(".", LOGO_FILE)


# ============================================================
# API - STATUS
# ============================================================

@app.route("/api/status", methods=["GET"])
def get_status():
    room_number = request.args.get("room", 1, type=int)
    room = get_room(room_number)

    return jsonify({
        "success": True,
        "room": room_number,
        "last_token": room["last_token"],
        "current_token": room["current_token"],
        "pending": room["pending"],
        "completed": room["completed"],
        "announcement_id": room["announcement_id"]
    })


# ============================================================
# API - GENERATE TOKEN
# ============================================================

@app.route("/api/token", methods=["POST"])
def generate_token():
    data = request.get_json(silent=True) or {}
    room_number = int(data.get("room", 1))

    room = get_room(room_number)

    room["last_token"] += 1
    new_token = room["last_token"]

    token_id = str(uuid.uuid4())

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    room["pending"].append(new_token)

    room["token_records"][token_id] = {
        "token": new_token,
        "token_id": token_id,
        "created_at": created_at,
        "room": room_number
    }

    print(f"NEW TOKEN GENERATED: {new_token}")

    return jsonify({
        "success": True,
        "token": new_token,
        "token_id": token_id,
        "created_at": created_at,
        "room": room_number
    })


# ============================================================
# API - TOKEN STATUS
# ============================================================

@app.route("/api/token-status", methods=["GET"])
def token_status():
    token_id = request.args.get("token_id")

    if not token_id:
        return jsonify({
            "success": False,
            "message": "Token ID is required"
        }), 400

    for room in rooms.values():
        record = room["token_records"].get(token_id)

        if record:
            token = record["token"]

            if room["current_token"] == token:
                status = "current"
            elif token in room["pending"]:
                status = "pending"
            elif token in room["completed"]:
                status = "completed"
            else:
                status = "unknown"

            return jsonify({
                "success": True,
                **record,
                "status": status
            })

    return jsonify({
        "success": False,
        "message": "Token not found"
    }), 404


# ============================================================
# API - NEXT TOKEN
# ============================================================

@app.route("/api/next", methods=["POST"])
def next_token():
    data = request.get_json(silent=True) or {}
    room_number = int(data.get("room", 1))

    room = get_room(room_number)

    # The previous current token becomes completed.
    if room["current_token"] is not None:
        previous_token = room["current_token"]

        if previous_token not in room["completed"]:
            room["completed"].append(previous_token)

        room["current_token"] = None

    # Call the oldest pending token.
    if room["pending"]:
        next_token_number = room["pending"].pop(0)
        room["current_token"] = next_token_number
        room["announcement_id"] += 1

        print(f"NEXT TOKEN CALLED: {next_token_number}")

        return jsonify({
            "success": True,
            "token": next_token_number,
            "room": room_number,
            "announcement_id": room["announcement_id"]
        })

    print("NO MORE TOKENS IN QUEUE")

    return jsonify({
        "success": False,
        "message": "No more tokens in queue"
    })


# ============================================================
# API - CALL AGAIN
# ============================================================

@app.route("/api/call-again", methods=["POST"])
def call_again():
    data = request.get_json(silent=True) or {}
    room_number = int(data.get("room", 1))

    room = get_room(room_number)

    if room["current_token"] is None:
        return jsonify({
            "success": False,
            "message": "No current token to call"
        })

    # Increment this so Main Display knows that it must
    # announce the same token again.
    room["announcement_id"] += 1

    print(f"TOKEN CALLED AGAIN: {room['current_token']}")

    return jsonify({
        "success": True,
        "token": room["current_token"],
        "room": room_number,
        "announcement_id": room["announcement_id"]
    })


# ============================================================
# API - RESET
# ============================================================

@app.route("/api/reset", methods=["POST"])
def reset_tokens():
    data = request.get_json(silent=True) or {}
    room_number = int(data.get("room", 1))

    rooms[room_number] = {
        "last_token": 0,
        "current_token": None,
        "pending": [],
        "completed": [],
        "token_records": {},
        "announcement_id": 0
    }

    print("TOKENS RESET")

    return jsonify({
        "success": True
    })


# ============================================================
# QR CODE PAGE
# ============================================================
# QR CODE
# ============================================================

@app.route("/qr")
def qr_page():
    room_number = request.args.get("room", 1, type=int)
    ip = get_local_ip()
    token_url = f"http://{ip}:{PORT}/token?room={room_number}" if room_number != 1 else f"http://{ip}:{PORT}/token"
    qr_img_src = f"/qr-image?room={room_number}" if room_number != 1 else "/qr-image"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GTM4Health QR Code</title>
<style>
* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    min-height: 100vh;
    background: #eef6fb;
    font-family: Arial, "Segoe UI", sans-serif;
    display: flex;
    flex-direction: column;
    color: #12314d;
}}
.header {{
    width: 100%;
    min-height: 82px;
    background: #0b4f7c;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 5vw;
    color: white;
    box-shadow: 0 2px 8px rgba(0,0,0,.12);
    position: relative;
    z-index: 1000;
}}
.header-brand {{
    display: flex;
    align-items: center;
    gap: 20px;
}}
.logo-link {{
    display: flex;
    align-items: center;
    text-decoration: none;
}}
.logo {{
    height: 48px;
    width: auto;
    max-width: 190px;
    object-fit: contain;
}}
.header-title {{
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 1px;
    white-space: nowrap;
}}
.header-nav-right {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-left: auto;
}}
.room-selector-box {{
    display: flex;
    align-items: center;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 8px;
    padding: 4px 10px;
    gap: 6px;
}}
.room-selector-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #d0e5f5;
}}
.room-select {{
    background: transparent;
    border: none;
    color: white;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    outline: none;
    font-family: inherit;
}}
.room-select option {{
    background: #0b4f7c;
    color: white;
}}
.menu-container {{
    position: relative;
}}
.menu-trigger-btn {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.32);
    color: white;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s ease;
}}
.menu-trigger-btn:hover {{
    background: #1683c4;
    border-color: #1683c4;
}}
.menu-popover {{
    display: none;
    position: absolute;
    top: calc(100% + 10px);
    right: 0;
    width: 280px;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 12px 36px rgba(11,79,124,0.25), 0 2px 8px rgba(0,0,0,0.1);
    border: 1px solid #d4e4f2;
    padding: 12px;
    z-index: 2000;
}}
.menu-popover.open {{ display: block; }}
.menu-section-header {{
    font-size: 11px;
    font-weight: 700;
    color: #607080;
    letter-spacing: 1.2px;
    padding: 4px 8px 6px;
    text-transform: uppercase;
}}
.menu-nav-link {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 12px;
    border-radius: 8px;
    text-decoration: none;
    color: #12314d;
    transition: all 0.15s ease;
}}
.menu-nav-link:hover {{ background: #eef6fb; color: #0b4f7c; }}
.menu-nav-link.active {{ background: #e1effa; color: #0b4f7c; font-weight: 600; border-left: 3px solid #1683c4; }}
.menu-link-icon {{ font-size: 18px; width: 24px; text-align: center; }}
.menu-link-content {{ display: flex; flex-direction: column; }}
.menu-link-title {{ font-size: 14px; line-height: 1.2; }}
.menu-link-desc {{ font-size: 11px; color: #6d8498; margin-top: 2px; }}
.menu-divider {{ height: 1px; background: #e2edf5; margin: 8px 0; }}
.menu-rooms-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; padding: 4px; }}
.room-btn {{
    padding: 7px 0;
    background: #f0f6fa;
    border: 1px solid #d0e2f0;
    border-radius: 6px;
    color: #0b4f7c;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    font-family: inherit;
    transition: all 0.15s ease;
}}
.room-btn:hover {{ background: #1683c4; border-color: #1683c4; color: white; }}
.room-btn.active {{ background: #0b4f7c; border-color: #0b4f7c; color: white; }}

.qr-container {{
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 30px 20px;
}}
.card {{
    width: min(420px, 100%);
    background: white;
    border-radius: 16px;
    padding: 30px 24px;
    text-align: center;
    box-shadow: 0 8px 30px rgba(12,68,105,.12);
}}
h1 {{ margin: 0 0 8px; color: #0b4f7c; font-size: 25px; }}
p {{ color: #607080; line-height: 1.5; }}
.qr {{ width: min(280px, 75vw); height: auto; margin: 16px auto; display: block; }}
.url {{ background: #eef6fb; border-radius: 8px; padding: 12px; word-break: break-all; color: #31556e; font-size: 13px; }}
.footer {{ padding: 16px 20px; text-align: center; font-size: 13px; color: white; background: #0b4f7c; }}

@media (max-width: 850px) {{
    .header {{ padding: 10px 14px; min-height: 64px; }}
    .header-brand {{ gap: 8px; }}
    .logo {{ height: 36px; max-width: 120px; margin-right: 0; }}
    .header-title {{ font-size: 15px; }}
    .room-selector-label {{ display: none; }}
    .room-selector-box {{ padding: 2px 6px; }}
    .room-select {{ font-size: 13px; }}
    .menu-btn-text {{ display: none; }}
    .menu-trigger-btn {{ padding: 7px 10px; }}
    .menu-popover {{ width: 250px; right: 0; }}
}}
@media (max-width: 480px) {{
    .header-title {{ display: none; }}
}}
</style>
</head>
<body>

<div class="header">
    <div class="header-brand">
        <a href="/" class="logo-link">
            <img src="/logo.png" class="logo" alt="GTM4Health">
        </a>
        <div class="header-title">QR CODE KIOSK</div>
    </div>
    <div class="header-nav-right">
        <div class="room-selector-box" title="Select Room">
            <span class="room-selector-label">ROOM</span>
            <select class="room-select" onchange="switchQrRoom(this.value)" aria-label="Select Room">
                <option value="1">Room 1</option>
                <option value="2">Room 2</option>
                <option value="3">Room 3</option>
                <option value="4">Room 4</option>
                <option value="5">Room 5</option>
                <option value="6">Room 6</option>
            </select>
        </div>
        <div class="menu-container">
            <button class="menu-trigger-btn" onclick="toggleNavMenu(event)" aria-label="Select Menu">
                <span>☰</span>
                <span><span class="menu-btn-text">Select</span> ▾</span>
            </button>
            <div class="menu-popover">
                <div class="menu-section-header">Select Page</div>
                <a href="/?room={room_number}" class="menu-nav-link">
                    <span class="menu-link-icon">📺</span>
                    <div class="menu-link-content">
                        <span class="menu-link-title">Main Display</span>
                        <span class="menu-link-desc">Queue screen</span>
                    </div>
                </a>
                <a href="/token?room={room_number}" class="menu-nav-link">
                    <span class="menu-link-icon">🎫</span>
                    <div class="menu-link-content">
                        <span class="menu-link-title">Token Generation</span>
                        <span class="menu-link-desc">Get new token</span>
                    </div>
                </a>
                <a href="/next?room={room_number}" class="menu-nav-link">
                    <span class="menu-link-icon">📢</span>
                    <div class="menu-link-content">
                        <span class="menu-link-title">Calling Console</span>
                        <span class="menu-link-desc">Call next patient</span>
                    </div>
                </a>
                <a href="/qr?room={room_number}" class="menu-nav-link active">
                    <span class="menu-link-icon">📱</span>
                    <div class="menu-link-content">
                        <span class="menu-link-title">QR Code</span>
                        <span class="menu-link-desc">Patient scan & take token</span>
                    </div>
                </a>
                <div class="menu-divider"></div>
                <div class="menu-section-header">Select Room</div>
                <div class="menu-rooms-grid">
                    <button type="button" class="room-btn" data-room="1" onclick="switchQrRoom(1)">Room 1</button>
                    <button type="button" class="room-btn" data-room="2" onclick="switchQrRoom(2)">Room 2</button>
                    <button type="button" class="room-btn" data-room="3" onclick="switchQrRoom(3)">Room 3</button>
                    <button type="button" class="room-btn" data-room="4" onclick="switchQrRoom(4)">Room 4</button>
                    <button type="button" class="room-btn" data-room="5" onclick="switchQrRoom(5)">Room 5</button>
                    <button type="button" class="room-btn" data-room="6" onclick="switchQrRoom(6)">Room 6</button>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="qr-container">
    <div class="card">
        <h1>GTM4Health</h1>
        <p>Scan to generate a queue token for <strong>Room {room_number}</strong>.</p>
        <img class="qr" src="{qr_img_src}" alt="QR Code">
        <div class="url">{token_url}</div>
    </div>
</div>

<div class="footer">
    © GTM4Health 2026
</div>

<script>
const currentRoom = {room_number};
document.querySelector(".room-select").value = currentRoom;
document.querySelectorAll(".room-btn").forEach(btn => {{
    if (parseInt(btn.getAttribute("data-room")) === currentRoom) {{
        btn.classList.add("active");
    }}
}});

function switchQrRoom(room) {{
    window.location.href = "/qr?room=" + room;
}}

function toggleNavMenu(event) {{
    if (event) event.stopPropagation();
    const popover = document.querySelector(".menu-popover");
    if (popover) popover.classList.toggle("open");
}}

document.addEventListener("click", function(e) {{
    if (!e.target.closest(".menu-container")) {{
        const popover = document.querySelector(".menu-popover");
        if (popover) popover.classList.remove("open");
    }}
}});
</script>
</body>
</html>"""

    return Response(html, mimetype="text/html")


@app.route("/qr-image")
def qr_image():
    room_number = request.args.get("room", 1, type=int)
    ip = get_local_ip()
    token_url = f"http://{ip}:{PORT}/token?room={room_number}" if room_number != 1 else f"http://{ip}:{PORT}/token"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(token_url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    return send_file(
        output,
        mimetype="image/png",
        download_name="GTM4Health_Token_QR.png"
    )


# ============================================================
# WEBSITE
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>GTM4Health Token Management</title>

<style>

/* ============================================================
   GLOBAL
   ============================================================ */

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    padding: 0;
    min-height: 100%;
}

body {
    font-family:
        Arial,
        "Segoe UI",
        sans-serif;

    background: #eef6fb;
    color: #12314d;
}

.page {
    display: none;
    min-height: 100vh;
}

.page.active {
    display: flex;
}


/* ============================================================
   HEADER & TOP-RIGHT MENU
   ============================================================ */

.header {
    width: 100%;
    min-height: 82px;

    background: #0b4f7c;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding:
        12px
        5vw;

    color: white;

    box-shadow:
        0 2px 8px
        rgba(0,0,0,.12);

    position: relative;
    z-index: 1000;
}

.header-brand {
    display: flex;
    align-items: center;
    gap: 20px;
}

.logo-link {
    display: flex;
    align-items: center;
    text-decoration: none;
}

.logo {
    height: 48px;
    width: auto;
    max-width: 190px;

    object-fit: contain;
    object-position: left center;
}

.header-title {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 1px;
    white-space: nowrap;
}

.header-nav-right {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-left: auto;
}

/* Room selector quick box */
.room-selector-box {
    display: flex;
    align-items: center;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 8px;
    padding: 4px 10px;
    gap: 6px;
    transition: background 0.2s ease;
}

.room-selector-box:hover {
    background: rgba(255, 255, 255, 0.22);
}

.room-selector-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #d0e5f5;
    user-select: none;
}

.room-select {
    background: transparent;
    border: none;
    color: white;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    outline: none;
    font-family: inherit;
}

.room-select option {
    background: #0b4f7c;
    color: white;
}

/* Menu Dropdown Container */
.menu-container {
    position: relative;
}

.menu-trigger-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.32);
    color: white;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s ease;
    user-select: none;
}

.menu-trigger-btn:hover {
    background: #1683c4;
    border-color: #1683c4;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15);
}

.menu-icon-bars {
    font-size: 15px;
    line-height: 1;
}

/* Popover */
.menu-popover {
    display: none;
    position: absolute;
    top: calc(100% + 10px);
    right: 0;
    width: 280px;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 12px 36px rgba(11,79,124,0.25), 0 2px 8px rgba(0,0,0,0.1);
    border: 1px solid #d4e4f2;
    padding: 12px;
    z-index: 2000;
    animation: popoverFadeIn 0.15s ease-out;
}

.menu-popover.open {
    display: block;
}

@keyframes popoverFadeIn {
    from {
        opacity: 0;
        transform: translateY(-6px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.menu-section-header {
    font-size: 11px;
    font-weight: 700;
    color: #607080;
    letter-spacing: 1.2px;
    padding: 4px 8px 6px;
    text-transform: uppercase;
}

.menu-nav-link {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 12px;
    border-radius: 8px;
    text-decoration: none;
    color: #12314d;
    transition: all 0.15s ease;
}

.menu-nav-link:hover {
    background: #eef6fb;
    color: #0b4f7c;
}

.menu-nav-link.active {
    background: #e1effa;
    color: #0b4f7c;
    font-weight: 600;
    border-left: 3px solid #1683c4;
}

.menu-link-icon {
    font-size: 18px;
    width: 24px;
    text-align: center;
}

.menu-link-content {
    display: flex;
    flex-direction: column;
}

.menu-link-title {
    font-size: 14px;
    line-height: 1.2;
}

.menu-link-desc {
    font-size: 11px;
    color: #6d8498;
    margin-top: 2px;
}

.menu-divider {
    height: 1px;
    background: #e2edf5;
    margin: 8px 0;
}

.menu-rooms-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    padding: 4px;
}

.room-btn {
    padding: 7px 0;
    background: #f0f6fa;
    border: 1px solid #d0e2f0;
    border-radius: 6px;
    color: #0b4f7c;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    font-family: inherit;
    transition: all 0.15s ease;
}

.room-btn:hover {
    background: #1683c4;
    border-color: #1683c4;
    color: white;
}

.room-btn.active {
    background: #0b4f7c;
    border-color: #0b4f7c;
    color: white;
}


/* ============================================================
   FOOTER
   ============================================================ */

.footer {
    width: 100%;

    padding: 16px 20px;

    text-align: center;

    font-size: 13px;

    color: white;

    background: #0b4f7c;
}


/* ============================================================
   MAIN DISPLAY
   ============================================================ */

#displayPage {
    flex-direction: column;
}

.display-content {
    flex: 1;

    display: grid;

    grid-template-columns:
        minmax(0, 1.5fr)
        minmax(250px, .7fr);

    gap: 28px;

    padding:
        35px
        5vw;
}

.current-section {
    background: white;

    border-radius: 14px;

    display: flex;
    flex-direction: column;

    align-items: center;
    justify-content: center;

    padding: 45px;

    border-top:
        7px solid #1683c4;

    box-shadow:
        0 5px 25px
        rgba(12,68,105,.08);
}

.display-label {
    color: #607080;

    font-size: 18px;
    font-weight: 600;

    letter-spacing: 4px;
}

.display-token {
    font-size:
        clamp(130px, 18vw, 270px);

    font-weight: 700;

    line-height: 1;

    color: #0b4f7c;

    margin-top: 15px;
}

.proceed {
    margin-top: 30px;

    color: #31556e;

    font-size:
        clamp(22px, 3vw, 30px);

    text-align: center;
}

.queue-section {
    background: #0b4f7c;

    color: white;

    border-radius: 14px;

    padding: 35px;

    box-shadow:
        0 5px 25px
        rgba(12,68,105,.15);
}

.queue-title {
    font-size: 18px;

    letter-spacing: 3px;

    font-weight: 600;

    padding-bottom: 20px;

    border-bottom:
        1px solid
        rgba(255,255,255,.25);
}

.queue-list {
    margin-top: 22px;

    display: flex;

    flex-direction: column;

    gap: 12px;
}

.queue-token {
    background:
        rgba(255,255,255,.12);

    padding:
        14px
        18px;

    border-radius: 8px;

    font-size: 28px;

    font-weight: 600;
}

.queue-empty {
    margin-top: 25px;

    opacity: .65;

    font-size: 17px;
}


/* ============================================================
   TOKEN GENERATION
   ============================================================ */

#tokenPage {
    flex-direction: column;
}

.token-content {
    flex: 1;

    display: flex;

    align-items: center;
    justify-content: center;

    padding: 35px 15px;
}

.token-card {
    width:
        min(390px, 92vw);

    background: #fffdf8;

    border:
        1px solid
        #e5ded1;

    position: relative;

    padding:
        28px
        22px;

    text-align: center;

    box-shadow:
        0 12px 30px
        rgba(15,23,42,.12);
}

.ticket-brand {
    color: #0b4f7c;

    font-size: 17px;

    font-weight: 800;

    letter-spacing: 2px;
}

.ticket-type {
    margin-top: 7px;

    color: #94a3b8;

    font-size: 10px;

    font-weight: 700;

    letter-spacing: 2px;
}

.separator {
    border-top:
        1px dashed
        #cbd5e1;

    margin:
        20px 0;
}

.token-label {
    color: #607080;

    font-size: 11px;

    font-weight: 700;

    letter-spacing: 2px;
}

.generated-token {
    margin:
        15px 0;

    color: #0b4f7c;

    font-size:
        clamp(90px, 25vw, 125px);

    font-weight: 900;

    line-height: .9;
}

.token-date-time {
    display: flex;

    justify-content: center;

    flex-wrap: wrap;

    gap: 8px 18px;

    color: #475569;

    font-size: 13px;
}

.token-message {
    color: #334155;

    font-size: 13px;

    line-height: 1.5;
}

.ticket-footer {
    margin-top: 18px;

    color: #94a3b8;

    font-size: 10px;
}


/* ============================================================
   CALLING
   ============================================================ */

#nextPage {
    flex-direction: column;
}

.management-content {
    flex: 1;

    padding:
        35px
        5vw;
}

.cards {
    display: grid;

    grid-template-columns:
        repeat(3, minmax(0, 1fr));

    gap: 22px;
}

.card {
    background: white;

    border-radius: 12px;

    padding: 30px;

    min-height: 230px;

    border-top:
        5px solid #1683c4;

    box-shadow:
        0 5px 20px
        rgba(12,68,105,.08);
}

.card-label {
    color: #607080;

    font-size: 14px;

    letter-spacing: 2px;

    font-weight: 600;
}

.current-number {
    color: #0b4f7c;

    font-size:
        clamp(65px, 8vw, 90px);

    font-weight: 700;

    margin-top: 35px;
}

.token-list {
    margin-top: 25px;

    display: flex;

    flex-wrap: wrap;

    gap: 10px;
}

.token-chip {
    background: #e8f4fb;

    color: #0b4f7c;

    padding:
        10px
        15px;

    border-radius: 6px;

    font-weight: 600;
}

.empty {
    color: #8a9aa6;

    margin-top: 25px;
}

.actions {
    display: flex;

    flex-wrap: wrap;

    gap: 14px;

    margin-top: 30px;
}

button {
    padding:
        15px
        25px;

    border-radius: 7px;

    font-size: 16px;

    font-weight: 600;

    cursor: pointer;
}

.call-button {
    background: #0b4f7c;

    color: white;

    border:
        1px solid
        #0b4f7c;
}

.call-again-button {
    background: white;

    color: #0b4f7c;

    border:
        1px solid
        #0b4f7c;
}

.reset-button {
    background: white;

    color: #a52c2c;

    border:
        1px solid
        #d8b2b2;
}


/* ============================================================
   MOBILE
   ============================================================ */

@media (max-width: 850px) {

    .display-content {
        grid-template-columns: 1fr;

        padding:
            20px
            15px;
    }

    .cards {
        grid-template-columns: 1fr;
    }

    .header {
        min-height: 64px;

        padding:
            10px
            14px;
    }

    .header-brand {
        gap: 8px;
    }

    .logo {
        height: 36px;

        max-width: 120px;

        margin-right: 0;
    }

    .header-title {
        font-size: 15px;
    }

    .room-selector-label {
        display: none;
    }

    .room-selector-box {
        padding: 2px 6px;
    }

    .room-select {
        font-size: 13px;
        padding: 2px 0;
    }

    .menu-btn-text {
        display: none;
    }

    .menu-trigger-btn {
        padding: 7px 10px;
    }

    .menu-popover {
        width: 250px;
        right: 0;
    }

    .current-section {
        padding: 30px 15px;
    }

    .queue-section {
        padding: 25px 20px;
    }

    .management-content {
        padding:
            22px
            15px;
    }

    .actions {
        flex-direction: column;
    }

    button {
        width: 100%;
    }
}

@media (max-width: 480px) {

    .header-title {
        display: none;
    }
}

@media (max-width: 420px) {

    .token-content {
        padding:
            25px
            10px;
    }

    .token-card {
        width: 100%;

        padding:
            24px
            16px;
    }

    .footer {
        font-size: 12px;
    }
}

</style>

</head>


<body>


<!-- =========================================================
     MAIN DISPLAY
========================================================= -->

<div id="displayPage" class="page">

    <div class="header">

        <div class="header-brand">
            <a href="/" class="logo-link">
                <img
                    src="/logo.png"
                    class="logo"
                    alt="GTM4Health"
                >
            </a>
            <div class="header-title">
                MAIN DISPLAY
            </div>
        </div>

        <div class="header-nav-right">
            <div class="room-selector-box" title="Select Room">
                <span class="room-selector-label">ROOM</span>
                <select class="room-select" onchange="switchRoom(this.value)" aria-label="Select Room">
                    <option value="1">Room 1</option>
                    <option value="2">Room 2</option>
                    <option value="3">Room 3</option>
                    <option value="4">Room 4</option>
                    <option value="5">Room 5</option>
                    <option value="6">Room 6</option>
                </select>
            </div>

            <div class="menu-container">
                <button class="menu-trigger-btn" onclick="toggleNavMenu(event)" aria-label="Select Menu">
                    <span class="menu-icon-bars">☰</span>
                    <span class="menu-label"><span class="menu-btn-text">Select</span> ▾</span>
                </button>
                <div class="menu-popover">
                    <div class="menu-section-header">Select Page</div>
                    <a href="/" class="menu-nav-link" data-route="/">
                        <span class="menu-link-icon">📺</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Main Display</span>
                            <span class="menu-link-desc">Queue screen</span>
                        </div>
                    </a>
                    <a href="/token" class="menu-nav-link" data-route="/token">
                        <span class="menu-link-icon">🎫</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Token Generation</span>
                            <span class="menu-link-desc">Get new token</span>
                        </div>
                    </a>
                    <a href="/next" class="menu-nav-link" data-route="/next">
                        <span class="menu-link-icon">📢</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Calling Console</span>
                            <span class="menu-link-desc">Call next patient</span>
                        </div>
                    </a>
                    <a href="/qr" class="menu-nav-link" data-route="/qr">
                        <span class="menu-link-icon">📱</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">QR Code</span>
                            <span class="menu-link-desc">Patient scan & take token</span>
                        </div>
                    </a>

                    <div class="menu-divider"></div>

                    <div class="menu-section-header">Select Room</div>
                    <div class="menu-rooms-grid">
                        <button type="button" class="room-btn" data-room="1" onclick="switchRoom(1)">Room 1</button>
                        <button type="button" class="room-btn" data-room="2" onclick="switchRoom(2)">Room 2</button>
                        <button type="button" class="room-btn" data-room="3" onclick="switchRoom(3)">Room 3</button>
                        <button type="button" class="room-btn" data-room="4" onclick="switchRoom(4)">Room 4</button>
                        <button type="button" class="room-btn" data-room="5" onclick="switchRoom(5)">Room 5</button>
                        <button type="button" class="room-btn" data-room="6" onclick="switchRoom(6)">Room 6</button>
                    </div>
                </div>
            </div>
        </div>

    </div>


    <div class="display-content">

        <div class="current-section">

            <div class="display-label">
                TOKEN NO.
            </div>

            <div
                id="displayToken"
                class="display-token"
            >
                ---
            </div>

            <div class="proceed">
                Please proceed to room <span id="displayRoomNumber">1</span>
            </div>

        </div>


        <div class="queue-section">

            <div class="queue-title">
                IN QUEUE
            </div>

            <div
                id="displayQueue"
                class="queue-list"
            >
            </div>

        </div>

    </div>


    <div class="footer">
        © GTM4Health 2026
    </div>

</div>


<!-- =========================================================
     TOKEN GENERATION
========================================================= -->

<div id="tokenPage" class="page">

    <div class="header">

        <div class="header-brand">
            <a href="/" class="logo-link">
                <img
                    src="/logo.png"
                    class="logo"
                    alt="GTM4Health"
                >
            </a>
            <div class="header-title">
                TOKEN GENERATION
            </div>
        </div>

        <div class="header-nav-right">
            <div class="room-selector-box" title="Select Room">
                <span class="room-selector-label">ROOM</span>
                <select class="room-select" onchange="switchRoom(this.value)" aria-label="Select Room">
                    <option value="1">Room 1</option>
                    <option value="2">Room 2</option>
                    <option value="3">Room 3</option>
                    <option value="4">Room 4</option>
                    <option value="5">Room 5</option>
                    <option value="6">Room 6</option>
                </select>
            </div>

            <div class="menu-container">
                <button class="menu-trigger-btn" onclick="toggleNavMenu(event)" aria-label="Select Menu">
                    <span class="menu-icon-bars">☰</span>
                    <span class="menu-label"><span class="menu-btn-text">Select</span> ▾</span>
                </button>
                <div class="menu-popover">
                    <div class="menu-section-header">Select Page</div>
                    <a href="/" class="menu-nav-link" data-route="/">
                        <span class="menu-link-icon">📺</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Main Display</span>
                            <span class="menu-link-desc">Queue screen</span>
                        </div>
                    </a>
                    <a href="/token" class="menu-nav-link" data-route="/token">
                        <span class="menu-link-icon">🎫</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Token Generation</span>
                            <span class="menu-link-desc">Get new token</span>
                        </div>
                    </a>
                    <a href="/next" class="menu-nav-link" data-route="/next">
                        <span class="menu-link-icon">📢</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Calling Console</span>
                            <span class="menu-link-desc">Call next patient</span>
                        </div>
                    </a>
                    <a href="/qr" class="menu-nav-link" data-route="/qr">
                        <span class="menu-link-icon">📱</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">QR Code</span>
                            <span class="menu-link-desc">Patient scan & take token</span>
                        </div>
                    </a>

                    <div class="menu-divider"></div>

                    <div class="menu-section-header">Select Room</div>
                    <div class="menu-rooms-grid">
                        <button type="button" class="room-btn" data-room="1" onclick="switchRoom(1)">Room 1</button>
                        <button type="button" class="room-btn" data-room="2" onclick="switchRoom(2)">Room 2</button>
                        <button type="button" class="room-btn" data-room="3" onclick="switchRoom(3)">Room 3</button>
                        <button type="button" class="room-btn" data-room="4" onclick="switchRoom(4)">Room 4</button>
                        <button type="button" class="room-btn" data-room="5" onclick="switchRoom(5)">Room 5</button>
                        <button type="button" class="room-btn" data-room="6" onclick="switchRoom(6)">Room 6</button>
                    </div>
                </div>
            </div>
        </div>

    </div>


    <div class="token-content">

        <div
            id="tokenArea"
            class="token-card"
        >

            <div class="ticket-brand">
                GTM4HEALTH
            </div>

            <div class="ticket-type">
                QUEUE TOKEN
            </div>

            <div class="separator"></div>

            <div class="token-label">
                YOUR TOKEN NUMBER
            </div>

            <div
                id="generatedToken"
                class="generated-token"
            >
                ---
            </div>

            <div
                id="tokenDateTime"
                class="token-date-time"
            >
                <span>—</span>
            </div>

            <div class="separator"></div>

            <div class="token-message">
                Please wait for your token to be called.
            </div>

            <div class="ticket-footer">
                © GTM4Health 2026
            </div>

        </div>

    </div>


    <div class="footer">
        © GTM4Health 2026
    </div>

</div>


<!-- =========================================================
     CALLING
========================================================= -->

<div id="nextPage" class="page">

    <div class="header">

        <div class="header-brand">
            <a href="/" class="logo-link">
                <img
                    src="/logo.png"
                    class="logo"
                    alt="GTM4Health"
                >
            </a>
            <div class="header-title">
                CALLING
            </div>
        </div>

        <div class="header-nav-right">
            <div class="room-selector-box" title="Select Room">
                <span class="room-selector-label">ROOM</span>
                <select class="room-select" onchange="switchRoom(this.value)" aria-label="Select Room">
                    <option value="1">Room 1</option>
                    <option value="2">Room 2</option>
                    <option value="3">Room 3</option>
                    <option value="4">Room 4</option>
                    <option value="5">Room 5</option>
                    <option value="6">Room 6</option>
                </select>
            </div>

            <div class="menu-container">
                <button class="menu-trigger-btn" onclick="toggleNavMenu(event)" aria-label="Select Menu">
                    <span class="menu-icon-bars">☰</span>
                    <span class="menu-label"><span class="menu-btn-text">Select</span> ▾</span>
                </button>
                <div class="menu-popover">
                    <div class="menu-section-header">Select Page</div>
                    <a href="/" class="menu-nav-link" data-route="/">
                        <span class="menu-link-icon">📺</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Main Display</span>
                            <span class="menu-link-desc">Queue screen</span>
                        </div>
                    </a>
                    <a href="/token" class="menu-nav-link" data-route="/token">
                        <span class="menu-link-icon">🎫</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Token Generation</span>
                            <span class="menu-link-desc">Get new token</span>
                        </div>
                    </a>
                    <a href="/next" class="menu-nav-link" data-route="/next">
                        <span class="menu-link-icon">📢</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">Calling Console</span>
                            <span class="menu-link-desc">Call next patient</span>
                        </div>
                    </a>
                    <a href="/qr" class="menu-nav-link" data-route="/qr">
                        <span class="menu-link-icon">📱</span>
                        <div class="menu-link-content">
                            <span class="menu-link-title">QR Code</span>
                            <span class="menu-link-desc">Patient scan & take token</span>
                        </div>
                    </a>

                    <div class="menu-divider"></div>

                    <div class="menu-section-header">Select Room</div>
                    <div class="menu-rooms-grid">
                        <button type="button" class="room-btn" data-room="1" onclick="switchRoom(1)">Room 1</button>
                        <button type="button" class="room-btn" data-room="2" onclick="switchRoom(2)">Room 2</button>
                        <button type="button" class="room-btn" data-room="3" onclick="switchRoom(3)">Room 3</button>
                        <button type="button" class="room-btn" data-room="4" onclick="switchRoom(4)">Room 4</button>
                        <button type="button" class="room-btn" data-room="5" onclick="switchRoom(5)">Room 5</button>
                        <button type="button" class="room-btn" data-room="6" onclick="switchRoom(6)">Room 6</button>
                    </div>
                </div>
            </div>
        </div>

    </div>


    <div class="management-content">

        <div class="cards">


            <div class="card">

                <div class="card-label">
                    CURRENT TOKEN
                </div>

                <div
                    id="currentToken"
                    class="current-number"
                >
                    ---
                </div>

            </div>


            <div class="card">

                <div class="card-label">
                    PENDING
                </div>

                <div
                    id="pendingTokens"
                    class="token-list"
                >
                </div>

            </div>


            <div class="card">

                <div class="card-label">
                    COMPLETED
                </div>

                <div
                    id="completedTokens"
                    class="token-list"
                >
                </div>

            </div>


        </div>


        <div class="actions">

            <button
                class="call-button"
                onclick="callNextToken()"
            >
                Call Next Token
            </button>

            <button
                class="call-again-button"
                onclick="callAgain()"
            >
                Call Again
            </button>

            <button
                class="reset-button"
                onclick="resetTokens()"
            >
                Reset Tokens
            </button>

        </div>

    </div>


    <div class="footer">
        © GTM4Health 2026
    </div>

</div>


<script>

/* ============================================================
   PAGE SELECTION
============================================================ */

const path = window.location.pathname;

if (path === "/" || path === "/display") {

    document
        .getElementById("displayPage")
        .classList
        .add("active");

}

else if (path === "/token") {

    document
        .getElementById("tokenPage")
        .classList
        .add("active");

}

else if (path === "/next" || path === "/calling") {

    document
        .getElementById("nextPage")
        .classList
        .add("active");

}


/* ============================================================
   ROOM & MENU MANAGEMENT
============================================================ */

function getInitialRoom() {
    const urlParams = new URLSearchParams(window.location.search);
    const roomFromUrl = urlParams.get("room");
    if (roomFromUrl && !isNaN(parseInt(roomFromUrl))) {
        return parseInt(roomFromUrl);
    }
    try {
        const savedRoom = localStorage.getItem("gtm4health_selected_room");
        if (savedRoom && !isNaN(parseInt(savedRoom))) {
            return parseInt(savedRoom);
        }
    } catch(e) {}
    return 1;
}

let currentRoom = getInitialRoom();

function switchRoom(roomNumber) {
    roomNumber = parseInt(roomNumber) || 1;
    currentRoom = roomNumber;
    try {
        localStorage.setItem("gtm4health_selected_room", roomNumber);
    } catch(e) {}

    // Update all select dropdowns
    document.querySelectorAll(".room-select").forEach(sel => {
        sel.value = roomNumber;
    });

    // Update all room buttons in the menu
    document.querySelectorAll(".room-btn").forEach(btn => {
        if (parseInt(btn.getAttribute("data-room")) === roomNumber) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    // Update display page room text
    const displayRoomNum = document.getElementById("displayRoomNumber");
    if (displayRoomNum) {
        displayRoomNum.innerText = roomNumber;
    }

    // Update URL query parameter without page reload
    const url = new URL(window.location.href);
    url.searchParams.set("room", roomNumber);
    window.history.replaceState({}, "", url.toString());

    // Update menu links
    updateMenuLinks();

    // Fetch updated status immediately
    getStatus();
}

function updateMenuLinks() {
    document.querySelectorAll(".menu-nav-link").forEach(link => {
        const route = link.getAttribute("data-route");
        if (route) {
            link.href = `${route}?room=${currentRoom}`;
        }
    });
}

function toggleNavMenu(event) {
    if (event) {
        event.stopPropagation();
    }
    const container = event ? event.target.closest(".menu-container") : null;
    const popover = container ? container.querySelector(".menu-popover") : document.querySelector(".menu-popover");
    if (popover) {
        const isOpen = popover.classList.contains("open");
        document.querySelectorAll(".menu-popover").forEach(p => p.classList.remove("open"));
        if (!isOpen) {
            popover.classList.add("open");
        }
    }
}

document.addEventListener("click", function(event) {
    if (!event.target.closest(".menu-container")) {
        document.querySelectorAll(".menu-popover").forEach(p => p.classList.remove("open"));
    }
});

function initHeaderAndRoom() {
    document.querySelectorAll(".room-select").forEach(sel => {
        sel.value = currentRoom;
    });

    document.querySelectorAll(".room-btn").forEach(btn => {
        if (parseInt(btn.getAttribute("data-room")) === currentRoom) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    const displayRoomNum = document.getElementById("displayRoomNumber");
    if (displayRoomNum) {
        displayRoomNum.innerText = currentRoom;
    }

    const currentPath = window.location.pathname;
    document.querySelectorAll(".menu-nav-link").forEach(link => {
        const route = link.getAttribute("data-route");
        const isMatch = (route === currentPath) ||
                        (route === "/" && (currentPath === "/" || currentPath === "/display")) ||
                        (route === "/next" && (currentPath === "/next" || currentPath === "/calling"));
        if (isMatch) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });

    updateMenuLinks();
}

initHeaderAndRoom();


/* ============================================================
   TOKEN FORMAT
============================================================ */

function formatToken(token) {

    if (
        token === null ||
        token === undefined
    ) {
        return "---";
    }

    return String(token).padStart(3, "0");
}


/* ============================================================
   TOKEN CHIPS
============================================================ */

function createTokenChips(tokens) {

    if (!tokens || tokens.length === 0) {

        return `
            <div class="empty">
                No tokens
            </div>
        `;
    }

    return tokens
        .map(token => `
            <div class="token-chip">
                ${formatToken(token)}
            </div>
        `)
        .join("");
}


/* ============================================================
   MAIN DISPLAY QUEUE
============================================================ */

function createQueue(tokens) {

    if (!tokens || tokens.length === 0) {

        return `
            <div class="queue-empty">
                No tokens in queue
            </div>
        `;
    }

    return tokens
        .map(token => `
            <div class="queue-token">
                ${formatToken(token)}
            </div>
        `)
        .join("");
}


/* ============================================================
   UPDATE ALL INTERFACES
============================================================ */

function updatePage(data) {

    const displayToken =
        document.getElementById("displayToken");

    if (displayToken) {

        displayToken.innerText =
            formatToken(data.current_token);

    }


    const displayQueue =
        document.getElementById("displayQueue");

    if (displayQueue) {

        displayQueue.innerHTML =
            createQueue(data.pending);

    }


    const currentToken =
        document.getElementById("currentToken");

    if (currentToken) {

        currentToken.innerText =
            formatToken(data.current_token);

    }


    const pendingTokens =
        document.getElementById("pendingTokens");

    if (pendingTokens) {

        pendingTokens.innerHTML =
            createTokenChips(data.pending);

    }


    const completedTokens =
        document.getElementById("completedTokens");

    if (completedTokens) {

        completedTokens.innerHTML =
            createTokenChips(data.completed);

    }

    const displayRoomNum =
        document.getElementById("displayRoomNumber");

    if (displayRoomNum) {

        displayRoomNum.innerText =
            data.room || currentRoom;

    }

}


/* ============================================================
   STATUS
============================================================ */

async function getStatus() {

    try {

        const response =
            await fetch(
                "/api/status?room=" + currentRoom,
                { cache: "no-store" }
            );

        const data =
            await response.json();

        updatePage(data);

        return data;

    }

    catch (error) {

        console.error(error);

        return null;
    }
}


/* ============================================================
   CALL NEXT
============================================================ */

async function callNextToken() {

    try {

        const response =
            await fetch(
                "/api/next",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            room: currentRoom
                        })
                }
            );

        const data =
            await response.json();

        if (!data.success) {

            alert(
                data.message ||
                "No more tokens in queue"
            );

        }

        await getStatus();

    }

    catch (error) {

        alert(
            "Unable to connect to server."
        );

        console.error(error);
    }
}


/* ============================================================
   CALL AGAIN
============================================================ */

async function callAgain() {

    try {

        const response =
            await fetch(
                "/api/call-again",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            room: currentRoom
                        })
                }
            );

        const data =
            await response.json();

        if (!data.success) {

            alert(
                data.message ||
                "No current token"
            );

            return;
        }

        /*
         * Main Display sees announcement_id change
         * and announces the same token again.
         */

    }

    catch (error) {

        alert(
            "Unable to connect to server."
        );

        console.error(error);
    }
}


/* ============================================================
   RESET
============================================================ */

async function resetTokens() {

    if (
        !confirm(
            "Reset all tokens?"
        )
    ) {
        return;
    }

    try {

        await fetch(
            "/api/reset",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        room: currentRoom
                    })
            }
        );

        await getStatus();

    }

    catch (error) {

        alert(
            "Unable to connect to server."
        );

        console.error(error);
    }
}


/* ============================================================
   VOICE ANNOUNCEMENT
============================================================ */

let lastAnnouncementId = 0;

function announceToken(token) {

    if (
        token === null ||
        token === undefined
    ) {
        return;
    }

    if (
        !("speechSynthesis" in window)
    ) {
        return;
    }

    window.speechSynthesis.cancel();

    const speech =
        new SpeechSynthesisUtterance(
            "Token number " +
            token +
            ". Please proceed to room " +
            currentRoom +
            "."
        );

    speech.rate = 0.85;
    speech.pitch = 1;
    speech.volume = 1;

    window.speechSynthesis.speak(speech);
}


/* ============================================================
   CHECK FOR NEW CALL / CALL AGAIN
============================================================ */

async function checkForUpdates() {

    if (path !== "/" && path !== "/display" && path !== "/next" && path !== "/calling") {
        return;
    }

    const data =
        await getStatus();

    if (!data) {
        return;
    }

    if (path === "/" || path === "/display") {
        if (
            data.announcement_id !==
            lastAnnouncementId
        ) {

            if (
                data.current_token !== null
            ) {

                announceToken(
                    data.current_token
                );
            }

            lastAnnouncementId =
                data.announcement_id;
        }
    }
}


/* ============================================================
   TOKEN PAGE - LOCAL STORAGE
============================================================ */

const TOKEN_STORAGE_KEY =
    "gtm4health_token_id";


function formatDateTime(dateTime) {

    if (!dateTime) {
        return "";
    }

    const parts =
        dateTime.split(" ");

    if (parts.length < 2) {
        return dateTime;
    }

    const dateParts =
        parts[0].split("-");

    const timeParts =
        parts[1].split(":");

    let hour =
        parseInt(
            timeParts[0],
            10
        );

    const minute =
        timeParts[1];

    const suffix =
        hour >= 12
            ? "PM"
            : "AM";

    hour =
        hour % 12;

    if (hour === 0) {
        hour = 12;
    }

    const date =
        dateParts.length === 3
            ? dateParts[2] +
              "/" +
              dateParts[1] +
              "/" +
              dateParts[0]
            : parts[0];

    const time =
        hour +
        ":" +
        minute +
        " " +
        suffix;

    return `
        <span>${date}</span>
        <span>${time}</span>
    `;
}


/* ============================================================
   TOKEN PAGE
============================================================ */

let tokenData = null;


async function loadSavedToken() {

    if (path !== "/token") {
        return;
    }

    const savedTokenId =
        localStorage.getItem(
            TOKEN_STORAGE_KEY
        );

    if (!savedTokenId) {

        showGenerateButton();

        return;
    }

    try {

        const response =
            await fetch(
                "/api/token-status?token_id=" +
                encodeURIComponent(
                    savedTokenId
                ),
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            localStorage.removeItem(
                TOKEN_STORAGE_KEY
            );

            showGenerateButton();

            return;
        }

        const data =
            await response.json();

        if (data.success) {

            showToken(
                data
            );

        }

        else {

            localStorage.removeItem(
                TOKEN_STORAGE_KEY
            );

            showGenerateButton();
        }

    }

    catch (error) {

        console.error(error);

        showOfflineTokenMessage();
    }
}


function showGenerateButton() {

    const area =
        document.getElementById(
            "tokenArea"
        );

    area.innerHTML = `

        <div class="ticket-brand">
            GTM4HEALTH
        </div>

        <div class="ticket-type">
            QUEUE TOKEN
        </div>

        <div class="separator"></div>

        <div class="token-label">
            GET YOUR TOKEN
        </div>

        <button
            onclick="generateToken()"
            style="
                width:100%;
                margin-top:22px;
                padding:15px;
                border:0;
                border-radius:7px;
                background:#0b4f7c;
                color:white;
                font-size:16px;
                font-weight:600;
                cursor:pointer;
            "
        >
            Generate Token
        </button>

        <div class="ticket-footer">
            © GTM4Health 2026
        </div>
    `;
}


function showOfflineTokenMessage() {

    const area =
        document.getElementById(
            "tokenArea"
        );

    area.innerHTML = `

        <div class="ticket-brand">
            GTM4HEALTH
        </div>

        <div class="separator"></div>

        <div class="token-label">
            CONNECTION UNAVAILABLE
        </div>

        <p style="
            color:#607080;
            font-size:13px;
            line-height:1.5;
        ">
            Please reconnect to the hospital Wi-Fi
            and try again.
        </p>

        <button
            onclick="loadSavedToken()"
            style="
                width:100%;
                padding:15px;
                border:0;
                border-radius:7px;
                background:#0b4f7c;
                color:white;
                font-size:16px;
                font-weight:600;
                cursor:pointer;
            "
        >
            Try Again
        </button>

        <div class="ticket-footer">
            © GTM4Health 2026
        </div>
    `;
}


async function generateToken() {

    try {

        const response =
            await fetch(
                "/api/token",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            room: currentRoom
                        })
                }
            );

        const data =
            await response.json();

        if (!data.success) {
            throw new Error(
                "Token generation failed"
            );
        }

        tokenData = data;

        localStorage.setItem(
            TOKEN_STORAGE_KEY,
            data.token_id
        );

        showToken(data);

    }

    catch (error) {

        alert(
            "Unable to generate token. " +
            "Please check your connection."
        );

        console.error(error);
    }
}


function showToken(data) {

    tokenData = data;

    const area =
        document.getElementById(
            "tokenArea"
        );

    area.innerHTML = `

        <div class="ticket-brand">
            GTM4HEALTH
        </div>

        <div class="ticket-type">
            QUEUE TOKEN
        </div>

        <div class="separator"></div>

        <div class="token-label">
            YOUR TOKEN NUMBER
        </div>

        <div class="generated-token">
            ${formatToken(data.token)}
        </div>

        <div style="font-size:16px; font-weight:700; color:#0b4f7c; margin-top:6px; letter-spacing:1px;">
            ROOM ${data.room || currentRoom}
        </div>

        <div class="token-date-time">
            ${formatDateTime(data.created_at)}
        </div>

        <div class="separator"></div>

        <div class="token-message">
            Please wait for your token to be called.
        </div>

        <button
            onclick="downloadToken()"
            style="
                width:100%;
                margin-top:20px;
                padding:13px;
                border:1px solid #0b4f7c;
                border-radius:7px;
                background:white;
                color:#0b4f7c;
                font-size:15px;
                font-weight:600;
                cursor:pointer;
            "
        >
            Download Token
        </button>

        <div class="ticket-footer">
            © GTM4Health 2026
        </div>
    `;
}


/* ============================================================
   DOWNLOAD TOKEN AS PNG
============================================================ */

function downloadToken() {

    if (!tokenData) {
        return;
    }

    const canvas =
        document.createElement(
            "canvas"
        );

    const width = 900;
    const height = 1250;

    canvas.width = width;
    canvas.height = height;

    const ctx =
        canvas.getContext("2d");

    ctx.fillStyle =
        "#fffdf8";

    ctx.fillRect(
        0,
        0,
        width,
        height
    );

    ctx.strokeStyle =
        "#e5ded1";

    ctx.lineWidth = 3;

    ctx.strokeRect(
        35,
        35,
        width - 70,
        height - 70
    );

    ctx.textAlign =
        "center";

    ctx.fillStyle =
        "#0b4f7c";

    ctx.font =
        "bold 38px Arial";

    ctx.fillText(
        "GTM4HEALTH",
        width / 2,
        105
    );

    ctx.fillStyle =
        "#94a3b8";

    ctx.font =
        "bold 19px Arial";

    ctx.fillText(
        "QUEUE TOKEN",
        width / 2,
        145
    );

    drawDashedLine(
        ctx,
        90,
        190,
        810,
        190
    );

    ctx.fillStyle =
        "#607080";

    ctx.font =
        "bold 21px Arial";

    ctx.fillText(
        "YOUR TOKEN NUMBER",
        width / 2,
        255
    );

    ctx.fillStyle =
        "#0b4f7c";

    ctx.font =
        "900 210px Arial";

    ctx.fillText(
        formatToken(
            tokenData.token
        ),
        width / 2,
        475
    );

    const dateTime =
        formatDateTimeText(
            tokenData.created_at
        );

    ctx.fillStyle =
        "#475569";

    ctx.font =
        "24px Arial";

    ctx.fillText(
        dateTime,
        width / 2,
        555
    );

    drawDashedLine(
        ctx,
        90,
        620,
        810,
        620
    );

    ctx.fillStyle =
        "#334155";

    ctx.font =
        "24px Arial";

    ctx.fillText(
        "Please wait for your token to be called.",
        width / 2,
        690
    );

    ctx.fillStyle =
        "#94a3b8";

    ctx.font =
        "18px Arial";

    ctx.fillText(
        "© GTM4Health 2026",
        width / 2,
        760
    );

    const link =
        document.createElement(
            "a"
        );

    link.download =
        "GTM4Health_Token_" +
        tokenData.token +
        ".png";

    link.href =
        canvas.toDataURL(
            "image/png"
        );

    link.click();
}


function formatDateTimeText(dateTime) {

    if (!dateTime) {
        return "";
    }

    const parts =
        dateTime.split(" ");

    if (parts.length < 2) {
        return dateTime;
    }

    const dateParts =
        parts[0].split("-");

    const timeParts =
        parts[1].split(":");

    let hour =
        parseInt(
            timeParts[0],
            10
        );

    const minute =
        timeParts[1];

    const suffix =
        hour >= 12
            ? "PM"
            : "AM";

    hour =
        hour % 12;

    if (hour === 0) {
        hour = 12;
    }

    const date =
        dateParts[2] +
        "/" +
        dateParts[1] +
        "/" +
        dateParts[0];

    return (
        date +
        "     " +
        hour +
        ":" +
        minute +
        " " +
        suffix
    );
}


function drawDashedLine(
    ctx,
    x1,
    y1,
    x2,
    y2
) {

    ctx.save();

    ctx.strokeStyle =
        "#cbd5e1";

    ctx.lineWidth = 2;

    ctx.setLineDash(
        [10, 10]
    );

    ctx.beginPath();

    ctx.moveTo(
        x1,
        y1
    );

    ctx.lineTo(
        x2,
        y2
    );

    ctx.stroke();

    ctx.restore();
}


/* ============================================================
   START
============================================================ */

getStatus();

setInterval(
    checkForUpdates,
    1000
);

if (path === "/token") {
    loadSavedToken();
}

</script>

</body>
</html>
"""


# ============================================================
# WEBSITE ROUTES
# ============================================================

@app.route("/")
@app.route("/token")
@app.route("/next")
@app.route("/display")
@app.route("/calling")
def website():
    return Response(
        HTML,
        mimetype="text/html"
    )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    ip = get_local_ip()

    print()
    print("=" * 60)
    print("GTM4Health Token Management System")
    print("=" * 60)
    print()
    print("Main Display:")
    print(f"  http://{ip}:{PORT}/")
    print()
    print("Token Generation:")
    print(f"  http://{ip}:{PORT}/token")
    print()
    print("Calling:")
    print(f"  http://{ip}:{PORT}/next")
    print()
    print("QR Code:")
    print(f"  http://{ip}:{PORT}/qr")
    print()
    print("Make sure the phone and laptop are on the same Wi-Fi.")
    print()
    print("=" * 60)
    print()

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
