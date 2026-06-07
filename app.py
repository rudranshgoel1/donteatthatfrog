from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    json,
    session,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_required
import requests
from flask_sqlalchemy import SQLAlchemy
import os
import dotenv
import threading
from slackeventsapi import SlackEventAdapter
import slack
import hmac
import time
import hashlib

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
workspaceid = os.getenv("WORKSPACE_ID")

db = SQLAlchemy(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"],  # 100 requests per minute
)

login_manager = LoginManager()
login_manager.init_app(app)

# slack ----------------------------------------------------------

client = slack.WebClient(token=os.getenv("SLACK_TOKEN"))
workspaceid = os.getenv("WORKSPACE_ID")

slack_event_adapter = SlackEventAdapter(
    os.getenv("SLACK_SIGNING_SECRET"), "/slack/events", app
)


def verify_slack_signature(req):
    slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET").encode()
    timestamp = req.headers.get("X-Slack-Request-Timestamp")

    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}"
    my_signature = (
        "v0="
        + hmac.new(
            slack_signing_secret, sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
    )
    slack_signature = req.headers.get("X-Slack-Signature", "")

    return hmac.compare_digest(my_signature, slack_signature)


@app.route("/slack/events", methods=["POST"])
def slack_events():
    if not verify_slack_signature(request):
        return "invalid signature", 403

    data = request.json

    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]})

    if data.get("type") == "event_callback":
        event = data.get("event", {})
        print(f"Event received: {event}")

    return jsonify({"status": "ok"})


# db tables ---------------------------------------------------------


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
    slack_id = db.Column(db.String(250), nullable=True)
    reportedby = db.Column(db.String(250), nullable=True)


with app.app_context():
    db.create_all()

# functions ------------------------------------------------------


def get_excuses():
    excuses = Excuses.query.filter_by(pending=False).order_by(Excuses.points.desc()).limit(3).all()
    return excuses


def get_all_excuses():
    excuses = Excuses.query.filter_by(pending=False).order_by(Excuses.points.desc())
    return excuses

def get_reported_excuses():
    excuses = Excuses.query.filter(Excuses.reason.like("%reported by a user%")).order_by(Excuses.points.desc()).all()
    return excuses

def get_every_excuse():
    excuses = Excuses.query.order_by(Excuses.points.desc()).all()
    return excuses

def ai_review(id: int, excuse: str):
    if not aikey:
        print("add api key in .env")

    payload = {
        "model": "anthropic/claude-opus-4.8-fast",
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
    return "0"


@app.route("/")
def home():
    if "isadmin" in session:
        print(session["isadmin"])
        
        return render_template("index.html")
    else:
        session["isadmin"] = False
        print(session["isadmin"])
        
        return render_template("index.html")


@app.route("/oauth/callback")
def oauth():
    code = request.args.get("code")
    redirect_source = session["source"]
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
        headers={"Authorization": f"Bearer {response['access_token']}"},
    )
    nameresponse = namerequest.json()

    print(nameresponse)

    fullname = (
        nameresponse["identity"]["first_name"]
        + " "
        + nameresponse["identity"]["last_name"]
    )
    session["fullname"] = fullname
    print(session["fullname"])
    session["slack_id"] = nameresponse["identity"]["slack_id"]
    
    if redirect_source == "add":
        return redirect("/add")
    elif redirect_source == "own":
        return redirect("/own")
    elif redirect_source == "readlogin":
        return redirect("/read")
    elif redirect_source == "alllogin":
        return redirect("/all")
    else:
        print("no redirect source provided, tf is wrong with this human, anyways, redirecting to homepage")
        return redirect("/")


@app.route("/add", methods=["POST", "GET"])
@limiter.limit("10 per day", exempt_when=lambda: request.method == "GET")
def add():
    if request.method == "GET":
        if "fullname" and "slack_id" in session:

            token = os.environ["SLACK_TOKEN"]
            slackid = session["slack_id"]

            response = client.users_info(
                user=slackid,
            )

            print(response)
            
            session["fullname"] = response["user"]["profile"]["display_name"]

            return render_template(
                "addexcuse.html",
                fullname=session["fullname"],
                slack_id=session["slack_id"],
            )
        
        session["source"] = "add"

        return redirect(
            f"https://auth.hackclub.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}/oauth/callback&response_type=code&scope=name profile slack_id"
        )

        # return render_template("addexcuse.html")
    if request.method == "POST":
        print(request.form)
        name = request.form["fullname"]
        slack_id = request.form["slack_id"]
        excuse = request.form["excuse"]
        points = "0"
        allexcuses = get_all_excuses()

        if excuse in allexcuses:
            error = "someone used this excuse already, be unique smh"
            return render_template("addexcuse.html", error=error)

        newexcuse = Excuses(
            name=name, excuse=excuse, points=points, pending=True, slack_id=slack_id
        )
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
    
    if "slack_id" not in session:
        slackid = "nologin"
    else:
        slackid = session["slack_id"]
        if slackid:
            print(slackid)

    return render_template(
        "allexcuses.html", excuses=excuses, ranked=ranked, pagination=None, slackid=slackid
    )
    
@app.route("/readlogin")
def readlogin():
    if "slack_id" not in session:
        session["source"] = "readlogin"
        
        return redirect(
            f"https://auth.hackclub.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}/oauth/callback&response_type=code&scope=name profile slack_id"
        )
    else:
        return redirect("/read")


@app.route("/all")
def readall():
    page = request.args.get("page", 1, type=int)

    query = get_all_excuses()
    pagination = db.paginate(query, page=page, per_page=10, error_out=False)

    excuses = pagination.items

    ranked = list(enumerate(excuses, start=(page - 1) * 10 + 1))
    
    if "slack_id" not in session:
        slackid = "nologin"
    else:
        slackid = session["slack_id"]
        if slackid:
            print(slackid)

    return render_template(
        "allexcuses.html", excuses=excuses, ranked=ranked, pagination=pagination, slackid=slackid
    )
    
@app.route("/alllogin")
def alllogin():
    if "slack_id" not in session:
        session["source"] = "alllogin"
        
        return redirect(
            f"https://auth.hackclub.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}/oauth/callback&response_type=code&scope=name profile slack_id"
        )
    else:
        return redirect("/all")

    
@app.route("/own")
def own():
    if "slack_id" not in session:
        session["source"] = "own"
        
        return redirect(
            f"https://auth.hackclub.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}/oauth/callback&response_type=code&scope=name profile slack_id"
        )
    else:
        sid = session["slack_id"]
        print(sid)
        
        excuses = Excuses.query.filter_by(slack_id=sid).order_by(Excuses.points.desc()).all()
        print(excuses)
        
        ranked = list(enumerate(excuses, start=1))
        
        return render_template("ownexcuses.html", excuses=excuses, ranked=ranked)


# admin routes ---------------------------------------------------------


@app.route("/admin", methods=["POST", "GET"])
def admin():
    if request.method == "POST":
        password = request.form["password"]
        if password:
            if password == adminpass:
                excuses = get_every_excuse()
                ranked = list(enumerate(excuses, start=1))
                
                session["isadmin"] = True
                
                return render_template(
                    "adminreview.html", excuses=excuses, ranked=ranked
                )
            else:
                error = "not authorized bozo, read .env and login again :icant:"
                return render_template("adminlogin.html", error=error)

    if request.method == "GET":
        if "isadmin" in session and session["isadmin"] == True:
            excuses = get_every_excuse()
            ranked = list(enumerate(excuses, start=1))
            
            return render_template("adminreview.html", excuses=excuses, ranked=ranked)
        else:
            return render_template("adminlogin.html")


@app.route("/remove/<int:id>", methods=["POST"])
def remove(id):
    excuse = Excuses.query.get(id)
    excuse.pending = True

    db.session.commit()

    return redirect("/admin")

@app.route("/hidden", methods=["POST", "GET"])
def hidden():
    if request.method == "GET" and "isadmin" in session and session["isadmin"] == True:
        excuses = Excuses.query.filter_by(pending=True).order_by(Excuses.points.desc()).all()
        ranked = list(enumerate(excuses, start=1))
        return render_template("hiddenexcuses.html", excuses=excuses, ranked=ranked) # todo: build this, right now it gives 404
    else:
        return jsonify({"status": 503, "message": "not authorized, login through /admin and come here"})

@app.route("/report/<int:id>", methods=["GET"])
@limiter.limit("2 per day")
def report(id):
    if "slack_id" not in session:
        session["source"] = "own"
        
        return redirect(
        f"https://auth.hackclub.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}/oauth/callback&response_type=code&scope=name profile slack_id"
        )
    else:
        token = os.environ["SLACK_TOKEN"]
        slackid = session["slack_id"]

        response = client.users_info(
            user=session["slack_id"],
        )

        print(response)
            
        session["fullname"] = response["user"]["profile"]["display_name"]
        
        excuse = Excuses.query.get(id)
        excuse.pending = True
        excuse.reportedby = session["fullname"] + " (@" + session["slack_id"] + ")"
        excuse.reason = "reported by " + session["fullname"] + " (@" + session["slack_id"] + ")" + "  |  " + excuse.reason
        db.session.commit()
        
        return redirect("/all")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
