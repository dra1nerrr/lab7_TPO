"""
Сценарий нагрузочного тестирования OpenBMC для CI/CD Pipeline (Locust).
"""

import os
from locust import HttpUser, task, between

class OpenBMCUser(HttpUser):
    host = os.getenv("OPENBMC_HOST", "http://127.0.0.1:18443")
    wait_time = between(0.5, 1.5)

    def on_start(self):
        login_payload = {"UserName": "root", "Password": "0penBmc"}
        with self.client.post("/redfish/v1/SessionService/Sessions", json=login_payload, name="[CI Load] Auth", catch_response=True) as resp:
            if resp.status_code in (200, 201):
                token = resp.headers.get("X-Auth-Token") or resp.json().get("Token")
                if token:
                    self.client.headers["X-Auth-Token"] = token
                resp.success()
            else:
                resp.failure("Auth error")

    @task(3)
    def check_system(self):
        with self.client.get("/redfish/v1/Systems/system", name="[CI Load] GET /Systems/system", catch_response=True) as resp:
            if resp.status_code == 200 and "PowerState" in resp.json():
                resp.success()
            else:
                resp.failure("Failed system check")

    @task(2)
    def check_thermal(self):
        with self.client.get("/redfish/v1/Chassis/chassis/Thermal", name="[CI Load] GET /Chassis/Thermal", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure("Failed thermal check")
