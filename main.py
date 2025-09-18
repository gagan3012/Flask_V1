# /// script
# dependencies = [
#   "flask",
#   "pandas",
#   "apscheduler",
#   "sqlalchemy",
#   "psycopg2-binary",
# ]
# ///


# Webapp for hosting Prolific surveys for the Edinburgh Napier University lab (reprohum project)
import json
from datetime import datetime
from flask import Flask, render_template, request, render_template_string
import pandas as pd
import ast
import os

import DataManager as dm

MAX_TIME = 3600  # seconds
PROLIFIC_COMPLETION_URL='https://www.google.com'
##https://app.prolific.com/submissions/complete?cc=CZ3UY0IC
# Load the data from CSV
df = pd.read_csv("pivoted_output2.csv")
column_names = df.columns.values.tolist()

app = Flask(__name__)


# === Convert triplet list to HTML table ===
def triplet_list_to_html(triplet_list):
    table = "<table class='table table-striped small'><thead><tr><th>Entity 1</th><th>Relation</th><th>Entity 2</th></tr></thead><tbody>"
    for t in triplet_list:
        table += f"<tr><td>{t['subject']}</td><td>{t['predicate']}</td><td>{t['object']}</td></tr>"
    table += "</tbody></table>"
    return table



# === Replace placeholders in HTML with actual values ===
def preprocess_html(html_content, row, task_id=-1):
    for column_name, value in row.items():
        placeholder = f"${{{column_name}}}"

        if column_name.startswith("triples_html_"):
            try:
                triplets = ast.literal_eval(value) if isinstance(value, str) else value
                html_value = triplet_list_to_html(triplets)
            except Exception as e:
                print(f"Error parsing {column_name}: {e}")
                html_value = "<p>Error loading triplets</p>"
        else:
            html_value = str(value)

        html_content = html_content.replace(placeholder, html_value)

    html_content = html_content.replace("${task_id}", str(task_id))
    return html_content

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"
# === Main Routes ===

@app.route('/submit', methods=[ 'POST'])
def index():
    if request.method == 'POST':
        print(request.json)

        task_id = request.json['task_id']
        prolific_pid = request.json['prolific_pid']
        folder_path = os.path.join('data', str(task_id))
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, f"{task_id}.json")
        with open(file_path, 'w') as outfile:
            json.dump(request.json, outfile)

        complete = dm.complete_task(task_id, str(request.json), prolific_pid)

        if complete == -1:
            return {"result": "Something went wrong? Is this your task?"}, 500

        return {"result": "OK"}, 200

    return "Nothing Here.", 200


@app.route('/row/<int:row_id>', methods=['GET'])
def row(row_id):
    if row_id >= len(df):
        return "Row ID out of range", 404

    with open("templates/evaluation_template_with_placeholders.html", "r", encoding="utf-8") as f:
        template = f.read()

    processed_html = preprocess_html(template, df.iloc[row_id], task_id=row_id)
    return render_template_string(processed_html)


@app.route('/study/')
def study():
    prolific_pid = request.args.get('PROLIFIC_PID')
    session_id = request.args.get('SESSION_ID')

    if prolific_pid is None or session_id is None:
        return "PROLIFIC_PID and SESSION_ID are required parameters.", 400

    task_id, task_number = dm.allocate_task(prolific_pid, session_id)

    if task_id == "Database Error - Please try again, if the problem persists contact us." and task_number == -1:
        return task_id, 500

    if task_id is None:
        return "No tasks available", 400

    with open("templates/evaluation_template_with_placeholders.html", "r", encoding="utf-8") as f:
        template = f.read()

    html_content = preprocess_html(template, df.iloc[task_number], task_id)
    html_content += f'<input type="hidden" id="prolific_pid" value="{prolific_pid}">'
    html_content += f'<input type="hidden" id="session_id" value="{session_id}">'
    html_content += f'<input type="hidden" id="task_id" value="{task_id}">'
    return render_template_string(html_content,PROLIFIC_COMPLETION_URL=PROLIFIC_COMPLETION_URL)


@app.route('/tasksallocated')
def tasksallocated():
    tasks = dm.get_all_tasks()
    return tasks


@app.route('/results/<task_id>')
def results(task_id):
    result = dm.get_specific_result(str(task_id))
    if result is None:
        return f"No result found for task_id: {task_id}", 400
    return str(result)


@app.route('/abdn')
def check_abandonment():
    print("Checking for abandoned tasks...")
    dm.expire_tasks(MAX_TIME)
    return dm.get_all_tasks(), 200


# === Scheduler: run check_abandonment every hour ===
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(func=check_abandonment, trigger="interval", seconds=MAX_TIME)
scheduler.start()


# === CLI Entry Point ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
