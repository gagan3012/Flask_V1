# Understanding Human Evaluation Results

## Overview

This script analyzes data from your human evaluation experiment where participants rated text quality on a 1-7 scale. It connects participant ratings with task information and generates multiple analysis reports.

**Main Goal:** Transform raw database results into meaningful statistics about:

- How participants rated each text
- Agreement between different raters
- Quality issues in the data
- Demographic patterns in ratings

## Step-by-Step Process

```
Database (SQLite/PostgreSQL)
    ↓
1. Extract all completed tasks + ratings
    ↓
2. Parse JSON responses (handle formatting errors)
    ↓
3. Create detailed CSV (one row per participant submission)
    ↓
4. Create aggregated CSV (group all ratings per task)
    ↓
5. Calculate statistics:
   • Average ratings per task
   • Inter-annotator agreement
   • Fleiss' Kappa (reliability measure)
   • Identify problematic tasks
   • Demographic analysis
    ↓
6. Generate comprehensive Excel report
```

---

## Understanding Results Files

### 1. **results_analysis.csv** (Main Data File)

**What it contains:** One row for each participant's submission

**Key columns:**

```
task_number         → Which task they completed (1-32)
prolific_id         → Participant's unique ID
grammar-item1       → Rating for question 1 (1-7 scale)
grammar-item2       → Rating for question 2 (1-7 scale)
...
grammar-item32      → Rating for question 32 (1-7 scale)
age                 → Participant age range
gender              → Participant gender
english_proficiency → English level (Native/Fluent/etc.)
```

### 2. **aggregated_results.csv** (Task Summary)

**What it contains:** One row per task, showing ALL ratings received

**Key columns:**

```
task_number         → Task ID
num_completions     → How many people rated this task (should be ~20)
valid_completions   → How many ratings were successfully parsed
participants        → List of all prolific IDs who rated this
grammar-item1_all   → All ratings for item 1: "7, 6, 7, 5, 6, ..."
grammar-item2_all   → All ratings for item 2: "6, 5, 7, 6, 6, ..."
```

### 3. **comprehensive_results.xlsx** (All-in-One)

**What it contains:** All files combined into one Excel workbook

**Sheets:**

1. Detailed_Results
2. Aggregated_Results
3. Average_Ratings
4. Inter_Annotator_Agreement
5. Problematic_Tasks
6. Demo_age / Demo_gender / Demo_english_proficiency
7. Incomplete_Responses
8. Suspicious_Patterns

---

## Code Structure Explained

### Core Functions (In Order of Execution)

#### 1. **`safe_json_parse(json_string, task_id)`**

```python
# What it does: Converts JSON strings from database into Python dictionaries
# Why it's needed: Database stores ratings as text, we need structured data
# Handles: Malformed JSON, single quotes, missing commas, Python dict strings
```

**Example:**

```python
Input:  "{'grammar-item1': 7, 'grammar-item2': 6}"
Output: {'grammar-item1': 7, 'grammar-item2': 6}
```

#### 2. **`get_all_results_with_tasks()`**

```python
# What it does: Joins 'tasks' and 'results' tables from database
# Returns: List of dictionaries with task info + ratings
```

**SQL query explained:**

```sql
SELECT 
    t.task_number,      -- Which task (1-32)
    t.prolific_id,      -- Participant ID
    r.json_string       -- Their ratings
FROM tasks t
LEFT JOIN results r ON t.prolific_id = r.prolific_id
WHERE t.status = 'completed'
```

#### 3. **`group_results_by_task_number()`**

```python
# What it does: Groups all ratings for each task together
# Returns: Dictionary where key=task_number, value=list of all ratings
```

**Example output:**

```python
{
    1: [
        {task_number: 1, prolific_id: 'ABC', ratings: {item1: 7, item2: 6}},
        {task_number: 1, prolific_id: 'DEF', ratings: {item1: 6, item2: 5}},
        ...
    ],
    2: [...],
    ...
}
```

#### 4. **`export_to_csv()`**

```python
# What it does: Creates results_analysis.csv (one row per participant)
# Process:
#   1. Get all results from database
#   2. Parse each JSON response
#   3. Extract demographics
#   4. Flatten ratings into columns
#   5. Save as CSV
```

#### 5. **`export_aggregated_by_task()`**

```python
# What it does: Creates aggregated_results.csv (one row per task)
# Process:
#   1. Group results by task
#   2. Collect all ratings for each item
#   3. Join ratings into comma-separated strings
#   4. Save as CSV
```

#### 6. **`calculate_average_ratings_per_task()`**

```python
# What it does: Calculates mean rating per task
# How:
#   ratings_df.groupby('task_number').mean()
```

#### 7. **`analyze_inter_annotator_agreement()`**

```python
# What it does: Calculates consistency measures
# Metrics:
#   - std (standard deviation)
#   - cv (coefficient of variation) = std / mean
#   - range (max - min)
```

#### 8. **`calculate_fleiss_kappa()`**

```python
# What it does: Calculates reliability statistic
# How:
#   1. Convert ratings to frequency matrix
#   2. Apply Fleiss' Kappa formula
#   3. Interpret result
```

**Matrix format:**

```
Task 1, Item 1: [0, 0, 1, 3, 5, 8, 3]  ← Counts of ratings 1-7
                 1  2  3  4  5  6  7
                 
Means: 0 people rated "1", 0 rated "2", 1 rated "3", etc.
```

#### 9. **`calculate_overall_fleiss_kappa()`**

```python
# What it does: Single kappa for entire study
# Process:
#   1. Collect ALL ratings (all tasks × all items)
#   2. Filter to tasks with consistent rater counts
#   3. Calculate one overall kappa
```

#### 10. **`identify_problematic_tasks()`**

```python
# What it does: Finds tasks with avg rating < threshold (default 4.0)
# Why: Helps identify low-quality texts
```

#### 11. **`check_suspicious_patterns()`**

```python
# What it does: Flags low-effort responses
# Checks:
#   - all_same: Did they rate everything identically?
#   - low_variance: std < 0.5?
```

#### 12. **`analyze_by_demographics()`**

```python
# What it does: Groups ratings by age/gender/proficiency
# How:
#   df.groupby('age')['avg_grammar'].mean()
```

#### 13. **`run_all_analyses()`**

```python
# What it does: Runs everything in sequence
# This is the main function that executes when you run the script
```

---

## How to Use

### Run Everything 

```bash
python AnalyzeResults.py
```

This generates all 12 result files automatically.

Note: Ensure your database is set up and accessible. You might need the env file with connection details.

It should be of the form:

```
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
```
    
## Understanding the Analysis

### 1. What is Fleiss' Kappa?

**Simple explanation:** Measures how often raters agree, accounting for chance

**Example:**

```
10 raters judge 20 texts
If they randomly guessed, they'd agree ~14% of the time (by chance)
If your kappa = 0.60, they agreed 60% more than random chance
```

**Why it matters:**

- Low kappa → Raters interpreted task differently or rating scale unclear
- High kappa → Raters consistently understood and applied criteria

### 2. What is Coefficient of Variation (CV)?

**Formula:** `CV = std / mean`

**Example:**

```
Task A: mean=6.0, std=0.6 → CV=0.10 (excellent agreement)
Task B: mean=6.0, std=1.8 → CV=0.30 (moderate agreement)
```

**Why use CV instead of just std?**

- CV is scale-independent
- Can compare agreement across different rating ranges

### 3. What is "Inter-Annotator Agreement"?

**Simple explanation:** How much different raters agree with each other

**Good agreement means:**

- Clear instructions
- Unambiguous rating criteria
- Reliable data


