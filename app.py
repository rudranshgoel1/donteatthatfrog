from flask import Flask, render_template, request, jsonify, redirect, url_for, json
import requests
from flask_sqlalchemy import SQLAlchemy
import os
import dotenv
import threading

# flask settings ---------------------------------------------------------

dotenv.load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
app.config["SECRET_KEY"] = os.getenv("SECRET")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

adminpass = os.getenv("ADMIN_PASSWORD")
aikey = os.getenv("AI_KEY")

db = SQLAlchemy(app)


class Excuses(db.Model):
    __tablename__ = "excuses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    excuse = db.Column(db.String(250), nullable=False)
    points = db.Column(db.String(250), nullable=False)
    pending = db.Column(db.Boolean, nullable=False, default=True)


with app.app_context():
    db.create_all()

# functions ------------------------------------------------------


def get_excuses():
    excuses = Excuses.query.filter_by().all()
    return excuses


def ai_review(id: int, excuse: str):
    if not aikey:
        print("add api key in .env")

    payload = {
        "model": "x-ai/grok-4.1-fast",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the Chief Procrastination Officer (CPO) of the world's most prestigious "
                    "Procrastination Leaderboard. Your job is to review and score excuses that people "
                    "give for procrastinating.\n\n"
                    "You award points across 3 dimensions:\n"
                    "- 🎨 Creativity Points: How original and inventive is the excuse?\n"
                    "- 😂 Audacity Points: How bold and shameless is it?\n"
                    "- 🎭 Believability Points: How convincingly could someone say this with a straight face?\n\n"
                    "IMPORTANT RULES:\n"
                    "- Each dimension is worth exactly the same — no dimension is weighted more than another.\n"
                    "- Points are absolute, not relative to other users — the same excuse always gets the same points.\n"
                    "- Be consistent. A mediocre excuse should always score similarly regardless of who submitted it.\n"
                    "- Total = Creativity + Audacity + Believability\n\n"
                    "Always respond ONLY in this JSON format, no preamble, no markdown backticks:\n"
                    '{"creativity": <points>, "audacity": <points>, "believability": <points>, "total": <sum>, "review": "<witty 1-2 sentence roast>"}'
                ),
            },
            { "role": "user", "content": excuse }
        ],
    }
    
    response = requests.post(
        "https://ai.hackclub.com/proxy/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {aikey}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    result = json.loads(data["choices"][0]["message"]["content"].strip())
    
    with app.app_context():
        exc = Excuses.query.get(id)
        exc.points = str(result["total"])
        exc.pending = False
        db.session.commit()


# routes ---------------------------------------------------------


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/add", methods=["POST", "GET"])
def add():
    if request.method == "GET":
        return render_template("addexcuse.html")
    if request.method == "POST":
        print(request.form)
        name = request.form["name"]
        excuse = request.form["excuse"]
        points = "0"

        newexcuse = Excuses(name=name, excuse=excuse, points=points, pending=True)
        db.session.add(newexcuse)
        db.session.commit()
        
        thread = threading.Thread(target=ai_review, kwargs={"id": newexcuse.id, "excuse": excuse})
        thread.daemon = True
        thread.start()

        error = "ig submitted for review, someone (@stolen_username) will review it and give you points for it, estimated time is 6-7 decades (jk check after 5 minutes)"

        #   return jsonify({'status': 'ok ig', 'message': 'yo lowk ts is working RAHHHH & added to db, if error then idk u tell me gng'})
        return redirect("/")


@app.route("/read")
def read():
    excuses = get_excuses()
    
    return render_template("allexcuses.html", excuses=excuses)


# admin routes ---------------------------------------------------------


@app.route("/admin", methods=["POST", "GET"])
def admin():
    if request.method == "POST":
        password = request.form["password"]
        if password:
            if password == adminpass:
                return render_template("adminreview.html")
            else:
                error = "not authorized bozo, read .env and login again :icant:"
                return render_template("adminlogin.html", error=error)

    if request.method == "GET":
        return render_template("adminlogin.html")


@app.route("/approve/<int:id>", methods=["POST", "GET"])
def approve(id):
    excuse = Excuses.query.get(id)
    excuse.pending = False

    db.session.commit()

    return redirect("/admin")


@app.route("/reject/<int:id>", methods=["POST", "GET"])
def reject(id):
    excuse = Excuses.query.get(id)
    db.session.delete(excuse)

    db.session.commit()

    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
