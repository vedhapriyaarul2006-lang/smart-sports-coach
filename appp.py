from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from flask_sqlalchemy import SQLAlchemy

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from flask_mail import Mail, Message

from apscheduler.schedulers.background import BackgroundScheduler

from datetime import datetime, date, timedelta

from zoneinfo import ZoneInfo

import os

import threading


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "smart-sports-coach-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///smart_sports.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# =========================================================
# EMAIL CONFIGURATION
# =========================================================

app.config["MAIL_SERVER"] = "smtp.gmail.com"

app.config["MAIL_PORT"] = 587

app.config["MAIL_USE_TLS"] = True

app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")

app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
    "MAIL_DEFAULT_SENDER"
) or app.config["MAIL_USERNAME"]

db = SQLAlchemy(app)

mail = Mail(app)


# =========================================================
# DATABASE MODELS
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    assessments = db.relationship(
        "HealthAssessment",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )


class HealthAssessment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    age = db.Column(db.Integer)

    gender = db.Column(db.String(30))

    height = db.Column(db.Float)

    weight = db.Column(db.Float)

    activity_level = db.Column(db.String(50))

    fitness_goal = db.Column(db.String(100))

    sleep_duration = db.Column(db.Float)

    water_intake = db.Column(db.Float)

    recommended_water = db.Column(db.Float)

    eating_habits = db.Column(db.String(200))

    medical_conditions = db.Column(db.String(300))

    preferred_sports_environment = db.Column(
        db.String(100)
    )

    available_exercise_time = db.Column(
        db.Integer
    )

    bmi = db.Column(db.Float)

    bmi_category = db.Column(db.String(50))

    health_score = db.Column(db.Float)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
# =========================================================
# NOTIFICATION SETTINGS
# =========================================================
class NotificationSettings(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        unique=True,
        nullable=False
    )

    workout_reminder = db.Column(
        db.Boolean,
        default=True
    )

    water_reminder = db.Column(
        db.Boolean,
        default=True
    )

    sleep_reminder = db.Column(
        db.Boolean,
        default=True
    )

    email_notification = db.Column(
        db.Boolean,
        default=True
    )

    reminder_time = db.Column(
        db.String(5),
        default="08:00"
    )

    last_sent_date = db.Column(
        db.Date,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def calculate_bmi(weight, height):

    if weight <= 0 or height <= 0:
        return 0

    height_m = height / 100

    bmi = weight / (height_m * height_m)

    return round(bmi, 2)


def get_bmi_category(bmi):

    if bmi < 18.5:
        return "Underweight"

    elif bmi < 25:
        return "Normal"

    elif bmi < 30:
        return "Overweight"

    else:
        return "Obesity"


def calculate_water(weight):

    if weight <= 0:
        return 0

    return round((weight * 35) / 1000, 2)


def calculate_health_score(
    bmi,
    sleep,
    water,
    recommended_water,
    activity_level,
    eating_habits
):

    score = 0

    # BMI score
    if 18.5 <= bmi < 25:
        score += 25

    elif 17 <= bmi < 30:
        score += 18

    else:
        score += 12

    # Sleep score
    if 7 <= sleep <= 9:
        score += 25

    elif 6 <= sleep < 7 or 9 < sleep <= 10:
        score += 18

    else:
        score += 10

    # Water score
    if recommended_water > 0:

        ratio = water / recommended_water

        if 0.8 <= ratio <= 1.2:
            score += 25

        elif 0.6 <= ratio < 0.8:
            score += 18

        elif ratio > 1.2:
            score += 15

        else:
            score += 10

    else:
        score += 10

    # Activity score
    activity = str(activity_level).lower()

    if "very active" in activity or "high" in activity:
        score += 25

    elif "active" in activity or "moderate" in activity:
        score += 20

    elif "light" in activity or "low" in activity:
        score += 15

    else:
        score += 10

    return round(min(score, 100), 1)


def get_health_status(score):

    if score >= 80:

        return (
            "Excellent Health",
            "Your lifestyle indicators are looking strong. "
            "Continue your healthy habits."
        )

    elif score >= 60:

        return (
            "Good Health",
            "You have a good foundation. Focus on consistency "
            "in exercise, sleep, hydration and nutrition."
        )

    elif score >= 40:

        return (
            "Needs Improvement",
            "Some lifestyle areas need attention. "
            "Improve gradually using your recommendations."
        )

    else:

        return (
            "Needs Attention",
            "Start with small healthy habits and improve "
            "your lifestyle step by step."
        )


# =========================================================
# RECOMMENDATIONS
# =========================================================

def generate_recommendations(assessment):

    recommendations = []

    bmi = float(assessment.bmi or 0)

    goal = str(
        assessment.fitness_goal or ""
    ).lower()

    activity = str(
        assessment.activity_level or ""
    ).lower()

    sleep = float(
        assessment.sleep_duration or 0
    )

    water = float(
        assessment.water_intake or 0
    )

    recommended_water = float(
        assessment.recommended_water or 0
    )

    # BMI recommendation
    if bmi >= 30:

        recommendations.append({
            "title": "Low-Impact Cardio",
            "category": "BMI Improvement",
            "priority": "High Priority",
            "reason": (
                "Try walking, cycling and other low-impact "
                "activities to improve fitness gradually."
            ),
            "icon": "🚶"
        })

    elif bmi >= 25:

        recommendations.append({
            "title": "Brisk Walking",
            "category": "BMI Improvement",
            "priority": "High Priority",
            "reason": (
                "Try regular brisk walking and gradually "
                "increase your walking duration."
            ),
            "icon": "🏃"
        })

    elif bmi < 18.5:

        recommendations.append({
            "title": "Strength Training",
            "category": "Body Strength",
            "priority": "Medium Priority",
            "reason": (
                "Focus on safe strength exercises and "
                "nutrient-rich foods."
            ),
            "icon": "💪"
        })

    else:

        recommendations.append({
            "title": "Balanced Fitness",
            "category": "General Fitness",
            "priority": "Medium Priority",
            "reason": (
                "Maintain a combination of cardio, "
                "strength and flexibility exercises."
            ),
            "icon": "🏋️"
        })

    # Fitness goal
    if (
        "weight" in goal
        or "lose" in goal
        or "fat" in goal
    ):

        recommendations.append({
            "title": "Weight Management",
            "category": "Fitness Goal",
            "priority": "High Priority",
            "reason": (
                "Combine cardio, strength exercises "
                "and balanced eating habits."
            ),
            "icon": "🔥"
        })

    elif (
        "muscle" in goal
        or "strength" in goal
        or "build" in goal
    ):

        recommendations.append({
            "title": "Strength Building",
            "category": "Fitness Goal",
            "priority": "High Priority",
            "reason": (
                "Include progressive strength exercises "
                "and adequate recovery."
            ),
            "icon": "💪"
        })

    elif (
        "flexibility" in goal
        or "flex" in goal
        or "yoga" in goal
    ):

        recommendations.append({
            "title": "Flexibility Training",
            "category": "Fitness Goal",
            "priority": "Medium Priority",
            "reason": (
                "Practice yoga and stretching exercises "
                "to improve flexibility."
            ),
            "icon": "🧘"
        })

    else:

        recommendations.append({
            "title": "General Fitness",
            "category": "Fitness Goal",
            "priority": "Medium Priority",
            "reason": (
                "Build a balanced routine using cardio, "
                "strength and flexibility activities."
            ),
            "icon": "⭐"
        })

    # Activity recommendation
    if (
        "sedentary" in activity
        or "beginner" in activity
        or "low" in activity
    ):

        recommendations.append({
            "title": "Start Gradually",
            "category": "Activity Level",
            "priority": "High Priority",
            "reason": (
                "Begin with manageable exercise sessions "
                "and increase activity slowly."
            ),
            "icon": "🌱"
        })

    elif "moderate" in activity:

        recommendations.append({
            "title": "Build Consistency",
            "category": "Activity Level",
            "priority": "Medium Priority",
            "reason": (
                "Maintain regular weekly activity and "
                "gradually increase exercise duration."
            ),
            "icon": "📈"
        })

    else:

        recommendations.append({
            "title": "Maintain Your Routine",
            "category": "Activity Level",
            "priority": "Medium Priority",
            "reason": (
                "Continue your routine and include "
                "suitable recovery days."
            ),
            "icon": "🔥"
        })

    # Sleep recommendation
    if sleep < 7:

        recommendations.append({
            "title": "Improve Sleep",
            "category": "Sleep",
            "priority": "High Priority",
            "reason": (
                "Follow a consistent sleep schedule and "
                "aim for 7 to 9 hours."
            ),
            "icon": "😴"
        })

    elif sleep > 9:

        recommendations.append({
            "title": "Review Sleep Routine",
            "category": "Sleep",
            "priority": "Medium Priority",
            "reason": (
                "Maintain a consistent sleep schedule "
                "and notice your energy levels."
            ),
            "icon": "🌙"
        })

    else:

        recommendations.append({
            "title": "Maintain Healthy Sleep",
            "category": "Sleep",
            "priority": "Low Priority",
            "reason": (
                "Continue maintaining your healthy sleep routine."
            ),
            "icon": "✨"
        })

    # Hydration recommendation
    if recommended_water > 0:

        ratio = water / recommended_water

        if ratio < 0.8:

            recommendations.append({
                "title": "Increase Hydration",
                "category": "Hydration",
                "priority": "High Priority",
                "reason": (
                    "Your water intake is below the project "
                    "baseline. Drink water regularly."
                ),
                "icon": "💧"
            })

        elif ratio <= 1.2:

            recommendations.append({
                "title": "Hydration On Track",
                "category": "Hydration",
                "priority": "Low Priority",
                "reason": (
                    "Your water intake is close to the "
                    "recommended project baseline."
                ),
                "icon": "💦"
            })

        else:

            recommendations.append({
                "title": "Review Water Intake",
                "category": "Hydration",
                "priority": "Medium Priority",
                "reason": (
                    "Your water intake is above the project "
                    "baseline. Avoid excessive water intake."
                ),
                "icon": "💧"
            })

    return recommendations

# =========================================================
# EMAIL FUNCTIONS
# =========================================================
def send_assessment_email(user, assessment):

    try:

        import requests
        import os

        subject = (
            "Smart Sports Coach - Health Assessment Result"
        )

        body = f"""
Hello {user.name},

Your health assessment has been completed successfully.

Your health summary:

Health Score: {assessment.health_score}/100

BMI: {assessment.bmi}

BMI Category: {assessment.bmi_category}

Recommended Water Intake:
{assessment.recommended_water} litres per day

Sleep Duration:
{assessment.sleep_duration} hours

Activity Level:
{assessment.activity_level}

Fitness Goal:
{assessment.fitness_goal}

Please follow your personalized recommendations.

Thank you for using Smart Sports Coach.

Regards,
Smart Sports Coach Team
"""

        api_key = os.environ.get("RESEND_API_KEY")

        if not api_key:
            print("Assessment email error: RESEND_API_KEY is not configured.")
            return

        response = requests.post(
            "https://api.resend.com/emails",

            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },

            json={
                "from": "Smart Sports Coach <onboarding@resend.dev>",
                "to": [user.email],
                "subject": subject,
                "text": body
            },

            timeout=10
        )

        if response.status_code in (200, 201):

            print(
                "Assessment email sent to:",
                user.email
            )

        else:

            print(
                "Assessment email error:",
                response.status_code,
                response.text
            )

    except Exception as error:

        print(
            "Assessment email error:",
            error
        )
# =========================================================
# BACKGROUND ASSESSMENT EMAIL
# =========================================================
def send_assessment_email_background(user_id, assessment_id):
    try:
        with app.app_context():

            # Load fresh database objects inside this background thread
            user = User.query.get(user_id)
            assessment = HealthAssessment.query.get(assessment_id)

            if not user or not assessment:
                print("Background email error: User or assessment not found.")
                return

            send_assessment_email(user, assessment)

    except Exception as error:
        print("Background assessment email error:", error)


def send_notification_email(
    user,
    notification_settings
):

    try:

        assessment = (
            HealthAssessment.query
            .filter_by(
                user_id=user.id
            )
            .order_by(
                HealthAssessment.created_at.desc()
            )
            .first()
        )

        reminder_items = []

        # Workout reminder
        if notification_settings.workout_reminder:

            reminder_items.append(
                "Workout Reminder\n"
                "Complete your planned workout today."
            )

        # Water reminder
        if notification_settings.water_reminder:

            water_text = (
                "Drink enough water throughout the day."
            )

            if (
                assessment
                and assessment.recommended_water
            ):

                water_text = (
                    f"Try to drink about "
                    f"{assessment.recommended_water} "
                    "litres of water today."
                )

            reminder_items.append(
                f"Water Reminder\n{water_text}"
            )

        # Sleep reminder
        if notification_settings.sleep_reminder:

            reminder_items.append(
                "Sleep Reminder\n"
                "Aim for 7 to 9 hours of quality sleep tonight."
            )

        # If no reminders are selected
        if not reminder_items:

            return False

        body = f"""Hello {user.name},

This is your personalized health reminder from Smart Sports Coach.

Today's reminders:

{"\n\n".join(reminder_items)}

Small healthy habits create long-term results.

Stay active and stay healthy!

Regards,
Smart Sports Coach Team
"""

        message = Message(
            subject="Smart Sports Coach - Health Reminder",
            recipients=[user.email],
            body=body
        )

        mail.send(message)

        print(
            "Personalized reminder sent to:",
            user.email
        )

        return True

    except Exception as error:

        print(
            "Personalized reminder error:",
            error
        )

        return False
    

# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email or not password:

            flash(
                "Please fill in all fields.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "Email already registered.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(user)

        db.session.commit()

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            session["user_id"] = user.id

            session["user_name"] = user.name

            flash(
                "Login successful!",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("index")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    if user is None:

        session.clear()

        return redirect(
            url_for("login")
        )

    assessments = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.asc(),
            HealthAssessment.id.asc()
        )
        .all()
    )

    assessment = (
        assessments[-1]
        if assessments
        else None
    )

    if assessment is None:

        return render_template(
            "dashboard.html",
            user=user,
            assessment=None,
            recommendations=[],
            score_change=0,
            bmi_change=0,
            water_change=0,
            sleep_change=0,
            health_status="Not Assessed",
            health_message=(
                "Complete your health assessment to receive "
                "personalized guidance."
            ),
            recommended_sport="Walking"
        )

    previous = (
        assessments[-2]
        if len(assessments) > 1
        else None
    )

    score_change = 0
    bmi_change = 0
    water_change = 0
    sleep_change = 0

    if previous:

        score_change = round(
            (assessment.health_score or 0)
            - (previous.health_score or 0),
            1
        )

        bmi_change = round(
            (assessment.bmi or 0)
            - (previous.bmi or 0),
            1
        )

        water_change = round(
            (assessment.water_intake or 0)
            - (previous.water_intake or 0),
            2
        )

        sleep_change = round(
            (assessment.sleep_duration or 0)
            - (previous.sleep_duration or 0),
            1
        )

    health_status, health_message = get_health_status(
        float(assessment.health_score or 0)
    )

    goal = str(
        assessment.fitness_goal or ""
    ).lower()

    if (
        "weight" in goal
        or "lose" in goal
        or "fat" in goal
    ):

        recommended_sport = "Brisk Walking"

    elif (
        "muscle" in goal
        or "strength" in goal
        or "build" in goal
    ):

        recommended_sport = "Strength Training"

    elif (
        "flex" in goal
        or "yoga" in goal
        or "mobility" in goal
    ):

        recommended_sport = "Yoga"

    else:

        recommended_sport = "Walking"

    return render_template(
        "dashboard.html",
        user=user,
        assessment=assessment,
        recommendations=generate_recommendations(
            assessment
        ),
        score_change=score_change,
        bmi_change=bmi_change,
        water_change=water_change,
        sleep_change=sleep_change,
        health_status=health_status,
        health_message=health_message,
        recommended_sport=recommended_sport
    )


# =========================================================
# HEALTH ASSESSMENT
# =========================================================

@app.route(
    "/assessment",
    methods=["GET", "POST"]
)
def assessment():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    if user is None:

        session.clear()

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        try:

            age = int(
                request.form.get(
                    "age",
                    0
                )
            )

            gender = request.form.get(
                "gender",
                ""
            )

            height = float(
                request.form.get(
                    "height",
                    0
                )
            )

            weight = float(
                request.form.get(
                    "weight",
                    0
                )
            )

            activity_level = request.form.get(
                "activity_level",
                ""
            )

            fitness_goal = request.form.get(
                "fitness_goal",
                ""
            )

            sleep_duration = float(
                request.form.get(
                    "sleep_duration",
                    0
                )
            )

            water_intake = float(
                request.form.get(
                    "water_intake",
                    0
                )
            )

            eating_habits = request.form.get(
                "eating_habits",
                ""
            )

            medical_conditions = request.form.get(
                "medical_conditions",
                ""
            )

            preferred_environment = request.form.get(
                "preferred_sports_environment",
                ""
            )

            available_exercise_time = int(
                request.form.get(
                    "available_exercise_time",
                    0
                )
            )

        except (
            ValueError,
            TypeError
        ):

            flash(
                "Please enter valid values.",
                "error"
            )

            return redirect(
                url_for("assessment")
            )

        if age <= 0:

            flash(
                "Please enter a valid age.",
                "error"
            )

            return redirect(
                url_for("assessment")
            )

        if height <= 0 or weight <= 0:

            flash(
                "Height and weight must be greater than zero.",
                "error"
            )

            return redirect(
                url_for("assessment")
            )

        bmi = calculate_bmi(
            weight,
            height
        )

        category = get_bmi_category(
            bmi
        )

        recommended_water = calculate_water(
            weight
        )

        health_score = calculate_health_score(
            bmi=bmi,
            sleep=sleep_duration,
            water=water_intake,
            recommended_water=recommended_water,
            activity_level=activity_level,
            eating_habits=eating_habits
        )

        new_assessment = HealthAssessment(

            user_id=user.id,

            age=age,

            gender=gender,

            height=height,

            weight=weight,

            activity_level=activity_level,

            fitness_goal=fitness_goal,

            sleep_duration=sleep_duration,

            water_intake=water_intake,

            recommended_water=recommended_water,

            eating_habits=eating_habits,

            medical_conditions=medical_conditions,

            preferred_sports_environment=preferred_environment,

            available_exercise_time=available_exercise_time,

            bmi=bmi,

            bmi_category=category,

            health_score=health_score,

            created_at=datetime.utcnow()
        )

        db.session.add(
            new_assessment
        )

        db.session.commit()

        # Send assessment email in the background
        email_thread = threading.Thread(
           target=send_assessment_email_background,
           args=(user.id, new_assessment.id),
           daemon=True
        )
        email_thread.start()


        flash(
            "Assessment completed successfully!",
            "success"
        )

        return redirect(
            url_for("result")
        )

    return render_template(
        "assessment.html",
        user=user
    )

# =========================================================
# WORKOUT MODEL
# =========================================================

class Workout(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    workout_name = db.Column(
        db.String(100),
        nullable=False
    )

    category = db.Column(
        db.String(50),
        nullable=False
    )

    duration = db.Column(
        db.Integer,
        nullable=False
    )

    calories_burned = db.Column(
        db.Integer,
        nullable=False
    )

    workout_date = db.Column(
        db.Date,
        nullable=False
    )

    completed = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "workouts",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )
# =========================================================
# DATABASE INITIALIZATION
# =========================================================

with app.app_context():
    db.create_all()

# =========================================================
# RESULT
# =========================================================

@app.route("/result")
def result():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    assessment = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    if assessment is None:

        return redirect(
            url_for("assessment")
        )

    return render_template(
        "result.html",
        user=user,
        assessment=assessment,
        recommendations=generate_recommendations(
            assessment
        )
    )


# =========================================================
# RECOMMENDATIONS
# =========================================================

@app.route("/recommendations")
def recommendations():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    assessment = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    if assessment is None:

        flash(
            "Please complete your health assessment first.",
            "error"
        )

        return redirect(
            url_for("assessment")
        )

    recommendations_list = generate_recommendations(
        assessment
    )

    score = float(
        assessment.health_score or 0
    )

    health_status, health_message = get_health_status(
        score
    )

    priority_actions = [
        item["title"]
        for item in recommendations_list
        if item["priority"] == "High Priority"
    ]

    previous = (
        HealthAssessment.query
        .filter(
            HealthAssessment.user_id == user.id,
            HealthAssessment.id != assessment.id
        )
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    progress_change = None

    if previous:

        progress_change = round(
            score - float(previous.health_score or 0),
            1
        )

    return render_template(
        "recommendations.html",
        user=user,
        assessment=assessment,
        recommendations_list=recommendations_list,
        health_status=health_status,
        health_message=health_message,
        progress_status="Keep improving",
        priority_actions=priority_actions,
        sports=[
            "Walking",
            "Cycling",
            "Yoga",
            "Stretching",
            "Bodyweight Exercises"
        ],
        progress_message=(
            f"Your latest health score is "
            f"{round(score)}/100."
        ),
        progress_change=progress_change
    )


# =========================================================
# WEEKLY PLAN
# =========================================================

@app.route("/weekly-plan")
def weekly_plan():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    assessment = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    if assessment is None:

        return redirect(
            url_for("assessment")
        )

    goal = str(
        assessment.fitness_goal or ""
    ).lower()

    if (
        "weight" in goal
        or "lose" in goal
        or "fat" in goal
    ):

        schedule = [
            ("Monday", "Brisk Walking", "25 min"),
            ("Tuesday", "Bodyweight Strength", "20 min"),
            ("Wednesday", "Stretching", "15 min"),
            ("Thursday", "Low Impact Cardio", "25 min"),
            ("Friday", "Bodyweight Strength", "20 min"),
            ("Saturday", "Walking / Cycling", "30 min"),
            ("Sunday", "Recovery", "Rest")
        ]

    elif (
        "muscle" in goal
        or "strength" in goal
        or "build" in goal
    ):

        schedule = [
            ("Monday", "Strength Training", "25 min"),
            ("Tuesday", "Walking", "20 min"),
            ("Wednesday", "Strength Training", "25 min"),
            ("Thursday", "Stretching", "15 min"),
            ("Friday", "Strength Training", "25 min"),
            ("Saturday", "Light Cardio", "20 min"),
            ("Sunday", "Recovery", "Rest")
        ]

    else:

        schedule = [
            ("Monday", "Brisk Walking", "25 min"),
            ("Tuesday", "Strength Training", "20 min"),
            ("Wednesday", "Yoga", "20 min"),
            ("Thursday", "Cycling / Walking", "25 min"),
            ("Friday", "Strength Training", "20 min"),
            ("Saturday", "Cardio", "30 min"),
            ("Sunday", "Recovery", "Rest")
        ]

    return render_template(
        "weekly_plan.html",
        user=user,
        assessment=assessment,
        schedule=schedule
    )


# =========================================================
# FITNESS PLAN
# =========================================================

@app.route("/fitness-plan")
def fitness_plan():

    return redirect(
        url_for("weekly_plan")
    )

# =========================================================
# PROGRESS
# =========================================================

@app.route("/progress")
def progress():

    # Check login
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get logged-in user
    user = db.session.get(
        User,
        session["user_id"]
    )

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    # =====================================================
    # HEALTH ASSESSMENT DATA
    # =====================================================

    assessments = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .all()
    )

    assessment = (
        assessments[0]
        if assessments
        else None
    )

    health_score = 0
    bmi = 0
    water_intake = 0
    sleep_duration = 0
    activity_level = "Not specified"

    if assessment:

        health_score = float(
            assessment.health_score or 0
        )

        bmi = float(
            assessment.bmi or 0
        )

        water_intake = float(
            assessment.water_intake or 0
        )

        sleep_duration = float(
            assessment.sleep_duration or 0
        )

        activity_level = (
            assessment.activity_level
            or "Not specified"
        )

    # =====================================================
    # ACTIVITY PROGRESS
    # =====================================================

    activity_name = str(
        activity_level
    ).lower()

    if (
        "very active" in activity_name
        or "high" in activity_name
    ):

        activity_progress = 100

    elif (
        "moderate" in activity_name
        or "active" in activity_name
    ):

        activity_progress = 75

    elif (
        "light" in activity_name
        or "low" in activity_name
    ):

        activity_progress = 40

    elif "sedentary" in activity_name:

        activity_progress = 20

    else:

        activity_progress = 0

    # =====================================================
    # SLEEP PROGRESS
    # =====================================================

    sleep_progress = min(
        (sleep_duration / 8) * 100,
        100
    )

    # =====================================================
    # HYDRATION PROGRESS
    # =====================================================

    hydration_progress = 0

    if assessment and assessment.weight:

        water_target = (
            float(assessment.weight) * 0.035
        )

        if water_target > 0:

            hydration_progress = min(
                (water_intake / water_target) * 100,
                100
            )

    # =====================================================
    # BMI PROGRESS
    # =====================================================

    if bmi == 0:

        bmi_progress = 0

    elif 18.5 <= bmi <= 24.9:

        bmi_progress = 100

    elif bmi < 18.5:

        bmi_progress = 70

    else:

        bmi_progress = 50

    # =====================================================
    # WORKOUT TRACKER DATA
    # =====================================================

    workouts = (
        Workout.query
        .filter_by(user_id=user.id)
        .order_by(
            Workout.workout_date.desc(),
            Workout.id.desc()
        )
        .all()
    )

    # Total number of workouts
    total_workouts = len(workouts)

    # Completed workouts
    completed_workouts = sum(
        1
        for workout in workouts
        if workout.completed
    )

    # Total calories burned
    total_calories = sum(
        workout.calories_burned or 0
        for workout in workouts
    )

    # Total workout minutes
    total_minutes = sum(
        workout.duration or 0
        for workout in workouts
    )

    # Workout completion percentage
    if total_workouts > 0:

        workout_progress = round(
            (completed_workouts / total_workouts) * 100,
            1
        )

    else:

        workout_progress = 0

    # =====================================================
    # WEEKLY WORKOUT CHART DATA
    # =====================================================

    today = date.today()

    # Monday of the current week
    week_start = today - timedelta(days=today.weekday())

    weekly_workout_minutes = {
        "Monday": 0,
        "Tuesday": 0,
        "Wednesday": 0,
        "Thursday": 0,
        "Friday": 0,
        "Saturday": 0,
        "Sunday": 0
    }

    for workout in workouts:

        if workout.workout_date:

            workout_date = workout.workout_date

            # Convert datetime into date
            if hasattr(workout_date, "date"):
               workout_date = workout_date.date()

            # Check whether workout belongs to this week
            if week_start <= workout_date <= today:

                day_name = workout_date.strftime("%A")

                weekly_workout_minutes[day_name] += (
                  workout.duration or 0
            )

    # =====================================================
    # SEND DATA TO PROGRESS HTML PAGE
    # =====================================================
    print("WEEKLY DATA:", weekly_workout_minutes)
    
    return render_template(
        "progress.html",

        user=user,

        assessment=assessment,

        assessments=assessments,

        # Health details
        health_score=round(
            health_score,
            1
        ),

        bmi=round(
            bmi,
            1
        ),

        water_intake=round(
            water_intake,
            1
        ),

        sleep_duration=round(
            sleep_duration,
            1
        ),

        activity_level=activity_level,

        # Health progress values
        activity_progress=round(
            activity_progress,
            2
        ),

        sleep_progress=round(
            sleep_progress,
            2
        ),

        hydration_progress=round(
            hydration_progress,
            2
        ),

        bmi_progress=round(
            bmi_progress,
            2
        ),

        # Workout tracker values
        workouts=workouts,

        total_workouts=total_workouts,

        completed_workouts=completed_workouts,

        total_calories=total_calories,

        total_minutes=total_minutes,

        workout_progress=workout_progress,

        weekly_workout_minutes=weekly_workout_minutes
    )


# =========================================================
# NUTRITION PLANNER
# =========================================================

@app.route("/nutrition")
def nutrition():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(
        User,
        session["user_id"]
    )

    if not user:
        session.clear()
        return redirect(url_for("login"))

    assessment = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    if not assessment:

        flash(
            "Please complete your health assessment first.",
            "error"
        )

        return redirect(
            url_for("assessment")
        )

    # -----------------------------------------------------
    # FITNESS GOAL
    # -----------------------------------------------------

    fitness_goal = (
        assessment.fitness_goal
        or "General Fitness"
    )

    goal = fitness_goal.lower()

    # -----------------------------------------------------
    # DEFAULT PLAN
    # -----------------------------------------------------

    nutrition_plan = {
        "breakfast": [
            "Oats with banana and milk",
            "2 boiled eggs",
            "A small handful of nuts"
        ],

        "lunch": [
            "Brown rice or chapati",
            "Dal or lean protein",
            "Mixed vegetables",
            "Curd"
        ],

        "snacks": [
            "Fruit",
            "Nuts or seeds",
            "Buttermilk"
        ],

        "dinner": [
            "Chapati or light rice",
            "Vegetable curry",
            "Dal or lean protein",
            "Salad"
        ]
    }

    # -----------------------------------------------------
    # WEIGHT LOSS
    # -----------------------------------------------------

    if (
        "weight loss" in goal
        or "lose weight" in goal
        or "fat loss" in goal
        or "weight" in goal
    ):

        nutrition_focus = (
            "Focus on balanced portions, vegetables, "
            "whole grains, fruits and lean protein. "
            "Limit highly processed and sugary foods."
        )

        nutrition_plan = {

            "breakfast": [
                "Vegetable oats",
                "2 boiled eggs",
                "One fruit"
            ],

            "lunch": [
                "2 chapatis or moderate brown rice",
                "Dal or grilled lean protein",
                "Large portion of vegetables",
                "Curd"
            ],

            "snacks": [
                "Apple or orange",
                "Small handful of nuts",
                "Green tea without added sugar"
            ],

            "dinner": [
                "2 chapatis",
                "Vegetable curry",
                "Dal or lean protein",
                "Salad"
            ]
        }

    # -----------------------------------------------------
    # MUSCLE / STRENGTH
    # -----------------------------------------------------

    elif (
        "muscle" in goal
        or "strength" in goal
        or "build" in goal
    ):

        nutrition_focus = (
            "Focus on adequate protein, nutrient-dense "
            "carbohydrates, vegetables and healthy fats "
            "to support training and recovery."
        )

        nutrition_plan = {

            "breakfast": [
                "Oats with milk and banana",
                "2–3 eggs",
                "Peanut butter toast"
            ],

            "lunch": [
                "Rice or chapati",
                "Chicken, fish, paneer or dal",
                "Mixed vegetables",
                "Curd"
            ],

            "snacks": [
                "Banana",
                "Milk or curd",
                "Nuts"
            ],

            "dinner": [
                "Rice or chapati",
                "Paneer, fish, chicken or dal",
                "Vegetables",
                "Salad"
            ]
        }

    # -----------------------------------------------------
    # FLEXIBILITY / YOGA
    # -----------------------------------------------------

    elif (
        "flexibility" in goal
        or "flex" in goal
        or "yoga" in goal
        or "mobility" in goal
    ):

        nutrition_focus = (
            "Focus on a balanced diet with fruits, "
            "vegetables, whole grains, protein and "
            "adequate hydration."
        )

        nutrition_plan = {

            "breakfast": [
                "Oats with fruit",
                "Boiled eggs or paneer",
                "Milk"
            ],

            "lunch": [
                "Brown rice or chapati",
                "Dal",
                "Mixed vegetables",
                "Curd"
            ],

            "snacks": [
                "Seasonal fruit",
                "Nuts",
                "Buttermilk"
            ],

            "dinner": [
                "Light chapati or rice",
                "Vegetable curry",
                "Dal or paneer",
                "Salad"
            ]
        }

    # -----------------------------------------------------
    # GENERAL FITNESS
    # -----------------------------------------------------

    else:

        nutrition_focus = (
            "Maintain a balanced diet containing vegetables, "
            "fruits, whole grains, protein-rich foods and "
            "healthy fats."
        )

    return render_template(
        "nutrition.html",
        user=user,
        assessment=assessment,
        fitness_goal=fitness_goal,
        nutrition_focus=nutrition_focus,
        nutrition_plan=nutrition_plan
    )

# =========================================================
# HYDRATION
# =========================================================

@app.route("/hydration")
def hydration():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    assessment = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    if assessment is None:

        return redirect(
            url_for("assessment")
        )

    return render_template(
        "hydration.html",
        user=user,
        assessment=assessment
    )


# =========================================================
# EXERCISE VIDEOS
# =========================================================

@app.route("/exercise-videos")
def exercise_videos():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    assessment = (
        HealthAssessment.query
        .filter_by(user_id=user.id)
        .order_by(
            HealthAssessment.created_at.desc(),
            HealthAssessment.id.desc()
        )
        .first()
    )

    if assessment is None:

        flash(
            "Please complete your health assessment first.",
            "error"
        )

        return redirect(
            url_for("assessment")
        )

    fitness_goal = (
        assessment.fitness_goal
        or "General Fitness"
    )

    activity_level = (
        assessment.activity_level
        or "Beginner"
    )

    preferred_environment = (
        assessment.preferred_sports_environment
        or "Any"
    )

    exercises = [

        {
            "name": "Brisk Walking",
            "icon": "🚶",
            "category": "Cardio",
            "level": "Beginner",
            "duration": "20–30 min",
            "description": (
                "A simple low-impact cardio activity."
            ),
            "video": (
                "https://www.youtube.com/results?search_query="
                "brisk+walking+beginner+exercise"
            )
        },

        {
            "name": "Bodyweight Squats",
            "icon": "🏋️",
            "category": "Strength",
            "level": "Beginner",
            "duration": "10–15 min",
            "description": (
                "A lower-body exercise for functional strength."
            ),
            "video": (
                "https://www.youtube.com/results?search_query="
                "bodyweight+squat+beginner+proper+form"
            )
        },

        {
            "name": "Beginner Yoga",
            "icon": "🧘",
            "category": "Flexibility",
            "level": "Beginner",
            "duration": "15–20 min",
            "description": (
                "Gentle yoga movements for flexibility."
            ),
            "video": (
                "https://www.youtube.com/results?search_query="
                "beginner+yoga+full+body"
            )
        },

        {
            "name": "Cycling",
            "icon": "🚴",
            "category": "Cardio",
            "level": "Beginner",
            "duration": "20–30 min",
            "description": (
                "Cardio exercise for indoor or outdoor use."
            ),
            "video": (
                "https://www.youtube.com/results?search_query="
                "beginner+cycling+workout"
            )
        },

        {
            "name": "Low Impact Cardio",
            "icon": "❤️",
            "category": "Cardio",
            "level": "Beginner",
            "duration": "15–25 min",
            "description": (
                "A lower-impact cardio workout."
            ),
            "video": (
                "https://www.youtube.com/results?search_query="
                "low+impact+cardio+beginner+workout"
            )
        },

        {
            "name": "Stretching Routine",
            "icon": "🤸",
            "category": "Stretching",
            "level": "Beginner",
            "duration": "10–15 min",
            "description": (
                "A gentle routine for mobility and flexibility."
            ),
            "video": (
                "https://www.youtube.com/results?search_query="
                "beginner+full+body+stretching+routine"
            )
        }

    ]

    return render_template(
        "exercise_videos.html",
        user=user,
        assessment=assessment,
        bmi=round(float(assessment.bmi or 0), 1),
        fitness_goal=fitness_goal,
        activity_level=activity_level,
        preferred_environment=preferred_environment,
        recommended_level="Beginner",
        exercises=exercises
    )


# =========================================================
# SETTINGS
# =========================================================
@app.route("/settings", methods=["GET", "POST"])
def settings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(
        User,
        session["user_id"]
    )

    if not user:
        session.clear()
        return redirect(url_for("login"))

    # Get existing notification settings
    notification_settings = (
        NotificationSettings.query
        .filter_by(user_id=user.id)
        .first()
    )

    # Create default settings for first-time users
    if not notification_settings:
        notification_settings = NotificationSettings(
            user_id=user.id
        )

        db.session.add(notification_settings)
        db.session.commit()

    # Save settings
    if request.method == "POST":

        notification_settings.workout_reminder = (
            request.form.get("workout_reminder") == "on"
        )

        notification_settings.water_reminder = (
            request.form.get("water_reminder") == "on"
        )

        notification_settings.sleep_reminder = (
            request.form.get("sleep_reminder") == "on"
        )

        notification_settings.email_notification = (
            request.form.get("email_notification") == "on"
        )

        notification_settings.reminder_time = request.form.get(
            "reminder_time",
            "08:00"
        )

        db.session.commit()

        flash(
            "Notification settings updated successfully! 🔔",
            "success"
        )

        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        user=user,
        notification_settings=notification_settings
    )

# =========================================================
# DAILY WORKOUT TRACKER
# =========================================================

@app.route("/workout-tracker", methods=["GET", "POST"])
def workout_tracker():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(
        User,
        session["user_id"]
    )

    if not user:
        session.clear()
        return redirect(url_for("login"))

    # =====================================================
    # ADD NEW WORKOUT
    # =====================================================

    if request.method == "POST":

        workout_name = request.form.get(
            "workout_name"
        )

        category = request.form.get(
            "category"
        )

        duration = request.form.get(
            "duration"
        )

        calories_burned = request.form.get(
            "calories_burned"
        )

        workout_date = request.form.get(
            "workout_date"
        )

        completed = (
            request.form.get("completed") == "on"
        )

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not workout_name or not category:

            flash(
                "Please enter workout name and category.",
                "danger"
            )

            return redirect(
                url_for("workout_tracker")
            )

        if not duration or not calories_burned:

            flash(
                "Please enter valid duration and calories.",
                "danger"
            )

            return redirect(
                url_for("workout_tracker")
            )

        if not workout_date:

            flash(
                "Please select the workout date.",
                "danger"
            )

            return redirect(
                url_for("workout_tracker")
            )

        # -------------------------------------------------
        # SAVE WORKOUT
        # -------------------------------------------------

        try:

            new_workout = Workout(

                user_id=user.id,

                workout_name=workout_name,

                category=category,

                duration=int(duration),

                calories_burned=int(calories_burned),

                workout_date=datetime.strptime(
                    workout_date,
                    "%Y-%m-%d"
                ).date(),

                completed=completed

            )

            db.session.add(new_workout)

            db.session.commit()

            flash(
                "Workout added successfully!",
                "success"
            )

        except Exception as error:

            db.session.rollback()

            print(
                "Workout error:",
                error
            )

            flash(
                "Unable to add workout. Please check the values.",
                "danger"
            )

        return redirect(
            url_for("workout_tracker")
        )

    # =====================================================
    # GET WORKOUT HISTORY
    # =====================================================

    workouts = (
        Workout.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Workout.workout_date.desc(),
            Workout.id.desc()
        )
        .all()
    )

    # =====================================================
    # WORKOUT STATISTICS
    # =====================================================

    total_workouts = len(workouts)

    completed_workouts = sum(
        1
        for workout in workouts
        if workout.completed
    )

    total_calories = sum(
        workout.calories_burned or 0
        for workout in workouts
    )

    total_duration = sum(
        workout.duration or 0
        for workout in workouts
    )

    # =====================================================
    # SEND DATA TO TEMPLATE
    # =====================================================

    return render_template(

        "workout_tracker.html",

        user=user,

        workouts=workouts,

        total_workouts=total_workouts,

        completed_workouts=completed_workouts,

        total_calories=total_calories,

        total_minutes=total_duration

    )


# =========================================================
# DELETE WORKOUT
# =========================================================

@app.route(
    "/delete-workout/<int:workout_id>",
    methods=["GET", "POST"]
)
def delete_workout(workout_id):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # FIND WORKOUT
    # -----------------------------------------------------

    workout = (
        Workout.query
        .filter_by(
            id=workout_id,
            user_id=session["user_id"]
        )
        .first_or_404()
    )

    # -----------------------------------------------------
    # DELETE WORKOUT
    # -----------------------------------------------------

    try:

        db.session.delete(workout)

        db.session.commit()

        flash(
            "Workout deleted successfully.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print(
            "Delete workout error:",
            error
        )

        flash(
            "Unable to delete workout.",
            "danger"
        )

    # -----------------------------------------------------
    # RETURN TO WORKOUT TRACKER
    # -----------------------------------------------------

    return redirect(
        url_for("workout_tracker")
    )
# =========================================================
# NOTIFICATION SCHEDULER
# =========================================================

def send_scheduled_notifications():

    with app.app_context():

        current_time = datetime.now(
            ZoneInfo("Asia/Kolkata")
        )

        current_time_string = current_time.strftime("%H:%M")

        current_date = current_time.date()

        users = User.query.all()

        for user in users:

            settings = (
                NotificationSettings.query
                .filter_by(user_id=user.id)
                .first()
            )

            if not settings:
                continue

            if not settings.email_notification:
                continue

            if settings.reminder_time != current_time_string:
                continue

            if settings.last_sent_date == current_date:
                continue

            sent = send_notification_email(
                user,
                settings
            )

            if sent:

                settings.last_sent_date = current_date

                db.session.commit()


def start_scheduler():

    scheduler = BackgroundScheduler(
        timezone="Asia/Kolkata"
    )

    scheduler.add_job(
        func=send_scheduled_notifications,
        trigger="interval",
        minutes=1,
        id="personalized_health_reminders",
        replace_existing=True
    )

    scheduler.start()

    print(
        "Personalized reminder scheduler started."
    )

    print(
        "Scheduler checks notification settings every minute."
    )
# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "index.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    return (
        "Something went wrong on the server. "
        "Please check the terminal for the error."
    ), 500


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    if (
        not app.debug
        or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    ):

        start_scheduler()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )