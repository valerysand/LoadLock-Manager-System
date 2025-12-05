#!/usr/bin/env python3
"""
Скрипт для фотографирования документа и извлечения данных с помощью ИИ
"""

import cv2
import base64
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class DocumentExtractor:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("Переменная OPENAI_API_KEY не установлена")
        
        self.base_url = "https://api.openai.com/v1"
        self.output_dir = Path("/Users/valerysandler/script/output")
        self.output_dir.mkdir(exist_ok=True)
    
    def capture_document(self, save_path=None):
        """Захватывает фото документа с веб-камеры"""
        print("Открываю веб-камеру...")
        
        # Пробуем разные индексы камер
        for camera_index in [0, 1, 2]:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                print(f"✓ Камера {camera_index} открыта успешно!")
                break
        else:
            print("\n❌ Ошибка: невозможно открыть веб-камеру")
            print("\nРешения для Mac:")
            print("1. Проверьте разрешения: System Settings > Privacy & Security > Camera")
            print("2. Дайте разрешение Terminal на доступ к камере")
            print("3. Используйте опцию загрузить изображение вручную\n")
            return None
        
        print("Нажмите SPACE для фото, q для выхода без фото")
        
        captured_image = None
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Отображаем превью
            cv2.imshow('Документ (SPACE - фото, q - выход)', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):  # SPACE
                captured_image = frame
                print("Фото сделано!")
                break
            elif key == ord('q'):
                print("Выход без фото")
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if captured_image is not None and save_path:
            cv2.imwrite(save_path, captured_image)
            print(f"Изображение сохранено: {save_path}")
        
        return captured_image
    
    def load_image_from_file(self, file_path):
        """Загружает изображение из файла"""
        if not os.path.exists(file_path):
            print(f"Ошибка: файл {file_path} не найден")
            return None
        print(f"✓ Изображение загружено: {file_path}")
        return file_path
    
    def image_to_base64(self, image_path):
        """Преобразует изображение в base64"""
        with open(image_path, 'rb') as image_file:
            return base64.standard_b64encode(image_file.read()).decode('utf-8')
    
    def extract_data(self, image_path, prompt=None):
        """Отправляет изображение в OpenAI для извлечения данных"""
        if not os.path.exists(image_path):
            print(f"Ошибка: файл {image_path} не найден")
            return None
        
        if prompt is None:
            prompt = """Please extract and analyze the text content from this document image.
            Return the results as JSON with this structure:
            {
                "document_type": "description of document type",
                "text_content": "all extracted text",
                "key_information": {
                    "field1": "value1",
                    "field2": "value2"
                },
                "notes": "any additional observations"
            }"""
        
        # Кодируем изображение
        image_base64 = self.image_to_base64(image_path)
        
        # Определяем тип изображения
        ext = Path(image_path).suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        print("Отправляю изображение на анализ...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
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
                }
            ],
            "max_tokens": 2048
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
                # Проверяем, не отказала ли модель
                if "я не могу" in content.lower() or "unable to" in content.lower():
                    print("\n⚠️  Модель не смогла обработать изображение")
                    print("Попробуйте:")
                    print("- Улучшить качество изображения")
                    print("- Убедиться, что это реальный документ с текстом")
                    print("- Использовать более четкое изображение")
                return content
            else:
                print("Ошибка: неожиданный формат ответа от API")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к API: {e}")
            if "404" in str(e):
                print("\nПопробуйте использовать другую модель:")
                print("- gpt-4o (рекомендуется)")
                print("- gpt-4-turbo")
                print("- gpt-3.5-turbo")
            return None
    
    def save_results(self, results, filename=None):
        """Сохраняет результаты в файл"""
        if filename is None:
            from datetime import datetime
            filename = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            if isinstance(results, str):
                # Пытаемся распарсить как JSON
                try:
                    json_data = json.loads(results)
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    f.write(results)
            else:
                json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"Результаты сохранены: {filepath}")
        return filepath


def main():
    """Основная функция"""
    print("=" * 50)
    print("Экстрактор данных из документов")
    print("=" * 50)
    
    try:
        extractor = DocumentExtractor()
    except ValueError as e:
        print(f"Ошибка инициализации: {e}")
        print("\nУбедитесь, что файл .env содержит OPENAI_API_KEY")
        return
    
    # Выбираем источник изображения
    print("\nВыберите источник изображения:")
    print("1. Веб-камера")
    print("2. Загрузить файл")
    choice = input("Введите номер (1 или 2): ").strip()
    
    image_path = None
    
    if choice == "1":
        # Захватываем фото с камеры
        image_path_obj = extractor.output_dir / "document.jpg"
        image = extractor.capture_document(str(image_path_obj))
        if image is not None:
            image_path = str(image_path_obj)
    
    elif choice == "2":
        # Загружаем файл
        file_path = input("Введите путь к файлу изображения: ").strip()
        image_path = extractor.load_image_from_file(file_path)
    
    else:
        print("Неверный выбор")
        return
    
    if image_path is None:
        print("Изображение не было получено")
        return
    
    # Извлекаем данные
    results = extractor.extract_data(image_path)
    
    if results:
        print("\n" + "=" * 50)
        print("Извлеченные данные:")
        print("=" * 50)
        print(results)
        
        # Сохраняем результаты
        extractor.save_results(results)
    else:
        print("Ошибка при извлечении данных")


if __name__ == "__main__":
    main()
