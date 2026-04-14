from flask import Flask, render_template, request, jsonify, redirect, url_for, json, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_required
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
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")

db = SQLAlchemy(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"],  # 100 requests per minute
)

login_manager = LoginManager()
login_manager.init_app(app)


class Excuses(db.Model):
    __tablename__ = "excuses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    excuse = db.Column(db.String(250), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    pending = db.Column(db.Boolean, nullable=False, default=True)
    reason = db.Column(
        db.String(250),
        nullable=False,
        default="no reason provided, wait or contact admin.",
    )


with app.app_context():
    db.create_all()

# functions ------------------------------------------------------


def get_excuses():
    excuses = Excuses.query.filter_by().order_by(Excuses.points.desc()).limit(3).all()
    return excuses


def get_all_excuses():
    excuses = Excuses.query.filter_by().order_by(Excuses.points.desc()).all()
    print(excuses)
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
                    "- CENSORSHIP RULES (STRICT — NO EXCEPTIONS):\n"
                    "  * ANY profanity, slurs, offensive language, or inappropriate words MUST be censored.\n"
                    "  * This includes mild swear words, strong swear words, slurs, and any vulgar language.\n"
                    "  * Censoring format: keep the FIRST and LAST letter, replace all middle letters with asterisks.\n"
                    "    Example: 'damn' → 'd**n', 'hell' → 'h**l', 'shit' → 's**t', 'fuck' → 'f**k'\n"
                    "  * For 3-letter words: keep first and last, replace only the middle letter.\n"
                    "    Example: 'ass' → 'a*s'\n"
                    "  * For 2-letter words or single letters used as slurs: replace entirely with '***'.\n"
                    "  * Do NOT let any bad word pass uncensored — not even minor ones.\n"
                    "  * Apply censoring consistently in BOTH the 'review' field AND the 'newexcuse' field.\n"
                    "  * Do NOT change the points awarded just because the excuse contains bad language.\n\n"
                    "Always respond ONLY in this JSON format, no preamble, no markdown backticks:\n"
                    '{"creativity": <points>, "audacity": <points>, "believability": <points>, "total": <sum>, '
                    '"review": "<9-10 words reason on the score given, all bad words censored>", '
                    '"newexcuse": "<same excuse but with ALL bad/offensive/vulgar words censored>" }'
                ),
            },
            {"role": "user", "content": excuse},
        ],
    }

    response = requests.post(
        "https://ai.hackclub.com/proxy/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {aikey}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    result = json.loads(data["choices"][0]["message"]["content"].strip())

    with app.app_context():
        exc = Excuses.query.get(id)
        exc.excuse = result["newexcuse"]
        exc.points = int(result["total"])
        exc.pending = False
        exc.reason = result["review"]
        db.session.commit()


# routes ---------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/oauth/callback")
def oauth():
    code = request.args.get("code")
    if not code:
        return "Error, oauth was not done properly, no code provided."

    payload = {
        "client_id": {client_id},
        "client_secret": {client_secret},
        "redirect_uri": f"{redirect_uri}/oauth/callback",
        "code": code,
        "grant_type": "authorization_code",
    }
    requestauth = requests.post(
        "https://auth.hackclub.com/oauth/token",
        data=payload,
    )
    response = requestauth.json()
    
    namerequest = requests.get(
        "https://auth.hackclub.com/api/v1/me",
        headers={
            "Authorization": f"Bearer {response['access_token']}"
        }
    )
    nameresponse = namerequest.json()

    fullname = nameresponse['identity']['first_name'] + " " + nameresponse['identity']['last_name']
    session['fullname'] = fullname
    
    return redirect("/add")


@app.route("/add", methods=["POST", "GET"])
@limiter.limit("10 per day")
def add():
    if request.method == "GET":
        if 'fullname' in session:
            return render_template("addexcuse.html", fullname=session['fullname'])
        
        return redirect(
            f"https://auth.hackclub.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}/oauth/callback&response_type=code&scope=name profile slack_id"
        )

        # return render_template("addexcuse.html")
    if request.method == "POST":
        print(request.form)
        name = request.form["fullname"]
        excuse = request.form["excuse"]
        points = "0"
        allexcuses = get_all_excuses()

        if excuse in allexcuses:
            error = "someone used this excuse already, be unique smh"
            return render_template("addexcuse.html", error=error)

        newexcuse = Excuses(name=name, excuse=excuse, points=points, pending=True)
        db.session.add(newexcuse)
        db.session.commit()

        thread = threading.Thread(
            target=ai_review, kwargs={"id": newexcuse.id, "excuse": excuse}
        )
        thread.daemon = True
        thread.start()

        error = "ig submitted for review, someone (@stolen_username) will review it and give you points for it, estimated time is 6-7 decades (jk check after 5 minutes)"

        #   return jsonify({'status': 'ok ig', 'message': 'yo lowk ts is working RAHHHH & added to db, if error then idk u tell me gng'})
        return redirect("/")


@app.route("/read")
def read():
    excuses = get_excuses()
    ranked = list(enumerate(excuses, start=1))
    print(ranked)
    return render_template("allexcuses.html", excuses=excuses, ranked=ranked)


@app.route("/all")
def readall():
    excuses = get_all_excuses()
    ranked = list(enumerate(excuses, start=1))
    print(ranked)
    return render_template("allexcuses.html", excuses=excuses, ranked=ranked)


# admin routes ---------------------------------------------------------


@app.route("/admin", methods=["POST", "GET"])
def admin():
    if request.method == "POST":
        password = request.form["password"]
        if password:
            if password == adminpass:
                excuses = get_all_excuses()
                ranked = list(enumerate(excuses, start=1))
                return render_template(
                    "adminreview.html", excuses=excuses, ranked=ranked
                )
            else:
                error = "not authorized bozo, read .env and login again :icant:"
                return render_template("adminlogin.html", error=error)

    if request.method == "GET":
        return render_template("adminlogin.html")


@app.route("/remove/<int:id>", methods=["POST"])
def remove(id):
    excuse = Excuses.query.get(id)
    excuse.pending = True

    db.session.commit()

    return redirect("/admin")

@app.route("/report/<int:id>", methods=["POST"])
def report(id):
    excuse = Excuses.query.get(id)
    
    # todo: build this


if __name__ == "__main__":
    app.run(debug=True, port=5000)
