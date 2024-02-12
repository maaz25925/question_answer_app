from flask import Flask, g, redirect, render_template, request, session, url_for
from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, "sqlite_db"):
        g.sqlite_db.close()


def get_current_user():
    user_result = None
    if "user" in session:
        user = session["user"]
        db = get_db()
        user_cur = db.execute(
            "SELECT id, name, password, expert, admin FROM users WHERE name = ?",
            [user],
        )
        user_result = user_cur.fetchone()
    return user_result


@app.route("/")
def index():
    user = get_current_user()
    db = get_db()
    question_cur = db.execute(
        """SELECT
            questions.id AS question_id,
            questions.question_text,
            askers.name AS asker_name,
            experts.name AS experts_name
            FROM questions
            JOIN users AS askers ON askers.id = questions.asked_by_id
            JOIN users AS experts ON experts.id = questions.expert_id
            WHERE questions.answer_text IS NOT NULL"""
    )
    questions_result = question_cur.fetchall()
    return render_template("home.html", user=user, questions=questions_result)


@app.route("/register", methods=["GET", "POST"])
def register():
    user = get_current_user()
    if request.method == "POST":
        db = get_db()
        existing_user_cur = db.execute(
            "SELECT id FROM users WHERE name = ?", [request.form["name"]]
        )
        existing_user = existing_user_cur.fetchone()
        if existing_user:
            return render_template(
                "register.html", user=user, error="User already exists!"
            )
        hashed_password = generate_password_hash(
            password=request.form["password"]
        )  # omitting method="sha256" due to error
        db.execute(
            "INSERT INTO users (name, password, expert, admin) VALUES (?, ?, ?, ?)",
            [request.form["name"], hashed_password, "0", "0"],
        )
        db.commit()
        session["user"] = request.form["name"]
        return redirect(url_for("index")), 201
    return render_template("register.html", user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    user = get_current_user()
    error = None
    if request.method == "POST":
        db = get_db()
        name, password = request.form["name"], request.form["password"]
        user_cur = db.execute(
            "SELECT id, name, password FROM users WHERE name = ?", [name]
        )
        user_result = user_cur.fetchone()
        if user_result:
            if check_password_hash(user_result["password"], password):
                session["user"] = user_result["name"]
                return redirect(url_for("index")), 200
            else:
                error = "Invalid password"
        else:
            error = "Invalid username"
    return render_template("login.html", user=user, error=error)


@app.route("/question/<question_id>")
def question(question_id):
    user = get_current_user()
    db = get_db()
    question_cur = db.execute(
        """SELECT
            questions.question_text,
            questions.answer_text,
            askers.name AS asker_name,
            experts.name AS expert_name
            FROM questions
            JOIN users AS askers ON askers.id = questions.asked_by_id
            JOIN users AS experts ON experts.id = questions.expert_id
            WHERE questions.id = ?""",
        [question_id],
    )
    question = question_cur.fetchone()
    return render_template("question.html", user=user, question=question)


@app.route("/answer/<question_id>", methods=["GET", "POST"])
def answer(question_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    if not user["expert"]:
        return redirect(url_for("index"))
    db = get_db()
    if request.method == "POST":
        db.execute(
            "UPDATE questions SET answer_text = ? WHERE id = ?",
            [request.form["answer"], question_id],
        )
        db.commit()
        return redirect(url_for("unanswered"))
    questions_cur = db.execute(
        "SELECT id, question_text FROM questions WHERE id = ?", [question_id]
    )
    question = questions_cur.fetchone()
    return render_template("answer.html", user=user, question=question)


@app.route("/ask", methods=["GET", "POST"])
def ask():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO questions (question_text, asked_by_id, expert_id) VALUES (?, ?, ?)",
            [request.form["question"], user["id"], request.form["expert"]],
        )
        db.commit()
        return redirect(url_for("index"))
    expert_cur = db.execute("SELECT id, name FROM users WHERE expert = 1")
    expert_results = expert_cur.fetchall()
    return render_template("ask.html", user=user, experts=expert_results)


@app.route("/unanswered")
def unanswered():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    if not user["expert"]:
        return redirect(url_for("index"))
    db = get_db()
    questions_cur = db.execute(
        """SELECT
            questions.id,
            questions.question_text,
            users.name
            FROM questions
            JOIN users ON users.id = questions.asked_by_id
            WHERE questions.answer_text IS NULL
            AND questions.expert_id = ?""",
        [user["id"]],
    )
    questions = questions_cur.fetchall()
    return render_template("unanswered.html", user=user, questions=questions)


@app.route("/users")
def users():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    if not user["admin"]:
        return redirect(url_for("index"))
    db = get_db()
    users_cur = db.execute("SELECT id, name, expert, admin FROM users")
    users_results = users_cur.fetchall()
    return render_template("users.html", user=user, users=users_results)


@app.route("/promote/<user_id>")
def promote(user_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    db.execute("UPDATE users SET expert = 1 WHERE id = ?", user_id)
    db.commit()
    return redirect(url_for("users"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
