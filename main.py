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
from flask import Flask, render_template, request, render_template_string, redirect, url_for
import pandas as pd
import ast
import os

import DataManager as dm

MAX_TIME = 3600  # seconds
PROLIFIC_COMPLETION_URL='https://www.google.com'
# PROLIFIC_COMPLETION_URL = 'https://app.prolific.com/submissions/complete?cc=CZ3UY0IC'
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
    # direct to /study while keeping the request args
    # if request.args:
    #     return redirect(url_for('study', **request.args))
    return "Hello, World! The server is running."
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

    with open("templates/eval_template_v2.html", "r", encoding="utf-8") as f:
        template = f.read()

    processed_html = preprocess_html(template, df.iloc[row_id], task_id=row_id)
    return render_template_string(processed_html)


# @app.route('/study/')
# def study():
#     prolific_pid = request.args.get('PROLIFIC_PID')
#     session_id = request.args.get('SESSION_ID')

#     if prolific_pid is None or session_id is None:
#         return "PROLIFIC_PID and SESSION_ID are required parameters.", 400

#     task_id, task_number = dm.allocate_task(prolific_pid, session_id)

#     if task_id == "Database Error - Please try again, if the problem persists contact us." and task_number == -1:
#         return task_id, 500

#     if task_id is None:
#         return "No tasks available", 400

#     with open("templates/evaluation_template_with_placeholders.html", "r", encoding="utf-8") as f:
#         template = f.read()

#     df_row_index = task_number % len(df) if len(df) > 0 else 0

#     html_content = preprocess_html(template, df.iloc[df_row_index], task_id)
#     html_content += f'<input type="hidden" id="prolific_pid" value="{prolific_pid}">'
#     html_content += f'<input type="hidden" id="session_id" value="{session_id}">'
#     html_content += f'<input type="hidden" id="task_id" value="{task_id}">'
#     return render_template_string(html_content,PROLIFIC_COMPLETION_URL=PROLIFIC_COMPLETION_URL)

@app.route("/study/")
def study():
    prolific_pid = request.args.get("PROLIFIC_PID")
    session_id = request.args.get("SESSION_ID")

    if prolific_pid is None or session_id is None:
        return "PROLIFIC_PID and SESSION_ID are required parameters.", 400

    task_id, task_number = dm.allocate_task(prolific_pid, session_id)

    if (
        task_id
        == "Database Error - Please try again, if the problem persists contact us."
        and task_number == -1
    ):
        return task_id, 500

    if task_id is None:
        return "No tasks available", 400

    # Use modulo to wrap around the DataFrame
    df_row_index = task_number % len(df) if len(df) > 0 else 0

    # Read the template
    with open("templates/eval_template_v2.html", "r", encoding="utf-8") as f:
        template = f.read()

    # Generate all 32 question cards dynamically
    question_cards_html = ""

    # Determine total questions based on CSV columns
    text_columns = [col for col in df.columns if col.startswith("text_")]
    total_questions = len(text_columns)

    for i in range(1, total_questions + 1):
        padded_num = str(i).zfill(2)  # Pad with zeros (01, 02, etc.)

        # Determine navigation buttons
        prev_button = f'<button class="btn btn-outline-secondary btn-nav prev-btn" {"disabled" if i == 1 else ""} onclick="showPrevQuestion()">Previous</button>'

        if i == total_questions:
            next_button = '<button class="btn btn-success btn-nav finish-btn" onclick="showSubmitCard()">Finish</button>'
        else:
            next_button = '<button class="btn btn-primary btn-nav next-btn" onclick="showNextQuestion()">Next</button>'

        card_html = f"""
        <!-- Question {i} -->
        <div class="card intro-card question-card" id="question-card-{i}">
            <div class="card-header">
                <h5 class="mb-0">Question {i} of {total_questions}</h5>
            </div>
            <div class="card-body">
                <div class="evaluation-box">
                    <h6>Data:</h6>
                    <div class="table-responsive">
                        ${{triples_html_{padded_num}}}
                    </div>
                </div>
                <div class="evaluation-box">
                    <h6>Text to evaluate:</h6>
                    <p class="lead">${{text_{padded_num}}}</p>
                </div>
                <div class="evaluation-box">
                    <h6>Grammaticality:</h6>
                    <p>Is the text grammatical (no spelling or grammatical errors)?</p>
                    <div class="rating-container">
                        <div class="rating-label">Very<br>Bad</div>
                        <div class="rating-btn" data-value="1" data-name="grammar-item{i}">1</div>
                        <div class="rating-btn" data-value="2" data-name="grammar-item{i}">2</div>
                        <div class="rating-btn" data-value="3" data-name="grammar-item{i}">3</div>
                        <div class="rating-btn" data-value="4" data-name="grammar-item{i}">4</div>
                        <div class="rating-btn" data-value="5" data-name="grammar-item{i}">5</div>
                        <div class="rating-btn" data-value="6" data-name="grammar-item{i}">6</div>
                        <div class="rating-btn" data-value="7" data-name="grammar-item{i}">7</div>
                        <div class="rating-label">Very<br>Good</div>
                    </div>
                </div>
                
                <div class="navigation-buttons">
                    {prev_button}
                    {next_button}
                </div>
                
                <p class="swipe-hint mt-4">
                    <small>Use the navigation buttons to move between questions</small>
                </p>
            </div>
        </div>
        """

        question_cards_html += card_html

    # Replace the placeholder in the template with generated cards
    template = template.replace("<!-- DYNAMIC_QUESTION_CARDS -->", question_cards_html)

    # Update the total questions in JavaScript
    template = template.replace(
        "const totalQuestions = 32;", f"const totalQuestions = {total_questions};"
    )
    template = template.replace(
        "out of 32 questions", f"out of {total_questions} questions"
    )

    # Process the template with CSV data
    html_content = preprocess_html(template, df.iloc[df_row_index], task_id)

    # Add hidden form fields for task info but add it before the closing </form> tag
    # html_content += f'<input type="hidden" id="prolific_pid" value="{prolific_pid}">'
    # html_content += f'<input type="hidden" id="session_id" value="{session_id}">'
    # html_content += f'<input type="hidden" id="task_id" value="{task_id}">'
    html_content = html_content.replace("prolific_pid_value", prolific_pid)
    html_content = html_content.replace("session_id_value", session_id)
    html_content = html_content.replace("task_id_value", str(task_id))

    return render_template_string(
        html_content, PROLIFIC_COMPLETION_URL=PROLIFIC_COMPLETION_URL
    )

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
