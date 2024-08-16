from flask import Flask, request, jsonify
import sqlite3
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Ініціалізація бази даних
with sqlite3.connect('sessions.db') as conn:
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
        account_id TEXT PRIMARY KEY,
        last_ping REAL
    )
    ''')
    conn.commit()    

# Перевірка, чи акаунт вже активний
def is_account_active(account_id):
    with sqlite3.connect('sessions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions WHERE account_id = ?', (account_id,))
        return cursor.fetchone() is not None

# Реєстрація нової сесії
def register_session(account_id):
    with sqlite3.connect('sessions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO sessions (account_id, last_ping) VALUES (?, ?)', 
                       (account_id, time.time()))
        conn.commit()

# Видалення сесії
def logout_session(account_id):
    with sqlite3.connect('sessions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE account_id = ?', (account_id,))
        conn.commit()

# Функція для перевірки клієнтів на втрату нетворка
def check_clients():
    while True:
        with sqlite3.connect('sessions.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT account_id, last_ping FROM sessions')
            sessions = cursor.fetchall()
            
            max_time = 30.0;
            
            current_time = time.time()
            
            for account_id, last_ping in sessions:
                print(current_time - last_ping)
                if current_time - last_ping > max_time:
                    # Оновлюємо статус сесії
                    logout_session(account_id)
                    print(f"Session for account_id {account_id} marked as open due to network loss.")
        
        time.sleep(30)

# Запуск перевірки клієнтів в окремому потоці
threading.Thread(target=check_clients, daemon=True).start()

@app.route('/ping', methods=['POST'])
def ping():
    data = request.json
    account_id = data.get('account_id')
    
    if account_id:
        with sqlite3.connect('sessions.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sessions WHERE account_id = ?', (account_id,))
            session = cursor.fetchone()
            
            if session:
                cursor.execute('UPDATE sessions SET last_ping = ? WHERE account_id = ?', ( time.time(), account_id))
                conn.commit()
                return jsonify({'status': 'ok'}), 200
            else:
                return jsonify({'status': 'error', 'message': 'Account not found'}), 404
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

@app.route('/check_account', methods=['POST'])
def check_account():
    data = request.json
    account_id = data.get('account_id')
    if is_account_active(account_id):
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'status': 'inactive'}), 200

@app.route('/register_session', methods=['POST'])
def register_new_session():
    data = request.json
    account_id = data.get('account_id')
    if is_account_active(account_id):
        return jsonify({'status': 'failed', 'message': 'Account already active'}), 400
    else:
        register_session(account_id)
        return jsonify({'status': 'success'}), 200

@app.route('/logout_session', methods=['POST'])
def logout():
    data = request.json
    account_id = data.get('account_id')
    logout_session(account_id)
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True)

