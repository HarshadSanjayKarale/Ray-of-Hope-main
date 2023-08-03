from flask import Flask, request, render_template, flash, url_for, redirect, session, Response
import pyrebase
from flask_session import Session
import requests.exceptions
from datetime import timedelta
from email.message import EmailMessage 
import ssl, smtplib
from dotenv import load_dotenv
import os


load_dotenv()


# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_TYPE'] = 'filesystem'   
Session(app)

email_sender = os.getenv('EMAIL_SENDER')
gmail_password = os.getenv('EMAIL_PASSWORD')

# Initialize Firebase config
firebase_config = os.getenv('FIREBASE_CONFIG')

firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)  # Set the timeout (e.g., 30 minutes)

# optimized
# this will be the home page showing ('i need help' and 'i can help')
@app.route('/', methods=['GET', 'POST'])
def home():
    '''basically the home page of the program'''
    return render_template('(a)home_page.html')


# redirects to a signin or signup page of helpee)
@app.route('/sign_in_helpee', methods=['GET', 'POST'])
def sign_in_helpee():
    if request.method == "POST":
        email = request.form['helpee_email']
        password = request.form['helpee_password']
        
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            user_id = user['localId']

            # session has only user_id now
            session['user_id'] = user_id

            # print("session", session)

            # Fetch user data from the database
            user_data = db.child('people').child('helpee').child(user_id).get().val()
            # print("user", user_data)

            # Check if user_data exists
            if user_data and 'data' in user_data:
                # Store user-specific data in the session using the user_id as part of the key
                session['user_data'] = user_data
                
                # this is how you acess the user data with 'data' and 'exams'
                # data can be acessed by futher indexing session['user_data]['data']
                """Important: this is where the whole data is stored currently"""
                # print("user data is here:", session['user_data'])

                # Successful login, redirect the user to the desired page
                # print("User logged in:", user_id)
                return redirect('/rest_page_for_helpee')
            else:
                # If user data is missing, display an error message
                return render_template('(helpee)login.html', error="User data not found.")
            
        except requests.exceptions.HTTPError as e:
            # Invalid credentials (HTTP 400 status code)
            return render_template('(helpee)login.html', error="Invalid credentials. Please try again.", invalid_input = True)
    
        except requests.exceptions.RequestException as e:
            # Network-related error (e.g., connection error)
            return render_template('(helpee)login.html', error="Error occurred during authentication. Please try again later.")

    # If the request method is not POST, render the login form
    return render_template('(helpee)login.html')


# need a feature that checks if the email exists in realtime
# currently just refreshes the page if the user is already present
@app.route('/sign_up_helpee', methods=['GET', 'POST'])
def sign_up_helpee():
    '''signup page'''
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['cpassword']
            self_name = request.form['name']
            self_contact = request.form['contact_number']
            gender = request.form['gender']
            edu = request.form['grade_level']
            address = request.form['address']
            udid = request.form['unique_disability_id']
            parent_name = request.form['parent_name']
            institute = request.form['institute_name']
            guardian_contact = request.form['parent_contact_number']
            user = auth.create_user_with_email_and_password(email, password)
            user_id = user['localId']

                # Create a dictionary with user data
            user_data = {
                'name': self_name,
                'email': email,
                'self_contact': self_contact,
                'gender': gender,
                'edu': edu,
                'address': address,
                'udid': udid,
                'institute': institute,
                'parent_name': parent_name,
                'guardian_contact': guardian_contact
                }
            
            # Store the user data in the Firebase Realtime Database under the user ID
            db.child('people').child('helpee').child(user_id).child('data').set(user_data)

            # Data successfully saved, render the success template
            return redirect('/sign_in_helpee')
            
        except Exception as e:
            # Error occurred during sign-up, show an error message
            return render_template('(helpee)signup.html', error="An error occurred during sign-up: " + str(e))

    return render_template('(helpee)signup.html')


# optimized
@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    '''sends an email after which the user can change the password'''
    try:
        email = request.json.get('email')
        
        # Validate the email input
        if not email:
            return Response(status=400, response='Invalid email format.')

        # Send password reset email
        auth.send_password_reset_email(email)
        
        return Response(status=200)
    
    except pyrebase.pyrebase.exceptions.HTTPError as e:
        # Handle HTTP errors, e.g., if the email is not found in the authentication system
        return Response(status=400, response='Email not found in the authentication system.')
    
    except requests.exceptions.RequestException as e:
        # Handle network-related errors
        return Response(status=500, response='Error occurred while processing your request. Please try again later.')


# fixed
@app.route('/rest_page_for_helpee', methods=['GET', 'POST'])
def rest_page_for_helpee():

    # this is the complete data here about the user
    user_data = db.child('people').child('helpee').child(session['user_id']).get().val()
    
    # check if exams are existing in user_data
    if 'exams' in user_data:
        # Fetch exam-specific data from user_data
        return render_template('(helpee)rest_page.html', data=user_data['data'], info=user_data.get('exams'))
    else:
        print("No exam data here")
        return render_template('(helpee)rest_page.html', data=user_data['data'], info=None)
    
@app.route('/rest_page_for_helper', methods=['GET', 'POST'])
def rest_page_for_helper():

    # this is the complete data here about the user
    user_data = session.get('helper_user_data')
    # print("user data:" , user_data['data'])
    
    student_data = db.child('people').child('helpee').get().val()
    # print("Student data", student_data)   

    exams_with_helper_not_found = []

    for user_id, data in student_data.items():
        exams = data.get("exams", {})
        for exam_id, exam_data in exams.items():
            if not exam_data.get("helper_found", True):
                exams_with_helper_not_found.append(exam_data)

    # print(exams_with_helper_not_found)

    # Fetch exam-specific data from user_data
    return render_template('(helper)rest_page.html', data=user_data['data'], exam_info = exams_with_helper_not_found)
    # else:
    #     print("No exam data here")
    #     return render_template('(helper)rest_page.html', data=user_data['data'], info=None)


@app.route('/get_help', methods=['GET', 'POST'])
def get_help():
    try:
        if request.method == 'POST':
            # collecting data from forms
            subject = request.form['exam_needs_help']
            med_language = request.form['language_medium']
            centre = request.form['location']
            exam_date = request.form['exam_date']
            start_time = request.form['exam_time']
            end_time = request.form['time_duration']

            # Data json
            helpee_data = {
                'subject': subject,
                'med_language': med_language,
                'location': centre,
                'exam_date': exam_date,
                'start_time': start_time,
                'end_time': end_time,
                'helper_found': False,
                'name' : session['user_data']['data']['name'],
                'contact' : session['user_data']['data']['self_contact'],
                '_examid' : "",
                '_parentnode' : ""
            }

            # this is adding the data no problems
            key = db.child('people').child('helpee').child(session['user_id']).child('exams').push(helpee_data)
            db.child('people').child('helpee').child(session['user_id']).child('exams').child(key['name']).update({'_examid': key['name']})
            db.child('people').child('helpee').child(session['user_id']).child('exams').child(key['name']).update({'_parentnode': session['user_id']})

            # Fetch the updated user data from the database after submitting the form
            user_data = db.child('people').child('helpee').child(session['user_id']).get().val()
            if user_data:
                # Update the session data for 'user_data' and 'exams'
                session['user_data']['data'] = user_data.get('data', {})
                session['user_data']['exams'] = user_data.get('exams', {})

            flash('Your request for help has been submitted.')  # Display a success message
            return redirect(url_for('rest_page_for_helpee'))  # Redirect to the rest_page

    except Exception as e:
        flash('An error occurred while processing your request. Please try again later.')
        print("Error in get_help:", e)

    # return render_template('(helpee)get_help.html', data=session['user_data']['data']['name'])
    return render_template('(helpee)get_help.html')


# redirects to signin or signup page of helper
@app.route('/sign_in_helper', methods=['GET', 'POST'])
def sign_in_helper():
    if request.method == "POST":
        email = request.form['helper_email']
        password = request.form['helper_password']

        try:
            user = auth.sign_in_with_email_and_password(email, password)
            user_id = user['localId']

            # storing userid in session now
            session['helper_user_id'] = user_id

            # fetch user data from the database
            helper_user_data = db.child('people').child('helper').child(user_id).get().val()
            session['helper_user_data'] = helper_user_data
            # print("helper data: ", session)
            return redirect ('/rest_page_for_helper')

        except requests.exceptions.HTTPError as e:
            # Invalid credentials (HTTP 400 status code)
            return render_template('(helper)login.html', error="Invalid credentials. Please try again.", invalid_input = True)
    
        except requests.exceptions.RequestException as e:
            # Network-related error (e.g., connection error)
            return render_template('(helper)login.html', error="Error occurred during authentication. Please try again later.")

    return render_template('(helper)login.html')

    
@app.route('/sign_up_helper', methods=['GET', 'POST'])
def sign_up_helper():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['cpassword']
            gender = request.form['gender']
            edu = request.form['grade_level']
            institute = request.form['institute_name']
            address = request.form['address']
            contact = request.form['contact_number']
            occupation = request.form['occupation']
            id_proof = request.form['id_proof']

            user = auth.create_user_with_email_and_password(email, password)

            user_id = user['localId']

                # Create a dictionary with user data
            user_data = {
                'name': name,
                'email': email,
                'gender': gender,
                'edu': edu,
                'institute': institute,
                'address': address,
                'contact': contact,
                'occupation' : occupation,
                'id_proof' : id_proof
                }
            
            # Store the user data in the Firebase Realtime Database under the user ID
            db.child('people').child('helper').child(user_id).child('data').set(user_data)
            # Data successfully saved, render the success template
            return redirect('/sign_in_helper')
            
        except Exception as e:
            # Error occurred during sign-up, show an error message
            return render_template('(helper)signup.html', error="An error occurred during sign-up: " + str(e))
        
    return render_template('(helper)signup.html')


@app.route('/help_button_clicked', methods=['POST'])
def help_button_clicked():
    data = request.get_json()  # Get the JSON data sent in the request body
    exam_id = data.get('examid')  # Extract the '_examid' from the JSON data
    parent_node = data.get('parentnode')  # Extract the '_parentnode' from the JSON data

    db.child('people').child('helpee').child(parent_node).child('exams').child(exam_id).update({'helper_found': True})

    helpee_data = db.child('people').child('helpee').child(parent_node).child('data').get().val()
    helper_data = db.child('people').child('helper').child(session['helper_user_id']).child('data').get().val()

    # print('helpee data: ', helpee_data['name'])
    # print('helper data: ', helper_data)

    # return "hi"
    # mailing
    subject_helper = f"This is a confirmation email"
    body_helper = f'''
    Thank You for participating in this cause
    You will be helping {helpee_data['name']} 
    Email : {helpee_data['email']}'''
    subject_helpee = f"This is a confirmation email"
    body_helpee = f'''
    Congrats You Have Found a Helper
    {helper_data['name']} will be helping you  
    Email : {helper_data['email']}'''

    mail_client(helpee_data['email'], subject_helpee, body_helpee)
    mail_client(helper_data['email'], subject_helper, body_helper)

def mail_client(email, subject, body):
        em = EmailMessage()
        em['From'] = email_sender
        em['To'] = email
        em['Subject'] = subject
        em.set_content(body)

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as mail:
            mail.login(email_sender, gmail_password)
            mail.sendmail(email_sender, email, em.as_string())

        return render_template('(a)home_page.html')
        
if __name__ == "__main__":
    app.run(debug=True)
