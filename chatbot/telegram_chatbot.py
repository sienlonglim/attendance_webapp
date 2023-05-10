import telebot
import requests
import json
import mysql.connector
from bs4 import BeautifulSoup
from datetime import datetime

# Function to get config and API details
def get_value_from_json(json_file, key, sub_key=None):
   '''
   Function to read the json file for our app secret key
   '''
   try:
       with open(json_file) as f:
           data = json.load(f)
           if sub_key:
               return data[key][sub_key]
           else:
               return data[key]
   except Exception as e:
       print("Error: ", e)
config = get_value_from_json("static/secrets.json", "mysql_connector")
bot = telebot.TeleBot(get_value_from_json("static/secrets.json", "digipen_attendance_bot", "auth_token"))

# Attendance check functions
def check_attendance(cohort, urllink):
    '''
    Function call for doing the scraping and API call
    Inputs:
        cohort - string jan2023 or feb2023
        urllink - link for wsg summary page
    Returns a dictionary of the data
    '''
    # Actual code for all the work is here!
    # Getting the html page using requests and parsing using bs4
    page = requests.get(urllink)
    soup = BeautifulSoup(page.text, 'html.parser')

    # Session code eg. BH92347
    session_page = soup.find(class_='alternative-text').find_all('span')
    session_code = session_page[3].text.split(': ')[1].split('.')[0]

    # API call using the session code, returns a json file containing students signed in
    api_url = f'https://www.myskillsfuture.gov.sg/api/get-attendance?attendanceCode={session_code}&motCode=1'
    api_response = requests.get(api_url, headers={'Accept': 'application/json'})
    present = set([x['name'] for x in api_response.json()])

    # Connect to server on localhost
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        query = ("SELECT student_name FROM students "
                "WHERE class=%s AND cohort_year=%s")
        cursor.execute(query, (cohort[:3],cohort[3:])) #eg of cohort -> 'jan2023'
        namelist = set([name for (name,) in cursor])
    except Exception as err:
        print(type(err), err)
    else:
        cursor.close()
        cnx.close()
    
    # Using set.difference will allow us to instantly get the absentees since our names are all unique
    # note that this will give errors if two people have the exact same name!
    absent = namelist.difference(present)
    present = list(present)
    absent = list(absent)
    present.sort()
    absent.sort()

    # Check hour and min to determine is morning/afternoon session
    currentDateAndTime = datetime.now()
    currentHour = currentDateAndTime.strftime("%H")
    currentMin = currentDateAndTime.strftime("%M")
    hourmin = currentHour + currentMin
    if int(hourmin) < 1230:
        session = 'Morning'
    else:
        session = 'Afternoon'
    
    # We will pass a dictionary of all the results for further use
    return {'session_code': session_code,
            'present':present,
            'n_present':len(present),
            'absent':absent,
            'n_absent':len(absent),
            'cohort':cohort[:3].upper(),
            'currentHour':currentHour,
            'currentMin':currentMin,
            'session': session}

def get_attendance_links(callback_dict):
    '''
    Function call for scraping the session code only
    Inputs:
        urllink - list of links for wsg summary page
    Returns a dictionary of the data
    '''
    session_codes = []
    cohorts = []
    for cohort, urllink in callback_dict.items():
        try:
            page = requests.get(urllink)
            soup = BeautifulSoup(page.text, 'html.parser')

            # Session code eg. BH92347
            session_page = soup.find(class_='alternative-text').find_all('span')
            session_codes.append(session_page[3].text.split(': ')[1].split('.')[0])
            cohorts.append(cohort[:3])
        except Exception as e:
            print(f'Error getting session code: {e}')

    # Check hour and min to determine is morning/afternoon session
    currentDateAndTime = datetime.now()
    currentHour = currentDateAndTime.strftime("%H")
    currentMin = currentDateAndTime.strftime("%M")
    hourmin = currentHour + currentMin
    if int(hourmin) < 1230:
        session = 'Morning'
    else:
        session = 'Afternoon'
        
    return {'session_code': session_codes,
            'session': session,
            'cohort': cohorts}

def build_attendance_message(attendance):
    '''
    Input: dictionary of data from check_attendance function
    Returns the built attendance message
    '''
    # To handle check_attendance() function that has more incoming data
    if len(attendance)>3:
        # Build absentees output
        if len(attendance['absent'])<1:
            absentees = 'None! =)\n'
        else:
            absentees = ''
            count = 1
            for absentee in attendance['absent']:
                absentees += str(count)+'. ' + absentee.title() + '\n'
                count +=1

        # Build the full message
        attendance_message = f'''*{attendance['cohort']} cohort*
{attendance['session']} - {attendance['currentHour']}{attendance['currentMin']}hrs:
{attendance['session_code']}

Total present: {attendance['n_present']}
Absentees:
{absentees}'''
    
    # To handle get_attendance_links() function data
    else:
        attendance_message=f'''*Links for {attendance['session']} session*:\n'''
        for session_code, cohort in zip(attendance['session_code'], attendance['cohort']):
             attendance_message = attendance_message + f"{cohort.title()} - https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={session_code}&MOT=1#\n"
    
    #print(f'Message obtained as follows: \n{"-"*100}\n{attendance_message}\n{"-"*100}')
    return attendance_message

# Start / help command
@bot.message_handler(commands=['help', 'start'])
def help(message):
    '''
    Message handler for commands 'help' and 'start'
    Replies with the possible functions of the bot
    '''
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
       telebot.types.InlineKeyboardButton('Provide feedback & suggestions', url='t.me/natuyuki'),
       telebot.types.InlineKeyboardButton('Message BOT directly to link account', url='t.me/digipen_attendance_bot')
    )
    bot.send_message(message.chat.id,
                     '1) Get attendance updates for current session - /attendance\n' +
                     '2) Count down to start of OJT - /countdown\n'
                     '3) Get personal alert (Works only in DM @digipen_attendance_bot) - /link',
                     reply_markup=keyboard)


# Countdown command
@bot.message_handler(commands=['countdown'])
def countdown(message):
    '''
    Message handler for countdown command
    Provides inline keyboard option for JAN or FEB
    Sends a callback query when keyboard button is pressed 
    '''
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(telebot.types.InlineKeyboardButton('Jan', callback_data='JAN countdown'), 
                 telebot.types.InlineKeyboardButton('Feb', callback_data='FEB countdown'))
    bot.send_message(message.chat.id, 'Select cohort for countdown', reply_markup=keyboard)    

# Callback query handler for Countdown command
@bot.callback_query_handler(func=lambda call: call.data in ['JAN countdown', 'FEB countdown'])
def countdown_callback(call):
    '''
    Callback query handler for countdown command
    Sends the countdown to the chat based on today
    '''
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.data == 'JAN countdown':
        ojt_date = datetime(2023, 7, 18)
    elif call.data == 'FEB countdown':
        ojt_date = datetime(2023, 8, 15)
    time_remaining = ojt_date - datetime.now()
    if time_remaining.total_seconds() < 0:
        bot.send_message(call.message.chat.id, "Started OJT lor!")
    else:
        bot.send_message(call.message.chat.id, f"{call.data.split()[0]} cohort\n{time_remaining.days} Days remaining until start of OJT ({ojt_date})")
    bot.answer_callback_query(call.id)


# Attendance command
@bot.message_handler(commands=['attendance'])
def take_attendance(message):
    '''
    Message handler for attendance command
    Provides inline keyboard option for JAN or FEB or Attendance Links
    Sends a callback query when a keyboard button is pressed 
    '''
    reply_markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    reply_markup.add(telebot.types.InlineKeyboardButton('Jan', callback_data='jan23'), 
                     telebot.types.InlineKeyboardButton('Feb', callback_data='feb23'),
                     telebot.types.InlineKeyboardButton('Attendance links', callback_data='links'))
    bot.send_message(message.chat.id, 'Select cohort for attendance', reply_markup=reply_markup)

# Callback query handler for Attendance command
@bot.callback_query_handler(func=lambda call: call.data in ['jan23', 'feb23', 'links'])
def attendance_callback(call): 
    '''
    Callback query handler for attendance command
    Sends the attendance message to the chat
    '''
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        callback_dict = {'jan23': 'https://www.myskillsfuture.gov.sg/api/take-attendance/RA134486',
                         'feb23': 'https://www.myskillsfuture.gov.sg/api/take-attendance/RA103536'} 
        if call.data == 'links':
            attendance = get_attendance_links(callback_dict) # Throws in dictionary values as a list into the function
        else:
            attendance = check_attendance(call.data, callback_dict[call.data])
        attendance_message = build_attendance_message(attendance)
    except Exception as e:
        print(f'Error encountered: {type(e)}{e}')
        bot.answer_callback_query(call.id, "No available sessions at the moment.")
    else:      
        bot.send_message(call.message.chat.id, attendance_message, parse_mode='markdown', disable_web_page_preview=True)


@bot.message_handler(commands=['inform_absentees'])
def inform_absentees(message):
    '''
    Message handler for inform_absentees command
    Sends a message to all absentees who have their chatID linked to the database
    '''
    classes = {'jan23': 'https://www.myskillsfuture.gov.sg/api/take-attendance/RA134486',
               'feb23': 'https://www.myskillsfuture.gov.sg/api/take-attendance/RA103536'}
    
    # Cycle through both classes
    for key, value in classes.items():
        attendance = check_attendance(key, value)
        # dummy for testing
        '''attendance = {'session_code': 'session_code',
                    'absent':['LIM SIEN LONG'],
                    'n_absent': 1,
                    'cohort':'JAN',
                    'currentHour':'08',
                    'currentMin':'09',
                    'session': 'Morning'}'''

        try:
            if attendance['n_absent'] >= 1:
                bot.send_message(message.chat.id, f"Found {attendance['n_absent']} absentee(s) in {key}")
                cnx = mysql.connector.connect(**config)
                cursor = cnx.cursor()
                placeholder = '%s'
                placeholders = ', '.join(placeholder for _ in range(len(attendance['absent'])))
                query = f'''
                SELECT chat_id, student_name
                FROM students
                WHERE student_name in ({placeholders}) and chat_id IS NOT NULL;
                '''
                cursor.execute(query, tuple(attendance['absent']))

                # Standard message for the absentees
                personal_message = f'''you are absent for {attendance['session']} session as of {attendance['currentHour']}{attendance['currentMin']}hrs.

https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session_code']}&MOT=1#
'''
                # Send a personal message to each absentee
                absentees = cursor.fetchall()
                total_absentees = 0
                for _ in absentees:
                    total_absentees +=1
                    bot.send_message(_[0], f"{_[1]},\n{personal_message}") #, parse_mode='markdown')
                # Sends a message to where the command was called, to update user on how many absentee(s) were updated
                bot.send_message(message.chat.id, f"Reminder sent for {total_absentees} linked absentee(s) in {key}")
            else:
                bot.send_message(message.chat.id, f"No absentees found for class {key}")
        except Exception as e:
            print(f'Error encountered: {type(e)}{e}')
            bot.send_message(message.chat.id, f'Error encountered: {type(e)}{e}')
        finally:
            cursor.close()
            cnx.close()
    
# Reset accidental keyboard layout modifications
@bot.message_handler(commands=['reset_keyboard'])
def reset_keyboard(message):
    remove_markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, 'Custom keyboards removed', reply_markup=remove_markup)

# Instructions for groupchat
@bot.message_handler(chat_types=['group'] , commands=['link'])
def link_id_instructions(message):
    '''
    Function to inform user about linking
    '''
    text_message = '''This command can only work in private chat.
Enable personalised attendance updates by talking to me directly and typing:

/link <name (case-insensitive)>

This will allow me to identify and update you personally if you have not taken your attendance for the session.
To unlink accounts from this chat, /unlink
    '''
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
       telebot.types.InlineKeyboardButton('Message me directly', url='t.me/digipen_attendance_bot')
    )
    bot.send_message(message.chat.id, text_message, reply_markup=keyboard)

# Link telegram user to namelist (private chat command /link)
@bot.message_handler(chat_types=['private'] , commands=['link'])
def link_id(message):
    '''
    Function to allow tagging a chatID to a person in the namelist to receive personal updates if absent
    - Chat must be a private chat for this to work
    '''
    if len(message.text.split(' ', 1)) < 2:
        text_message = '''Enable personalised attendance updates by typing:

/link <name (case-insensitive)>

This will allow me to identify and update you personally if you have not taken your attendance for the session.
To unlink accounts from this chat, /unlink
        '''
        bot.send_message(message.chat.id, text_message)
    else:
        telegram_username = message.chat.username
        student_name = message.text.split(' ', 1)[1]
        try:
            cnx = mysql.connector.connect(**config)
            cursor = cnx.cursor()
            query = ("SELECT student_name FROM students "
                    "WHERE student_name LIKE %s")
            cursor.execute(query, (f'%{student_name}%',)) 
            name_matches = [name[0] for name in cursor]
            no_of_matches = len(name_matches)
            if no_of_matches > 1:
                bot.send_message(message.chat.id, f'{no_of_matches} matches found - {name_matches}\n\nPlease key in a more specific name for a full match')
            elif no_of_matches == 1:
                reply_markup = telebot.types.InlineKeyboardMarkup(row_width=2)
                reply_markup.add(telebot.types.InlineKeyboardButton('Yes', callback_data=f'update_db={name_matches[0]}={message.chat.id}'), 
                                telebot.types.InlineKeyboardButton('No', callback_data=f'update_db=No={message.chat.id}'))
                bot.send_message(message.chat.id, f'{no_of_matches} match found - {name_matches[0]}\nConfirm update', reply_markup=reply_markup)
            else:
                raise KeyError(f'0 Match for {student_name}')
        except Exception as err:
            print(type(err), err)
            bot.send_message(message.chat.id, f'Oops something went wrong, please check your input and try again.')
        finally:
            cursor.close()
            cnx.close()

# Unlink telegram user from namelist
@bot.message_handler(chat_types=['private'] , commands=['unlink'])
def unlink_id(message):
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        query = ('''UPDATE students
                 SET chat_id = NULL
                 WHERE chat_id = %s''')
        cursor.execute(query, (message.chat.id,)) 
        if cursor.rowcount > 0:
            cnx.commit()
            bot.send_message(message.chat.id, f'ChatID {message.chat.id} removed from database')
        else:
            raise KeyError('No ID matched in database')
    except Exception as err:
        print(type(err), err)
        bot.send_message(message.chat.id, f'Could not find any linked account to this chat')
    finally:
        cursor.close()
        cnx.close()

# Callback query handler for Account linking
@bot.callback_query_handler(func=lambda call: call.data.startswith('update_db'))
def link_callback(call):
    data = call.data.split('=')
    if data[1] == 'No':
        bot.send_message(call.message.chat.id, 'Request canceled')
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        try:
            cnx = mysql.connector.connect(**config)
            cursor = cnx.cursor()
            query = ("UPDATE students "
                     "SET chat_id = %s "
                     "WHERE student_name = %s")
            cursor.execute(query, (int(data[2]), data[1]))
        except Exception as err:
            print(type(err), err)
            bot.send_message(call.message.chat.id, f'Oops something went wrong, please check your input and try again.')
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            cnx.commit()
            bot.send_message(call.message.chat.id, f'ChatID - {int(data[2])} now tagged to {data[1]}\n\nThis chat will receive updates if {data[1]} is absent')
            bot.delete_message(call.message.chat.id, call.message.message_id)
        finally:
            cursor.close()
            cnx.close()
            bot.answer_callback_query(call.id)
        
            
if __name__ == "__main__":
    print('Bot started')
    bot.infinity_polling()
