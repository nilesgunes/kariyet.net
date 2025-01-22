from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import re
from werkzeug.utils import secure_filename


app=Flask(__name__)
app.secret_key = 'my_very_secret_key'# This is required for session handling.

#Got the DB connection here
def get_db_connection():
    conn = sqlite3.connect("job_search.db")
    conn.row_factory = sqlite3.Row
    return conn

#Home Page
@app.route("/")
def home():
    #Got the language from cookie(it is defaulted to English if not set)
    lang=request.cookies.get("lang","en")

    # I Assumed the user's city is determined dynamically but hardcoded Istanbul for the demonstration purposes
    user_city="Istanbul"  #
    conn=get_db_connection()

    #Fetched up to 5 job postings as requested in the assignment
    jobs=conn.execute(
        "SELECT * FROM JobPostings WHERE city = ? LIMIT 5", (user_city,)
    ).fetchall()

    #If fewer than 5 jobs are found, fetch additional postings from other cities
    if len(jobs) < 5:
        additional_jobs = conn.execute(
            "SELECT * FROM JobPostings WHERE city != ? LIMIT ?",
            (user_city, 5 - len(jobs))
        ).fetchall()
        jobs.extend(additional_jobs)

    #Processed the jobs to ensure image paths are correctly prefixed for static files. Please be careful that I am getting the images from /static/images
    processed_jobs = []
    for job in jobs:
        job_dict = dict(job)
        image_path = job_dict['image_path']
        if not image_path.startswith('/static/'):
            image_path = f"/static/images/{image_path}"
        job_dict['image_path'] = image_path
        processed_jobs.append(job_dict)

    conn.close()

    #Pased the jobs city and the lang to the template.
    return render_template("home.html", jobs=processed_jobs, user=session.get("user"), user_city=user_city, lang=lang)

#Login Page Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method=="POST":
        email=request.form["email"]
        password=request.form["password"]

        conn=get_db_connection()
        user=conn.execute(
            "SELECT * FROM Users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        if user:
            profile_pic = "/static/uploads/" + user["profile_picture"] if user["profile_picture"] else "/static/uploads/default.png"#Handled the missing or null profile_picture
            print(f"Profile pic is in: {profile_pic}")
            session["user"] = {
                "user_id": user["user_id"],
                "name": user["name"],
                "surname": user["surname"],
                "email": user["email"],
                "profile_pic": profile_pic,
                "country": user["country"],
                "city": user["city"],
                "preferred_language": user["preferred_language"]
            }
            flash("Login successful!","success")
            conn.close()
            return redirect("/")
        else:
            flash("Invalid email or password.","danger")
            conn.close()
    return render_template("login.html")

#Login Via Google Route
@app.route('/login/google',methods=['GET','POST'])
def login_google():
    if request.method =='POST':
        #Checked if the email is registered via Google
        email =request.form['email']
        conn = get_db_connection()
        user = conn.execute(
            """
            SELECT user_id, name, profile_picture FROM Users
            WHERE email = ? AND google_authenticated = 1
            """,
            (email,)
        ).fetchone()
        conn.close()
        if user :
            # Log in the user
            session['user'] ={
                'user_id': user['user_id'],
                'name': user['name'],
                'email': email,
                'profile_picture': user['profile_picture']
            }
            flash("Login successful via Google!", "success")
            return redirect('/')
        else:
            flash("No Google account is found. Please register first.", "danger")
            return redirect('/login/google')
    return render_template('login_google.html')

# Register Page Route
@app.route("/register",methods=["GET", "POST"])
def register():
    if request.method =="POST":
        #Collected the form data
        name = request.form.get("name")
        surname = request.form.get("surname")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        country = request.form.get("country")
        city = request.form.get("city")
        profile_picture = request.files.get("profile_picture")
        preferred_language = request.form.get("preferred_language", "EN")

        #Validated the required fields. We are told profile pic was optional
        if not all([name, surname, email, password, country, city]):
            flash("All fields except profile picture are required.", "danger")
            return redirect("/register")

        #Password validation is done here via regex
        if len(password) < 8 or not re.search(r"\d", password) or not re.search(r"\W", password):
            flash("Password must be at least 8 characters long, contain at least 1 number, and 1 special character.", "danger")
            return redirect("/register")
        if password !=confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect("/register")

        #Saved the profile picture if provided
        profile_pic_filename ="default.png"
        if profile_picture:
            filename = secure_filename(f"{email}_profile.png")
            profile_pic_filename = filename
            try:
                profile_picture.save(os.path.join(UPLOAD_FOLDER, filename))
            except Exception as e:
                flash("Error while saving the picture. Please try again.","danger")
                print(f"File Save Error: {e}")
                return redirect("/register")

        #Inserted the user into the database
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO Users (name, surname, email, password, profile_picture, country, city, google_authenticated, preferred_language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, surname, email, password, profile_pic_filename, country, city, 0, preferred_language)
            )
            conn.commit()

            #Fetched the newly registered user
            user = conn.execute("SELECT * FROM Users WHERE email = ?", (email,)).fetchone()

            #Automatically logged in the user
            session["user"] ={
                "user_id": user["user_id"],
                "name": user["name"],
                "surname": user["surname"],
                "email": user["email"],
                "profile_pic": f"/static/uploads/{user['profile_picture']}",
                "country": user["country"],
                "city": user["city"],
                "preferred_language": user["preferred_language"]
            }
            flash("Registration successful! You are now logged in.", "success")
            return redirect("/")
        except sqlite3.IntegrityError:
            flash("This email is already registered.", "danger")
        except Exception as e:
            flash("An error occurred during registration. Please try again.", "danger")
            print(f"Database Error: {e}")
        finally:
            conn.close()

    return render_template("register.html")

#Registry Via Google Route
@app.route("/register/google", methods=["POST"])
def register_google():
    email = request.form.get("email")

    #Ensured the email is provided.
    if not email:
        flash("Please provide a valid email address.", "danger")
        return redirect("/register")
    conn =get_db_connection()

    #Checked to see if the user already exists in my DB
    user = conn.execute(
        "SELECT * FROM Users WHERE email = ?",
        (email,)
    ).fetchone()

    if user:
        #IF the user already exists, logged them in.
        session["user"] = {
            "user_id": user["user_id"],
            "name": user["name"] or "Google User",
            "email": user["email"],
            "profile_pic": user["profile_picture"] or "default.png"
        }
        flash("Welcome back! You are logged in.", "success")
        conn.close()
        return redirect("/")

    #Registered the new user with only the email
    try:
        conn.execute(
            """
            INSERT INTO Users (name, surname, email, password, profile_picture, country, city, google_authenticated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (email,email,email,email, "default.png", "N/A", "N/A", 1)
        )
        conn.commit()

        #Fetched the newly created user.
        new_user = conn.execute(
            "SELECT * FROM Users WHERE email = ?",
            (email,)
        ).fetchone()

        #Logged in the newly registered user.
        session["user"] ={
            "user_id": new_user["user_id"],
            "name": new_user["name"] or "Google User",
            "email": new_user["email"],
            "profile_pic": new_user["profile_picture"] or "default.png"
        }
        flash("You have been successfully registered and logged in with Google.", "success")

    except Exception as e:
        flash("An error occurred during Google registration.", "danger")
        print(f"Error: {e}")
    finally:
        conn.close()
    return redirect("/")

# Logout Route
@app.route("/logout")
def logout():
    session.pop("user",None)
    flash("Logged out successfully.","info")
    return redirect(url_for("home"))

#Sarch Route
@app.route("/search")
def search():
    lang = request.cookies.get("lang", "en")

    # Get search parameters
    initial_search = request.args.get("job", "").strip().lower()
    filters = {
        'country': request.args.get("country", "").strip().lower(),
        'city': request.args.get("city", "").strip().lower(),
        'town': request.args.get("town", "").strip().lower(),
        'preference': request.args.get("preference", "").strip().lower()
    }

    # Construct the base query
    base_query = """
        SELECT * FROM JobPostings 
        WHERE (
            LOWER(position_en) LIKE ? 
            OR LOWER(position_tr) LIKE ?
            OR LOWER(description_en) LIKE ?
            OR LOWER(description_tr) LIKE ?
            OR LOWER(expected_skills) LIKE ?
        )
    """
    params = [f"%{initial_search}%"] * 5

    # Add filters to the query
    if filters['country']:
        base_query += " AND LOWER(country) = ?"
        params.append(filters['country'])
    if filters['city']:
        base_query += " AND LOWER(city) = ?"
        params.append(filters['city'])
    if filters['town']:
        base_query += " AND LOWER(town) = ?"
        params.append(filters['town'])
    if filters['preference']:
        base_query += " AND LOWER(working_preference) = ?"
        params.append(filters['preference'])

    # Execute the query
    conn = get_db_connection()
    jobs = conn.execute(base_query, params).fetchall()
    conn.close()

    # Process jobs for frontend rendering
    processed_jobs = []
    for job in jobs:
        job_dict = dict(job)
        if not job_dict['image_path'].startswith('/static/'):
            job_dict['image_path'] = f"/static/images/{job_dict['image_path']}"
        processed_jobs.append(job_dict)

    return render_template("search_results.html", jobs=processed_jobs, user=session.get("user"), lang=lang)


@app.route("/job/<int:job_id>")
def job_details(job_id):
    lang =request.cookies.get("lang","en")
    conn =get_db_connection()
    
    #Fetched the job details including applications count
    job = conn.execute('''
        SELECT *, '/static/images/' || image_path AS full_image_path,
               (SELECT COUNT(*) FROM Applications WHERE job_id = JobPostings.job_id) as applications_count
        FROM JobPostings
        WHERE job_id = ?
    ''', (job_id,)).fetchone()
    if not job:
        conn.close()
        return render_template("404.html", lang=lang), 404

    #Checked if the current user has already applied. If applied not apply button is showed.
    has_applied =False
    if 'user' in session:
        has_applied = conn.execute('''
            SELECT 1 FROM Applications 
            WHERE job_id = ? AND user_id = ?
        ''', (job_id, session['user']['user_id'])).fetchone() is not None

    #Fetched the similar jobs
    similar_jobs = conn.execute('''
        SELECT *, '/static/images/' || image_path AS full_image_path,
               (SELECT COUNT(*) FROM Applications WHERE job_id = JobPostings.job_id) as applications_count
        FROM JobPostings
        WHERE city = ? AND job_id != ?
        LIMIT 3
    ''', (job["city"], job_id)).fetchall()
    conn.close()

    return render_template(
        "job_posting_details.html",
        job=job,
        similar_jobs=similar_jobs,
        user=session.get("user"),
        has_applied=has_applied,
        lang=lang
    )

@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_to_job(job_id):
    if "user" not in session:
        flash("Please log in to apply for this job.","info")
        return redirect("/login")

    user_id = session["user"]["user_id"]
    conn = get_db_connection()

    try:
        #Tried to insert the application.
        conn.execute('''
            INSERT INTO Applications (job_id, user_id, application_date)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (job_id, user_id))

        #Updated the applications count in JobPostings here.
        conn.execute('''
            UPDATE JobPostings 
            SET applications_count = applications_count + 1
            WHERE job_id = ?
        ''', (job_id,))
        conn.commit()
        flash("Your application has been submitted successfully.", "success")

    except sqlite3.IntegrityError:
        # This will be triggered if the user has already applied
        flash("You have already applied to this job.", "warning")
    except Exception as e:
        print(f"Error: {e}")
        flash("An error occurred while submitting your application.", "danger")
    finally:
        conn.close()
    return redirect(f"/job/{job_id}")

# Autocomplete Endpoint
@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    search_query = request.args.get("q", "").lower() # User's input is received here 
    field = request.args.get("field", "") # Which field to search (job title or city) is received here.
    conn = get_db_connection()
    if field == "position":
        #Autocompletion for job titles
        results = conn.execute(
            "SELECT DISTINCT position_en FROM JobPostings WHERE LOWER(position_en) LIKE ? LIMIT 10",
            (f"%{search_query}%",)
        ).fetchall()
    elif field == "city":
        #Autocompletion for cities
        results = conn.execute(
            "SELECT DISTINCT city FROM JobPostings WHERE LOWER(city) LIKE ? LIMIT 10",
            (f"%{search_query}%",)
        ).fetchall()
    else:
        return jsonify([])#Returned an empty list for invalid field
    conn.close()
    return jsonify([row[0] for row in results])#Returned the results as a JSON array

if __name__ == "__main__":
    UPLOAD_FOLDER = "static/uploads"
    #Ensured the uploads folder exists
    os.makedirs(UPLOAD_FOLDER,exist_ok=True)
    app.run(debug=True, port=5001)
