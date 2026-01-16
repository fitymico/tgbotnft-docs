#-----------------------------------------------------------------------------------------------------------
@dp.message(Command("test_reminders"))
async def test_reminders(message: Message):
    """Тест напоминаний (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    # Получаем активные напоминания
    reminders = db.get_due_reminders()
    
    if not reminders:
        await message.answer("ℹ️ Нет напоминаний для отправки в данный момент")
        return
    
    await message.answer(f"📊 Найдено {len(reminders)} напоминаний для отправки")
    
    # Вручную запускаем отправку
    await send_reminder_notifications()
    
    await message.answer("✅ Тест отправки напоминаний выполнен")

@dp.message(Command("create_test_reminder"))
async def create_test_reminder(message: Message):
    """Создать тестовое напоминание (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    # Создаем тестовое напоминание с временем через 1 минуту
    user = db.get_user(ADMIN_ID)
    if not user:
        await message.answer("❌ Админ не найден в базе")
        return
    
    # Создаем тестовую лицензию (если нет активной)
    active_license = db.get_active_license(ADMIN_ID)
    if not active_license:
        # Создаем тестовую лицензию
        license_key = db.create_license_key(user[0], "basic", 30)
        db.update_user_subscription(ADMIN_ID, "basic", license_key, (datetime.now() + timedelta(days=30)).isoformat())
    
    # Получаем активную лицензию
    active_license = db.get_active_license(ADMIN_ID)
    if not active_license:
        await message.answer("❌ Не удалось создать тестовую лицензию")
        return
    
    license_key = active_license[3]
    expires_at = datetime.now() + timedelta(minutes=5)  # Через 5 минут
    
    # Создаем напоминание за 1 минуту (вместо 1 часа)
    one_minute_before = datetime.now() + timedelta(minutes=1)
    
    # Удаляем старые напоминания для этой лицензии
    db.cursor.execute('DELETE FROM reminders WHERE license_key = ?', (license_key,))
    
    # Создаем тестовое напоминание
    db.cursor.execute('''
        INSERT INTO reminders (user_id, license_key, reminder_type, scheduled_time)
        VALUES (?, ?, ?, ?)
    ''', (user[0], license_key, '1_hour', one_minute_before.isoformat()))
    db.conn.commit()
    
    await message.answer(
        f"✅ Создано тестовое напоминание!\n\n"
        f"• Лицензия: {license_key}\n"
        f"• Время напоминания: {one_minute_before.strftime('%H:%M:%S')}\n"
        f"• Тип: Тест (1 минута вместо 1 часа)\n\n"
        f"Напоминание придет через 1 минуту!"
    )

@dp.message(Command("show_reminders"))
async def show_reminders(message: Message):
    """Показать все напоминания (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    # Получаем все напоминания
    db.cursor.execute('''
        SELECT r.*, u.telegram_id, u.username, lk.expires_at, lk.is_active
        FROM reminders r
        LEFT JOIN users u ON r.user_id = u.user_id
        LEFT JOIN license_keys lk ON r.license_key = lk.key
        ORDER BY r.scheduled_time
    ''')
    reminders = db.cursor.fetchall()
    
    if not reminders:
        await message.answer("📭 Нет напоминаний в базе")
        return
    
    text = "📊 <b>Все напоминания:</b>\n\n"
    
    for reminder in reminders:
        reminder_id = reminder[0]
        user_id = reminder[1]
        license_key = reminder[2]
        reminder_type = reminder[3]
        scheduled_time = datetime.fromisoformat(reminder[4])
        sent = reminder[5]
        sent_at = reminder[6] if reminder[6] else "Не отправлено"
        telegram_id = reminder[8] if reminder[8] else "N/A"
        username = reminder[9] if reminder[9] else "N/A"
        expires_at = reminder[10] if reminder[10] else "N/A"
        is_active = reminder[11] if reminder[11] else 0
        
        text += f"<b>ID:</b> {reminder_id}\n"
        text += f"<b>Пользователь:</b> {username} (ID: {telegram_id})\n"
        text += f"<b>Тип:</b> {reminder_type}\n"
        text += f"<b>Время отправки:</b> {scheduled_time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        text += f"<b>Статус:</b> {'✅ Отправлено' if sent else '⏳ Ожидает'}\n"
        text += f"<b>Лицензия активна:</b> {'✅ Да' if is_active else '❌ Нет'}\n"
        text += "─" * 30 + "\n"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

@dp.message(Command("force_reminder"))
async def force_reminder(message: Message):
    """Принудительно отправить напоминание сейчас (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    # Парсим команду: /force_reminder <telegram_id> <type>
    parts = message.text.split()
    
    if len(parts) < 3:
        await message.answer(
            "📋 <b>Использование:</b>\n"
            "/force_reminder <telegram_id> <type>\n\n"
            "Примеры:\n"
            "/force_reminder 123456789 1_hour\n"
            "/force_reminder 123456789 3_days\n\n"
            "Типы: '3_days' или '1_hour'",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        telegram_id = int(parts[1])
        reminder_type = parts[2]
        
        if reminder_type not in ['3_days', '1_hour']:
            await message.answer("❌ Неверный тип напоминания. Используйте '3_days' или '1_hour'")
            return
        
        # Получаем пользователя
        user = db.get_user(telegram_id)
        if not user:
            await message.answer(f"❌ Пользователь с ID {telegram_id} не найден")
            return
        
        # Получаем активную лицензию
        active_license = db.get_active_license(telegram_id)
        if not active_license:
            await message.answer(f"❌ У пользователя {telegram_id} нет активной подписки")
            return
        
        plan_id = active_license[4]
        plan = SUBSCRIPTION_PLANS.get(plan_id, {})
        plan_name = plan.get('name', 'Неизвестный тариф')
        expires_at = datetime.fromisoformat(active_license[5]) if active_license[5] else datetime.now()
        
        # Отправляем напоминание
        if reminder_type == '3_days':
            message_text = (
                f"⏰ <b>ТЕСТ: Напоминание о продлении подписки</b>\n\n"
                f"Ваша подписка <b>{plan_name}</b> истекает через <b>3 дня</b> ({expires_at.strftime('%d.%m.%Y %H:%M')})\n\n"
                f"<i>Это тестовое сообщение!</i>"
            )
        else:  # '1_hour'
            message_text = (
                f"⚠️ <b>ТЕСТ: СРОЧНОЕ НАПОМИНАНИЕ</b>\n\n"
                f"Ваша подписка <b>{plan_name}</b> истекает через <b>1 час</b>!\n"
                f"Дата окончания: {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"<i>Это тестовое сообщение!</i>"
            )
        
        keyboard = [
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")],
            [InlineKeyboardButton(text="🔑 Проверить лицензию", callback_data="my_license")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        await message.answer(f"✅ Тестовое напоминание ({reminder_type}) отправлено пользователю {telegram_id}")
        
    except ValueError:
        await message.answer("❌ Неверный формат Telegram ID")
    except Exception as e:
        logger.error(f"Ошибка при отправке тестового напоминания: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        
#-----------------------------------------------------------------------------------------------------------