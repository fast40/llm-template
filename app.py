import sqlite3
import contextlib

import openai
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request

DB = 'test.db'
TABLE = 'test'

load_dotenv()

client = openai.OpenAI()

app = Flask(__name__)


@app.route('/')
def index():
    return redirect('/chat')  # placholder


@app.route('/chat')
def chat():
    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'SELECT role, content from {TABLE} ORDER BY number ASC')
        rows = cur.fetchall()

    return render_template('chat.html', chats=rows)


@app.route('/llm', methods=['POST'])
def llm():
    # with open('project_prompt.txt', 'r') as system_prompt_file:
    #     system_prompt = system_prompt_file.read()

    json_data = request.get_json()

    system_prompt = 'You are a helpful assistant.'

    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'INSERT INTO {TABLE} (role, content, number) values (?, ?, (SELECT COALESCE(MAX(number) + 1, 0) FROM {TABLE}))', ('user', json_data['prompt']))
        cur.execute(f'SELECT role, content from {TABLE} ORDER BY number ASC')
        rows = cur.fetchall()

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'system', 'content': system_prompt}, *[{ 'role': row[0], 'content': row[1] } for row in rows]]
    ).choices[0].message

    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'INSERT INTO {TABLE} (role, content, number) values (?, ?, (SELECT COALESCE(MAX(number) + 1, 0) FROM {TABLE}))', (response.role, response.content))
        con.commit()

    return str(response.content)


@app.route('/reset-chat')
def reset_chat():
    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'DROP TABLE IF EXISTS {TABLE}')
        cur.execute(f'''
            CREATE TABLE {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                number INTEGER DEFAULT 0
            )''')
        con.commit()

    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)

