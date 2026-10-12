"""
Тесты Redfish API для OpenBMC (CI/CD Pipeline).
Формирует JUnit XML отчет для Jenkins (reports/api_tests.xml).
"""

import os
import pytest
import requests

BASE_URL = os.getenv("OPENBMC_HOST", "http://127.0.0.1:18443")
USER = os.getenv("OPENBMC_USER", "root")
PASS = os.getenv("OPENBMC_PASS", "0penBmc")


@pytest.fixture(scope="session")
def auth_session():
    s = requests.Session()
    s.verify = False
    # Авторизация через Redfish
    resp = s.post(f"{BASE_URL}/redfish/v1/SessionService/Sessions", json={"UserName": USER, "Password": PASS}, timeout=5)
    assert resp.status_code in (200, 201), f"Auth failed: {resp.status_code}"
    token = resp.headers.get("X-Auth-Token") or resp.json().get("Token")
    assert token, "X-Auth-Token missing"
    s.headers.update({"X-Auth-Token": token})
    yield s
    s.close()


def test_01_redfish_root():
    """Проверка доступности ServiceRoot."""
    r = requests.get(f"{BASE_URL}/redfish/v1", verify=False, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "SessionService" in data
    assert "Systems" in data


def test_02_system_info(auth_session):
    """Проверка информации о сервере и состояния питания."""
    r = auth_session.get(f"{BASE_URL}/redfish/v1/Systems/system", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data.get("PowerState") in ("On", "Off")
    assert data.get("Status", {}).get("Health") == "OK"


def test_03_thermal_sensors(auth_session):
    """Проверка датчиков температуры шасси."""
    r = auth_session.get(f"{BASE_URL}/redfish/v1/Chassis/chassis/Thermal", timeout=5)
    assert r.status_code == 200
    temps = r.json().get("Temperatures", [])
    assert len(temps) > 0
    for t in temps:
        assert t.get("ReadingCelsius") is not None
        assert t.get("ReadingCelsius") < t.get("UpperThresholdCritical", 85.0)


def test_04_power_reset_action(auth_session):
    """Проверка действия управления питанием."""
    r = auth_session.post(f"{BASE_URL}/redfish/v1/Systems/system/Actions/ComputerSystem.Reset", json={"ResetType": "On"}, timeout=5)
    assert r.status_code in (200, 202, 204)
