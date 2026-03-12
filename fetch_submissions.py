#!/usr/bin/env python3
"""
Helper script to fetch quiz submissions from Canvas API using a provided API token.
Saves the results to a JSON file for the scraper to use.
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Canvas quiz submissions via API.")
    parser.add_argument('--url', type=str, required=True, help="Base URL of Canvas (e.g. https://canvas.nus.edu.sg)")
    parser.add_argument('--course', type=int, required=True, help="Course ID")
    parser.add_argument('--quiz', type=int, required=True, help="Quiz ID")
    parser.add_argument('--token', type=str, help="Canvas API Token (can also use CANVAS_API_TOKEN env var)")
    parser.add_argument('--output', type=str, default="submissions_list.json", help="Output JSON file path")
    return parser.parse_args()

def main():
    args = parse_args()
    
    token = args.token or os.environ.get('CANVAS_API_TOKEN')
    if not token:
        print("Error: Canvas API token is required. Pass via --token or CANVAS_API_TOKEN env var.")
        sys.exit(1)

    base_url = args.url.rstrip('/')
    api_url = f"{base_url}/api/v1/courses/{args.course}/quizzes/{args.quiz}/submissions"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    params = {
        "include[]": "user",
        "per_page": 100
    }
    
    print(f"Fetching submissions for Course {args.course}, Quiz {args.quiz}...")
    
    all_submissions = []
    
    # Handle pagination
    url = api_url
    while url:
        print(f"Fetching page: {url}")
        response = requests.get(url, headers=headers, params=params if url == api_url else None)
        
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            sys.exit(1)
            
        data = response.json()
        submissions = data.get('quiz_submissions', [])
        all_submissions.extend(submissions)
        print(f"  Got {len(submissions)} submissions. Total so far: {len(all_submissions)}")
        
        # Check for next page in Link header
        url = None
        if 'Link' in response.headers:
            links = response.headers['Link'].split(',')
            for link in links:
                if 'rel="next"' in link:
                    url = link[link.find('<')+1:link.find('>')]
                    break

    # Clean up the data to keep only what we need
    cleaned_submissions = []
    for sub in all_submissions:
        user = sub.get('user', {})
        cleaned_submissions.append({
            'quiz_submission_id': sub.get('id'),
            'student_name': user.get('name', f"Student_{sub.get('id')}"),
            'user_id': sub.get('user_id'),
            'score': sub.get('score'),
            'finished_at': sub.get('finished_at')
        })

    # Save to JSON
    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_submissions, f, indent=2)
        
    print(f"\nSuccessfully fetched {len(cleaned_submissions)} submissions.")
    print(f"Saved to: {output_path}")

if __name__ == '__main__':
    main()
