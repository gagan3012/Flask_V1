from bs4 import BeautifulSoup
import pandas as pd

# Load the HTML file
html_file = "/Users/vivian.fresen/prolifics_flaskServer/prolific-html-webapp/templates/list11.html"

with open(html_file, "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

# Find all sections containing questions
questions = soup.find_all("div", id=lambda x: x and x.startswith("item_"))

data_list = []

# Iterate over each question section
task_id = 1  # Initialize task counter
for question in questions:
    # Extract the question number
    question_number = question.find("h3").text.strip()
    
    # Extract the table data
    table = question.find("table")
    rows = table.find_all("tr")
    
    table_data = []
    for row in rows:
        cells = row.find_all("td")
        table_data.append([cell.text.strip() for cell in cells])

    # Extract the corresponding text to evaluate
    text_evaluate = question.find("div", id="article").find("h5").text.strip()
    
    # Flatten the table data and store the result
    for row in table_data:
        data_list.append([task_id, text_evaluate] + row)

    task_id += 1  # Increment task counter

# Convert extracted data to DataFrame (formatted for Prolific)
df = pd.DataFrame(data_list, columns=["task_id", "outputb1", "question1", "question2", "question3"])

# Save as `data.csv` for Prolific App
csv_file = "/Users/vivian.fresen/prolifics_flaskServer/prolific-html-webapp/templates/data2.csv"
df.to_csv(csv_file, index=False, encoding="utf-8")

print(f" CSV file for Prolific saved: {csv_file}")
