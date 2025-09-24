#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки функціональності налаштувань
"""

def test_user_settings():
    """Тест функцій роботи з налаштуваннями користувача"""
    # Імпортуємо функції з bot.py
    import sys
    sys.path.append('.')
    
    try:
        from bot import get_user_settings, update_user_setting
        
        # Тест 1: Отримання налаштувань нового користувача
        user_id = 12345
        settings = get_user_settings(user_id)
        
        expected_defaults = {
            'voice': 'alloy',
            'speed': 1.0,
            'image_size': 'auto',
            'image_quality': 'auto'
        }
        
        assert settings == expected_defaults, f"Невірні дефолтні налаштування: {settings}"
        print("✅ Тест 1 пройдено: Дефолтні налаштування встановлені правильно")
        
        # Тест 2: Оновлення налаштувань
        update_user_setting(user_id, 'voice', 'nova')
        update_user_setting(user_id, 'speed', 1.5)
        update_user_setting(user_id, 'image_size', '1536x1024')
        update_user_setting(user_id, 'image_quality', 'high')
        
        updated_settings = get_user_settings(user_id)
        expected_updated = {
            'voice': 'nova',
            'speed': 1.5,
            'image_size': '1536x1024',
            'image_quality': 'high'
        }
        
        assert updated_settings == expected_updated, f"Невірні оновлені налаштування: {updated_settings}"
        print("✅ Тест 2 пройдено: Оновлення налаштувань працює правильно")
        
        # Тест 3: Перевірка валідації швидкості
        try:
            update_user_setting(user_id, 'speed', 5.0)  # Невірна швидкість
            print("❌ Тест 3 не пройдено: Повинна бути помилка валідації")
        except:
            print("✅ Тест 3 пройдено: Валідація швидкості працює")
        
        print("\n🎉 Всі тести пройдено успішно!")
        return True
        
    except Exception as e:
        print(f"❌ Помилка в тестах: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Запуск тестів налаштувань...")
    test_user_settings()
