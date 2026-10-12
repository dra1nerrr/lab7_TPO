"""
WebUI автотесты для OpenBMC с использованием Selenium WebDriver (CI/CD Pipeline).
Формирует JUnit XML отчет для Jenkins (reports/webui_tests.xml) и сохраняет скриншоты в screenshots/.
"""

import os
import time
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = os.getenv("OPENBMC_HOST", "http://127.0.0.1:18443")
USER = os.getenv("OPENBMC_USER", "root")
PASS = os.getenv("OPENBMC_PASS", "0penBmc")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


class OpenBMCWebUITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--ignore-certificate-errors")
        cls.driver = webdriver.Chrome(options=options)
        cls.wait = WebDriverWait(cls.driver, 10)

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()

    def save_screen(self, name: str):
        path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
        self.driver.save_screenshot(path)

    def do_login(self, username, password):
        self.driver.get(f"{BASE_URL}/#/login")
        self.driver.refresh()
        u_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#username, [data-test-id='login-input-username']")))
        p_input = self.driver.find_element(By.CSS_SELECTOR, "#password, [data-test-id='login-input-password']")
        btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], [data-test-id='login-button-submit']")
        u_input.clear()
        u_input.send_keys(username)
        p_input.clear()
        p_input.send_keys(password)
        btn.click()

    def test_01_successful_login(self):
        """Тест 1: Успешная авторизация в WebUI."""
        self.do_login(USER, PASS)
        self.wait.until(lambda d: "/login" not in d.current_url)
        header = self.wait.until(EC.visibility_of_element_located((By.ID, "app-header")))
        self.assertTrue(header.is_displayed())
        self.save_screen("01_login_success")

    def test_02_invalid_credentials(self):
        """Тест 2: Авторизация с неверными данными."""
        self.do_login(USER, "wrong_pass")
        err = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        self.assertTrue(err.is_displayed())
        self.save_screen("02_invalid_credentials")

    def test_03_inventory_view(self):
        """Тест 3: Проверка страницы инвенторики оборудования."""
        self.do_login(USER, PASS)
        self.wait.until(lambda d: "/login" not in d.current_url)
        self.driver.get(f"{BASE_URL}/#/hardware-status/inventory")
        main_el = self.wait.until(EC.visibility_of_element_located((By.ID, "app-main")))
        self.assertIn("processor", main_el.text.lower())
        self.save_screen("03_inventory")

    def test_04_power_operations(self):
        """Тест 4: Управление питанием сервера через WebUI."""
        self.do_login(USER, PASS)
        self.wait.until(lambda d: "/login" not in d.current_url)
        self.driver.get(f"{BASE_URL}/#/operations/server-power-operations")
        btn = self.wait.until(EC.element_to_be_clickable((By.ID, "power-on-btn")))
        btn.click()
        time.sleep(0.2)
        status_el = self.driver.find_element(By.ID, "power-status")
        self.assertEqual(status_el.text.strip(), "On")
        self.save_screen("04_power_on")

    def test_05_sensors_view(self):
        """Тест 5: Проверка датчиков температуры компонентов."""
        self.do_login(USER, PASS)
        self.wait.until(lambda d: "/login" not in d.current_url)
        self.driver.get(f"{BASE_URL}/#/hardware-status/sensors")
        main_el = self.wait.until(EC.visibility_of_element_located((By.ID, "app-main")))
        self.assertIn("CPU0 Core Temp", main_el.text)
        self.save_screen("05_sensors")

    def test_06_account_lockout(self):
        """Тест 6: Блокировка учетной записи после серии неудачных попыток."""
        for _ in range(5):
            self.do_login(USER, "bad_password")
            time.sleep(0.1)
        self.do_login(USER, PASS)
        err = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        self.assertIn("locked", err.text.lower())
        self.save_screen("06_account_locked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
