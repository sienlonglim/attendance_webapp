import requests
import pywhatkit
import json
from bs4 import BeautifulSoup
from datetime import datetime
import mysql.connector
from mysql.connector import errorcode

def check_attendance(cohort, urllink):
    '''
    Function call for doing the scraping and API call
    '''
    # Actual code for all the work is here!
    # Getting the html page using requests and parsing using bs4
    page = requests.get(urllink)
    soup = BeautifulSoup(page.text, 'html.parser')

    # Session code eg. BH92347
    session = soup.find_all(class_='session-desc')
    session_code  = session[3].text.strip()

    # API call using the session code, returns a json file containing students signed in
    api_url = f'https://www.myskillsfuture.gov.sg/api/get-attendance?attendanceCode={session_code}&motCode=1'
    api_response = requests.get(api_url, headers={'Accept': 'application/json'})
    present = set([x['name'] for x in api_response.json()])

    # Access local database
    with open("static/secrets.json") as f:
           data = json.load(f)
           config = data['mysql_connector']
    
    # Connect to server on localhost
    try:
        cnx = mysql.connector.connect(**config)
        print('Connected')
        cursor = cnx.cursor()
        query = ("SELECT student_name FROM students "
                "WHERE class=%s AND cohort_year=%s")
        cursor.execute(query, (cohort[:3],cohort[3:])) #eg of cohort -> 'jan2023'
        namelist = set([name for (name,) in cursor])
    except mysql.connector.Error as err:
        print(err)
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
    return {'session': session_code, 'present':present, 'n_present':len(present), 'absent':absent, 'n_absent':len(absent)}

def send_whatsapp_message(message, group = 'HMASwA39Eu77B69Fb6rCZu'):
    '''
    Function that takes inputs:
        message - string of message to send
        group - the whatsapp group invitation ID, already preset
    '''
    try:
        #pywhatkit.sendwhats_image("+6596261242", img_path="static/sample.jpg", caption=message, tab_close=True)
        pywhatkit.sendwhatmsg_to_group_instantly(group, message, tab_close=True)
        print('Message sent!')
    except Exception as e:
        print(e)

if __name__ == "__main__":
    urllink = 'https://www.myskillsfuture.gov.sg/api/take-attendance/6d8fbe3b26cf07a04f5a2c2f1086410c'

    try:
        attendance = check_attendance('jan2023', urllink)
        print('Got attendance, now building message...\n')

        # Build absentees output
        if len(attendance['absent'])<1:
            absentees = 'None! =)'
        else:
            absentees = ''
            count = 1
            for x in attendance['absent']:
                absentees += str(count)+'. ' + x + '\n'
                count +=1

        # Build the full message
        currentDateAndTime = datetime.now()
        currentHour = currentDateAndTime.strftime("%H")
        currentMin = currentDateAndTime.strftime("%M")
        attendance_message = f"*Attendance update at {currentHour}{currentMin}hrs:*\n{attendance['session']} \n\nTotal present: {attendance['n_present']}\nAbsentees:\n{absentees}\nLink: 'https://www.myskillsfuture.gov.sg/content/portal/en/individual/take-attendance.html?attendanceCode={attendance['session']}&MOT=1#'"
        print(f'Message obtained as follows: \n{"-"*100}\n{attendance_message}\n{"-"*100}')
    except Exception as e:
        print(e)
    else:
        # Send the message if no problems
        send = input('Send message? y/n : ')
        if send == 'y':
            print('Now sending')
            send_whatsapp_message(attendance_message) 
        else:
            print('Aborted')