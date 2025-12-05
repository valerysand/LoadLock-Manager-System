#!/usr/bin/env python3
"""
Скрипт для распознавания номера הוראה (номер инструкции) машины в клинруме
и добавления его в базу данных
"""

import cv2
import base64
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from datetime import datetime
import sqlite3

load_dotenv()

class MachineNumberExtractor:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("Переменная OPENAI_API_KEY не установлена")
        
        self.base_url = "https://api.openai.com/v1"
        self.output_dir = Path("/Users/valerysandler/script/output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Инициализируем базу данных
        self.db_path = self.output_dir / "machines.db"
        self.init_database()
    
    def init_database(self):
        """Создает базу данных для хранения номеров машин"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hora_number TEXT NOT NULL UNIQUE,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                status TEXT DEFAULT 'registered',
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✓ База данных инициализирована: {self.db_path}")
    
    def capture_document(self, save_path=None):
        """Захватывает фото номера הוראה с веб-камеры"""
        print("Открываю веб-камеру...")
        
        for camera_index in [0, 1, 2]:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                print(f"✓ Камера {camera_index} открыта")
                break
        else:
            print("❌ Ошибка: невозможно открыть веб-камеру")
            return None
        
        print("Нажмите SPACE для фото, q для выхода")
        
        captured_image = None
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            cv2.imshow('Фото номера הוראה (SPACE - фото, q - выход)', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                captured_image = frame
                print("✓ Фото сделано!")
                break
            elif key == ord('q'):
                print("Отмена")
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if captured_image is not None and save_path:
            cv2.imwrite(save_path, captured_image)
            print(f"✓ Сохранено: {save_path}")
        
        return captured_image
    
    def load_image_from_file(self, file_path):
        """Загружает изображение из файла"""
        if not os.path.exists(file_path):
            print(f"❌ Файл не найден: {file_path}")
            return None
        print(f"✓ Изображение загружено: {file_path}")
        return file_path
    
    def image_to_base64(self, image_path):
        """Преобразует изображение в base64"""
        with open(image_path, 'rb') as image_file:
            return base64.standard_b64encode(image_file.read()).decode('utf-8')
    
    def extract_hora_number(self, image_path):
        """Извлекает номер הוראה из изображения"""
        if not os.path.exists(image_path):
            print(f"❌ Файл не найден: {image_path}")
            return None
        
        # Специальный промпт для распознавания номера הוראה
        prompt = """You are a specialist in recognizing machine instruction numbers (מספר הוראה) in industrial workshops.

Analyze this image carefully and:
1. Find and extract the "מספר הוראה" (instruction number) - this is usually a number on a label/tag on the machine
2. Return ONLY a JSON object with this exact structure:
{
    "hora_number": "THE NUMBER YOU FOUND (e.g., 12345 or H-12345)",
    "confidence": "high/medium/low",
    "location": "where on the image the number is located",
    "additional_info": "any other visible text or identifiers"
}

If you cannot find a clear instruction number, still return JSON with "hora_number": "NOT_FOUND" and explain why in "additional_info"."""
        
        image_base64 = self.image_to_base64(image_path)
        ext = Path(image_path).suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        print("🔍 Анализирую изображение...")
        
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
                content = result['choices'][0]['message']['content']
                return content
            else:
                print("❌ Неожиданный ответ от API")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка API: {e}")
            return None
    
    def parse_hora_response(self, response_text):
        """Парсит ответ ИИ и извлекает номер הוראה"""
        try:
            # Пытаемся найти JSON в ответе
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data
            else:
                return None
        except json.JSONDecodeError:
            print("❌ Не удалось распарсить ответ ИИ")
            return None
    
    def add_to_database(self, hora_number, image_path, notes=""):
        """Добавляет номер הוראה в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO machines (hora_number, image_path, notes)
                VALUES (?, ?, ?)
            ''', (hora_number, image_path, notes))
            
            conn.commit()
            print(f"✓ Номер {hora_number} добавлен в базу данных")
            return True
        
        except sqlite3.IntegrityError:
            print(f"⚠️  Номер {hora_number} уже существует в базе данных")
            return False
        
        finally:
            conn.close()
    
    def get_all_machines(self):
        """Получает все машины из базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM machines ORDER BY date_added DESC')
        machines = cursor.fetchall()
        conn.close()
        
        return machines
    
    def export_to_csv(self):
        """Экспортирует базу данных в CSV"""
        machines = self.get_all_machines()
        csv_path = self.output_dir / f"machines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("ID,Номер הוראה,Дата добавления,Путь изображения,Статус,Примечания\n")
            for machine in machines:
                f.write(f"{machine[0]},{machine[1]},{machine[2]},{machine[3]},{machine[4]},{machine[5]}\n")
        
        print(f"✓ Экспортировано в: {csv_path}")
        return csv_path


def main():
    """Основная функция"""
    print("=" * 60)
    print("📱 Система распознавания номеров הוראה для клинрума")
    print("=" * 60)
    
    try:
        extractor = MachineNumberExtractor()
    except ValueError as e:
        print(f"❌ Ошибка: {e}")
        return
    
    while True:
        print("\n" + "=" * 60)
        print("Меню:")
        print("1. 📸 Сфотографировать номер הוראה (камера)")
        print("2. 📁 Загрузить фото из файла")
        print("3. 📊 Показать все машины в базе данных")
        print("4. 💾 Экспортировать в CSV")
        print("5. ❌ Выход")
        print("=" * 60)
        
        choice = input("Выберите опцию (1-5): ").strip()
        
        if choice == "1":
            # Фотографируем
            image_path = extractor.output_dir / f"hora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image = extractor.capture_document(str(image_path))
            
            if image is not None:
                process_image(extractor, str(image_path))
        
        elif choice == "2":
            # Загружаем файл
            file_path = input("Введите путь к файлу: ").strip()
            image_path = extractor.load_image_from_file(file_path)
            
            if image_path:
                process_image(extractor, image_path)
        
        elif choice == "3":
            # Показываем все машины
            show_machines(extractor)
        
        elif choice == "4":
            # Экспортируем в CSV
            extractor.export_to_csv()
        
        elif choice == "5":
            print("\n👋 До свидания!")
            break
        
        else:
            print("❌ Неверная опция")


def process_image(extractor, image_path):
    """Обрабатывает изображение и добавляет номер в БД"""
    response = extractor.extract_hora_number(image_path)
    
    if response:
        print("\n" + "=" * 60)
        print("Результат анализа:")
        print("=" * 60)
        print(response)
        
        # Парсим ответ
        data = extractor.parse_hora_response(response)
        
        if data and data.get('hora_number') != 'NOT_FOUND':
            hora_number = data.get('hora_number', 'UNKNOWN')
            confidence = data.get('confidence', 'unknown')
            additional_info = data.get('additional_info', '')
            
            print(f"\n✓ Найден номер הוראה: {hora_number}")
            print(f"  Уверенность: {confidence}")
            print(f"  Информация: {additional_info}")
            
            # Добавляем в базу данных
            notes = f"Confidence: {confidence}, Info: {additional_info}"
            extractor.add_to_database(hora_number, image_path, notes)
        else:
            print("\n❌ Не удалось распознать номер הוראה")
            print("   Попробуйте еще раз с более четким изображением")
    else:
        print("❌ Ошибка при обработке изображения")


def show_machines(extractor):
    """Показывает все машины в базе данных"""
    machines = extractor.get_all_machines()
    
    print("\n" + "=" * 60)
    print("📊 Все машины в базе данных:")
    print("=" * 60)
    
    if not machines:
        print("База данных пуста")
    else:
        for machine in machines:
            print(f"ID: {machine[0]}")
            print(f"  Номер הוראה: {machine[1]}")
            print(f"  Дата: {machine[2]}")
            print(f"  Статус: {machine[4]}")
            if machine[5]:
                print(f"  Примечания: {machine[5]}")
            print()


if __name__ == "__main__":
    main()
