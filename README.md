WW2 RAG консультант

Небольшой сервис на FastAPI, который отвечает на вопросы по базе знаний о Второй мировой войне.
Используется подход RAG. Сначала из базы знаний ищутся подходящие фрагменты текста, после чего модель формирует ответ на их основе.

База знаний состоит из нескольких текстовых файлов со статьями о событиях Великой Отечественной войны.

Что используется

Python 3.11
FastAPI (асинхронный сервер)
LangChain и FAISS для поиска по текстам
OpenAI API для генерации ответа, эмбеддингов, распознавания изображений и аудио
PostgreSQL для хранения истории диалогов
SQLAlchemy 2 async
Telegram бот на aiogram
Docker и docker compose

⸻

Установка

Сначала нужно создать файл .env.

cp .env.example .env

В нем нужно указать значения:

API_KEY — ключ для авторизации запросов к API
AI_PROXY_URL — адрес прокси OpenAI. Если оставить пустым, будет использоваться обычный API OpenAI
OPENAI_API_KEY — ключ OpenAI (если используется прямое подключение)
TELEGRAM_BOT_TOKEN — токен Telegram бота
POSTGRES_USER — пользователь базы
POSTGRES_PASSWORD — пароль
POSTGRES_DB — имя базы
DATABASE_URL — строка подключения к базе (asyncpg)

После этого установить зависимости.

pip install -r requirements.txt


⸻

Создание базы знаний

Тексты для базы лежат в папке

data/knowledge

Это несколько файлов со статьями о Второй мировой войне.

Чтобы построить векторную базу:

python -m app.rag.ingest

Скрипт читает все txt файлы, режет текст на части и создаёт FAISS индекс.

В процессе будет примерно такой вывод:

Читаю файл: bitva_za_moskvu.txt
Читаю файл: blokada_leningrada.txt
Читаю файл: operaciya_barbarossa.txt
Читаю файл: stalingradskaya_bitva.txt
Читаю файл: velikaya_otechestvennaya_vojna.txt
Загружено 5 файлов
Всего чанков: ~800
Создаю FAISS индекс
Индекс сохранён в data/faiss_store

Индекс сохраняется в папке

data/faiss_store


⸻

Запуск

После создания индекса можно запускать сервис.

docker compose up --build -d

Поднимается два контейнера

api — сам FastAPI сервер
postgres — база данных

Порты

api — 8002
postgres — 5434

Посмотреть логи можно так

docker compose logs -f api

В логах при запуске будет сообщение о загрузке FAISS индекса.

FAISS loaded: N chunks

Это означает что индекс загружен в память.

⸻

API

Все запросы требуют два заголовка

X-API-Key
X-User-Id

Первый используется для авторизации.
Второй для идентификации пользователя и хранения его истории диалога.

⸻

Проверка сервиса

GET /health

curl http://localhost:8002/health

Ответ примерно такой

{
 "status": "ok",
 "faiss": "loaded",
 "faiss_chunks": 695,
 "db": "connected"
}


⸻

Текстовый вопрос

POST /ask-text

Пример запроса

curl -X POST http://localhost:8002/ask-text \
-H "X-API-Key: ключ" \
-H "X-User-Id: user1" \
-F "text=Когда началась операция Барбаросса?"

Можно также отправить изображение

-F "image=@photo.jpg"

Сначала изображение описывается моделью, затем описание добавляется к вопросу.

Ответ возвращается примерно в таком виде

{
 "answer": "Операция Барбаросса началась 22 июня 1941 года...",
 "citations": [
  {
   "source": "operaciya_barbarossa.txt",
   "chunk_id": 3,
   "section": "Начало войны",
   "quote": "22 июня 1941 года Германия напала на Советский Союз"
  }
 ]
}


⸻

Голосовой вопрос

POST /ask-audio

Отправляется mp3 или ogg файл.

curl -X POST http://localhost:8002/ask-audio \
-H "X-API-Key: ключ" \
-H "X-User-Id: user1" \
-F "audio=@question.mp3"

Аудио сначала распознается через Whisper, после этого выполняется обычный поиск по базе знаний.

⸻

Очистка истории

POST /memory/clear

curl -X POST http://localhost:8002/memory/clear \
-H "X-API-Key: ключ" \
-H "X-User-Id: user1"

Очищает историю сообщений пользователя.

⸻

Smoke test

Есть простой скрипт проверки

tests/smoke_test.sh

Он проверяет

доступность сервиса
ответ на /ask-text
очистку памяти
проверку авторизации
запись в базу

Запустите тест так. Сначала убедитесь, что переменная API_KEY задана (она берётся из .env или можно задать вручную через export API_KEY=...). После этого выполните:

bash tests/smoke_test.sh


⸻

Проверка базы

Можно посмотреть записи диалогов.

docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB 
  -c \"SELECT * FROM dialog_messages ORDER BY created_at DESC LIMIT 5;\"

Там сохраняются

user_id
question
answer
created_at

⸻

Бот

Можно запустить Telegram бота.

python -m bot.telegram_bot

Бот принимает текст и голосовые сообщения и отправляет их в API.

⸻

CLI клиент

Также есть простой клиент для терминала.

python -m client.cli_client

Можно задавать вопросы прямо из консоли.

⸻

Структура проекта

ww2
app
bot
client
tests
data
Dockerfile
docker-compose.yml
requirements.txt
.env.example
README.md

В app находится основной код сервера.
В bot Telegram бот.
В client простой CLI клиент.
В tests скрипт проверки.
В data лежит база знаний и FAISS индекс.