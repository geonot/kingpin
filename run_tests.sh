#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "===== Starting All Tests ====="

# --- Backend Tests ---
echo ""
echo "--- Running Backend Tests ---"
# Backup original files
cp casino_be/requirements.txt casino_be/requirements.txt.bak
cp casino_be/pytest.ini casino_be/pytest.ini.bak

# Modify files for test environment (workarounds for sandbox)
echo "Applying workarounds for backend test environment..."
sed -i '/psycopg2-binary/s/^/#/' casino_be/requirements.txt
sed -i '/addopts.*--cov/s/^/#/' casino_be/pytest.ini

echo "Running backend tests..."
(
  cd casino_be && \
  export TESTING=True && \
  export PYTHONPATH=/app && \
  python -m pip install -r requirements.txt --quiet && \
  python -m pytest tests/test_api.py
)
BE_TEST_RESULT=$?

# Restore original files
mv casino_be/requirements.txt.bak casino_be/requirements.txt
mv casino_be/pytest.ini.bak casino_be/pytest.ini
echo "Backend workarounds reverted."

if [ $BE_TEST_RESULT -ne 0 ]; then
  echo "Backend tests failed!"
  exit $BE_TEST_RESULT
else
  echo "Backend tests passed!"
fi
# --- End Backend Tests ---


# --- Frontend Unit Tests ---
echo ""
echo "--- Running Frontend Unit Tests ---"
(
  cd casino_fe && \
  npm install --quiet && \
  npm run test:unit
)
FE_UNIT_TEST_RESULT=$?

if [ $FE_UNIT_TEST_RESULT -ne 0 ]; then
  echo "Frontend unit tests failed!"
  exit $FE_UNIT_TEST_RESULT
else
  echo "Frontend unit tests passed!"
fi
# --- End Frontend Unit Tests ---


# --- Frontend E2E Tests ---
echo ""
echo "--- Running Frontend E2E Tests ---"
echo "Starting Docker Compose stack for E2E tests..."
# Ensure Docker daemon is accessible; this script assumes it is.
# The following command might fail in environments without Docker or with permission issues.
docker-compose up -d --build
DC_UP_RESULT=$?

if [ $DC_UP_RESULT -ne 0 ]; then
  echo "Docker Compose stack failed to start!"
  # Attempt to bring it down just in case some services started
  docker-compose down -v --remove-orphans || true
  exit $DC_UP_RESULT
fi

echo "Waiting for services to be healthy (approx 30s)..."
sleep 30 # Give services time to start, especially DB and backend migrations

FE_E2E_TEST_RESULT=0
echo "Running Playwright E2E tests..."
(
  cd casino_fe && \
  # Assuming VUE_APP_API_BASE_URL is handled by Nginx proxy within Docker setup
  # Playwright's webServer config might try to start dev server,
  # but reuseExistingServer:true should use the one from docker-compose.
  npx playwright test # npm run test:e2e could also be used
)
FE_E2E_TEST_RESULT=$?

echo "Stopping Docker Compose stack..."
docker-compose down -v --remove-orphans
DC_DOWN_RESULT=$?

if [ $DC_DOWN_RESULT -ne 0 ]; then
  echo "Warning: Docker Compose stack failed to stop cleanly."
  # Not exiting here, as tests might have run.
fi

if [ $FE_E2E_TEST_RESULT -ne 0 ]; then
  echo "Frontend E2E tests failed!"
  exit $FE_E2E_TEST_RESULT
else
  echo "Frontend E2E tests passed!"
fi
# --- End Frontend E2E Tests ---

echo ""
echo "===== All Tests Completed ====="
exit 0
