from flask import Flask, render_template, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
import os
import dotenv

# flask settings ---------------------------------------------------------

dotenv.load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI")
app.config['SECRET_KEY'] = os.getenv("SECRET")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Excuses(db.Model):
    __tablename__ = 'excuses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    excuse = db.Column(db.String(250), nullable=False)
    
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
        
        newexcuse = Excuses(name=name, excuse=excuse)
        db.session.add(newexcuse)
        db.session.commit()
        
    #   return jsonify({'status': 'ok ig', 'message': 'yo lowk ts is working RAHHHH & added to db, if error then idk u tell me gng'})
        return redirect('/')
    
@app.route('/review', methods=['POST', 'GET'])
def review():
    if request.method == 'GET':
        return render_template('review.html')
    if request.method == 'POST':
        return jsonify({'status': 'ok', 'message': 'review done or sm shit idk'})
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)