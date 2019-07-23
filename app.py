from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
import os
from flask_cors import CORS
import random

import numpy as np
from cdm import estimate_skills, remedial_hamming

app = Flask(__name__, static_url_path = '')

# Format db path
db_path = os.path.join(os.path.dirname(__file__), "db.sqlite")
db_uri = "sqlite:///{}".format(db_path)

# App configs
app.config["SECRET_KEY"] = "thisisthesecretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
CORS(app)
db = SQLAlchemy(app)

# All tables in DB
class User(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    username = db.Column(db.String(), unique = True)
    password = db.Column(db.String())

class Question(db.Model):
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    originalQuestionID = db.Column(db.String(), unique = True)
    answerKey = db.Column(db.String())
    isMultipleChoiceQuestion = db.Column(db.Boolean)
    includesDiagram = db.Column(db.Boolean)
    diagramName = db.Column(db.String())
    schoolGrade = db.Column(db.Integer)
    year = db.Column(db.Integer)
    question = db.Column(db.String())
    subject = db.Column(db.String())
    category = db.Column(db.String())
    qmatrix = db.Column(db.String())

# Token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if "Authorization" in request.headers:
            auth = request.headers["Authorization"]
            if auth.split(" ")[0] == "Bearer":
                token = auth.split(" ")[1]

        if not token:
            return jsonify({"message": "Token is missing!"})

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"])

            current_user = User.query.filter_by(id = data["id"]).first()
        except:
            return jsonify({"message": "Invalid token"}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# Routings
@app.route("/register", methods=["POST"])
def register_user():
    data = request.get_json()

    # Fields existance validation
    if "username" not in data or "password" not in data:
        return make_response("Bad request: missing fields", 401, {"WWW-Authenticate": "Basic realm-'Proper informations required!'"})

    # Fields length validation
    if len(data["username"]) > 100:
        return make_response("Bad request: field length invalid", 401, {"WWW-Authenticate": "Basic realm-'Proper informations required!'"})

    # Check if username already existed
    username_data = User.query.filter_by(username = data["username"]).first()

    if username_data:
        return jsonify({"success": False, "message": "This username has been taken"})

    # If everything is ok, hash the password
    hashed_password = generate_password_hash(data["password"], method = "sha256", salt_length = 8)

    new_user = User(
        username = data["username"],
        password = hashed_password
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({"success": True, "message": "New user created"})

@app.route("/login", methods=["POST"])
def user_login():
    login_data = request.get_json()

    # Fields existance validation
    if "username" not in login_data or "password" not in login_data:
        return make_response("Bad request: missing fields", 401, {"WWW-Authenticate": "Basic realm-'Proper informations required!'"})

    user = User.query.filter_by(username = login_data["username"]).first()

    if not user:
        return jsonify({"success": False, "message": "Wrong username or password"})

    # Compare password
    if check_password_hash(user.password, login_data["password"]):
        token = jwt.encode({
            "id": user.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days = 30)
        }, app.config["SECRET_KEY"])
    return jsonify({"success": True, "username": login_data["username"], "message": "Login success", "token": token.decode("UTF-8")})

    return jsonify({"success": False, "message": "Wrong username or password"})

@app.route("/exam/grade/<school_grade>/question/<num_question>", methods=["GET"])
@token_required
def gen_random_test(current_user, school_grade, num_question):
    questions = Question.query.filter_by(schoolGrade = school_grade).all()
    
    if (len(questions) < int(num_question)):
        return jsonify({"success": False, "message": "There are too few questions of requested type"})

    random_indices = random.sample(range(len(questions)), int(num_question))

    output = []

    for index in random_indices:
        data = {}
        data["originalQuestionID"] = questions[index].originalQuestionID
        data["isMultipleChoiceQuestion"] = questions[index].isMultipleChoiceQuestion
        data["includesDiagram"] = questions[index].includesDiagram
        data["diagramName"] = questions[index].diagramName
        data["question"] = questions[index].question

        output.append(data)

    return jsonify({"success": True, "questions": output})

@app.route("/public/images/<image_id>", methods=["GET"])
def get_public_image(image_id):
    return send_from_directory("public/images", image_id)

@app.route("/exam/check", methods=["POST"])
@token_required
def check_exam_result(current_user):
    items = request.get_json()

    score = 0
    grade = 8

    data = {}
    for item in items:
        # data["questionID"] = item["questionID"]
        question = Question.query.filter_by(originalQuestionID = item["questionID"]).first()

        grade = question.schoolGrade

        if item["answer"] == question.answerKey:
            data[question.originalQuestionID] = True
            score += 1
        else:
            data[question.originalQuestionID] = False

    # Preprocess for estimate skill function
    questions = Question.query.filter_by(schoolGrade = grade).all()
    student_score = np.zeros(len(questions), dtype = int)

    index = 0
    for question in questions:
        if question.originalQuestionID in data:
            if data[question.originalQuestionID]:
                student_score[index] = 1

        index += 1
            
    est_skills = estimate_skills(grade, np.array2string(student_score))

    return jsonify({"result": data, "grade": grade, "score": score, "total": len(items), "skill_state": np.array2string(est_skills)})

@app.route("/exam/remedial/hamming", methods=["POST"])
@token_required
def generate_remedial_hamming_questions(current_user):
    data = request.get_json()
    student_skill = np.fromstring(data["student_skill"], sep = " ", dtype = int)
    
    idx = remedial_hamming(data["grade"], student_skill)

    questions = Question.query.filter_by(schoolGrade = data["grade"]).all()

    output = []

    for index in idx:
        data = {}
        data["originalQuestionID"] = questions[index].originalQuestionID
        data["isMultipleChoiceQuestion"] = questions[index].isMultipleChoiceQuestion
        data["includesDiagram"] = questions[index].includesDiagram
        data["diagramName"] = questions[index].diagramName
        data["question"] = questions[index].question

        output.append(data)

    return jsonify({"success": True, "questions": output})

# Debugging routes
@app.route("/users", methods=["GET"])
def get_all_users():
    users = User.query.all()

    output = []

    for user in users:
        user_data = {}
        user_data["id"] = user.id
        user_data["username"] = user.username
        user_data["password"] = user.password

        output.append(user_data)

    return jsonify({"users": output})

@app.route("/questions", methods=["GET"])
def get_all_questions():
    questions = Question.query.all()

    output = []

    for question in questions:
        q_data = {}

        q_data["id"] = question.id
        q_data["originalQuestionID"] = question.originalQuestionID
        q_data["answerKey"] = question.answerKey
        q_data["isMultipleChoiceQuestion"] = question.isMultipleChoiceQuestion
        q_data["includesDiagram"] = question.includesDiagram
        q_data["diagramName"] = question.diagramName
        q_data["schoolGrade"] = question.schoolGrade
        q_data["year"] = question.year
        q_data["question"] = question.question
        q_data["subject"] = question.subject
        q_data["category"] = question.category
        q_data["qmatrix"] = question.qmatrix

        output.append(q_data)

    return jsonify({"questions": output, "total": len(questions)})

@app.route("/questions/import", methods=["POST"])
def import_questions():
    questions = request.get_json()

    for question in questions:
        new_question = Question(
            originalQuestionID = question["originalQuestionID"],
            answerKey = question["answerKey"],
            isMultipleChoiceQuestion = bool(question["isMultipleChoiceQuestion"]),
            includesDiagram = bool(question["includesDiagram"]),
            diagramName = question["diagramName"] if "diagramName" in question else "",
            schoolGrade = question["schoolGrade"],
            year = question["year"],
            question = question["question"],
            subject = question["subject"],
            category = question["category"],
            qmatrix = question["qmatrix"]
        )
        db.session.add(new_question)
        db.session.commit()

    return jsonify({"success": True, "count": len(questions)})

@app.route("/question/<question_id>", methods=["GET"])
def get_question_by_id(question_id):
    question = Question.query.filter_by(originalQuestionID = question_id).first()

    if not question:
        return jsonify({"success": False, "message": "There is no question with this id"})

    q_data = {}

    q_data["originalQuestionID"] = question.originalQuestionID
    q_data["answerKey"] = question.answerKey
    q_data["isMultipleChoiceQuestion"] = question.isMultipleChoiceQuestion
    q_data["includesDiagram"] = question.includesDiagram
    q_data["diagramName"] = question.diagramName
    q_data["schoolGrade"] = question.schoolGrade
    q_data["year"] = question.year
    q_data["question"] = question.question
    q_data["subject"] = question.subject
    q_data["category"] = question.category
    q_data["qmatrix"] = question.qmatrix

    return jsonify({"success": True, "data": q_data})

@app.route("/question/<question_id>", methods=["PUT"])
def update_question_by_id(question_id):
    question = Question.query.filter_by(originalQuestionID = question_id).first()

    if not question:
        return jsonify({"success": False, "message": "There is no question with this id"})

    new_question = request.get_json()

    question.originalQuestionID = new_question["originalQuestionID"]
    question.answerKey = new_question["answerKey"]
    question.isMultipleChoiceQuestion = bool(new_question["isMultipleChoiceQuestion"])
    question.includesDiagram = bool(new_question["includesDiagram"])
    question.diagramName = new_question["diagramName"]
    question.schoolGrade = new_question["schoolGrade"]
    question.year = new_question["year"]
    question.question = new_question["question"]
    question.subject = new_question["subject"]
    question.category = new_question["category"]
    question.qmatrix = new_question["qmatrix"]

    db.session.commit()

    return jsonify({"success": True, "message": "Question has been updated"})

if __name__ == '__main__':
    app.run(debug=True)
