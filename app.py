from flask import Flask, render_template, request, jsonify, json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'testing'

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
        
        
        return jsonify({'status': 'ok', 'message': 'yo lowk ts is working RAHHHH'})
    
@app.route('/review', methods=['POST', 'GET'])
def review():
    if request.method == 'GET':
        return render_template('review.html')
    if request.method == 'POST':
        return jsonify({'status': 'ok', 'message': 'review done or sm shit idk'})
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)