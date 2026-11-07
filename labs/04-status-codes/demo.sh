#!/usr/bin/env bash
# Hit the running API once per status code and check each answer.
# Start the server first:  uvicorn app:app --port 8000
# Then run:                bash demo.sh            (or BASE=http://host:port bash demo.sh)
set -u
BASE="${BASE:-http://localhost:8000}"
ADMIN="Authorization: Bearer admin-token"
VIEWER="Authorization: Bearer viewer-token"
JSON="Content-Type: application/json"
NEW_ID="ord-$(date +%s)"   # unique per run, so 201 works every time
fails=0

check() {  # check <expected> <label> <curl args...>
  local expected="$1" label="$2"; shift 2
  local got
  got=$(curl -s -o /dev/null -w "%{http_code}" "$@")
  if [ "$got" = "$expected" ]; then mark="ok  "; else mark="FAIL"; fails=$((fails + 1)); fi
  printf "%s %s (got %s)  %s\n" "$mark" "$expected" "$got" "$label"
}

check 200 "read an order that exists"     -H "$VIEWER" "$BASE/orders/ord-001"
check 201 "create a new order"            -H "$ADMIN" -H "$JSON" -d "{\"order_id\":\"$NEW_ID\",\"item\":\"pen\",\"quantity\":3}" "$BASE/orders"
check 400 "body is not valid JSON"        -H "$ADMIN" -H "$JSON" -d '{"order_id": "ord-9",' "$BASE/orders"
check 401 "no token"                      "$BASE/orders/ord-001"
check 403 "viewer token tries to create"  -H "$VIEWER" -H "$JSON" -d '{"order_id":"ord-777","item":"pen","quantity":1}' "$BASE/orders"
check 404 "order does not exist"          -H "$VIEWER" "$BASE/orders/ord-404"
check 409 "order id already taken"        -H "$ADMIN" -H "$JSON" -d "{\"order_id\":\"$NEW_ID\",\"item\":\"pen\",\"quantity\":1}" "$BASE/orders"
check 422 "valid JSON, quantity is 0"     -H "$ADMIN" -H "$JSON" -d '{"order_id":"ord-888","item":"pen","quantity":0}' "$BASE/orders"
check 500 "simulated bug on the server"   "$BASE/simulate/crash"

echo
if [ "$fails" -eq 0 ]; then echo "All 9 status codes behaved as expected."; else echo "$fails check(s) failed."; fi
exit "$fails"
