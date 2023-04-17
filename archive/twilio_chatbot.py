from twilio.rest import Client
from bs4 import BeautifulSoup
from datetime import datetime
import requests
import json
import mysql.connector

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
account_sid = get_value_from_json("static/secrets.json", "twilio", "account_sid")
auth_token = get_value_from_json("static/secrets.json", "twilio", "auth_token")

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


urllink = 'https://www.myskillsfuture.gov.sg/api/take-attendance/6d8fbe3b26cf07a04f5a2c2f1086410c'

try:
    attendance = check_attendance('jan23', urllink)
    print('Got attendance, now building message')

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
    client = Client(account_sid, auth_token)
except Exception as e:
    print(e)
else:      
    message = client.messages.create(from_='whatsapp:+14155238886', body=attendance_message, to='whatsapp:+6596261242')


