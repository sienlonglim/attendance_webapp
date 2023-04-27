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
        print('Connected')
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

    currentDateAndTime = datetime.now()
    currentHour = currentDateAndTime.strftime("%H")
    currentMin = currentDateAndTime.strftime("%M")
    hourmin = currentHour + currentMin
    if int(hourmin) < 1230:
        session = 'Morning'
    else:
        session = 'Afternoon'
    
    # We will pass a dictionary of all the results back to the routing function, which will then be used to render the html
    return {'session_code': session_code,
            'present':present,
            'n_present':len(present),
            'absent':absent,
            'n_absent':len(absent),
            'cohort':cohort[:3].upper(),
            'currentHour':currentHour,
            'currentMin':currentMin,
            'session': session}

def get_attendance_links(urllinks):
    '''
    Function call for scraping the session code only
    Inputs:
        urllink - list of links for wsg summary page
    Returns a dictionary of the data
    '''
    session_codes = []
    for urllink in urllinks:
        page = requests.get(urllink)
        soup = BeautifulSoup(page.text, 'html.parser')

        # Session code eg. BH92347
        session_page = soup.find(class_='alternative-text').find_all('span')
        session_codes.append(session_page[3].text.split(': ')[1].split('.')[0])
    return {'session_code': session_codes}

def build_attendance_message(attendance):
    '''
    Input: dictionary of data from check_attendance function
    Returns the built attendance message
    '''
    if len(attendance)>2:
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
    else:
        attendance_message=f'''*Links for {attendance['session']} session*:
JAN - https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session_code'][0]}&MOT=1#

FEB - https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session_code'][1]}&MOT=1#
        '''
    
    #print(f'Message obtained as follows: \n{"-"*100}\n{attendance_message}\n{"-"*100}')
    return attendance_message

# Start / help command
@bot.message_handler(commands=['help', 'start'])
def help(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
       telebot.types.InlineKeyboardButton('Provide feedback & suggestions', url='t.me/natuyuki')
    )
    bot.send_message(message.chat.id,
                     '1) Get attendance updates for current session press /attendance\n' +
                     '2) Count down to start of OJT press /countdown',
                     reply_markup=keyboard)


# Countdown command
@bot.message_handler(commands=['countdown'])
def countdown(message):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(telebot.types.InlineKeyboardButton('Jan', callback_data='JAN countdown'), 
                 telebot.types.InlineKeyboardButton('Feb', callback_data='FEB countdown'))
    bot.send_message(message.chat.id, 'Select cohort for countdown', reply_markup=keyboard)    

# Callback query handler for Countdown command
@bot.callback_query_handler(func=lambda call: call.data in ['July 18th', 'August 15th'])
def countdown_callback(call):
    if call.data == 'JAN countdown':
        ojt_date = datetime(2023, 7, 18)
    elif call.data == 'FEB countdown':
        ojt_date = datetime(2023, 8, 15)
    time_remaining = ojt_date - datetime.now()
    if time_remaining.total_seconds() < 0:
        bot.send_message(call.message.chat.id, "Started OJT lor!")
    else:
        bot.send_message(call.message.chat.id, f"{call.data.split()[0]} cohort\n{time_remaining.days} Days remaining until start of OJT ({call.data})")
    bot.answer_callback_query(call.id)


# Attendance command
@bot.message_handler(commands=['attendance'])
def take_attendance(message):
    reply_markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    reply_markup.add(telebot.types.InlineKeyboardButton('Jan', callback_data='jan23'), 
                     telebot.types.InlineKeyboardButton('Feb', callback_data='feb23'),
                     telebot.types.InlineKeyboardButton('Attendance links', callback_data='links'))
    bot.send_message(message.chat.id, 'Select cohort for attendance', reply_markup=reply_markup)

# Callback query handler for Attendance command
@bot.callback_query_handler(func=lambda call: call.data in ['jan23', 'feb23', 'links'])
def attendance_callback(call): 
    try:
        callback_dict = {'jan23': 'https://www.myskillsfuture.gov.sg/api/take-attendance/RA103536',
                         'feb23': 'https://www.myskillsfuture.gov.sg/api/take-attendance/RA103534'}
        if call.data == 'links':
            attendance = get_attendance_links(callback_dict.values()) # Throws in dictionary values as a list into the function
        else:
            attendance = check_attendance(call.data, callback_dict[call.data])
        print('Got attendance, now building message')
        attendance_message = build_attendance_message(attendance)
        session_active = True
    except Exception as e:
        print(f'Error encountered: {type(e)}{e}')
        session_active = False
        bot.answer_callback_query(call.id, "No available sessions at the moment.")
    else:      
        bot.send_message(call.message.chat.id, attendance_message, parse_mode='markdown', disable_web_page_preview=True)
    
    # 2nd part to send updates to linked accounts - NEED TO INCORPORATE THIS TO HAVE THE LINK AND TIME IF POSSIBLE, also use a list if possible
    if session_active:
        try:
            if len(attendance['absent']) >= 1:
                cnx = mysql.connector.connect(**config)
                cursor = cnx.cursor()
                for absentee in attendance['absent']:
                    query = '''
                    SELECT chat_id
                    FROM students
                    WHERE student_name = %s and chat_id IS NOT NULL
                    '''
                    cursor.execute(query, (absentee,))
                    personal_message = f'''*{attendance['cohort']} cohort*
{attendance['session']} - {attendance['currentHour']}{attendance['currentMin']}hrs:
{attendance['session_code']}

Your attendance is not marked yet

https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session_code']}&MOT=1#
'''
                    receiver = cursor.fetchone()[0]
                    if receiver:
                        bot.send_message(receiver, personal_message)
        except Exception as e:
            print(f'Error encountered: {type(e)}{e}')
        else:
            bot.answer_callback_query(call.id)
        finally:
            cursor.close()
            cnx.close()

'''@bot.message_handler(commands=['test'])
def test(message):
    attendance = {'absent': ['LIM SIEN LONG']}'''     


# Reset accidental keyboard layout modifications
@bot.message_handler(commands=['reset_keyboard'])
def reset_keyboard(message):
    remove_markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, 'Custom keyboards removed', reply_markup=remove_markup)


# Link telegram user to namelist
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
                raise KeyError('0 Match')
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
    except Exception as err:
        print(type(err), err)
        bot.send_message(message.chat.id, f'Could not find any linked account to this chat')
    else:
        cnx.commit()
        bot.send_message(message.chat.id, 'ChatID unlinked in database')
    finally:
        cursor.close()
        cnx.close()

# Callback query handler for Account linking
@bot.callback_query_handler(func=lambda call: call.data.startswith('update_db'))
def link_callback(call):
    data = call.data.split('=')
    if data[1] == 'No':
        bot.send_message(call.message.chat.id, 'Request canceled')
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
        else:
            cnx.commit()
            bot.send_message(call.message.chat.id, f'ChatID - {int(data[2])} now tagged to {data[1]}\nThis Chat will receive updates if {data[1]} is absent')
        finally:
            cursor.close()
            cnx.close()
            bot.answer_callback_query(call.id)
        
            
if __name__ == "__main__":
    print('Bot started')
    bot.infinity_polling()
