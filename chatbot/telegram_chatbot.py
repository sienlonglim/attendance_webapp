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
    session = soup.find(class_='alternative-text').find_all('span')
    session_code = session[3].text.split(': ')[1].split('.')[0]

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
    
    # We will pass a dictionary of all the results back to the routing function, which will then be used to render the html
    return {'session': session_code, 'present':present, 'n_present':len(present), 'absent':absent, 'n_absent':len(absent), 'cohort':cohort[:3].upper()}

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
        session = soup.find(class_='alternative-text').find_all('span')
        session_codes.append(session[3].text.split(': ')[1].split('.')[0])
    return {'session': session_codes}

def build_attendance_message(attendance):
    '''
    Input: dictionary of data from check_attendance function
    Returns the built attendance message
    '''
    currentDateAndTime = datetime.now()
    currentHour = currentDateAndTime.strftime("%H")
    currentMin = currentDateAndTime.strftime("%M")
    hourmin = currentHour + currentMin
    if int(currentHour) < 1230:
        session = 'Morning'
    else:
        session = 'Afternoon'

    if len(attendance)>1:
        # Build absentees output
        if len(attendance['absent'])<1:
            absentees = 'None! =)\n'
        else:
            absentees = ''
            count = 1
            for x in attendance['absent']:
                absentees += str(count)+'. ' + x.title() + '\n'
                count +=1

        # Build the full message
        attendance_message = f"*{attendance['cohort']} cohort*\n{session} - {currentHour}{currentMin}hrs:\n{attendance['session']} \n\nTotal present: {attendance['n_present']}\nAbsentees:\n{absentees}"
    else:
        attendance_message=f'''*Links for {session} session*:
JAN - https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session'][0]}&MOT=1#

FEB - https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session'][1]}&MOT=1#
        '''
    
    print(f'Message obtained as follows: \n{"-"*100}\n{attendance_message}\n{"-"*100}')
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
    except Exception as e:
        print(f'Error encountered: {type(e)}{e}')
        bot.answer_callback_query(call.id, "No available sessions at the moment.")
    else:      
        bot.send_message(call.message.chat.id, attendance_message, parse_mode='markdown', disable_web_page_preview=True)
        bot.answer_callback_query(call.id)

# Reset accidental keyboard layout modifications
@bot.message_handler(commands=['reset_keyboard'])
def reset_keyboard(message):
    remove_markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, 'Custom keyboards removed', reply_markup=remove_markup)

# Link telegram user to namelist
@bot.message_handler(chat_types=['private'] , commands=['link'])
def link_id(message):
    if len(message.text.split(' ', 1)) < 2:
        text_message = '''To enable personalised attendance updates input the following:
/link <YOURFULLNAME(CAPS) as per DigiPen record>
This will allow me to identify and update you personally if you have not taken your attendance for the session.
        '''
        bot.send_message(message.chat.id, text_message)
    else:
        telegram_user_id = message.chat.id.username
        username = message.text.split(' ', 1)[1]
        bot.send_message(message.chat.id, f'{telegram_user_id} : {username}')

if __name__ == "__main__":
    print('Bot started')
    bot.infinity_polling()

'''
@bot.message_handler(func = lambda message : message.chat.type == 'private', commands=['link_telegram_id'])
def echo(message):
    bot.reply_to(message, message.text)'''