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
    
    # Створення таблиці для лідерборда
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT,
        level_name TEXT,
        recordMax REAL
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
            
            max_time = 30.0
            
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

# Функція для отримання лідерборду
def get_leaderboard(level_name):
    with sqlite3.connect('sessions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT account_id, recordMax FROM leaderboard WHERE level_name = ? ORDER BY recordMax ASC', 
                       (level_name,))
        return cursor.fetchall()

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
                cursor.execute('UPDATE sessions SET last_ping = ? WHERE account_id = ?', (time.time(), account_id))
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

@app.route('/add_record', methods=['POST'])
def add_record():
    data = request.json
    account_id = data.get('account_id')
    level_name = data.get('level_name')
    record_max = data.get('recordMax')

    if account_id and level_name and record_max is not None:
        with sqlite3.connect('sessions.db') as conn:
            cursor = conn.cursor()

            # Перевірка існуючого рекорду
            cursor.execute('SELECT recordMax FROM leaderboard WHERE account_id = ? AND level_name = ?',
                           (account_id, level_name))
            existing_record = cursor.fetchone()

            # Якщо рекорд існує та новий результат більший
            if existing_record is not None and record_max > existing_record[0]:
                cursor.execute('UPDATE leaderboard SET recordMax = ? WHERE account_id = ? AND level_name = ?',
                               (record_max, account_id, level_name))
                conn.commit()
                return jsonify({'status': 'success', 'message': 'Record updated'}), 200
            # Якщо запису немає, створюємо новий
            elif existing_record is None:
                cursor.execute('INSERT INTO leaderboard (account_id, level_name, recordMax) VALUES (?, ?, ?)',
                               (account_id, level_name, record_max))
                conn.commit()
                return jsonify({'status': 'success', 'message': 'New record added'}), 200
            else:
                return jsonify({'status': 'ignored', 'message': 'Lower or equal score'}), 200

    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

@app.route('/get_records', methods=['GET'])
def get_records():
    level_name = request.args.get('level_name')
    records = get_leaderboard(level_name)
    return jsonify({'leaderboard': records}), 200

@app.route('/get_all_leaderboard_records', methods=['GET'])
def get_all_leaderboard_records():
    with sqlite3.connect('sessions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT account_id, level_name, recordMax FROM leaderboard')
        records = cursor.fetchall()

        leaderboard = []
        for record in records:
            leaderboard.append({
                'account_id': record[0],
                'level_name': record[1],
                'recordMax': record[2]
            })

        return jsonify({'status': 'success', 'leaderboard': leaderboard}), 200

if __name__ == '__main__':
    app.run(debug=True)
