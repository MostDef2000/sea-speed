# Sea Speed

Sea Speed — система видеонаблюдения и анализа дорожного потока. Проект получает HLS-видеопоток с камеры, обнаруживает транспорт с помощью YOLO, формирует события со снимками, показывает текущее состояние в операторском интерфейсе и подготавливает данные для оценки скорости.

## Назначение проекта

Основные задачи Sea Speed:

- показывать оператору живой HLS-поток;
- определять движение в кадре;
- запускать AI-детекцию только при наличии движения;
- обнаруживать транспортные средства;
- ограничивать обработку заданной ROI-зоной;
- строить актуальный overlay с результатами детекции;
- формировать события со снимком, классом и уверенностью;
- оценивать скорость в пикселях в секунду;
- пересчитывать скорость в км/ч после калибровки;
- хранить состояние, события и настройки на VPS;
- управлять разработкой через GitHub.

## Текущий статус

Ветка `agent/migrate-baseline-v0` содержит текущий рабочий baseline проекта без изменения логики.

В baseline перенесены:

- FastAPI backend с VPS;
- операторский frontend с VPS;
- AI worker с Windows-ноутбука;
- Windows-скрипты запуска и остановки worker;
- рабочие заметки и документация;
- project skills и правила управления изменениями.

На текущем этапе:

- baseline ещё не объединён с `main`;
- автоматический деплой GitHub → VPS ещё не настроен;
- автоматическое обновление worker на ноутбуке ещё не настроено;
- текущая рабочая система на VPS и ноутбуке продолжает работать отдельно от репозитория.

## Архитектура

```text
Камера / HLS
      |
      v
Windows-ноутбук
AI worker: FFmpeg + motion detection + YOLO + tracking + speed
      |
      | HTTPS / JSON / JPEG / Bearer token
      v
VPS
FastAPI backend + JSON storage + media storage
      |
      v
Операторский web-интерфейс
https://mostdef.ru/sea-speed/
```

## Разделение ответственности

### VPS

На VPS должны работать все постоянные сервисы проекта:

- Nginx;
- публикация HLS;
- FastAPI backend;
- операторский frontend;
- хранение состояния worker;
- хранение событий;
- хранение event snapshots;
- хранение latest overlay;
- настройки ROI;
- настройки калибровки скорости;
- API health check;
- deploy и rollback инфраструктура.

Текущие runtime-пути:

```text
/opt/sea-speed-api/app/main.py
/opt/sea-speed-api/data/
/opt/sea-speed-api/media/
/var/www/mostdef.ru/sea-speed/index.html
```

### Windows-ноутбук

Ноутбук используется только как вычислительный узел для AI worker:

- читает HLS через FFmpeg;
- декодирует кадры;
- выполняет motion detection;
- запускает YOLO;
- фильтрует детекции;
- применяет ROI;
- ведёт tracking;
- рассчитывает движение и скорость;
- создаёт overlay и event snapshots;
- отправляет состояние и события на VPS.

Текущий runtime-путь:

```text
D:\sea-speed\
```

Ноутбук не должен быть главным хранилищем исходного кода. Источником истины является GitHub.

## Основной поток данных

1. Камера публикует HLS-поток.
2. Worker запускает FFmpeg и получает кадры заданного размера и FPS.
3. Motion detector сравнивает последовательные кадры.
4. При движении активируется YOLO.
5. YOLO ищет транспортные классы.
6. Детекции фильтруются по движению и ROI.
7. Worker обновляет tracking и оценивает скорость.
8. Worker формирует latest overlay.
9. Worker отправляет state и overlay на VPS.
10. При выполнении условий worker создаёт событие и snapshot.
11. API сохраняет состояние, настройки и события.
12. Frontend периодически запрашивает API и показывает оператору актуальные данные.

## Поддерживаемые классы транспорта

Текущий worker обрабатывает классы:

```text
car
truck
bus
motorcycle
bicycle
```

## AI worker

Основной файл:

```text
worker/hls_motion_yolo_worker_events.py
```

Worker использует:

- `ffmpeg` — чтение и декодирование HLS;
- `opencv-python` — обработка изображения и motion detection;
- `numpy` — работа с массивами и геометрией;
- `ultralytics` — YOLO;
- `requests` — обмен с VPS API.

### Motion gate

YOLO не обязан постоянно работать на каждом кадре. Сначала определяется движение. После обнаружения движения AI остаётся активным ограниченное время, чтобы обработать проезжающий объект целиком.

Основные параметры:

```text
MOTION_THRESHOLD
MOTION_MIN_AREA
MOTION_ACTIVE_SECONDS
```

### Детекция

Основные параметры YOLO:

```text
MODEL_NAME
YOLO_CONFIDENCE
YOLO_IMAGE_SIZE
```

Текущий baseline использует локальную модель:

```text
yolo11s.pt
```

Файл модели хранится только на ноутбуке и не добавляется в GitHub.

### ROI

ROI задаётся в операторском интерфейсе многоугольником. Worker периодически получает конфигурацию с VPS и пропускает только детекции, центр которых находится внутри рабочей зоны.

Настройка хранится на VPS:

```text
cam1_roi.json
```

### Tracking и скорость

Для оценки движения worker использует нижнюю центральную точку bounding box:

```text
x = (x1 + x2) / 2
y = y2
```

Это лучше соответствует точке контакта транспорта с дорожным покрытием, чем геометрический центр объекта.

Worker поддерживает два вида оценки скорости:

1. Движение объекта в `px/s`.
2. Пересчёт в `km/h` через коэффициент `kmh_per_px_s`.

Также в проекте есть две калибровочные линии и известное расстояние между ними. Эти данные используются как основа для измерения скорости по времени прохождения участка.

Настройки хранятся на VPS:

```text
cam1_speed_config.json
cam1_speed_lines.json
```

Точность `km/h` зависит от корректной геометрической калибровки камеры.

### События

Событие может содержать:

- уникальный `event_id`;
- время создания;
- класс объекта;
- confidence;
- bounding box;
- скорость в `px/s`;
- скорость в `km/h`, если доступна;
- snapshot URL;
- дополнительные диагностические поля.

Worker сохраняет локальные рабочие файлы в:

```text
output/latest/
output/events/
```

Папка `output/` является runtime-данными и не хранится в GitHub.

## Windows-скрипты worker

```text
worker/start_worker.cmd
worker/stop_worker.cmd
worker/restart_worker.cmd
worker/status_worker.cmd
worker/run_event_worker_forever.cmd
```

Назначение:

- `start_worker.cmd` — запускает worker в новом окне;
- `stop_worker.cmd` — создаёт stop flag и завершает worker;
- `restart_worker.cmd` — выполняет остановку и повторный запуск;
- `status_worker.cmd` — показывает связанные процессы;
- `run_event_worker_forever.cmd` — запускает worker в цикле и перезапускает его после аварийного завершения или обрыва FFmpeg.

Stop flag:

```text
D:\sea-speed\stop_worker.flag
```

## Backend API

Основной файл:

```text
api/app/main.py
```

Технология:

```text
FastAPI
```

### API endpoints

```text
GET  /api/cam1/state
POST /api/cam1/state

GET  /api/cam1/events
POST /api/cam1/events

GET  /api/cam1/roi
POST /api/cam1/roi

GET  /api/cam1/speed-config
POST /api/cam1/speed-config

GET  /api/cam1/speed-lines
POST /api/cam1/speed-lines

GET  /api/health
```

Во внешнем интерфейсе Nginx публикует API под префиксом:

```text
/sea-speed/api/
```

### State

State содержит текущее состояние worker:

- `worker_online`;
- `updated_at`;
- `motion_now`;
- `motion_area`;
- `ai_active`;
- `detections`;
- `tracks`;
- `last_overlay_url`;
- диагностическое сообщение.

Worker считается online, если последнее состояние было получено не более 30 секунд назад.

### Events

События хранятся в JSON-файле. Новые события добавляются в начало списка. Текущий baseline сохраняет до 500 последних событий.

### Media

API публикует media через FastAPI StaticFiles:

```text
/sea-speed/media/overlays/cam1_latest_overlay.jpg
/sea-speed/media/events/<event_id>.jpg
```

### Текущие data-файлы

```text
cam1_state.json
events.json
cam1_roi.json
cam1_speed_config.json
cam1_speed_lines.json
```

Текущий baseline использует JSON storage. База данных пока не используется.

## Frontend

Основной файл:

```text
frontend/sea-speed/index.html
```

Текущий интерфейс показывает:

- live HLS video;
- подключение и отключение потока;
- worker online/offline;
- motion status;
- AI status;
- количество detections;
- количество tracks;
- latest overlay;
- последние события;
- snapshot каждого события;
- скорость в `px/s`;
- скорость в `km/h`;
- State JSON;
- debug log;
- ROI editor;
- speed factor editor;
- speed lines editor;
- расстояние между калибровочными линиями.

Для воспроизведения HLS в браузере используется `hls.js`.

## Конфигурация worker

Worker получает конфигурацию через переменные окружения.

### Источник видео

```text
HLS_URL
HLS_BASIC_AUTH_BASE64
FRAME_WIDTH
FRAME_HEIGHT
SAMPLE_FPS
CAMERA_ID
```

`HLS_BASIC_AUTH_BASE64` содержит Base64-представление `login:password`. Это не шифрование, поэтому значение является секретом.

### AI

```text
MODEL_NAME
YOLO_CONFIDENCE
YOLO_IMAGE_SIZE
```

### Motion

```text
MOTION_THRESHOLD
MOTION_MIN_AREA
MOTION_ACTIVE_SECONDS
```

### VPS API

```text
SEA_SPEED_API_URL
SEA_SPEED_EVENT_API_URL
SEA_SPEED_ROI_URL
SEA_SPEED_SPEED_CONFIG_URL
SEA_SPEED_SPEED_LINES_URL
SEA_SPEED_API_TOKEN
```

### Интервалы и события

```text
STATE_POST_INTERVAL_SEC
EVENT_COOLDOWN_SEC
ROI_REFRESH_SEC
SPEED_CONFIG_REFRESH_SEC
SPEED_LINES_REFRESH_SEC
ALLOW_EVENT_WITHOUT_LINE_SPEED
MIN_EVENT_SPEED_PX_PER_SEC
```

### Tracking и speed validation

```text
DETECTION_TRACK_MAX_GAP_SEC
DETECTION_SPEED_MIN_DT_SEC
DETECTION_SPEED_MAX_DT_SEC
DETECTION_SPEED_MIN_KMH
DETECTION_SPEED_MAX_KMH
DETECTION_SPEED_SMOOTH_SAMPLES
LINE_SPEED_MIN_TRAVEL_SEC
LINE_SPEED_MAX_TRAVEL_SEC
LINE_SPEED_MIN_INSTANT_KMH
LINE_SPEED_MAX_INSTANT_KMH
```

## Секреты

В GitHub запрещено хранить:

```text
.env
SEA_SPEED_API_TOKEN
HLS_BASIC_AUTH_BASE64
логины и пароли камеры
SSH-ключи
VPS credentials
runtime logs
event snapshots
overlay images
video files
локальные модели YOLO
```

Секреты должны находиться только:

- в переменных окружения VPS;
- в GitHub Actions Secrets;
- в локальной защищённой конфигурации Windows worker.

## Структура репозитория

```text
sea-speed/
├── README.md
├── .gitignore
├── api/
│   └── app/
│       └── main.py
├── frontend/
│   └── sea-speed/
│       └── index.html
├── worker/
│   ├── hls_motion_yolo_worker_events.py
│   ├── README.txt
│   ├── start_worker.cmd
│   ├── stop_worker.cmd
│   ├── restart_worker.cmd
│   ├── status_worker.cmd
│   └── run_event_worker_forever.cmd
├── docs/
│   ├── migration-plan.md
│   ├── описание логики скринов.txt
│   ├── поднять воркера.txt
│   └── принцип работы.txt
└── skills/
    ├── CHANGE_POLICY.md
    ├── sea-speed-worker.md
    ├── sea-speed-api.md
    ├── sea-speed-frontend.md
    ├── sea-speed-deploy.md
    ├── sea-speed-diagnostics.md
    ├── sea-speed-governance.md
    └── sea-speed-review.md
```

## Source of truth

GitHub является единственным источником истины для:

- исходного кода;
- структуры проекта;
- истории изменений;
- документации;
- release-кандидатов;
- deploy-версий.

VPS является runtime-средой, а не местом ручного редактирования исходного кода.

Ноутбук является вычислительным worker-узлом, а не главным хранилищем проекта.

## Целевая схема разработки

```text
Задача в ChatGPT
      |
      v
Обсуждение и фиксация scope
      |
      v
Изменение в отдельной GitHub-ветке
      |
      v
Review и проверка
      |
      v
Merge в main после подтверждения
      |
      v
GitHub Actions
      |
      v
Автоматический deploy на VPS
      |
      v
Health check и при необходимости rollback
```

ChatGPT используется как интерфейс управления разработкой:

- восстанавливает актуальное состояние репозитория;
- готовит implementation brief;
- вносит утверждённые изменения;
- создаёт feature branch;
- проверяет scope;
- готовит review;
- сопровождает release lifecycle.

## Целевая схема деплоя VPS

После настройки deploy-инфраструктуры выпуск должен выполняться так:

1. Изменения проходят review.
2. Изменения объединяются с `main`.
3. GitHub Actions подключается к VPS по SSH.
4. API и frontend обновляются из конкретного commit SHA.
5. API service перезапускается.
6. Выполняется запрос к `/api/health`.
7. При неуспешной проверке выполняется rollback.

Автоматический deploy не должен выполняться из feature-веток.

## Обновление Windows worker

Целевая модель:

1. Worker-код хранится в GitHub.
2. После release ноутбук получает новую версию папки `worker/`.
3. Локальные секреты, `.venv`, модель и runtime output сохраняются.
4. Worker перезапускается.

Первый этап может использовать ручное обновление. Позже обновление можно автоматизировать через PowerShell и Windows Task Scheduler.

## Проверка работоспособности

Минимальная последовательность диагностики:

1. HLS открывается по адресу камеры.
2. FFmpeg на ноутбуке получает кадры.
3. Worker process запущен.
4. `GET /api/cam1/state` обновляется.
5. `worker_online = true`.
6. Latest overlay обновляется.
7. Events API возвращает события.
8. Snapshot URL открывается.
9. Frontend отображает state и события.
10. `GET /api/health` возвращает `ok: true`.

## Текущие ограничения baseline

- архитектура рассчитана на одну камеру `cam1`;
- часть путей Windows привязана к `D:\sea-speed`;
- worker-зависимости пока не зафиксированы отдельным `requirements.txt`;
- deploy-конфигурация ещё не перенесена в репозиторий;
- GitHub Actions ещё не настроен;
- Windows worker ещё не обновляется автоматически;
- используется JSON storage вместо базы данных;
- точность km/h зависит от калибровки;
- tracking и speed estimation требуют дальнейшей стабилизации;
- UI и worker содержат накопленные MVP-патчи, которые позже нужно упорядочивать отдельными задачами без изменения baseline.

## Ближайшие этапы

1. Завершить review baseline v0.
2. Создать pull request в `main`.
3. Зафиксировать Python dependencies для API и worker.
4. Добавить systemd unit и Nginx configuration templates.
5. Добавить GitHub Actions deploy на VPS.
6. Проверить health check и rollback.
7. Настроить безопасное обновление Windows worker.
8. После стабилизации начать функциональную разработку через отдельные ветки.

## Главный принцип

Любое изменение должно быть воспроизводимым из GitHub. На VPS и ноутбуке не должно оставаться уникального исходного кода, которого нет в репозитории.
