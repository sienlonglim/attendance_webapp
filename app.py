from flask import Flask, render_template, url_for, request, redirect, flash
from markupsafe import escape
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import base64
import json
import requests
import mysql.connector
from mysql.connector import errorcode

app = Flask(__name__)
debug= False # Debug mode should be off if hosted on an external website

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

# Getting the credentials for the session and database access
app.secret_key = get_value_from_json("static/secrets.json", "flask", "SECRET_KEY")
config = get_value_from_json("static/secrets.json", "mysql_connector")

# If hosting on pythonanywhere use the following directory instead
# app.secret_key = get_value_from_json("/home/natuyuki/scraping_attendance/static/secrets.json", "flask", "SECRET_KEY")

@app.route("/")
def index():
    '''
    Routing for index page, will redirect to attendance page since we only have one layout
    '''
    return redirect(url_for('attendance'))

@app.route('/attendance', methods=('GET', 'POST'))
def attendance():
    if request.method == 'POST':
        # Receive the inputs from the form and pass them into the check_attendance function
        urllink = request.form.get('urllink', False)
        cohort = request.form.get('cohort', False)

        if not urllink:
            flash('URL required')
        else:
            try:
                attendance_report = check_attendance(cohort, urllink)
            except Exception as e:
                # Catch any exceptions and log them in the app logger, this also handles the error message on the html
                flash(e) if app.debug==True else flash('Oops, something went wrong')
                app.logger.info(e)
            else:
                return render_template('attendance.html', attendance_report=attendance_report)
    return render_template('attendance.html', attendance_report=None)

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

        # Scraping the QR image for display on webapp
        images = soup.find_all('img')
        data_url = images[1]['src']
        encoded_data_url = data_url.split(',')[1] # Removing the prefix 'data:image/png;base64,'
        bytes_decoded = base64.b64decode(encoded_data_url)
        session_QR = Image.open(BytesIO(bytes_decoded))
        session_QR.save("static/session_QR.png")
        session_QR = True

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
        return {'QR': session_QR, 'session': session_code, 'present':present, 'n_present':len(present), 'absent':absent, 'n_absent':len(absent)}

# For visualling checking the namelist (just in case), there is no DOM access to this except a direct url input
@app.route("/attendance/namelist/<cohort>")
def namelist(cohort):
    # Connect to server on localhost
    try:
        cnx = mysql.connector.connect(**config)
        print('Connected')
        cursor = cnx.cursor()
        query = ("SELECT student_name FROM students "
                "WHERE class=%s AND cohort_year=%s")
        if cohort=='jan2023' or cohort=='feb2023':
            cursor.execute(query, (cohort[:3],cohort[3:])) #eg of cohort -> 'jan2023'
            namelist = [name for (name,) in cursor]
            namelist.sort()
        else:
            namelist = None
    except mysql.connector.Error as err:
        print(err)
    else:
        cursor.close()
        cnx.close()
    return render_template('namelist.html', namelist=namelist, cohort=escape(cohort.capitalize()))

# Run the app if it is the main script
if __name__ == '__main__':
    app.run(debug=debug)



    