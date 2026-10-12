"""
Локальный исполнитель Jenkins Pipeline для верификации лабораторной работы №7.
Имитирует выполнение Jenkinsfile, запускает все этапы и собирает артефакты в папку reports/.
"""

import os
import subprocess
import sys
import time
import requests

from openbmc_service import start_openbmc_service, stop_openbmc_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def print_stage(name):
    print("\n" + "=" * 65)
    print(f"▶ [Pipeline Stage] {name}")
    print("=" * 65)


def main():
    start_time = time.time()
    print_stage("1. Checkout & Environment Setup")
    env_info_path = os.path.join(REPORTS_DIR, "env_info.txt")
    with open(env_info_path, "w", encoding="utf-8") as f:
        f.write(f"Python: {sys.version}\n")
        f.write(f"Platform: {sys.platform}\n")
        f.write("Runner: Jenkins Local Pipeline Simulation\n")
    print(f"Окружение инициализировано. Записан: {env_info_path}")

    print_stage("2. Start OpenBMC (QEMU / Platform Service)")
    start_openbmc_service(18443)
    boot_log_path = os.path.join(REPORTS_DIR, "qemu_boot.log")
    with open(boot_log_path, "w", encoding="utf-8") as f:
        f.write("[BOOT] Starting OpenBMC platform services...\n")
        # Health-check
        for _ in range(10):
            try:
                r = requests.get("http://127.0.0.1:18443/healthz", timeout=1)
                if r.status_code == 200:
                    f.write("[BOOT] Health check passed: HTTP 200 OK\n")
                    f.write("[BOOT] OpenBMC ready for testing.\n")
                    print("OpenBMC сервис успешно запущен и отвечает на http://127.0.0.1:18443")
                    break
            except Exception:
                time.sleep(0.5)

    print_stage("3. Run OpenBMC API Tests (PyTest)")
    api_xml = os.path.join(REPORTS_DIR, "api_tests.xml")
    api_html = os.path.join(REPORTS_DIR, "api_report.html")
    cmd_api = [
        sys.executable, "-m", "pytest",
        os.path.join(BASE_DIR, "test_api.py"),
        "-v", "-s",
        f"--junitxml={api_xml}",
        f"--html={api_html}",
        "--self-contained-html"
    ]
    res_api = subprocess.run(cmd_api, capture_output=True, text=True)
    print(res_api.stdout)
    if res_api.returncode != 0:
        print("[ERROR API]:", res_api.stderr)

    print_stage("4. Run OpenBMC WebUI Tests (Selenium WebDriver)")
    webui_xml = os.path.join(REPORTS_DIR, "webui_tests.xml")
    webui_html = os.path.join(REPORTS_DIR, "webui_report.html")
    cmd_webui = [
        sys.executable, "-m", "pytest",
        os.path.join(BASE_DIR, "test_webui.py"),
        "-v", "-s",
        f"--junitxml={webui_xml}",
        f"--html={webui_html}",
        "--self-contained-html"
    ]
    res_webui = subprocess.run(cmd_webui, capture_output=True, text=True)
    print(res_webui.stdout)
    if res_webui.returncode != 0:
        print("[ERROR WebUI]:", res_webui.stderr)

    print_stage("5. Run OpenBMC Load Tests (Locust)")
    locust_csv = os.path.join(REPORTS_DIR, "locust_stats")
    locust_html = os.path.join(REPORTS_DIR, "locust_report.html")
    cmd_locust = [
        sys.executable, "-m", "locust",
        "-f", os.path.join(BASE_DIR, "locustfile.py"),
        "--headless",
        "--host", "http://127.0.0.1:18443",
        "-u", "10",
        "-r", "2",
        "-t", "12s",
        f"--csv={locust_csv}",
        f"--html={locust_html}",
        "OpenBMCUser"
    ]
    res_locust = subprocess.run(cmd_locust, capture_output=True, text=True)
    print(res_locust.stdout)
    if res_locust.returncode != 0:
        print("[ERROR Locust]:", res_locust.stderr)

    print_stage("Teardown: Stop OpenBMC & Archive Artifacts")
    stop_openbmc_service()

    total_time = time.time() - start_time
    print(f"\n==========================================================")
    print(f"✅ Pipeline выполнен за {total_time:.2f} сек!")
    print(f"Сформированные артефакты в каталоге {REPORTS_DIR}:")
    for f in os.listdir(REPORTS_DIR):
        fpath = os.path.join(REPORTS_DIR, f)
        print(f"  - {f} ({os.path.getsize(fpath)} байт)")

    print(f"\nСформированные скриншоты в каталоге {SCREENSHOTS_DIR}:")
    for f in os.listdir(SCREENSHOTS_DIR):
        fpath = os.path.join(SCREENSHOTS_DIR, f)
        print(f"  - {f} ({os.path.getsize(fpath)} байт)")


if __name__ == "__main__":
    main()
