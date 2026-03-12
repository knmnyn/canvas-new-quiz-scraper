# Canvas Quiz Scraper

A robust, two-step pipeline for extracting student responses and comments from Canvas quizzes. 

The Canvas API does not easily expose the actual text of student answers and instructor comments for quizzes. This tool solves that by programmatically navigating the Canvas web interface as an authenticated user to scrape the full quiz history page for every student.

## Requirements

- Python 3.8+
- `requests` (for API fetching)
- `playwright` (for browser automation)
- A Chromium/Chrome browser

```bash
pip install requests playwright
playwright install chromium
```

## How It Works

The pipeline consists of two steps:
1. **Fetch Submissions (`fetch_submissions.py`)**: Uses the Canvas API to get a list of all students who submitted the quiz, along with their submission IDs.
2. **Scrape Responses (`scrape_quiz.py`)**: Connects to a running browser session (where you are logged into Canvas) and navigates to each student's quiz history page to extract their answers and comments into a CSV.

---

## Step 1: Fetch Submission List

First, you need to generate a Canvas API token:
1. Go to Canvas -> Account -> Settings
2. Scroll down to "Approved Integrations" and click "+ New Access Token"
3. Copy the generated token.

Run the fetch script to generate a `submissions.json` file:

```bash
export CANVAS_API_TOKEN="your_token_here"
python fetch_submissions.py \
  --url "https://canvas.nus.edu.sg" \
  --course 85611 \
  --quiz 80613 \
  --output submissions.json
```

**Arguments:**
- `--url`: Base URL of your Canvas instance
- `--course`: The Course ID (found in the URL: `/courses/XXXX`)
- `--quiz`: The Quiz ID (found in the URL: `/quizzes/YYYY`)
- `--output`: Path to save the JSON list
- `--token`: (Optional) Pass token directly instead of using env var

---

## Step 2: Scrape Responses

Because the quiz history pages require Canvas authentication (often via SSO like Microsoft/Okta), the scraper connects to an *already authenticated* browser session using the Chrome DevTools Protocol (CDP).

### 2a. Start Chrome/Chromium with Remote Debugging

Close all existing instances of Chrome/Chromium, then start it from the terminal with remote debugging enabled:

**Mac:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

**Linux:**
```bash
chromium-browser --remote-debugging-port=9222
```

### 2b. Log into Canvas

In the newly opened browser window, navigate to your Canvas URL (e.g., `https://canvas.nus.edu.sg`) and log in manually. Ensure you can access the course and quiz.

### 2c. Run the Scraper

Run the scraper script, pointing it to the JSON file generated in Step 1:

```bash
python scrape_quiz.py \
  --url "https://canvas.nus.edu.sg" \
  --course 85611 \
  --quiz 80613 \
  --submissions-file submissions.json \
  --output final_quiz_responses.csv
```

**Arguments:**
- `--url`, `--course`, `--quiz`: Same as Step 1
- `--submissions-file`: Path to the JSON file from Step 1
- `--output`: Path for the final CSV file
- `--cdp-port`: Port for browser connection (default: 9222)
- `--start`: Starting index to resume a broken run (default: 0)
- `--end`: Ending index (default: all)
- `--save-interval`: How often to save progress to the CSV (default: 25)

## Output Format

The output is a CSV file where each row represents a single question for a single student.

Columns included:
- `student_name`
- `quiz_submission_id`
- `total_score`
- `finished_at`
- `question_number` (e.g., "Question 1")
- `question_id`
- `question_text`
- `q_score` (Score for this specific question)
- `selected_answers` (For multiple choice/dropdowns, pipe `|` separated)
- `student_text_answer` (For open-ended essay questions)
- `instructor_comment` (Any additional comments left by the grader)
