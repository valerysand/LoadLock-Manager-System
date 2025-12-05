#!/usr/bin/env python3
"""
Система управления LoadLock с отслеживанием статуса
"""

from flask import Flask, render_template, request, jsonify, send_file
import base64
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from datetime import datetime
import sqlite3
import io
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Используем динамические пути для совместимости с облаком
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

# Создаем директории если их нет
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
Path(OUTPUT_DIR).mkdir(exist_ok=True)

# Статусы для LoadLock
LOADLOCK_STATUSES = {
    'inserted': {'label': 'הוכנס', 'color': '#0dcaf0', 'emoji': '📥'},
    'working': {'label': 'בעבודה', 'color': '#0d6efd', 'emoji': '⚙️'},
    'missing': {'label': 'חוסרים', 'color': '#fd7e14', 'emoji': '⚠️'},
    'qc': {'label': 'QC', 'color': '#6f42c1', 'emoji': '�'},
    'packaging': {'label': 'באריזה', 'color': '#0dcaf0', 'emoji': '📦'},
    'ready': {'label': 'מוכן', 'color': '#198754', 'emoji': '✅'},
}

class LoadLockManager:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        self.base_url = "https://api.openai.com/v1"
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True)
        self.db_path = self.output_dir / "loadlock.db"
        self.init_database()
    
    def init_database(self):
        """Инициализирует базу данных LoadLock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица для LoadLock камер
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loadlocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hora_number TEXT NOT NULL UNIQUE,
                name TEXT,
                status TEXT DEFAULT 'inserted',
                current_sample TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP,
                image_path TEXT,
                notes TEXT
            )
        ''')
        
        # Таблица для истории изменений статуса
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loadlock_id INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (loadlock_id) REFERENCES loadlocks(id)
            )
        ''')
        
        # Таблица для образцов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loadlock_id INTEGER NOT NULL,
                sample_name TEXT NOT NULL,
                material TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (loadlock_id) REFERENCES loadlocks(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def image_to_base64(self, image_path):
        """Преобразует изображение в base64"""
        with open(image_path, 'rb') as image_file:
            return base64.standard_b64encode(image_file.read()).decode('utf-8')
    
    def extract_hora_number(self, image_path):
        """Извлекает номер הוראה из изображения"""
        if not os.path.exists(image_path):
            return None
        
        prompt = """You are a specialist in recognizing machine instruction numbers (מספר הוראה) in vacuum chamber systems.

Analyze this image carefully and extract the "מספר הוראה" (instruction number).
Return ONLY a JSON object with this exact structure:
{
    "hora_number": "THE NUMBER YOU FOUND",
    "confidence": "high/medium/low",
    "location": "where on the image",
    "additional_info": "any other visible text"
}"""
        
        image_base64 = self.image_to_base64(image_path)
        ext = Path(image_path).suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }],
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            return None
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return None
    
    def parse_hora_response(self, response_text):
        """Парсит ответ ИИ"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return None
        except json.JSONDecodeError:
            return None
    
    def add_loadlock(self, hora_number, name="", image_path="", notes=""):
        """Добавляет новый LoadLock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO loadlocks (hora_number, name, image_path, notes, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (hora_number, name or hora_number, image_path, notes, datetime.now()))
            
            conn.commit()
            loadlock_id = cursor.lastrowid
            return True, loadlock_id
        
        except sqlite3.IntegrityError:
            return False, None
        
        finally:
            conn.close()
    
    def get_all_loadlocks(self):
        """Получает все LoadLock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, hora_number, name, status, current_sample, 
                   date_added, last_updated, notes 
            FROM loadlocks 
            ORDER BY name
        ''')
        loadlocks = cursor.fetchall()
        conn.close()
        
        return loadlocks
    
    def update_status(self, loadlock_id, new_status, notes=""):
        """Обновляет статус LoadLock"""
        if new_status not in LOADLOCK_STATUSES:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Получаем старый статус
            cursor.execute('SELECT status FROM loadlocks WHERE id = ?', (loadlock_id,))
            result = cursor.fetchone()
            if not result:
                return False
            
            old_status = result[0]
            
            # Обновляем статус
            cursor.execute('''
                UPDATE loadlocks 
                SET status = ?, last_updated = ?
                WHERE id = ?
            ''', (new_status, datetime.now(), loadlock_id))
            
            # Добавляем запись в историю
            cursor.execute('''
                INSERT INTO status_history (loadlock_id, old_status, new_status, notes)
                VALUES (?, ?, ?, ?)
            ''', (loadlock_id, old_status, new_status, notes))
            
            conn.commit()
            return True
        
        finally:
            conn.close()
    
    def add_sample(self, loadlock_id, sample_name, material="", notes=""):
        """Добавляет образец в LoadLock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO samples (loadlock_id, sample_name, material, notes)
                VALUES (?, ?, ?, ?)
            ''', (loadlock_id, sample_name, material, notes))
            
            # Обновляем текущий образец в LoadLock
            cursor.execute('''
                UPDATE loadlocks 
                SET current_sample = ?
                WHERE id = ?
            ''', (sample_name, loadlock_id))
            
            conn.commit()
            return True
        
        finally:
            conn.close()
    
    def get_loadlock_history(self, loadlock_id):
        """Получает историю изменений статуса"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT old_status, new_status, timestamp, notes
            FROM status_history
            WHERE loadlock_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
        ''', (loadlock_id,))
        
        history = cursor.fetchall()
        conn.close()
        
        return history
    
    def get_loadlock_samples(self, loadlock_id):
        """Получает все образцы в LoadLock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, sample_name, material, date_added, notes
            FROM samples
            WHERE loadlock_id = ?
            ORDER BY date_added DESC
        ''', (loadlock_id,))
        
        samples = cursor.fetchall()
        conn.close()
        
        return samples
    
    def delete_loadlock(self, loadlock_id):
        """Удаляет LoadLock"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM loadlocks WHERE id = ?', (loadlock_id,))
        cursor.execute('DELETE FROM status_history WHERE loadlock_id = ?', (loadlock_id,))
        cursor.execute('DELETE FROM samples WHERE loadlock_id = ?', (loadlock_id,))
        
        conn.commit()
        conn.close()

# Инициализируем менеджер
try:
    manager = LoadLockManager()
except ValueError as e:
    print(f"Error: {e}")

def allowed_file(filename):
    """Проверяет расширение файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Главная страница"""
    return render_template('loadlock.html', statuses=LOADLOCK_STATUSES)

@app.route('/api/loadlocks', methods=['GET'])
def get_loadlocks():
    """Получает все LoadLock"""
    loadlocks = manager.get_all_loadlocks()
    
    result = []
    for ll in loadlocks:
        result.append({
            'id': ll[0],
            'hora_number': ll[1],
            'name': ll[2],
            'status': ll[3],
            'current_sample': ll[4],
            'date_added': ll[5],
            'last_updated': ll[6],
            'notes': ll[7],
            'status_info': LOADLOCK_STATUSES.get(ll[3], {})
        })
    
    return jsonify(result), 200

@app.route('/api/loadlock/<int:ll_id>/status', methods=['POST'])
def update_status(ll_id):
    """Обновляет статус LoadLock"""
    data = request.json
    new_status = data.get('status')
    notes = data.get('notes', '')
    
    if manager.update_status(ll_id, new_status, notes):
        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'Failed to update status'}), 400

@app.route('/api/loadlock/<int:ll_id>/history', methods=['GET'])
def get_history(ll_id):
    """Получает историю изменений"""
    history = manager.get_loadlock_history(ll_id)
    
    result = []
    for h in history:
        result.append({
            'old_status': h[0],
            'new_status': h[1],
            'timestamp': h[2],
            'notes': h[3],
            'old_status_info': LOADLOCK_STATUSES.get(h[0], {}),
            'new_status_info': LOADLOCK_STATUSES.get(h[1], {})
        })
    
    return jsonify(result), 200

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Загружает и обрабатывает изображение"""
    if 'file' not in request.files:
        return jsonify({'error': 'File not found'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'File not selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file format'}), 400
    
    # Сохраняем файл
    filename = secure_filename(f"hora_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Обрабатываем изображение
    response = manager.extract_hora_number(filepath)
    
    if not response:
        return jsonify({'error': 'Error processing image'}), 500
    
    # Парсим ответ
    data = manager.parse_hora_response(response)
    
    if not data:
        return jsonify({'error': 'Error parsing response'}), 500
    
    if data.get('hora_number') == 'NOT_FOUND':
        return jsonify({
            'success': False,
            'message': 'Could not recognize instruction number',
            'additional_info': data.get('additional_info', '')
        }), 200
    
    hora_number = data.get('hora_number', 'UNKNOWN')
    confidence = data.get('confidence', 'unknown')
    
    # Добавляем в БД
    added, loadlock_id = manager.add_loadlock(
        hora_number, 
        name=f"LoadLock {hora_number}",
        image_path=filepath,
        notes=f"Confidence: {confidence}"
    )
    
    return jsonify({
        'success': True,
        'hora_number': hora_number,
        'confidence': confidence,
        'loadlock_id': loadlock_id,
        'already_exists': not added
    }), 200

@app.route('/api/loadlock/<int:ll_id>/sample', methods=['POST'])
def add_sample(ll_id):
    """Добавляет образец"""
    data = request.json
    sample_name = data.get('sample_name')
    material = data.get('material', '')
    notes = data.get('notes', '')
    
    if manager.add_sample(ll_id, sample_name, material, notes):
        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'Failed to add sample'}), 400

@app.route('/api/loadlock/<int:ll_id>/samples', methods=['GET'])
def get_samples(ll_id):
    """Получает образцы"""
    samples = manager.get_loadlock_samples(ll_id)
    
    result = []
    for s in samples:
        result.append({
            'id': s[0],
            'sample_name': s[1],
            'material': s[2],
            'date_added': s[3],
            'notes': s[4]
        })
    
    return jsonify(result), 200

@app.route('/api/loadlock/<int:ll_id>', methods=['DELETE'])
def delete_loadlock(ll_id):
    """Удаляет LoadLock"""
    try:
        manager.delete_loadlock(ll_id)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
