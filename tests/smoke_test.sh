#!/usr/bin/env bash
set -euo pipefail

# ── Настройки (API_KEY задаётся в .env или при вызове) ───────────
API_URL="${API_URL:-http://localhost:8002}"
API_KEY="${API_KEY:?Укажите API_KEY (из .env или export API_KEY=...)}"
USER_ID="smoke_test_user"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo "════════════════════════════════════════════"
echo " WW2 RAG — Smoke Test"
echo " API: ${API_URL}"
echo "════════════════════════════════════════════"
echo ""

# ── 1. Health check ────────────────────────────────────────────
echo "1. GET /health…"
HEALTH=$(curl -s "${API_URL}/health")
echo "$HEALTH" | jq . 2>/dev/null || echo "$HEALTH"

if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('faiss')=='loaded' and d.get('db')=='connected'" 2>/dev/null; then
    pass "Health OK (FAISS loaded, DB connected)"
else
    fail "Health check failed"
fi
echo ""

# ── 2. /ask-text — текстовый запрос ───────────────────────────
echo "2. POST /ask-text — текстовый вопрос…"
RESPONSE=$(curl -s -X POST "${API_URL}/ask-text" \
    -H "X-API-Key: ${API_KEY}" \
    -H "X-User-Id: ${USER_ID}" \
    -F "text=Когда началась Сталинградская битва?")

echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"

if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('answer')" 2>/dev/null; then
    pass "/ask-text вернул ответ"
else
    fail "/ask-text: нет поля answer"
fi

if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); c=d.get('citations') or d.get('sources') or []; assert len(c)>0" 2>/dev/null; then
    pass "/ask-text вернул citations с именами файлов"
else
    fail "/ask-text: citations пусты или отсутствуют"
fi
echo ""

# ── 3. /memory/clear — очистка памяти ─────────────────────────
echo "3. POST /memory/clear…"
RESPONSE=$(curl -s -X POST "${API_URL}/memory/clear" \
    -H "X-API-Key: ${API_KEY}" \
    -H "X-User-Id: ${USER_ID}")

echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"

if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok'" 2>/dev/null; then
    pass "/memory/clear OK"
else
    fail "/memory/clear: неожиданный ответ"
fi
echo ""

# ── 4. Проверка 401 (неверный ключ) ───────────────────────────
echo "4. Проверка авторизации (неверный ключ)…"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/ask-text" \
    -H "X-API-Key: wrong-key" \
    -H "X-User-Id: ${USER_ID}" \
    -F "text=test")

if [ "$HTTP_CODE" -eq 401 ]; then
    pass "Неверный ключ → 401"
else
    fail "Ожидали 401, получили $HTTP_CODE"
fi
echo ""

# ── 5. Проверка БД ────────────────────────────────────────────
echo "5. Проверка записей в PostgreSQL…"
COMPOSE_CMD="docker-compose"
command -v docker-compose >/dev/null 2>&1 || COMPOSE_CMD="docker compose"
$COMPOSE_CMD exec -T postgres psql -U "${POSTGRES_USER:?Укажите POSTGRES_USER}" -d "${POSTGRES_DB:?Укажите POSTGRES_DB}" \
    -c "SELECT user_id, left(question, 50) AS question, left(answer, 50) AS answer, created_at FROM dialog_messages ORDER BY created_at DESC LIMIT 5;" \
    2>/dev/null && pass "Записи в БД найдены" || fail "Не удалось прочитать БД"
echo ""

echo "════════════════════════════════════════════"
echo -e "${GREEN} Smoke test пройден!${NC}"
echo "════════════════════════════════════════════"
