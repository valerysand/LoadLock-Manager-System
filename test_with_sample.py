#!/usr/bin/env python3
"""
Скрипт для тестирования с примером документа
"""

from document_extractor import DocumentExtractor
import os

def main():
    print("=" * 50)
    print("Тест экстрактора с примером документа")
    print("=" * 50)
    
    try:
        extractor = DocumentExtractor()
    except ValueError as e:
        print(f"Ошибка: {e}")
        return
    
    # Ищем примеры документов в папке
    print("\nДоступные документы:")
    output_dir = extractor.output_dir
    
    documents = []
    for file in output_dir.glob("*"):
        if file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            documents.append(file)
            print(f"  - {file.name}")
    
    if not documents:
        print("  Документов не найдено в папке output/")
        print("\n  Используйте опцию загрузить файл со своего компьютера:")
        file_path = input("  Введите путь к файлу: ").strip()
        if os.path.exists(file_path):
            documents = [file_path]
        else:
            print("  Файл не найден")
            return
    else:
        choice = input("\nВыберите документ (номер или путь): ").strip()
        if choice.isdigit() and int(choice) < len(documents):
            file_path = documents[int(choice)]
        else:
            file_path = choice
    
    if os.path.exists(file_path):
        print(f"\nАнализирую: {file_path}")
        results = extractor.extract_data(file_path)
        
        if results:
            print("\n" + "=" * 50)
            print("Результаты:")
            print("=" * 50)
            print(results)
            extractor.save_results(results)
        else:
            print("Ошибка при анализе")
    else:
        print(f"Файл не найден: {file_path}")


if __name__ == "__main__":
    main()
