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

## Troubleshooting & OS-Specific Notes

- **Cross-platform support**: The scripts are pure Python and are expected to work on **macOS, Linux, and Windows** as long as the dependencies are installed and Chrome/Chromium is available.

- **Python command name**
  - On **macOS/Linux**, your Python executable may be `python3` instead of `python`. Adjust commands accordingly:
    - `python3 fetch_submissions.py ...`
    - `python3 scrape_quiz.py ...`
  - On **Windows**, `python` is usually correct once Python is added to your PATH.

- **Chrome / Chromium path**
  - **macOS**: The example uses `/Applications/Google Chrome.app/...`. If you use a different Chrome build (e.g., Canary) or a non-standard install location, update the path accordingly.
  - **Windows**: The example uses `"C:\Program Files\Google\Chrome\Application\chrome.exe"`. On some systems it may be under `"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"` or a user-specific install path—update the command to match your system.
  - **Linux**: The example uses `chromium-browser`. If your distro uses a different binary name (e.g., `chromium` or `google-chrome`), substitute that in the command.

- **Remote debugging and login issues**
  - If `scrape_quiz.py` fails to connect with an error like **"Error connecting to browser on port 9222"**, verify that:
    - Chrome/Chromium is running.
    - It was started with `--remote-debugging-port=9222`.
    - Nothing (firewall, corporate security tools) is blocking `http://localhost:9222`.
  - If the script reports that you are **logged out** (e.g., it detects a login page), switch to the browser window, log back into Canvas, ensure you can open a quiz history page, then rerun the script.

- **Playwright not installed / browser missing**
  - If you see import errors for `playwright` or errors about missing browser binaries:
    - Install the package: `pip install playwright`
    - Install the Chromium runtime: `playwright install chromium`
  - On some systems you may need to run these with `python -m pip` or `python3 -m pip` depending on how Python is configured.

- **Encoding / CSV issues**
  - The CSV is written as UTF-8. If Excel or another tool shows garbled characters, explicitly import the file as UTF-8 or open it with a tool that supports UTF-8 by default (e.g., LibreOffice, VS Code, or a modern text editor).
