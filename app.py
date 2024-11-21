import uuid
import sqlite3
import contextlib
import pathlib
import re
import json

import openai
from dotenv import load_dotenv
from flask import Flask, Response, render_template, redirect, request

DB = 'test.db'
TABLE = 'test'

load_dotenv()

client = openai.OpenAI()


def save_message(role, content):
    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'INSERT INTO {TABLE} (role, content) values (?, ?)', (role, content))
        return cur.lastrowid


def get_messages():
    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'SELECT role, content from {TABLE} ORDER BY id ASC')
        return cur.fetchall()


def llm(messages, model='gpt-4o-mini'):
        return client.chat.completions.create(model=model, messages=messages).choices[0].message.content


class llm_stream:
    def __init__(self, messages, model='gpt-4o-mini'):
        self.completion = client.chat.completions.create(model=model, messages=messages, stream=True)
        self.text = ''

    def __iter__(self):
        return self
    
    def __next__(self):
        chunk = next(self.completion)

        if chunk.choices[0].delta.content is None:
            raise StopIteration

        self.text += chunk.choices[0].delta.content

        # return chunk.choices[0].delta.content
        return chunk.choices[0].delta


def extract_code_blocks(llm_output):
    '''
    Returns a list of dicts like
    {
        'language': <language>,
        'code': <code>
    }

    <language> and/or <code> will be '' in the dict if not present in the code block
    '''

    # note: this fails if there are three backticks in the code block itself
    matches = re.findall('```(.*)\n([\\s\\S]*?)```', llm_output)  # re.findall returns a list of tuples of the capturing groups in each match

    return tuple({
        'language': match[0],
        'code': match[1]
    } for match in matches)


def write_to_file(file_path, content):
    path = pathlib.Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as file:
        file.write(content)


def system(input_dict):
    system_prompt = 'You are a helpful assistant. Write some code to help the user do what they ask.'

    if input_dict['prompt'] != '':
        save_message('user', input_dict['prompt'])

    stream = llm_stream([{'role': 'system', 'content': system_prompt}, *[{ 'role': row[0], 'content': row[1] } for row in get_messages()]])

    yield from (json.dumps(dict(x)) + '\n' for x in stream)

    # code_blocks = extract_code_blocks(stream.text)
    #
    # for code_block in code_blocks:
    #     write_to_file('file_' + str(uuid.uuid4()), code_block['code'])

    # print([code_block['code'] for code_block in code_blocks])

    save_message('assistant', stream.text)


# --- FLASK APP ---


app = Flask(__name__)


@app.route('/')
def index():
    return redirect('/chat')  # placholder


@app.route('/chat')
def chat():
    return render_template('chat.html', chats=get_messages())
    

@app.route('/llm', methods=['POST'])
def llm_route():
    return Response(system(request.get_json()), content_type='application/json')


@app.route('/reset-chat')
def reset_chat():
    with sqlite3.connect(DB) as con, contextlib.closing(con.cursor()) as cur:
        cur.execute(f'DROP TABLE IF EXISTS {TABLE}')
        # if there's an issue with the table creation make sure there isn't a trailing comma!
        cur.execute(f'''
            CREATE TABLE {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT
            )''')
        con.commit()

    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)

