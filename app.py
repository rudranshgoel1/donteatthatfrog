from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import dotenv

# flask settings ---------------------------------------------------------

dotenv.load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI")
app.config['SECRET_KEY'] = os.getenv("SECRET")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

adminpass = os.getenv("ADMIN_PASSWORD")

db = SQLAlchemy(app)


class Excuses(db.Model):
    __tablename__ = 'excuses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    excuse = db.Column(db.String(250), nullable=False)
    points = db.Column(db.String(250), nullable=False)
    pending = db.Column(db.Boolean, nullable=False, default=True)

with app.app_context():
    db.create_all()

# routes ---------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add', methods=['POST', 'GET'])
def add():
    if request.method == 'GET':
        return render_template('addexcuse.html')
    if request.method == 'POST':
        print(request.form)
        name = request.form['name']
        excuse = request.form['excuse']
        points = "0"
        
        newexcuse = Excuses(name=name, excuse=excuse, points=points)
        db.session.add(newexcuse)
        db.session.commit()
        
        error = "ig submitted for review, someone (@stolen_username) will review it and give you points for it, estimated time is 6-7 decades (jk check after 5 minutes)"
        
    #   return jsonify({'status': 'ok ig', 'message': 'yo lowk ts is working RAHHHH & added to db, if error then idk u tell me gng'})
        return redirect('/', error=error)
    
@app.route('/read')
def read():
    if request.method == 'GET':
        return render_template('allexcuses.html')
    
# admin routes ---------------------------------------------------------
    
@app.route('/admin', methods=['POST', 'GET'])
def admin():
    if request.method == 'POST':
        password = request.form['password']
        if password:
            if password == adminpass:
                return render_template('adminreview.html')
            else:
                error = "not authorized bozo, read .env and login again :icant:"
                return render_template('adminlogin.html', error=error)
    
    if request.method == 'GET':
        return render_template('adminlogin.html')
    
@app.route('/approve/<int:id>', methods=['POST', 'GET'])
def approve(id):
    excuse = Excuses.query.get(id)
    excuse.pending = False
    
    db.session.commit()
    
    return redirect('/admin', isAuthenticated='true')

@app.route('/reject/<int:id>', methods=['POST', 'GET'])
def reject(id):
    excuse = Excuses.query.get(id)
    db.session.delete(excuse)
    
    db.session.commit()
    
    return redirect('/admin', isAuthenticated='true')

if __name__ == '__main__':
    app.run(debug=True, port=5000)