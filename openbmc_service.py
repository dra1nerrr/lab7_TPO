"""
Универсальный сервер OpenBMC для CI/CD Pipeline.
Предоставляет:
1. Web UI OpenBMC (Phosphor WebUI / Vue) для Selenium-тестов.
2. Redfish REST API стандарта DMTF v1.8 для PyTest и Locust.
"""

import json
import logging
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpenBMC_CI_Service")

WEBUI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>OpenBMC Web UI</title>
  <style>
    body { font-family: 'IBM Plex Sans', Arial, sans-serif; margin: 0; background: #f4f4f4; color: #161616; }
    header#app-header { background: #161616; color: #fff; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
    nav a { color: #fff; margin-right: 20px; text-decoration: none; font-size: 14px; }
    main { padding: 28px; max-width: 960px; margin: 28px auto; background: #fff; border-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    .form-group { margin-bottom: 16px; }
    label { display: block; margin-bottom: 6px; font-weight: 600; }
    input { padding: 8px 10px; width: 300px; border: 1px solid #8d8d8d; font-size: 14px; }
    button { padding: 10px 22px; background: #0f62fe; color: #fff; border: none; cursor: pointer; font-size: 14px; }
    .alert-danger { background: #fff1f1; border-left: 4px solid #da1e28; color: #da1e28; padding: 12px 16px; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { border: 1px solid #e0e0e0; padding: 10px 12px; text-align: left; }
    th { background: #e8e8e8; }
  </style>
</head>
<body>
  <header id="app-header" style="display:none;">
    <div><strong>OpenBMC</strong> | Romulus BMC (CI Pipeline)</div>
    <nav>
      <a href="#/overview" data-test-id="nav-item-overview">Overview</a>
      <a href="#/hardware-status/inventory" data-test-id="nav-item-inventory">Inventory and LEDs</a>
      <a href="#/hardware-status/sensors" data-test-id="nav-item-sensors">Sensors</a>
      <a href="#/operations/server-power-operations" data-test-id="nav-item-server-power-operations">Server power operations</a>
      <a href="#/logs/event-logs" data-test-id="nav-item-event-logs">Event logs</a>
    </nav>
  </header>
  <main id="app-main"></main>
  <script>
    let authed = false;
    let powerState = "On";
    let failedAttempts = 0;
    let isLocked = false;

    function render() {
      const hash = window.location.hash || "#/login";
      const header = document.getElementById("app-header");
      const main = document.getElementById("app-main");

      if (hash === "#/login") {
        authed = false;
      } else if (!authed) {
        window.location.hash = "#/login";
        return;
      }
      header.style.display = (hash === "#/login") ? "none" : "flex";

      if (hash === "#/login") {
        main.innerHTML = `
          <h1>Log in to OpenBMC</h1>
          <div id="login-error-container"></div>
          <form id="login-form">
            <div class="form-group">
              <label for="username">Username</label>
              <input id="username" data-test-id="login-input-username" type="text" autocomplete="off" />
            </div>
            <div class="form-group">
              <label for="password">Password</label>
              <input id="password" data-test-id="login-input-password" type="password" autocomplete="off" />
            </div>
            <button type="submit" data-test-id="login-button-submit" class="btn-primary">Log in</button>
          </form>
        `;
        document.getElementById("login-form").onsubmit = async (e) => {
          e.preventDefault();
          const u = document.getElementById("username").value;
          const p = document.getElementById("password").value;
          const errBox = document.getElementById("login-error-container");
          try {
            const res = await fetch("/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ username: u, password: p })
            });
            const data = await res.json();
            if (res.ok) {
              authed = true;
              window.location.hash = "#/overview";
            } else {
              errBox.innerHTML = `<div class="alert-danger" role="alert">${data.message || "Invalid username or password."}</div>`;
            }
          } catch (err) {
            errBox.innerHTML = '<div class="alert-danger" role="alert">Invalid username or password.</div>';
          }
        };
      } else if (hash.includes("inventory")) {
        main.innerHTML = `
          <h1>Inventory and LEDs</h1>
          <table>
            <tr><th>Component</th><th>Name</th><th>Status</th></tr>
            <tr><td>System</td><td>Romulus Server System</td><td>Enabled / OK</td></tr>
            <tr><td>BMC</td><td>OpenBMC Romulus Controller</td><td>Enabled / OK</td></tr>
            <tr><td>Processor</td><td>IBM POWER9 (24 cores)</td><td>Enabled / OK</td></tr>
            <tr><td>DIMM</td><td>64GB DDR4 Memory Module</td><td>Enabled / OK</td></tr>
          </table>
        `;
      } else if (hash.includes("sensors")) {
        main.innerHTML = `
          <h1>Sensors</h1>
          <table>
            <tr><th>Sensor Name</th><th>Current Value</th><th>Status</th></tr>
            <tr><td>CPU0 Core Temp</td><td>42.5 °C</td><td>OK</td></tr>
            <tr><td>CPU1 Core Temp</td><td>44.0 °C</td><td>OK</td></tr>
            <tr><td>Ambient Temp</td><td>24.0 °C</td><td>OK</td></tr>
          </table>
        `;
      } else if (hash.includes("server-power-operations")) {
        main.innerHTML = `
          <h1>Server power operations</h1>
          <p>Current power state: <strong id="power-status">${powerState}</strong></p>
          <button id="power-on-btn" data-test-id="serverPowerOperations-button-powerOn">Power on</button>
        `;
        document.getElementById("power-on-btn").onclick = () => {
          powerState = "On";
          document.getElementById("power-status").innerText = "On";
        };
      } else if (hash.includes("event-logs")) {
        main.innerHTML = `
          <h1>Event logs</h1>
          <table>
            <tr><th>ID</th><th>Severity</th><th>Description</th></tr>
            <tr><td>1</td><td>OK</td><td>Server poweron event triggered successfully</td></tr>
          </table>
        `;
      } else {
        main.innerHTML = `<h1>OpenBMC Overview</h1><p>System: Romulus POWER9. Status: Operating normally.</p>`;
      }
    }
    window.addEventListener("hashchange", render);
    window.addEventListener("DOMContentLoaded", render);
  </script>
</body>
</html>
"""

class OpenBMCCIHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    failed_attempts = 0

    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code: int, data: dict, extra_headers: dict = None):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if not path:
            path = "/"

        # Healthcheck endpoint
        if path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # WebUI frontend
        if path in ("/", "/index.html") or path.startswith("/#"):
            body = WEBUI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Redfish ServiceRoot
        if path in ("/redfish", "/redfish/v1"):
            self._send_json(200, {
                "@odata.type": "#ServiceRoot.v1_5_0.ServiceRoot",
                "Id": "RootService",
                "Name": "Root Service",
                "RedfishVersion": "1.8.0",
                "UUID": "7c823f65-4e78-4395-8d5f-97217db5679a",
                "SessionService": {"@odata.id": "/redfish/v1/SessionService"},
                "Systems": {"@odata.id": "/redfish/v1/Systems"},
                "Chassis": {"@odata.id": "/redfish/v1/Chassis"}
            })
            return

        # Redfish ComputerSystem
        if path == "/redfish/v1/Systems/system":
            self._send_json(200, {
                "@odata.type": "#ComputerSystem.v1_13_0.ComputerSystem",
                "Id": "system",
                "Name": "Romulus OpenBMC Host System",
                "SystemType": "Physical",
                "Manufacturer": "OpenBMC",
                "Model": "Romulus POWER9 Server",
                "PowerState": "On",
                "Status": {"State": "Enabled", "Health": "OK"},
                "ProcessorSummary": {"Count": 2, "Model": "IBM POWER9", "Status": {"State": "Enabled", "Health": "OK"}},
                "MemorySummary": {"TotalSystemMemoryGiB": 64, "Status": {"State": "Enabled", "Health": "OK"}}
            })
            return

        # Redfish Thermal
        if path in ("/redfish/v1/Chassis/chassis", "/redfish/v1/Chassis/chassis/Thermal"):
            self._send_json(200, {
                "@odata.type": "#Thermal.v1_7_1.Thermal",
                "Id": "Thermal",
                "Name": "Thermal Information",
                "Temperatures": [
                    {
                        "MemberId": "0",
                        "Name": "CPU0 Core Temp",
                        "ReadingCelsius": 42.5,
                        "Status": {"State": "Enabled", "Health": "OK"},
                        "UpperThresholdNonCritical": 75.0,
                        "UpperThresholdCritical": 85.0
                    },
                    {
                        "MemberId": "1",
                        "Name": "CPU1 Core Temp",
                        "ReadingCelsius": 44.0,
                        "Status": {"State": "Enabled", "Health": "OK"},
                        "UpperThresholdNonCritical": 75.0,
                        "UpperThresholdCritical": 85.0
                    }
                ]
            })
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if path == "/login":
            u = body.get("username")
            p = body.get("password")
            if OpenBMCCIHandler.failed_attempts >= 5:
                self._send_json(403, {"status": "error", "message": "Account locked due to multiple failed login attempts."})
                return
            if u == "root" and p == "0penBmc":
                OpenBMCCIHandler.failed_attempts = 0
                self._send_json(200, {"status": "ok"})
            else:
                OpenBMCCIHandler.failed_attempts += 1
                self._send_json(401, {"status": "error", "message": "Invalid username or password."})
            return

        if path == "/redfish/v1/SessionService/Sessions":
            u = body.get("UserName")
            p = body.get("Password")
            if u == "root" and p == "0penBmc":
                token = f"bmc_token_{uuid.uuid4().hex[:12]}"
                self._send_json(201, {
                    "Id": "session_ci",
                    "UserName": "root",
                    "Token": token
                }, extra_headers={"X-Auth-Token": token, "Location": "/redfish/v1/SessionService/Sessions/1"})
            else:
                self._send_json(401, {"error": "Unauthorized"})
            return

        if path == "/redfish/v1/Systems/system/Actions/ComputerSystem.Reset":
            self._send_json(202, {"TaskState": "Completed", "TaskStatus": "OK"})
            return

        self._send_json(404, {"error": "Not Found"})

    def do_DELETE(self):
        self.send_response(204)
        self.end_headers()


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


_server_instance = None

def start_openbmc_service(port: int = 18443):
    global _server_instance
    if _server_instance is not None:
        return
    _server_instance = ThreadedServer(("0.0.0.0", port), OpenBMCCIHandler)
    t = threading.Thread(target=_server_instance.serve_forever, daemon=True)
    t.start()
    logger.info(f"OpenBMC CI Service успешно запущен на порту {port}")
    time.sleep(0.2)

def stop_openbmc_service():
    global _server_instance
    if _server_instance:
        _server_instance.shutdown()
        _server_instance = None
        logger.info("OpenBMC CI Service остановлен.")


if __name__ == "__main__":
    start_openbmc_service(18443)
    print("OpenBMC Service running on http://127.0.0.1:18443. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_openbmc_service()
