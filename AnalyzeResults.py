"""
Script to analyze results and connect them with original tasks.
This allows you to see how multiple humans have rated each task.
"""

# /// script
# dependencies = [
#   "apscheduler",
#   "sqlalchemy",
#   "psycopg2-binary",
#   "uuid",
#   "python-dotenv",
#   "pandas",
#   "openpyxl",
#   "numpy",
#   "statsmodels"
# ]
# ///

import sqlite3
import psycopg2
import os
import json
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from CreateDatabase import create_connection

load_dotenv()


def safe_json_parse(json_string, task_id):
    """
    Safely parse JSON string with multiple fallback strategies.
    Returns parsed JSON or None if all attempts fail.
    """
    if not json_string:
        return None

    # Strategy 1: Try direct JSON parsing
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Try replacing single quotes with double quotes
    try:
        return json.loads(json_string.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    # Strategy 3: Try to fix common JSON issues
    try:
        # Remove any trailing commas before closing braces/brackets
        import re

        fixed = re.sub(r",\s*}", "}", json_string)
        fixed = re.sub(r",\s*]", "]", fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Strategy 4: Try ast.literal_eval for Python dict strings
    try:
        import ast

        return ast.literal_eval(json_string)
    except (ValueError, SyntaxError):
        pass

    # Log the problematic JSON for manual inspection
    print(f"\n⚠️  WARNING: Could not parse JSON for task {task_id}")
    print(f"JSON string preview (first 200 chars): {json_string[:200]}...")
    print(f"JSON string preview (last 200 chars): ...{json_string[-200:]}")
    print(f"JSON string length: {len(json_string)} characters")

    return None


def get_all_results_with_tasks():
    """
    Retrieves all results and joins them with their corresponding task information.
    Returns a list of dictionaries containing combined task and result data.
    """
    try:
        conn = create_connection()
        cursor = conn.cursor()

        is_postgres = hasattr(conn, "server_version")

        query = """
        SELECT 
            t.task_number,
            t.id as task_id,
            t.prolific_id,
            t.session_id,
            t.time_allocated,
            t.status,
            r.json_string
        FROM tasks t
        LEFT JOIN results r ON t.prolific_id = r.prolific_id AND t.task_number = (
            SELECT CAST(r.json_string AS TEXT) 
            FROM results r2 
            WHERE r2.id = t.id
        )
        WHERE t.status = 'completed'
        ORDER BY t.task_number, t.prolific_id
        """

        # Simpler query - join by ID
        simple_query = """
        SELECT 
            t.task_number,
            t.id as task_id,
            t.prolific_id,
            t.session_id,
            t.time_allocated,
            t.status,
            r.json_string,
            r.id as result_id
        FROM tasks t
        LEFT JOIN results r ON t.prolific_id = r.prolific_id
        WHERE t.status = 'completed'
        ORDER BY t.task_number, t.prolific_id
        """

        cursor.execute(simple_query)

        if is_postgres:
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            cursor.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(simple_query)
            results = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return results

    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"An error occurred: {e}")
        return None


def group_results_by_task_number():
    """
    Groups all results by task_number to see multiple ratings for each task.
    Returns a dictionary where keys are task_numbers and values are lists of results.
    """
    all_results = get_all_results_with_tasks()

    if all_results is None:
        return None

    grouped = {}
    parse_errors = 0
    successful_parses = 0

    for result in all_results:
        task_num = result["task_number"]
        if task_num not in grouped:
            grouped[task_num] = []

        # Parse the JSON string to get the actual ratings
        if result["json_string"]:
            parsed = safe_json_parse(result["json_string"], result["task_id"])
            if parsed:
                result["parsed_ratings"] = parsed
                successful_parses += 1
            else:
                result["parsed_ratings"] = None
                parse_errors += 1

        grouped[task_num].append(result)

    print(f"\n📊 Parsing Summary:")
    print(f"   ✅ Successfully parsed: {successful_parses}")
    print(f"   ❌ Parse errors: {parse_errors}")

    return grouped


def export_to_csv(output_file="results_analysis.csv"):
    """
    Exports the results to a CSV file with one row per task completion.
    """
    all_results = get_all_results_with_tasks()

    if all_results is None:
        print("No results to export.")
        return

    # Prepare data for DataFrame
    export_data = []
    parse_errors = 0
    successful_exports = 0

    for result in all_results:
        row = {
            "task_number": result["task_number"],
            "task_id": result["task_id"],
            "prolific_id": result["prolific_id"],
            "session_id": result["session_id"],
            "time_allocated": result["time_allocated"],
            "status": result["status"],
        }

        # Parse JSON string to extract individual ratings
        if result["json_string"]:
            ratings = safe_json_parse(result["json_string"], result["task_id"])

            if ratings:
                successful_exports += 1

                # Extract demographics if available
                if "demographics" in ratings:
                    row["gender"] = ratings["demographics"].get("gender", "")
                    row["age"] = ratings["demographics"].get("age", "")
                    row["english_proficiency"] = ratings["demographics"].get(
                        "english_proficiency", ""
                    )

                # FIXED: Extract responses dict and flatten it
                if "responses" in ratings and isinstance(ratings["responses"], dict):
                    # The ratings are nested inside a 'responses' key
                    for key, value in ratings["responses"].items():
                        row[key] = value
                elif "responses" in ratings and isinstance(ratings["responses"], str):
                    # If responses is a string, parse it again
                    responses_dict = safe_json_parse(
                        ratings["responses"], result["task_id"]
                    )
                    if responses_dict:
                        for key, value in responses_dict.items():
                            row[key] = value
                else:
                    # Try to extract all rating fields directly
                    for key, value in ratings.items():
                        if key not in [
                            "task_id",
                            "prolific_pid",
                            "session_id",
                            "demographics",
                            "consent_given",
                        ]:
                            # Handle nested dictionaries
                            if isinstance(value, dict):
                                for nested_key, nested_value in value.items():
                                    row[f"{key}_{nested_key}"] = nested_value
                            else:
                                row[key] = value

                # Also extract consent_given and responses at top level
                if "consent_given" in ratings:
                    row["consent_given"] = ratings.get("consent_given", "")

            else:
                parse_errors += 1
                row["parse_error"] = True

        export_data.append(row)

    # Create DataFrame and export
    df = pd.DataFrame(export_data)

    # Debug: Check what columns we actually have
    print(f"\n🔍 DEBUG: CSV Columns Created:")
    print(f"   Total columns: {len(df.columns)}")
    grammar_cols = [
        col for col in df.columns if "grammar" in col.lower() or col.startswith("item")
    ]
    if grammar_cols:
        print(
            f"   ✅ Grammar columns found ({len(grammar_cols)}): {grammar_cols[:5]}..."
        )
    else:
        print(f"   ⚠️  No grammar columns found!")
        print(f"   Available columns: {list(df.columns)}")
        print(f"\n   Sample first row:")
        if len(df) > 0:
            print(f"   {df.iloc[0].to_dict()}")

    df.to_csv(output_file, index=False)
    print(f"\n✅ Results exported to {output_file}")
    print(f"   Total rows: {len(df)}")
    print(f"   Unique tasks: {df['task_number'].nunique()}")
    print(f"   Successfully exported: {successful_exports}")
    print(f"   Parse errors: {parse_errors}")

    return df


def export_aggregated_by_task(output_file="aggregated_results.csv"):
    """
    Exports aggregated statistics for each task showing how multiple participants rated it.
    """
    grouped = group_results_by_task_number()

    if grouped is None:
        print("No results to aggregate.")
        return

    aggregated_data = []

    for task_num, results in grouped.items():
        row = {
            "task_number": task_num,
            "num_completions": len(results),
            "participants": ", ".join(
                [r["prolific_id"] for r in results if r["prolific_id"]]
            ),
        }

        # Collect all ratings for this task
        all_ratings = {}
        valid_results = 0

        for result in results:
            if result.get("parsed_ratings"):
                valid_results += 1
                ratings = result["parsed_ratings"]
                for key, value in ratings.items():
                    if key not in [
                        "task_id",
                        "prolific_pid",
                        "session_id",
                        "demographics",
                    ]:
                        if key not in all_ratings:
                            all_ratings[key] = []
                        all_ratings[key].append(value)

        row["valid_completions"] = valid_results

        # Add rating lists to the row
        for rating_key, rating_values in all_ratings.items():
            row[f"{rating_key}_all"] = ", ".join([str(v) for v in rating_values])

        aggregated_data.append(row)

    # Create DataFrame and export
    df = pd.DataFrame(aggregated_data)
    df = df.sort_values("task_number")
    df.to_csv(output_file, index=False)
    print(f"\n✅ Aggregated results exported to {output_file}")
    print(f"   Tasks with results: {len(df)}")

    return df


def diagnose_json_errors():
    """
    Diagnostic function to identify and report all JSON parsing issues.
    """
    try:
        conn = create_connection()
        cursor = conn.cursor()

        query = """
        SELECT id, prolific_id, json_string
        FROM results
        """

        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        print("\n🔍 JSON Diagnostic Report")
        print("=" * 80)

        total = len(results)
        errors = []

        for row in results:
            result_id = row[0]
            prolific_id = row[1]
            json_string = row[2]

            parsed = safe_json_parse(json_string, result_id)
            if parsed is None and json_string:
                errors.append(
                    {
                        "id": result_id,
                        "prolific_id": prolific_id,
                        "json_preview": json_string[:100] if json_string else "None",
                    }
                )

        print(f"\nTotal records: {total}")
        print(f"Parse errors: {len(errors)}")

        if errors:
            print(f"\n❌ Records with JSON errors:")
            for err in errors[:10]:  # Show first 10 errors
                print(f"\n   ID: {err['id']}")
                print(f"   Prolific ID: {err['prolific_id']}")
                print(f"   JSON Preview: {err['json_preview']}...")

    except (sqlite3.Error, psycopg2.Error) as e:
        print(f"Database error: {e}")


def print_task_summary(task_number):
    """
    Prints a detailed summary of all ratings for a specific task.
    """
    grouped = group_results_by_task_number()

    if grouped is None or task_number not in grouped:
        print(f"No results found for task {task_number}")
        return

    results = grouped[task_number]

    print(f"\n{'=' * 60}")
    print(f"TASK NUMBER: {task_number}")
    print(f"Total Completions: {len(results)}")
    print(f"{'=' * 60}\n")

    for idx, result in enumerate(results, 1):
        print(f"Completion #{idx}")
        print(f"  Participant ID: {result['prolific_id']}")
        print(f"  Session ID: {result['session_id']}")
        print(f"  Time Allocated: {result['time_allocated']}")

        if result.get("parsed_ratings"):
            print(f"  Ratings:")
            for key, value in result["parsed_ratings"].items():
                if key not in ["task_id", "prolific_pid", "session_id"]:
                    print(f"    {key}: {value}")
        else:
            print(f"  ⚠️  No valid ratings data available")
        print()


# ============================================================================
# COMMON ANALYSIS TASKS
# ============================================================================


def calculate_average_ratings_per_task(csv_file="results_analysis.csv"):
    """
    Calculate average ratings per task for all grammar items.

    Returns:
        DataFrame with mean ratings per task
    """
    print("\n📊 Calculating Average Ratings per Task...")

    # Load the detailed results
    df = pd.read_csv(csv_file)

    # Get all grammar rating columns
    grammar_cols = [col for col in df.columns if col.startswith("grammar-item")]

    if not grammar_cols:
        print("❌ No grammar rating columns found!")
        return None

    # Calculate mean ratings per task
    task_means = df.groupby("task_number")[grammar_cols].mean()

    # Add overall average across all items
    task_means["overall_average"] = task_means.mean(axis=1)

    # Sort by task number
    task_means = task_means.sort_index()

    print(f"✅ Calculated averages for {len(task_means)} tasks")
    print(f"\nSample (first 5 tasks):")
    print(task_means.head())

    # Export to CSV
    output_file = "task_average_ratings.csv"
    task_means.to_csv(output_file)
    print(f"\n💾 Saved to {output_file}")

    return task_means


def analyze_inter_annotator_agreement(csv_file="aggregated_results.csv"):
    """
    Analyze inter-annotator agreement for each grammar item.
    Calculates standard deviation and coefficient of variation.

    Returns:
        DataFrame with agreement statistics per task and item
    """
    print("\n📊 Analyzing Inter-Annotator Agreement...")

    # Load aggregated results
    agg_df = pd.read_csv(csv_file)

    agreement_data = []

    # Check if we have the responses_all column (new format)
    if "responses_all" in agg_df.columns:
        print("   ℹ️  Found 'responses_all' column, parsing responses...")

        for idx, row in agg_df.iterrows():
            task_num = row["task_number"]

            if pd.notna(row["responses_all"]):
                # Parse the responses_all column which contains comma-separated dicts
                try:
                    import ast

                    # Split by dictionary boundaries
                    responses_str = str(row["responses_all"])

                    # Extract individual response dictionaries
                    responses_list = []
                    current_dict = ""
                    brace_count = 0

                    for char in responses_str:
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1

                        current_dict += char

                        if brace_count == 0 and current_dict.strip():
                            try:
                                parsed = ast.literal_eval(
                                    current_dict.strip().rstrip(",")
                                )
                                responses_list.append(parsed)
                                current_dict = ""
                            except:
                                current_dict = ""

                    # Now we have a list of response dictionaries
                    # Collect ratings for each grammar item
                    all_item_ratings = {}

                    for response_dict in responses_list:
                        for key, value in response_dict.items():
                            if key.startswith("grammar-item"):
                                if key not in all_item_ratings:
                                    all_item_ratings[key] = []
                                all_item_ratings[key].append(float(value))

                    # Calculate agreement statistics for each item
                    for item_name, ratings in all_item_ratings.items():
                        if len(ratings) > 1:
                            agreement_data.append(
                                {
                                    "task_number": task_num,
                                    "item": item_name,
                                    "mean": np.mean(ratings),
                                    "std": np.std(ratings, ddof=1),
                                    "cv": np.std(ratings, ddof=1) / np.mean(ratings)
                                    if np.mean(ratings) > 0
                                    else 0,
                                    "min": min(ratings),
                                    "max": max(ratings),
                                    "range": max(ratings) - min(ratings),
                                    "num_ratings": len(ratings),
                                }
                            )

                except Exception as e:
                    print(f"   ⚠️  Error parsing task {task_num}: {e}")

    else:
        # Old format: individual grammar-item columns with _all suffix
        for idx, row in agg_df.iterrows():
            task_num = row["task_number"]

            # Process each grammar item
            for col in agg_df.columns:
                if col.endswith("_all") and col.startswith("grammar-item"):
                    item_name = col.replace("_all", "")

                    if pd.notna(row[col]):
                        # Parse ratings
                        ratings = [
                            float(x) for x in str(row[col]).split(", ") if x.strip()
                        ]

                        if ratings:
                            agreement_data.append(
                                {
                                    "task_number": task_num,
                                    "item": item_name,
                                    "mean": np.mean(ratings),
                                    "std": np.std(ratings, ddof=1),
                                    "cv": np.std(ratings, ddof=1) / np.mean(ratings)
                                    if np.mean(ratings) > 0
                                    else 0,
                                    "min": min(ratings),
                                    "max": max(ratings),
                                    "range": max(ratings) - min(ratings),
                                    "num_ratings": len(ratings),
                                }
                            )

    if not agreement_data:
        print("❌ No rating data found!")
        return None

    agreement_df = pd.DataFrame(agreement_data)

    print(f"✅ Analyzed {len(agreement_df)} task-item combinations")
    print(f"\nAgreement Summary:")
    print(f"   Average Std Dev: {agreement_df['std'].mean():.3f}")
    print(f"   Average CV: {agreement_df['cv'].mean():.3f}")

    # Show sample
    print(f"\n   Sample data (first 5 rows):")
    print(agreement_df.head().to_string(index=False))

    # Export to CSV
    output_file = "inter_annotator_agreement.csv"
    agreement_df.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}")

    return agreement_df


def identify_problematic_tasks(csv_file="results_analysis.csv", threshold=4.0):
    """
    Identify tasks with low average grammaticality ratings.

    Args:
        csv_file: Path to results CSV file
        threshold: Rating threshold below which tasks are considered problematic

    Returns:
        DataFrame with problematic tasks
    """
    print(f"\n🔍 Identifying Problematic Tasks (threshold < {threshold})...")

    df = pd.read_csv(csv_file)

    # Get all grammar rating columns
    grammar_cols = [col for col in df.columns if col.startswith("grammar-item")]

    if not grammar_cols:
        print("❌ No grammar rating columns found!")
        return None

    # Calculate average grammar rating for each row
    df["avg_grammar"] = df[grammar_cols].mean(axis=1)

    # Filter problematic tasks
    low_quality = df[df["avg_grammar"] < threshold][
        ["task_number", "prolific_id", "avg_grammar"]
    ].sort_values("avg_grammar")

    print(f"✅ Found {len(low_quality)} problematic task completions")

    if len(low_quality) > 0:
        print(f"\nWorst 10 completions:")
        print(low_quality.head(10))

        # Group by task to see which tasks are consistently problematic
        problematic_tasks = (
            low_quality.groupby("task_number")
            .agg({"avg_grammar": ["mean", "count"]})
            .round(3)
        )
        problematic_tasks.columns = ["avg_rating", "num_low_ratings"]

        print(f"\n📋 Tasks with multiple low ratings:")
        print(problematic_tasks[problematic_tasks["num_low_ratings"] > 1])

    # Export to CSV
    output_file = "problematic_tasks.csv"
    low_quality.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}")

    return low_quality


def analyze_by_demographics(csv_file="results_analysis.csv"):
    """
    Analyze ratings by demographic groups (age, gender, English proficiency).

    Returns:
        Dictionary with DataFrames for each demographic analysis
    """
    print("\n📊 Analyzing Ratings by Demographics...")

    df = pd.read_csv(csv_file)

    # Get all grammar rating columns
    grammar_cols = [col for col in df.columns if col.startswith("grammar-item")]

    if not grammar_cols:
        print("❌ No grammar rating columns found!")
        return None

    # Calculate average grammar rating
    df["avg_grammar"] = df[grammar_cols].mean(axis=1)

    results = {}

    # Analyze by age
    if "age" in df.columns:
        age_analysis = (
            df.groupby("age")["avg_grammar"].agg(["mean", "std", "count"]).round(3)
        )
        results["age"] = age_analysis
        print(f"\n📈 By Age Group:")
        print(age_analysis)

    # Analyze by gender
    if "gender" in df.columns:
        gender_analysis = (
            df.groupby("gender")["avg_grammar"].agg(["mean", "std", "count"]).round(3)
        )
        results["gender"] = gender_analysis
        print(f"\n👥 By Gender:")
        print(gender_analysis)

    # Analyze by English proficiency
    if "english_proficiency" in df.columns:
        proficiency_analysis = (
            df.groupby("english_proficiency")["avg_grammar"]
            .agg(["mean", "std", "count"])
            .round(3)
        )
        results["english_proficiency"] = proficiency_analysis
        print(f"\n🗣️ By English Proficiency:")
        print(proficiency_analysis)

    # Export to Excel with multiple sheets
    output_file = "demographic_analysis.xlsx"
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for demo_type, demo_df in results.items():
            demo_df.to_excel(writer, sheet_name=demo_type)

    print(f"\n💾 Saved to {output_file}")

    return results


def check_incomplete_responses(csv_file="results_analysis.csv"):
    """
    Check for incomplete responses (missing ratings).

    Returns:
        DataFrame with incomplete responses
    """
    print("\n🔍 Checking for Incomplete Responses...")

    df = pd.read_csv(csv_file)

    # Get all grammar rating columns
    grammar_cols = [col for col in df.columns if col.startswith("grammar-item")]

    if not grammar_cols:
        print("❌ No grammar rating columns found!")
        return None

    # Count missing ratings per participant
    df["missing_count"] = df[grammar_cols].isna().sum(axis=1)

    # Filter incomplete responses
    incomplete = df[df["missing_count"] > 0][
        ["prolific_id", "task_number", "missing_count"]
    ].sort_values("missing_count", ascending=False)

    print(f"✅ Found {len(incomplete)} incomplete responses")

    if len(incomplete) > 0:
        print(f"\nParticipants with most missing data:")
        print(incomplete.head(10))

        # Summary by participant
        participant_summary = (
            incomplete.groupby("prolific_id")
            .agg({"missing_count": "sum", "task_number": "count"})
            .rename(columns={"task_number": "num_incomplete_tasks"})
        )
        print(f"\n👤 By Participant:")
        print(participant_summary.sort_values("missing_count", ascending=False))

    # Export to CSV
    output_file = "incomplete_responses.csv"
    incomplete.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}")

    return incomplete


def check_suspicious_patterns(csv_file="results_analysis.csv"):
    """
    Check for suspicious response patterns (e.g., all same rating, straight-lining).

    Returns:
        DataFrame with suspicious responses
    """
    print("\n🚨 Checking for Suspicious Response Patterns...")

    df = pd.read_csv(csv_file)

    # Get all grammar rating columns
    grammar_cols = [col for col in df.columns if col.startswith("grammar-item")]

    if not grammar_cols:
        print("❌ No grammar rating columns found!")
        return None

    suspicious_data = []

    for idx, row in df.iterrows():
        ratings = row[grammar_cols].dropna()

        if len(ratings) == 0:
            continue

        # Check for all same rating (straight-lining)
        all_same = ratings.nunique() == 1

        # Check for very low variance
        low_variance = ratings.std() < 0.5 if len(ratings) > 1 else False

        # Check for response time if available (placeholder)

        if all_same or low_variance:
            suspicious_data.append(
                {
                    "prolific_id": row["prolific_id"],
                    "task_number": row["task_number"],
                    "all_same": all_same,
                    "low_variance": low_variance,
                    "std": ratings.std(),
                    "unique_values": ratings.nunique(),
                    "most_common_rating": ratings.mode()[0]
                    if len(ratings) > 0
                    else None,
                }
            )

    if not suspicious_data:
        print("✅ No suspicious patterns detected!")
        return pd.DataFrame()

    suspicious_df = pd.DataFrame(suspicious_data)

    print(f"⚠️  Found {len(suspicious_df)} suspicious responses")
    print(f"\n   Straight-lining (all same): {suspicious_df['all_same'].sum()}")
    print(f"   Low variance: {suspicious_df['low_variance'].sum()}")

    if len(suspicious_df) > 0:
        print(f"\nMost suspicious responses:")
        print(suspicious_df.head(10))

    # Export to CSV
    output_file = "suspicious_responses.csv"
    suspicious_df.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}")

    return suspicious_df


def calculate_fleiss_kappa(csv_file="aggregated_results.csv", max_items=None):
    """
    Calculate Fleiss' Kappa for inter-annotator agreement.

    Args:
        csv_file: Path to aggregated results CSV
        max_items: Maximum number of items to analyze (None for all)

    Returns:
        DataFrame with Fleiss' Kappa for each item
    """
    print("\n📊 Calculating Fleiss' Kappa (Inter-Annotator Agreement)...")

    try:
        from statsmodels.stats.inter_rater import fleiss_kappa
    except ImportError:
        print("❌ statsmodels not installed. Install with: pip install statsmodels")
        return None

    # Load aggregated results
    agg_df = pd.read_csv(csv_file)

    kappa_results = []

    # Check if we have the responses_all column (new format)
    if "responses_all" in agg_df.columns:
        print("   ℹ️  Found 'responses_all' column, parsing responses...")

        import ast

        # Collect all ratings per grammar item across all tasks
        all_item_ratings = {}

        for idx, row in agg_df.iterrows():
            if pd.notna(row["responses_all"]):
                try:
                    responses_str = str(row["responses_all"])

                    # Extract individual response dictionaries
                    responses_list = []
                    current_dict = ""
                    brace_count = 0

                    for char in responses_str:
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1

                        current_dict += char

                        if brace_count == 0 and current_dict.strip():
                            try:
                                parsed = ast.literal_eval(
                                    current_dict.strip().rstrip(",")
                                )
                                responses_list.append(parsed)
                                current_dict = ""
                            except:
                                current_dict = ""

                    # Organize by grammar item
                    for response_dict in responses_list:
                        for key, value in response_dict.items():
                            if key.startswith("grammar-item"):
                                if key not in all_item_ratings:
                                    all_item_ratings[key] = []
                                all_item_ratings[key].append(int(float(value)))

                except Exception as e:
                    print(f"   ⚠️  Error parsing row {idx}: {e}")

        # Calculate Fleiss' Kappa for each item
        items_to_process = list(all_item_ratings.keys())
        if max_items:
            items_to_process = items_to_process[:max_items]

        for item_name in items_to_process:
            ratings = all_item_ratings[item_name]

            # Group ratings by task (assume every N ratings is one task)
            num_tasks = len(agg_df)
            ratings_per_task = len(ratings) // num_tasks if num_tasks > 0 else 0

            if ratings_per_task > 1:
                # Create matrix: each row is a task, columns are counts of ratings 1-7
                ratings_matrix = []

                for task_idx in range(num_tasks):
                    start_idx = task_idx * ratings_per_task
                    end_idx = start_idx + ratings_per_task
                    task_ratings = ratings[start_idx:end_idx]

                    # Count occurrences of each rating (1-7)
                    counts = [task_ratings.count(i) for i in range(1, 8)]
                    ratings_matrix.append(counts)

                try:
                    kappa = fleiss_kappa(ratings_matrix, method="fleiss")
                    kappa_results.append(
                        {
                            "item": item_name,
                            "fleiss_kappa": round(kappa, 4),
                            "num_tasks": num_tasks,
                            "ratings_per_task": ratings_per_task,
                            "interpretation": interpret_kappa(kappa),
                        }
                    )
                except Exception as e:
                    print(f"   ⚠️  Error calculating kappa for {item_name}: {e}")

    else:
        # Old format with individual columns
        grammar_cols = [
            col
            for col in agg_df.columns
            if col.startswith("grammar-item") and col.endswith("_all")
        ]

        if max_items:
            grammar_cols = grammar_cols[:max_items]

        for col in grammar_cols:
            item_name = col.replace("_all", "")

            # Convert ratings to matrix format
            ratings_matrix = []
            valid_tasks = 0

            for ratings_str in agg_df[col].dropna():
                try:
                    ratings = [int(float(x)) for x in str(ratings_str).split(", ")]
                    # Count occurrences of each rating (1-7)
                    counts = [ratings.count(i) for i in range(1, 8)]
                    ratings_matrix.append(counts)
                    valid_tasks += 1
                except (ValueError, AttributeError):
                    continue

            if len(ratings_matrix) > 0:
                try:
                    kappa = fleiss_kappa(ratings_matrix, method="fleiss")
                    kappa_results.append(
                        {
                            "item": item_name,
                            "fleiss_kappa": round(kappa, 4),
                            "num_tasks": valid_tasks,
                            "interpretation": interpret_kappa(kappa),
                        }
                    )
                except Exception as e:
                    print(f"   ⚠️  Error calculating kappa for {item_name}: {e}")

    if not kappa_results:
        print("❌ No valid kappa calculations!")
        return None

    kappa_df = pd.DataFrame(kappa_results)

    print(f"✅ Calculated Fleiss' Kappa for {len(kappa_df)} items")
    print(f"\n{kappa_df.to_string(index=False)}")

    # Export to CSV
    output_file = "fleiss_kappa_results.csv"
    kappa_df.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}")

    return kappa_df

def calculate_overall_fleiss_kappa(csv_file="aggregated_results.csv"):
    """
    Calculate overall Fleiss' Kappa across all grammar items.
    This provides a single measure of inter-annotator agreement for the entire study.

    Args:
        csv_file: Path to aggregated results CSV

    Returns:
        Dictionary with overall kappa value and interpretation
    """
    print("\n📊 Calculating Overall Fleiss' Kappa...")

    try:
        from statsmodels.stats.inter_rater import fleiss_kappa
    except ImportError:
        print("❌ statsmodels not installed. Install with: pip install statsmodels")
        return None

    # Load aggregated results
    agg_df = pd.read_csv(csv_file)

    # Check if we have the responses_all column
    if "responses_all" not in agg_df.columns:
        print("❌ 'responses_all' column not found!")
        return None

    print("   ℹ️  Parsing all responses...")

    import ast

    # Collect ALL ratings across all items and all tasks
    all_ratings_by_task = []  # Each element will be a list of response dicts for one task

    for idx, row in agg_df.iterrows():
        if pd.notna(row["responses_all"]):
            try:
                responses_str = str(row["responses_all"])

                # Extract individual response dictionaries
                responses_list = []
                current_dict = ""
                brace_count = 0

                for char in responses_str:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1

                    current_dict += char

                    if brace_count == 0 and current_dict.strip():
                        try:
                            parsed = ast.literal_eval(current_dict.strip().rstrip(","))
                            responses_list.append(parsed)
                            current_dict = ""
                        except:
                            current_dict = ""

                # Store all responses for this task
                if len(responses_list) > 0:
                    all_ratings_by_task.append(responses_list)

            except Exception as e:
                print(f"   ⚠️  Error parsing row {idx}: {e}")

    if not all_ratings_by_task:
        print("❌ No valid rating data found!")
        return None

    # Determine the number of raters (should be consistent)
    num_raters_per_task = [
        len(task_responses) for task_responses in all_ratings_by_task
    ]

    print(
        f"   ℹ️  Number of raters per task: min={min(num_raters_per_task)}, max={max(num_raters_per_task)}, mean={np.mean(num_raters_per_task):.1f}"
    )

    # Use only tasks with the most common number of raters to ensure consistency
    from collections import Counter

    rater_count_distribution = Counter(num_raters_per_task)
    most_common_rater_count = rater_count_distribution.most_common(1)[0][0]

    print(f"   ℹ️  Using tasks with {most_common_rater_count} raters (most common)")

    # Filter to only tasks with consistent number of raters
    filtered_ratings = [
        task for task in all_ratings_by_task if len(task) == most_common_rater_count
    ]

    print(
        f"   ℹ️  Filtered from {len(all_ratings_by_task)} to {len(filtered_ratings)} tasks"
    )

    # Now create a combined rating matrix
    # We'll treat each (task, item) combination as a separate subject
    print(f"   ℹ️  Processing {len(filtered_ratings)} tasks...")

    all_rating_vectors = []

    for task_responses in filtered_ratings:
        # Get all grammar items from first response (to know which items exist)
        if len(task_responses) > 0:
            grammar_items = sorted(
                [
                    key
                    for key in task_responses[0].keys()
                    if key.startswith("grammar-item")
                ]
            )

            # For each grammar item in this task, collect all raters' responses
            for item_name in grammar_items:
                item_ratings = []

                # Collect ratings from all raters for this item
                for response_dict in task_responses:
                    if item_name in response_dict:
                        try:
                            rating = int(float(response_dict[item_name]))
                            item_ratings.append(rating)
                        except (ValueError, TypeError):
                            print(
                                f"   ⚠️  Invalid rating for {item_name}: {response_dict[item_name]}"
                            )

                # Only include if we have ratings from all raters
                if len(item_ratings) == most_common_rater_count:
                    # Create counts for ratings 1-7
                    counts = [item_ratings.count(i) for i in range(1, 8)]
                    all_rating_vectors.append(counts)

    if len(all_rating_vectors) == 0:
        print("❌ Insufficient rating data for Fleiss' Kappa calculation!")
        return None

    # Convert to numpy array
    ratings_matrix = np.array(all_rating_vectors)

    print(f"   ℹ️  Matrix shape: {ratings_matrix.shape}")
    print(f"   ℹ️  Total subjects (task×item combinations): {len(all_rating_vectors)}")
    print(f"   ℹ️  Raters per subject: {most_common_rater_count}")
    print(f"   ℹ️  Rating categories: 7 (scale 1-7)")

    # Verify the matrix sum is correct
    expected_total = len(all_rating_vectors) * most_common_rater_count
    actual_total = ratings_matrix.sum()
    print(f"   ℹ️  Total ratings: expected={expected_total}, actual={actual_total}")

    # Calculate overall Fleiss' Kappa
    try:
        overall_kappa = fleiss_kappa(ratings_matrix, method="fleiss")

        result = {
            "overall_kappa": round(overall_kappa, 4),
            "interpretation": interpret_kappa(overall_kappa),
            "num_subjects": len(all_rating_vectors),
            "num_tasks": len(filtered_ratings),
            "num_raters": most_common_rater_count,
            "excluded_tasks": len(all_ratings_by_task) - len(filtered_ratings),
        }

        print(f"\n✅ Overall Fleiss' Kappa Calculated!")
        print(f"   📊 Kappa: {result['overall_kappa']}")
        print(f"   📝 Interpretation: {result['interpretation']}")
        print(f"   🎯 Subjects analyzed: {result['num_subjects']}")
        print(f"   📋 Tasks: {result['num_tasks']}")
        print(f"   👥 Raters per subject: {result['num_raters']}")
        if result["excluded_tasks"] > 0:
            print(
                f"   ⚠️  Excluded tasks (inconsistent rater count): {result['excluded_tasks']}"
            )

        # Save to file
        output_file = "overall_fleiss_kappa.txt"
        with open(output_file, "w") as f:
            f.write("=" * 60 + "\n")
            f.write("OVERALL FLEISS' KAPPA - INTER-RATER AGREEMENT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Overall Kappa:       {result['overall_kappa']}\n")
            f.write(f"Interpretation:      {result['interpretation']}\n")
            f.write(f"Subjects Analyzed:   {result['num_subjects']}\n")
            f.write(f"Tasks Included:      {result['num_tasks']}\n")
            f.write(f"Tasks Excluded:      {result['excluded_tasks']}\n")
            f.write(f"Raters per Subject:  {result['num_raters']}\n\n")
            f.write(
                "Note: Only tasks with consistent number of raters were included.\n\n"
            )
            f.write("Kappa Interpretation Scale:\n")
            f.write("  < 0.00:  Poor\n")
            f.write("  0.00-0.20: Slight\n")
            f.write("  0.20-0.40: Fair\n")
            f.write("  0.40-0.60: Moderate\n")
            f.write("  0.60-0.80: Substantial\n")
            f.write("  0.80-1.00: Almost Perfect\n")

        print(f"\n💾 Saved to {output_file}")

        return result

    except Exception as e:
        print(f"❌ Error calculating overall Fleiss' Kappa: {e}")
        import traceback

        traceback.print_exc()

        # Debug info
        print(f"\n🔍 Debug Info:")
        print(f"   Matrix shape: {ratings_matrix.shape}")
        print(f"   Matrix sum per row (first 5): {ratings_matrix.sum(axis=1)[:5]}")
        print(f"   Expected sum per row: {most_common_rater_count}")

        return None

def calculate_kappa_by_item_group(csv_file="aggregated_results.csv", items_per_group=8):
    """
    Calculate Fleiss' Kappa for groups of items (e.g., every 8 items).
    Useful for understanding agreement patterns across different sections.

    Args:
        csv_file: Path to aggregated results CSV
        items_per_group: Number of items to group together

    Returns:
        DataFrame with kappa per group
    """
    print(
        f"\n📊 Calculating Fleiss' Kappa by Item Groups ({items_per_group} items/group)..."
    )

    try:
        from statsmodels.stats.inter_rater import fleiss_kappa
    except ImportError:
        print("❌ statsmodels not installed. Install with: pip install statsmodels")
        return None

    agg_df = pd.read_csv(csv_file)

    if "responses_all" not in agg_df.columns:
        print("❌ 'responses_all' column not found!")
        return None

    import ast

    # Collect ratings by item
    all_item_ratings = {}

    for idx, row in agg_df.iterrows():
        if pd.notna(row["responses_all"]):
            try:
                responses_str = str(row["responses_all"])
                responses_list = []
                current_dict = ""
                brace_count = 0

                for char in responses_str:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                    current_dict += char
                    if brace_count == 0 and current_dict.strip():
                        try:
                            parsed = ast.literal_eval(current_dict.strip().rstrip(","))
                            responses_list.append(parsed)
                            current_dict = ""
                        except:
                            current_dict = ""

                for response_dict in responses_list:
                    for key, value in response_dict.items():
                        if key.startswith("grammar-item"):
                            if key not in all_item_ratings:
                                all_item_ratings[key] = []
                            all_item_ratings[key].append(int(float(value)))

            except Exception as e:
                print(f"   ⚠️  Error parsing row {idx}: {e}")

    # Sort items and group them
    sorted_items = sorted(all_item_ratings.keys())
    num_groups = (len(sorted_items) + items_per_group - 1) // items_per_group

    group_results = []

    for group_idx in range(num_groups):
        start_idx = group_idx * items_per_group
        end_idx = min(start_idx + items_per_group, len(sorted_items))
        group_items = sorted_items[start_idx:end_idx]

        print(f"\n   Processing Group {group_idx + 1}: Items {start_idx + 1}-{end_idx}")

        # Combine ratings from all items in this group
        group_rating_vectors = []

        # Assume same number of tasks for all items
        num_tasks = len(agg_df)
        ratings_per_task = (
            len(all_item_ratings[group_items[0]]) // num_tasks if num_tasks > 0 else 0
        )

        for item_name in group_items:
            ratings = all_item_ratings[item_name]

            for task_idx in range(num_tasks):
                start = task_idx * ratings_per_task
                end = start + ratings_per_task
                task_ratings = ratings[start:end]

                if len(task_ratings) > 1:
                    counts = [task_ratings.count(i) for i in range(1, 8)]
                    group_rating_vectors.append(counts)

        if len(group_rating_vectors) > 0:
            try:
                ratings_matrix = np.array(group_rating_vectors)
                kappa = fleiss_kappa(ratings_matrix, method="fleiss")

                group_results.append(
                    {
                        "group": f"Group {group_idx + 1}",
                        "items": f"{sorted_items[start_idx]}-{sorted_items[end_idx - 1]}",
                        "num_items": len(group_items),
                        "fleiss_kappa": round(kappa, 4),
                        "interpretation": interpret_kappa(kappa),
                        "num_subjects": len(group_rating_vectors),
                    }
                )

            except Exception as e:
                print(f"   ⚠️  Error calculating kappa for group {group_idx + 1}: {e}")

    if not group_results:
        print("❌ No valid group kappa calculations!")
        return None

    group_df = pd.DataFrame(group_results)

    print(f"\n✅ Calculated Fleiss' Kappa for {len(group_df)} groups")
    print(f"\n{group_df.to_string(index=False)}")

    # Export to CSV
    output_file = "kappa_by_item_group.csv"
    group_df.to_csv(output_file, index=False)
    print(f"\n💾 Saved to {output_file}")

    return group_df

def interpret_kappa(kappa):
    """Interpret Fleiss' Kappa value"""
    if kappa < 0:
        return "Poor"
    elif kappa < 0.20:
        return "Slight"
    elif kappa < 0.40:
        return "Fair"
    elif kappa < 0.60:
        return "Moderate"
    elif kappa < 0.80:
        return "Substantial"
    else:
        return "Almost Perfect"


def export_to_excel_comprehensive(output_file="comprehensive_results.xlsx"):
    """
    Export all results to a comprehensive Excel file with multiple sheets.

    Returns:
        Path to the created Excel file
    """
    print("\n📊 Creating Comprehensive Excel Report...")

    try:
        # First, generate all the CSV files
        detailed_df = export_to_csv("results_analysis.csv")
        aggregated_df = export_aggregated_by_task("aggregated_results.csv")

        # Run all analyses
        avg_ratings = calculate_average_ratings_per_task("results_analysis.csv")
        agreement = analyze_inter_annotator_agreement("aggregated_results.csv")
        problematic = identify_problematic_tasks("results_analysis.csv")
        demographics = analyze_by_demographics("results_analysis.csv")
        incomplete = check_incomplete_responses("results_analysis.csv")
        suspicious = check_suspicious_patterns("results_analysis.csv")

        # Create Excel writer
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            # Main data sheets
            pd.read_csv("results_analysis.csv").to_excel(
                writer, sheet_name="Detailed_Results", index=False
            )
            pd.read_csv("aggregated_results.csv").to_excel(
                writer, sheet_name="Aggregated_Results", index=False
            )

            # Analysis sheets
            if avg_ratings is not None:
                avg_ratings.to_excel(writer, sheet_name="Average_Ratings")

            if agreement is not None:
                agreement.to_excel(
                    writer, sheet_name="Inter_Annotator_Agreement", index=False
                )

            if problematic is not None and len(problematic) > 0:
                problematic.to_excel(
                    writer, sheet_name="Problematic_Tasks", index=False
                )

            if demographics is not None:
                for demo_type, demo_df in demographics.items():
                    sheet_name = f"Demo_{demo_type[:20]}"  # Limit sheet name length
                    demo_df.to_excel(writer, sheet_name=sheet_name)

            if incomplete is not None and len(incomplete) > 0:
                incomplete.to_excel(
                    writer, sheet_name="Incomplete_Responses", index=False
                )

            if suspicious is not None and len(suspicious) > 0:
                suspicious.to_excel(
                    writer, sheet_name="Suspicious_Patterns", index=False
                )

        print(f"\n✅ Comprehensive Excel report created: {output_file}")
        return output_file

    except Exception as e:
        print(f"❌ Error creating comprehensive Excel report: {e}")
        return None


def run_all_analyses():
    """
    Run all analysis functions and generate comprehensive reports.
    """
    print("\n" + "=" * 80)
    print("🚀 RUNNING COMPREHENSIVE ANALYSIS")
    print("=" * 80)

    # Step 1: Diagnose JSON issues
    print("\n[1/10] Diagnosing JSON parsing issues...")
    diagnose_json_errors()

    # Step 2: Export base files
    print("\n[2/10] Exporting detailed results...")
    export_to_csv("results_analysis.csv")

    print("\n[3/10] Exporting aggregated results...")
    export_aggregated_by_task("aggregated_results.csv")

    # Step 3: Run analyses
    print("\n[4/10] Calculating average ratings...")
    calculate_average_ratings_per_task()

    print("\n[5/10] Analyzing inter-annotator agreement...")
    analyze_inter_annotator_agreement()

    print("\n[6/10] Identifying problematic tasks...")
    identify_problematic_tasks()

    print("\n[7/10] Analyzing by demographics...")
    analyze_by_demographics()

    print("\n[8/10] Checking for quality issues...")
    check_incomplete_responses()
    check_suspicious_patterns()

    # Step 4: Calculate Fleiss' Kappa
    print("\n[9/10] Calculating Fleiss' Kappa per item...")
    calculate_fleiss_kappa()

    print("\n[10/10] Calculating Overall Fleiss' Kappa...")
    calculate_overall_fleiss_kappa()

    # Bonus: Calculate kappa by item groups
    print("\n[Bonus] Calculating Fleiss' Kappa by item groups...")
    calculate_kappa_by_item_group()

    # Step 5: Create comprehensive Excel report
    print("\n[Final] Creating comprehensive Excel report...")
    export_to_excel_comprehensive()

    print("\n" + "=" * 80)
    print("✅ ANALYSIS COMPLETE!")
    print("=" * 80)
    print("\nGenerated files:")
    print("  • results_analysis.csv")
    print("  • aggregated_results.csv")
    print("  • task_average_ratings.csv")
    print("  • inter_annotator_agreement.csv")
    print("  • problematic_tasks.csv")
    print("  • demographic_analysis.xlsx")
    print("  • incomplete_responses.csv")
    print("  • suspicious_responses.csv")
    print("  • fleiss_kappa_results.csv")
    print("  • overall_fleiss_kappa.txt")
    print("  • kappa_by_item_group.csv")
    print("  • comprehensive_results.xlsx")


if __name__ == "__main__":
    # Run comprehensive analysis
    run_all_analyses()
