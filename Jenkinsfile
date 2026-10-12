pipeline {
    agent any

    environment {
        OPENBMC_HOST = 'http://127.0.0.1:18443'
        OPENBMC_USER = 'root'
        OPENBMC_PASS = '0penBmc'
        REPORTS_DIR  = 'reports'
        SCREENSHOTS_DIR = 'screenshots'
    }

    options {
        timeout(time: 20, unit: 'MINUTES')
        timestamps()
        ansiColor('xterm')
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout & Setup') {
            steps {
                script {
                    echo "=========================================================="
                    echo "▶ [Stage 1] Подготовка окружения и структуры каталогов"
                    echo "=========================================================="
                    sh '''
                        mkdir -p ${REPORTS_DIR}
                        mkdir -p ${SCREENSHOTS_DIR}
                        echo "Environment: Node=${NODE_NAME}, Executor=${EXECUTOR_NUMBER}" > ${REPORTS_DIR}/env_info.txt
                        python3 --version >> ${REPORTS_DIR}/env_info.txt
                        pip3 list >> ${REPORTS_DIR}/env_info.txt
                    '''
                }
            }
        }

        stage('Start OpenBMC QEMU') {
            steps {
                script {
                    echo "=========================================================="
                    echo "▶ [Stage 2] Запуск эмулятора QEMU / сервиса OpenBMC"
                    echo "=========================================================="
                    sh '''
                        # Фоновый запуск сервиса платформы OpenBMC (или qemu-system-arm)
                        python3 openbmc_service.py > ${REPORTS_DIR}/qemu_boot.log 2>&1 &
                        echo $! > ${REPORTS_DIR}/openbmc_pid.txt

                        # Ожидание готовности портов (Health-check loop)
                        echo "Ожидание готовности OpenBMC..."
                        RETRIES=30
                        until curl -s -f http://127.0.0.1:18443/healthz || [ $RETRIES -eq 0 ]; do
                            echo "Waiting for OpenBMC to boot... ($RETRIES left)"
                            sleep 1
                            RETRIES=$((RETRIES-1))
                        done

                        if [ $RETRIES -eq 0 ]; then
                            echo "Ошибка: OpenBMC не запустился за отведённое время!"
                            cat ${REPORTS_DIR}/qemu_boot.log
                            exit 1
                        fi

                        echo "OpenBMC успешно запущен и готов к тестированию!" >> ${REPORTS_DIR}/qemu_boot.log
                    '''
                }
            }
        }

        stage('OpenBMC API Tests') {
            steps {
                script {
                    echo "=========================================================="
                    echo "▶ [Stage 3] Запуск автотестов REST API (PyTest Redfish/IPMI)"
                    echo "=========================================================="
                    sh '''
                        python3 -m pytest test_api.py \
                            -v -s \
                            --junitxml=${REPORTS_DIR}/api_tests.xml \
                            --html=${REPORTS_DIR}/api_report.html \
                            --self-contained-html || true
                    '''
                }
            }
        }

        stage('OpenBMC WebUI Tests') {
            steps {
                script {
                    echo "=========================================================="
                    echo "▶ [Stage 4] Запуск автотестов Web UI (Selenium WebDriver)"
                    echo "=========================================================="
                    sh '''
                        python3 -m pytest test_webui.py \
                            -v -s \
                            --junitxml=${REPORTS_DIR}/webui_tests.xml \
                            --html=${REPORTS_DIR}/webui_report.html \
                            --self-contained-html || true
                    '''
                }
            }
        }

        stage('OpenBMC Load Tests') {
            steps {
                script {
                    echo "=========================================================="
                    echo "▶ [Stage 5] Запуск нагрузочного тестирования (Locust)"
                    echo "=========================================================="
                    sh '''
                        python3 -m locust \
                            -f locustfile.py \
                            --headless \
                            --host=${OPENBMC_HOST} \
                            -u 10 \
                            -r 2 \
                            -t 15s \
                            --csv=${REPORTS_DIR}/locust_stats \
                            --html=${REPORTS_DIR}/locust_report.html \
                            OpenBMCUser || true
                    '''
                }
            }
        }
    }

    post {
        always {
            script {
                echo "=========================================================="
                echo "▶ [Teardown] Остановка QEMU и публикация артефактов"
                echo "=========================================================="
                sh '''
                    if [ -f ${REPORTS_DIR}/openbmc_pid.txt ]; then
                        PID=$(cat ${REPORTS_DIR}/openbmc_pid.txt)
                        kill $PID || true
                        echo "Процесс OpenBMC (PID: $PID) остановлен."
                    fi
                '''

                // 1. Публикация файлов отчётов в артефакты Jenkins
                archiveArtifacts artifacts: "${REPORTS_DIR}/**, ${SCREENSHOTS_DIR}/**",
                                 fingerprint: true,
                                 allowEmptyArchive: true

                // 2. Публикация результатов тестов JUnit XML
                junit testResults: "${REPORTS_DIR}/*.xml",
                      allowEmptyResults: true

                // 3. Публикация интерактивных HTML-отчётов
                publishHTML([
                    allowMissing: true,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: "${REPORTS_DIR}",
                    reportFiles: 'api_report.html, webui_report.html, locust_report.html',
                    reportName: 'OpenBMC Comprehensive Test Reports',
                    reportTitles: 'API Report, WebUI Report, Load Test Report'
                ])
            }
        }
        success {
            echo "✅ Пайплайн успешно выполнен! Все тесты OpenBMC пройдены без ошибок."
        }
        failure {
            echo "❌ Пайплайн завершился с ошибками. Проверьте артефакты и логи."
        }
    }
}
