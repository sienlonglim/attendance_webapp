

def take_attendance_v2(message):
    keyboard = [telebot.types.InlineKeyboardButton('Jan Cohort', callback_data='jan23'),
                telebot.types.InlineKeyboardButton('Feb Cohort', callback_data='feb23')]
    reply_markup = telebot.types.InlineKeyboardMarkup(keyboard)
    
    bot.send_message(message.chat.id, 'Select cohort', reply_markup=reply_markup)
    #bot.answer_callback_query
