#!/usr/bin/env python3
"""
Canvas Quiz Scraper

A robust tool to scrape student answers and comments from Canvas quiz submissions.
Uses Playwright to connect to an existing authenticated browser session via CDP.

This script is designed to be cross-platform and should work on macOS, Linux, and Windows as long as Python, Playwright, and Chrome/Chromium are installed. See the "Troubleshooting & OS-Specific Notes" section in the README for details on starting Chrome/Chromium with remote debugging and common connection issues.

Requirements:
- playwright (`pip install playwright`)
- An active browser session logged into Canvas with remote debugging enabled
"""

import json
import csv
import sys
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

EXTRACT_JS = """
(function() {
    var data = {
        student_name: '',
        quiz_submission_id: new URLSearchParams(window.location.search).get('quiz_submission_id'),
        total_score: '',
        finished_at: '',
        questions: []
    };
    
    // Get student name from title
    var title = document.title || '';
    var nameMatch = title.match(/^(.+?)'s quiz history/);
    if (nameMatch) data.student_name = nameMatch[1].trim();
    
    // Get score
    var scoreText = document.body.innerText.match(/Score for this quiz: ([\\d.]+) out of/);
    if (scoreText) data.total_score = scoreText[1];
    
    // Get submission time
    var submittedText = document.body.innerText.match(/Submitted (.+)/);
    if (submittedText) data.finished_at = submittedText[1].trim();
    
    document.querySelectorAll('.question').forEach(function(q) {
        var qNum = q.querySelector('.question_name')?.textContent?.trim() || '';
        var qId = q.id || '';
        var qText = q.querySelector('.question_text')?.innerText?.replace(/\\s+/g,' ').trim() || '';
        var scoreInput = q.querySelector('input[id$="_visible"]');
        var qScore = scoreInput ? scoreInput.value : '';
        var textAnswer = q.querySelector('.quiz_response_text')?.innerText?.trim() || '';
        var selectedAnswers = [];
        q.querySelectorAll('.selected_answer .answer_text').forEach(function(a) {
            selectedAnswers.push(a.innerText.trim());
        });
        var comment = q.querySelector('textarea[id^="question_comment_"]')?.value?.trim() || '';
        data.questions.push({
            question_number: qNum,
            question_id: qId,
            question_text: qText.substring(0, 300),
            q_score: qScore,
            selected_answers: selectedAnswers.join(' | '),
            student_text_answer: textAnswer,
            instructor_comment: comment
        });
    });
    return JSON.stringify(data);
})()
"""

FIELDNAMES = [
    'student_name', 'quiz_submission_id', 'total_score', 'finished_at',
    'question_number', 'question_id', 'question_text',
    'q_score', 'selected_answers', 'student_text_answer', 'instructor_comment'
]

def parse_args():
    parser = argparse.ArgumentParser(description="Scrape Canvas quiz submissions into a CSV.")
    parser.add_argument('--url', type=str, required=True, help="Base URL of Canvas (e.g. https://canvas.nus.edu.sg)")
    parser.add_argument('--course', type=int, required=True, help="Course ID")
    parser.add_argument('--quiz', type=int, required=True, help="Quiz ID")
    parser.add_argument('--submissions-file', type=str, required=True, help="JSON file containing list of submissions (from Canvas API)")
    parser.add_argument('--output', type=str, default="quiz_responses.csv", help="Output CSV file path")
    parser.add_argument('--cdp-port', type=int, default=9222, help="Chrome DevTools Protocol port (default: 9222)")
    parser.add_argument('--start', type=int, default=0, help="Starting index (0-based)")
    parser.add_argument('--end', type=int, default=None, help="Ending index (exclusive)")
    parser.add_argument('--save-interval', type=int, default=25, help="Save progress every N submissions")
    return parser.parse_args()

def main():
    args = parse_args()

    # Load submission list
    submissions_path = Path(args.submissions_file)
    if not submissions_path.exists():
        print(f"Error: Submissions file '{args.submissions_file}' not found.")
        sys.exit(1)
        
    with open(submissions_path, 'r', encoding='utf-8') as f:
        all_submissions = json.load(f)

    start = args.start
    end = args.end if args.end is not None else len(all_submissions)
    submissions = all_submissions[start:end]

    print(f"Processing submissions {start+1} to {end} ({len(submissions)} total)", flush=True)

    output_path = Path(args.output)
    all_rows = []
    incomplete = []

    with sync_playwright() as p:
        # Connect to existing browser via CDP
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{args.cdp_port}")
        except Exception as e:
            print(f"Error connecting to browser on port {args.cdp_port}: {e}")
            print("Make sure Chrome/Chromium is running with --remote-debugging-port=9222")
            sys.exit(1)
            
        context = browser.contexts[0]
        page = context.pages[0]
        
        print(f"Connected to browser. Current page: {page.title()}", flush=True)

        for i, sub in enumerate(submissions):
            # Handle different JSON structures from Canvas API
            quiz_submission_id = sub.get('quiz_submission_id') or sub.get('id')
            student_name = sub.get('student_name') or sub.get('user', {}).get('name', f"Student_{quiz_submission_id}")
            score = sub.get('score', '')
            finished_at = sub.get('finished_at', '')

            if not quiz_submission_id:
                print(f"Skipping entry {i} - no submission ID found")
                continue

            url = f"{args.url.rstrip('/')}/courses/{args.course}/quizzes/{args.quiz}/history?quiz_submission_id={quiz_submission_id}"
            print(f"[{i+1}/{len(submissions)}] {student_name} (id={quiz_submission_id})...", end=' ', flush=True)

            rows = None
            for attempt in range(3):
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    # Wait for questions to appear
                    try:
                        page.wait_for_selector('.question', timeout=15000)
                    except:
                        pass
                    
                    result_json = page.evaluate(EXTRACT_JS)
                    result = json.loads(result_json)
                    
                    if not result.get('questions'):
                        if attempt < 2:
                            print(f"empty(retry)...", end=' ', flush=True)
                            time.sleep(2)
                            continue
                        break
                    
                    # Check for login page
                    if 'Login' in page.title() or 'Sign In' in page.title():
                        print("\nERROR: Logged out! Please log back into Canvas in the browser.")
                        browser.close()
                        sys.exit(1)
                    
                    # Use student name from API if page name extraction fails
                    if not result.get('student_name'):
                        result['student_name'] = student_name
                    if not result.get('total_score'):
                        result['total_score'] = str(score)
                    if not result.get('finished_at'):
                        result['finished_at'] = str(finished_at)
                    
                    questions = result['questions']
                    rows = []
                    for q in questions:
                        rows.append({
                            'student_name': result['student_name'],
                            'quiz_submission_id': str(quiz_submission_id),
                            'total_score': result['total_score'],
                            'finished_at': result['finished_at'],
                            'question_number': q['question_number'],
                            'question_id': q['question_id'],
                            'question_text': q['question_text'],
                            'q_score': q['q_score'],
                            'selected_answers': q['selected_answers'],
                            'student_text_answer': q['student_text_answer'],
                            'instructor_comment': q['instructor_comment'],
                        })
                    
                    # Assume success if we got at least 1 question
                    if len(rows) > 0:
                        break
                        
                except Exception as e:
                    if attempt < 2:
                        print(f"err({type(e).__name__},retry)...", end=' ', flush=True)
                        time.sleep(3)

            if rows:
                all_rows.extend(rows)
                print(f"OK ({len(rows)} questions)", flush=True)
            else:
                incomplete.append((student_name, quiz_submission_id))
                print("FAILED", flush=True)

            # Save progress periodically
            if (i + 1) % args.save_interval == 0:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                    writer.writeheader()
                    writer.writerows(all_rows)
                print(f"  >>> Progress saved: {len(all_rows)} rows, {i+1}/{len(submissions)} students", flush=True)

        browser.close()

    # Final save
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n=== DONE ===")
    print(f"CSV saved to: {output_path}")
    print(f"Total rows: {len(all_rows)}, Students: {len(set(r['student_name'] for r in all_rows))}")
    if incomplete:
        print(f"\nFailed submissions ({len(incomplete)}):")
        for name, qsid in incomplete:
            print(f"  {name} (id={qsid})")

if __name__ == '__main__':
    main()
