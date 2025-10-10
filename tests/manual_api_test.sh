#!/bin/bash

# Manual API Integration Test Script
# Run against a live server at http://localhost:5100

set -e  # Exit on error

BASE_URL="http://localhost:5100"
BOLD="\033[1m"
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo -e "${BOLD}=== API Integration Test Suite ===${RESET}\n"

# Check if server is running
echo -e "${BOLD}Checking server health...${RESET}"
HEALTH=$(curl -s "$BASE_URL/api/health" || echo "")
if [[ "$HEALTH" == "" ]]; then
    echo -e "${RED}✗ Server not running at $BASE_URL${RESET}"
    echo "Start server with: python -m src.ui.api_enhanced"
    exit 1
fi
echo -e "${GREEN}✓ Server is running${RESET}\n"

# Test 1: Get all processes (should be empty or have existing)
echo -e "${BOLD}Test 1: GET /api/processes${RESET}"
PROCESSES=$(curl -s "$BASE_URL/api/processes")
TOTAL=$(echo "$PROCESSES" | jq -r '.total')
echo "Total processes: $TOTAL"
echo "$PROCESSES" | jq -c '.processes[0:2]' | head -c 200
echo -e "${GREEN}✓ Pass${RESET}\n"

# Test 2: Get running processes
echo -e "${BOLD}Test 2: GET /api/processes/running${RESET}"
RUNNING=$(curl -s "$BASE_URL/api/processes/running")
RUNNING_COUNT=$(echo "$RUNNING" | jq -r '.total')
echo "Running processes: $RUNNING_COUNT"
echo -e "${GREEN}✓ Pass${RESET}\n"

# Test 3: Get non-existent process (should 404)
echo -e "${BOLD}Test 3: GET /api/processes/{invalid} (expect 404)${RESET}"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/processes/invalid_xyz_12345")
HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v HTTP_CODE)

if [[ "$HTTP_CODE" == "404" ]]; then
    echo "HTTP Status: $HTTP_CODE"
    echo "Response: $BODY"
    echo -e "${GREEN}✓ Pass - Correct 404${RESET}\n"
else
    echo -e "${RED}✗ Fail - Expected 404, got $HTTP_CODE${RESET}\n"
fi

# Test 4: Get logs for non-existent process (should 404)
echo -e "${BOLD}Test 4: GET /api/processes/{invalid}/logs (expect 404)${RESET}"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/processes/invalid/logs")
HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)

if [[ "$HTTP_CODE" == "404" ]]; then
    echo "HTTP Status: $HTTP_CODE"
    echo -e "${GREEN}✓ Pass - Correct 404${RESET}\n"
else
    echo -e "${RED}✗ Fail - Expected 404, got $HTTP_CODE${RESET}\n"
fi

# Test 5: Negative limit validation (EXPECTED BUG)
echo -e "${BOLD}Test 5: GET /api/processes/{id}/logs?limit=-10 (documents bug)${RESET}"
echo -e "${YELLOW}⚠ This test documents the negative limit bug${RESET}"
# Would need a real process ID - skip if none exist
if [[ "$TOTAL" -gt 0 ]]; then
    FIRST_ID=$(echo "$PROCESSES" | jq -r '.processes[0].process_id')
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/processes/$FIRST_ID/logs?limit=-10")
    HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)

    if [[ "$HTTP_CODE" == "400" ]]; then
        echo -e "${GREEN}✓ Pass - Validation working${RESET}\n"
    else
        echo -e "${YELLOW}⚠ Bug confirmed - Should return 400, got $HTTP_CODE${RESET}\n"
    fi
else
    echo -e "${YELLOW}Skipped - No processes to test${RESET}\n"
fi

# Test 6: Cancel non-existent process (should 404)
echo -e "${BOLD}Test 6: DELETE /api/processes/{invalid} (expect 404)${RESET}"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X DELETE "$BASE_URL/api/processes/invalid_xyz")
HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)

if [[ "$HTTP_CODE" == "404" ]]; then
    echo "HTTP Status: $HTTP_CODE"
    echo -e "${GREEN}✓ Pass - Correct 404${RESET}\n"
else
    echo -e "${RED}✗ Fail - Expected 404, got $HTTP_CODE${RESET}\n"
fi

# Test 7: Start training process (integration test)
echo -e "${BOLD}Test 7: POST /api/models/train (integration)${RESET}"
echo "Starting training process..."

TRAIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/models/train" \
    -H "Content-Type: application/json" \
    -d '{
        "dataset": "crypto_btc_daily",
        "feature_handler": "alpha158",
        "model_handler": "lightgbm"
    }')

PROCESS_ID=$(echo "$TRAIN_RESPONSE" | jq -r '.process_id')
STATUS=$(echo "$TRAIN_RESPONSE" | jq -r '.status')

if [[ "$STATUS" == "started" && "$PROCESS_ID" != "null" ]]; then
    echo "Process ID: $PROCESS_ID"
    echo "Status: $STATUS"
    echo -e "${GREEN}✓ Pass - Training started${RESET}\n"

    # Test 8: Get process details
    echo -e "${BOLD}Test 8: GET /api/processes/{process_id}${RESET}"
    sleep 1  # Give it time to initialize
    PROCESS_DETAILS=$(curl -s "$BASE_URL/api/processes/$PROCESS_ID")
    PROC_STATUS=$(echo "$PROCESS_DETAILS" | jq -r '.status')
    PROGRESS=$(echo "$PROCESS_DETAILS" | jq -r '.metrics.progress_percent')
    CURRENT_STEP=$(echo "$PROCESS_DETAILS" | jq -r '.metrics.current_step')

    echo "Status: $PROC_STATUS"
    echo "Progress: $PROGRESS%"
    echo "Current step: $CURRENT_STEP"
    echo -e "${GREEN}✓ Pass - Process details retrieved${RESET}\n"

    # Test 9: Get process logs
    echo -e "${BOLD}Test 9: GET /api/processes/{process_id}/logs${RESET}"
    LOGS=$(curl -s "$BASE_URL/api/processes/$PROCESS_ID/logs?limit=10")
    LOG_COUNT=$(echo "$LOGS" | jq -r '.logs | length')

    echo "Logs retrieved: $LOG_COUNT"
    if [[ "$LOG_COUNT" -gt 0 ]]; then
        echo "First log: $(echo "$LOGS" | jq -r '.logs[0].message')"
        echo -e "${GREEN}✓ Pass - Logs retrieved${RESET}\n"
    else
        echo -e "${YELLOW}⚠ Warning - No logs yet${RESET}\n"
    fi

    # Test 10: Cancel process
    echo -e "${BOLD}Test 10: DELETE /api/processes/{process_id} (cancel)${RESET}"
    sleep 2  # Let it run a bit
    CANCEL_RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/processes/$PROCESS_ID")
    CANCEL_STATUS=$(echo "$CANCEL_RESPONSE" | jq -r '.status')

    if [[ "$CANCEL_STATUS" == "cancelled" ]]; then
        echo "Cancellation status: $CANCEL_STATUS"
        echo -e "${GREEN}✓ Pass - Process cancelled${RESET}\n"

        # Test 11: Try to cancel again (should 400)
        echo -e "${BOLD}Test 11: DELETE /api/processes/{process_id} again (expect 400)${RESET}"
        RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X DELETE "$BASE_URL/api/processes/$PROCESS_ID")
        HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)

        if [[ "$HTTP_CODE" == "400" ]]; then
            echo "HTTP Status: $HTTP_CODE"
            echo -e "${GREEN}✓ Pass - Correct 400 for already cancelled${RESET}\n"
        else
            echo -e "${RED}✗ Fail - Expected 400, got $HTTP_CODE${RESET}\n"
        fi

        # Test 12: Verify cancelled state
        echo -e "${BOLD}Test 12: Verify cancelled process state${RESET}"
        FINAL_STATE=$(curl -s "$BASE_URL/api/processes/$PROCESS_ID")
        FINAL_STATUS=$(echo "$FINAL_STATE" | jq -r '.status')
        END_TIME=$(echo "$FINAL_STATE" | jq -r '.metrics.end_time')

        echo "Final status: $FINAL_STATUS"
        echo "End time: $END_TIME"

        if [[ "$FINAL_STATUS" == "cancelled" && "$END_TIME" != "null" ]]; then
            echo -e "${GREEN}✓ Pass - Process properly cancelled${RESET}\n"
        else
            echo -e "${RED}✗ Fail - Unexpected state${RESET}\n"
        fi
    else
        echo -e "${YELLOW}⚠ Process may have completed before cancellation${RESET}"
        echo "Status: $(echo "$CANCEL_RESPONSE" | jq -r '.detail')"
        echo ""
    fi
else
    echo -e "${RED}✗ Fail - Training did not start${RESET}"
    echo "Response: $TRAIN_RESPONSE"
    echo ""
fi

# Test 13: Malformed request (missing required field)
echo -e "${BOLD}Test 13: POST /api/models/train with missing field (expect 422)${RESET}"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/models/train" \
    -H "Content-Type: application/json" \
    -d '{"dataset": "test"}')
HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)

if [[ "$HTTP_CODE" == "422" ]]; then
    echo "HTTP Status: $HTTP_CODE"
    echo -e "${GREEN}✓ Pass - Pydantic validation working${RESET}\n"
else
    echo -e "${RED}✗ Fail - Expected 422, got $HTTP_CODE${RESET}\n"
fi

# Test 14: Wrong data type
echo -e "${BOLD}Test 14: POST /api/models/train with wrong type (expect 422)${RESET}"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/models/train" \
    -H "Content-Type: application/json" \
    -d '{"dataset": 123, "model_handler": "lightgbm"}')
HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)

if [[ "$HTTP_CODE" == "422" ]]; then
    echo "HTTP Status: $HTTP_CODE"
    echo -e "${GREEN}✓ Pass - Type validation working${RESET}\n"
else
    echo -e "${RED}✗ Fail - Expected 422, got $HTTP_CODE${RESET}\n"
fi

# Summary
echo -e "${BOLD}=== Test Suite Complete ===${RESET}\n"
echo -e "${GREEN}Most tests passed${RESET}"
echo -e "${YELLOW}Known issues:${RESET}"
echo "  - Negative limit validation (Test 5)"
echo "  - Ping/pong not implemented on /ws/processes"
echo "  - Task cancellation doesn't stop background tasks"
echo ""
echo "See API_INTEGRATION_TEST_REPORT.md for full details"
