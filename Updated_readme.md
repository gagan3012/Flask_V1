# Human Evaluation Experiment Guide

**Complete guide for running your Prolific human evaluation study and analyzing results**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Pre-Experiment Setup](#pre-experiment-setup)
3. [Running the Experiment](#running-the-experiment)
4. [Collecting Results](#collecting-results)
5. [Analyzing Results](#analyzing-results)
6. [Troubleshooting](#troubleshooting)
7. [Appendix](#appendix)

---

## 🎯 Overview

This system allows you to run grammaticality evaluation studies on Prolific. Participants rate text generations on a 7-point scale (1=Very Bad to 7=Very Good) for grammaticality. The system:

- ✅ Automatically assigns tasks to participants
- ✅ Prevents duplicate assignments
- ✅ Collects demographic information
- ✅ Handles consent forms
- ✅ Tracks completion status
- ✅ Exports results for analysis

**Study Design:**

- Each task (text item) is rated by multiple participants (default: 20)
- Each participant rates multiple items (default: 32)
- Ratings are on a 7-point Likert scale
- Time limit: 60 minutes per participant (configurable)

---

## 🚀 Pre-Experiment Setup

### Step 1: Prepare Your Data

**Required File:** `pivoted_output2.csv`

Your CSV must contain columns in this format:

```
text_01, text_02, text_03, ..., text_32
triples_html_01, triples_html_02, ..., triples_html_32
```

**Example CSV structure:**

```csv
text_01,text_02,text_03,triples_html_01,triples_html_02
"The cat sat on the mat.","Dogs are loyal animals.","...","[...]","[...]"
```

- **`text_XX`**: The text to be evaluated
- **`triples_html_XX`**: Structured data (RDF triples) in JSON format

📝 **Note:** Each row in your CSV becomes a task assigned to participants.

### Step 2: Configure the Database

**File to edit:** [`CreateDatabase.py`](CreateDatabase.py)

```python
COMPLETIONS_PER_TASK = 20  # How many participants rate each task
NUMBER_OF_TASKS = len(df)  # Automatically set from your CSV
```

**Run the database initialization:**

```bash
python CreateDatabase.py
```

✅ **What this does:**

- Creates `database.db` (SQLite) or connects to PostgreSQL (Supabase)
- Creates three tables: `tasks`, `results`, `consent`
- Populates tasks (each task × 20 completions = 20 task entries per row)

⚠️ **WARNING:** Do NOT run this script if your database already exists—it will recreate it!

### Step 3: Configure the Application

**File to edit:** [`main.py`](main.py)

```python
MAX_TIME = 3600  # Task timeout in seconds (default: 1 hour)
PROLIFIC_COMPLETION_URL = 'https://app.prolific.com/submissions/complete?cc=YOUR_CODE'
```

**Update the completion code:**

1. Create your Prolific study
2. Get your completion code from Prolific
3. Replace `YOUR_CODE` in the URL above

### Step 4: Set Up Environment Variables (Optional)

For PostgreSQL/Supabase deployment, create a `.env` file:

```env
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=your_host.supabase.co
DB_PORT=5432
DB_NAME=postgres
```

If these are not set, the system defaults to SQLite (`database.db`). To connect to PostgreSQL, ensure these variables are correctly set. Please contact me for the Supabase credentials if needed.

### Step 5: Test Locally

```bash
# Install dependencies
pip install flask pandas apscheduler sqlalchemy psycopg2-binary python-dotenv

# Run the server
python main.py
```

Visit: `http://localhost:5000/study/?PROLIFIC_PID=TEST123&SESSION_ID=TEST456`

✅ **Verify:**

- Consent form displays correctly
- Instructions are clear
- Questions load with your data
- Submit button works
- Task is marked as completed in database

---

## 🏃 Running the Experiment

Note: Current deployment is on Render.com (free tier) and it is recommended to use PostgreSQL for production. We have deployed the app at: `https://flask-v1-75ei.onrender.com/`. 

### Step 1: Create Prolific Study

**Study Settings:**

| Setting | Value |
|---------|-------|
| **Study Name** | "[Your Project] - Grammaticality Evaluation" |
| **Study URL** | `https://flask-v1-75ei.onrender.com/study/?PROLIFIC_PID={{%PROLIFIC_PID%}}&SESSION_ID={{%SESSION_ID%}}` |
| **Estimated Time** | 10 minutes |
| **Reward** | £2.10 |
| **Places** | (Number of participants needed) |
| **Device Type** | Desktop only (recommended) |
| **Approval Rate** | ≥95% |
| **Age** | 18+ |
| **Language** | English (fluent) |

**Important:** Use Prolific's URL parameters in our study URL:

```
https://flask-v1-75ei.onrender.com/study/?PROLIFIC_PID={{%PROLIFIC_PID%}}&SESSION_ID={{%SESSION_ID%}}
```

### Step 2: Monitor Progress

**Check task allocation:**

```bash
# Visit this URL in browser
https://flask-v1-75ei.onrender.com/tasksallocated
```

**Returns JSON like:**

```json
[
  {"id": "abc-123", "task_number": 1, "status": "completed", "prolific_id": "PROLIFIC123"},
  {"id": "def-456", "task_number": 1, "status": "waiting", "prolific_id": null},
  ...
]
```

**Check specific result:**

```bash
https://flask-v1-75ei.onrender.com/results/abc-123-def-456
```

### Step 3: Handle Issues During Experiment

**Participants report problems?**

1. **Task won't load:** Check server logs, verify database connection
2. **Can't submit:** Check that PROLIFIC_COMPLETION_URL is correct
3. **Timeout issues:** Verify MAX_TIME is set correctly
4. **Task already completed:** This is expected—worker may have refreshed

**Manual database queries:**

```python
from CreateDatabase import create_connection
conn = create_connection()
cursor = conn.cursor()

# Check how many tasks are completed
cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
print(cursor.fetchall())

# Find a specific participant's tasks
cursor.execute("SELECT * FROM tasks WHERE prolific_id = 'PROLIFIC123'")
print(cursor.fetchall())

conn.close()
```

---

## 📊 Collecting Results

### When to Download Results

Wait until:

- ✅ All Prolific submissions are approved
- ✅ Database shows sufficient completions
- ✅ No pending tasks remain

**Check completion status:**

```python
from CreateDatabase import create_connection
conn = create_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        COUNT(DISTINCT task_number) as unique_tasks,
        COUNT(*) as total_completions,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'waiting' THEN 1 ELSE 0 END) as waiting,
        SUM(CASE WHEN status = 'allocated' THEN 1 ELSE 0 END) as allocated
    FROM tasks
""")
print(cursor.fetchone())
```


---

## 📈 Analyzing Results

### Quick Start: Run All Analyses

```bash
python AnalyzeResults.py
```

This generates:

- ✅ `results_analysis.csv` - Detailed results (one row per completion)
- ✅ `aggregated_results.csv` - Grouped by task (all ratings per task)
- ✅ `task_average_ratings.csv` - Mean ratings per task
- ✅ `inter_annotator_agreement.csv` - Agreement statistics
- ✅ `problematic_tasks.csv` - Low-quality tasks
- ✅ `demographic_analysis.xlsx` - Ratings by demographics
- ✅ `incomplete_responses.csv` - Missing data
- ✅ `suspicious_responses.csv` - Quality control flags
- ✅ `fleiss_kappa_results.csv` - Inter-rater reliability
- ✅ `comprehensive_results.xlsx` - All-in-one Excel file

### Understanding Output Files

#### 1. `results_analysis.csv` (Detailed Results)

**One row per task completion**

| Column | Description | Example |
|--------|-------------|---------|
| `task_number` | Task ID from your CSV | 1, 2, 3, ... |
| `prolific_id` | Participant identifier | PROLIFIC123 |
| `grammar-item1` to `grammar-item32` | Ratings (1-7) | 7, 6, 5, ... |
| `age` | Age range | "25-34" |
| `gender` | Self-reported gender | "Female" |
| `english_proficiency` | English level | "Native" |

**Use this for:**

- Participant-level analysis
- Demographic comparisons
- Quality control checks

#### 2. `aggregated_results.csv` (Grouped by Task)

**One row per task number**

| Column | Description | Example |
|--------|-------------|---------|
| `task_number` | Task ID | 1 |
| `num_completions` | Total ratings received | 20 |
| `valid_completions` | Successfully parsed ratings | 19 |
| `participants` | List of Prolific IDs | "P1, P2, P3, ..." |
| `grammar-item1_all` | All ratings for item 1 | "7, 6, 7, 5, ..." |

**Use this for:**

- Inter-annotator agreement
- Task-level statistics
- Identifying problematic tasks

#### 3. `task_average_ratings.csv` (Mean Ratings)

| Column | Description |
|--------|-------------|
| `task_number` | Task ID |
| `grammar-item1` to `grammar-item32` | Mean ratings |
| `overall_average` | Mean across all items |

**Use this for:**

- Ranking text quality
- Comparing systems
- Final quality scores

#### 4. `inter_annotator_agreement.csv` (Agreement Stats)

| Column | Description | Interpretation |
|--------|-------------|----------------|
| `task_number` | Task ID | - |
| `item` | Grammar item | "grammar-item1" |
| `mean` | Average rating | Higher = better quality |
| `std` | Standard deviation | Lower = more agreement |
| `cv` | Coefficient of variation | Lower = more reliable |
| `range` | Max - Min | Lower = more agreement |

**Interpreting CV (Coefficient of Variation):**

- **CV < 0.15:** Excellent agreement
- **CV 0.15-0.30:** Good agreement
- **CV 0.30-0.50:** Moderate agreement
- **CV > 0.50:** Poor agreement (investigate!)

#### 5. `fleiss_kappa_results.csv` (Inter-Rater Reliability)

| Kappa Value | Interpretation |
|-------------|----------------|
| < 0.00 | Poor agreement |
| 0.00-0.20 | Slight agreement |
| 0.21-0.40 | Fair agreement |
| 0.41-0.60 | Moderate agreement |
| 0.61-0.80 | Substantial agreement |
| 0.81-1.00 | Almost perfect agreement |


---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### ❌ "JSON parsing error"

**Problem:** Some results have malformed JSON.

**Solution:**

```python
from AnalyzeResults import diagnose_json_errors

# This will show you which records have issues
diagnose_json_errors()
```

**Manual fix:**

1. Check the database directly
2. Look for incomplete submissions
3. May need to exclude these participants

#### ❌ "No tasks available"

**Problem:** All tasks are allocated or completed.

**Causes:**

- All tasks have been assigned (this is normal at the end)
- Database connection issue
- Tasks stuck in "allocated" status

**Solution:**

```python
from DataManager import expire_tasks

# Release tasks that timed out
expire_tasks(MAX_TIME)
```

#### ❌ Participant can't submit

**Problem:** Submit button doesn't work.

**Check:**

1. Console errors in browser (F12)
2. Server logs for POST request errors
3. PROLIFIC_COMPLETION_URL is correct
4. Network connectivity

**Test submission manually:**

```bash
curl -X POST https://flask-v1-75ei.onrender.com/submit \
  -H "Content-Type: application/json" \
  -d '{"task_id":"test","prolific_pid":"TEST","ratings":{}}'
```

#### ❌ Low inter-annotator agreement

**Problem:** Fleiss' Kappa < 0.4 or high standard deviation.

**Possible causes:**

- Task is genuinely ambiguous
- Participants didn't understand instructions
- Poor quality participants
- Rating scale not clear

**Solutions:**

1. Review task design and instructions
2. Check for suspicious response patterns
3. Consider excluding low-quality raters
4. May need to collect more ratings per task

#### ❌ Missing results

**Problem:** Task shows as "completed" but no results in database.

**Debug:**

```python
from CreateDatabase import create_connection

conn = create_connection()
cursor = conn.cursor()

# Find orphaned tasks
cursor.execute("""
    SELECT t.id, t.task_number, t.prolific_id
    FROM tasks t
    LEFT JOIN results r ON t.id = r.id
    WHERE t.status = 'completed' AND r.id IS NULL
""")

orphaned = cursor.fetchall()
print(f"Found {len(orphaned)} completed tasks without results")
```

**Possible causes:**

- Network issue during submission
- Database write failure
- Browser crashed before submission

---

## 📚 Appendix

### A. Database Schema

#### `tasks` table

```sql
id              TEXT/VARCHAR(255)  -- Unique task instance ID
task_number     INTEGER            -- Row number from CSV (1-N)
prolific_id     TEXT/VARCHAR(255)  -- Participant ID
session_id      TEXT/VARCHAR(255)  -- Prolific session ID
time_allocated  TEXT/TIMESTAMP     -- When task was assigned
status          TEXT/VARCHAR(50)   -- 'waiting', 'allocated', 'completed'
```

#### `results` table

```sql
id              TEXT/VARCHAR(255)  -- Links to tasks.id
json_string     TEXT               -- Full JSON response
prolific_id     TEXT/VARCHAR(255)  -- Participant ID
```

#### `consent` table

```sql
id                  TEXT/VARCHAR(255)  -- Unique consent ID
prolific_id         TEXT/VARCHAR(255)  -- Participant ID
session_id          TEXT/VARCHAR(255)  -- Prolific session ID
consent_given       BOOLEAN            -- True if consented
consent_timestamp   TEXT/TIMESTAMP     -- When consent given
ip_address          TEXT/VARCHAR(45)   -- IP address (for logging)
```

### B. JSON Response Format

Example of what's stored in `results.json_string`:

```json
{
  "task_id": "abc-123-def",
  "prolific_pid": "PROLIFIC123",
  "session_id": "SESSION456",
  "grammar-item1": 7,
  "grammar-item2": 6,
  "grammar-item3": 5,
  ...
  "grammar-item32": 7,
  "demographics": {
    "gender": "Female",
    "age": "25-34",
    "english_proficiency": "Native"
  }
}
```