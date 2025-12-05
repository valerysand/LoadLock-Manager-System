# 🚀 Деплой LoadLock Manager на Render

## Вариант 1: Render.com (Рекомендуется - БЕСПЛАТНО!)

### Шаг 1: Подготовка Git репозитория

```bash
cd /Users/valerysandler/script

# Инициализируем Git
git init
git add .
git commit -m "Initial commit"

# Создаем репозиторий на GitHub (опционально)
# Если хотите использовать GitHub для деплоя
```

### Шаг 2: Создание аккаунта на Render

1. Откройте https://render.com
2. Нажмите "Sign up" и зарегистрируйтесь
3. Подтвердите email

### Шаг 3: Создание Web Service

1. На Render нажмите **New** → **Web Service**
2. Выберите **Public Git Repository**
3. Вставьте URL вашего репозитория (если используете GitHub)
   - Или используйте встроенную git функцию Render

### Шаг 4: Конфигурация

Заполните поля:
- **Name**: `loadlock-manager`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`
- **Region**: выберите ближайший регион

### Шаг 5: Окружение переменные

В секции **Environment** добавьте:

```
OPENAI_API_KEY=sk-proj-your-key-here
FLASK_ENV=production
```

### Шаг 6: Deploy!

Нажмите **Create Web Service**

⏳ Деплой займет 2-3 минуты. После завершения получите URL типа:
```
https://loadlock-manager.onrender.com
```

---

## Вариант 2: Heroku

### Требования:
- Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
- Аккаунт на Heroku

### Шаги:

```bash
# 1. Логин в Heroku
heroku login

# 2. Создайте приложение
heroku create loadlock-manager

# 3. Установите переменные окружения
heroku config:set OPENAI_API_KEY=sk-proj-your-key-here

# 4. Задеплойте через Git
git push heroku main

# 5. Посмотрите логи
heroku logs --tail
```

**URL приложения**:
```
https://loadlock-manager.herokuapp.com
```

---

## Вариант 3: Railway.app

### Быстрый деплой:

1. Откройте https://railway.app
2. Нажмите **New Project** → **Deploy from GitHub**
3. Выберите ваш репозиторий
4. Добавьте переменные окружения:
   - `OPENAI_API_KEY`
5. Railway автоматически задеплоит

---

## Вариант 4: Docker на AWS/Azure/GCP

### Используя Docker:

```bash
# 1. Соберите образ
docker build -t loadlock-manager .

# 2. Запустите локально для теста
docker run -p 5001:5001 \
  -e OPENAI_API_KEY=sk-proj-your-key \
  loadlock-manager

# 3. Загрузите на Docker Hub
docker tag loadlock-manager YOUR_USERNAME/loadlock-manager
docker push YOUR_USERNAME/loadlock-manager

# 4. На облачном сервере
docker pull YOUR_USERNAME/loadlock-manager
docker run -p 5001:5001 \
  -e OPENAI_API_KEY=sk-proj-your-key \
  YOUR_USERNAME/loadlock-manager
```

---

## ✅ Проверка после деплоя

```bash
# Проверьте статус
curl https://your-app-url.com/api/loadlocks

# Должен вернуть JSON (может быть пусто, если нет данных)
[]
```

---

## 🔒 Безопасность перед продакшеном

✅ **Отключен debug режим** - файл уже обновлен  
✅ **Используется gunicorn** - вместо встроенного сервера Flask  
✅ **Переменные окружения** - API ключ не в коде  
✅ **Port управляется окружением** - для cloud compatibility  

### Дополнительно рекомендуется:

1. **Добавьте CORS для безопасности**:
```python
from flask_cors import CORS
CORS(app, resources={r"/api/*": {"origins": ["https://your-domain.com"]}})
```

2. **Добавьте Rate limiting**:
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/upload', methods=['POST'])
@limiter.limit("5 per minute")
def upload_file():
    # ...
```

3. **Используйте HTTPS** - все облачные платформы предоставляют SSL

4. **Регулярно делайте бэкапы БД**:
```bash
# Скопируйте loadlock.db регулярно
```

---

## 📊 Мониторинг приложения

### Render:
- Dashboard показывает логи в реальном времени
- Автоматический перезапуск при ошибках
- Метрики CPU/Memory

### Heroku:
```bash
heroku logs --tail
```

### Railway:
- Встроенный dashboard с метриками
- Логи в реальном времени

---

## 🚨 Если что-то пошло не так

### Проверьте логи:
```bash
# Render - через веб-интерфейс Dashboard
# Heroku
heroku logs --tail

# Railway - через веб-интерфейс
```

### Частые проблемы:

**1. "ModuleNotFoundError: No module named 'cv2'"**
- OpenCV требует компиляции на сервере
- Решение: используйте `opencv-python-headless`

**2. "OPENAI_API_KEY not set"**
- Проверьте переменные окружения в Dashboard
- Убедитесь, что ключ скопирован правильно

**3. "Port already in use"**
- На облаке PORT выставляется автоматически
- Код уже это обрабатывает

**4. "Database locked"**
- SQLite может иметь проблемы с конкурентностью
- Решение: Мигрируйте на PostgreSQL для продакшена

---

## 💾 Миграция на PostgreSQL (опционально, для масштабирования)

```bash
# Установите postgresql driver
pip install psycopg2-binary

# Обновите connection string
DATABASE_URL=postgresql://user:password@host/dbname
```

```python
import os
from urllib.parse import urlparse

if 'DATABASE_URL' in os.environ:
    db_url = os.environ.get('DATABASE_URL')
    # используйте db_url вместо SQLite
else:
    db_path = "loadlock.db"  # локально
```

---

## 🎉 Готово!

Приложение теперь доступно в интернете!

**Поделитесь ссылкой**: https://your-app-url.com

**Используйте с мобильного**: откройте приложение на телефоне в браузере по адресу выше

Enjoy! 🚀
