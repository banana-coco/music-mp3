from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
import os
import string
import random
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB limit

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

class AudioFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class ShortURL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500), nullable=False)
    short_code = db.Column(db.String(10), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def generate_short_code():
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(characters, k=6))
        if not ShortURL.query.filter_by(short_code=code).first():
            return code

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    files = AudioFile.query.order_by(AudioFile.upload_date.desc()).all()
    urls = ShortURL.query.order_by(ShortURL.created_at.desc()).all()
    return render_template('index.html', files=files, urls=urls)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('ファイルがありません')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('ファイルが選択されていません')
        return redirect(request.url)
    if file and file.filename.lower().endswith('.mp3'):
        filename = secure_filename(file.filename)
        base_name = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1]
        unique_filename = f"{base_name}_{int(datetime.now().timestamp())}{ext}"
        
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        new_file = AudioFile(filename=unique_filename, display_name=filename)
        db.session.add(new_file)
        db.session.commit()
        flash('アップロードが完了しました')
    else:
        flash('MP3ファイルのみアップロード可能です')
    
    return redirect(url_for('index'))

@app.route('/shorten', methods=['POST'])
def shorten_url():
    original_url = request.form.get('url')
    if not original_url:
        flash('URLを入力してください')
        return redirect(url_for('index'))
    
    if not (original_url.startswith('http://') or original_url.startswith('https://')):
        original_url = 'https://' + original_url

    short_code = generate_short_code()
    new_url = ShortURL(original_url=original_url, short_code=short_code)
    db.session.add(new_url)
    db.session.commit()
    flash('URLを短縮しました')
    return redirect(url_for('index'))

@app.route('/r/<short_code>')
def redirect_to_url(short_code):
    link = ShortURL.query.filter_by(short_code=short_code).first_or_404()
    return redirect(link.original_url)

@app.route('/download/<int:file_id>')
def download_file(file_id):
    audio = AudioFile.query.get_or_404(file_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], audio.filename, as_attachment=True)

@app.route('/play/<int:file_id>')
def play_file(file_id):
    audio = AudioFile.query.get_or_404(file_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], audio.filename)

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    audio = AudioFile.query.get_or_404(file_id)
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], audio.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(audio)
        db.session.commit()
        flash('削除しました')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}')
    return redirect(url_for('index'))

@app.route('/delete_url/<int:url_id>', methods=['POST'])
def delete_url(url_id):
    link = ShortURL.query.get_or_404(url_id)
    db.session.delete(link)
    db.session.commit()
    flash('URLを削除しました')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
