import os  # Import the os module to handle file paths and directory operations.
import sys  # Import the sys module to read command line flags like --now.
import json  # Import the json module to read configuration parameters from config.json.
import datetime  # Import the datetime module to fetch and format the current date.
import time  # Import the time module to pause execution inside the scheduler loop.
import requests  # Import the requests module to download HTML content from websites.
from bs4 import BeautifulSoup  # Import BeautifulSoup to parse and scrape HTML content.
import schedule  # Import the schedule module to run the script at specific times.
import gspread  # Import the gspread module to read and write data to Google Sheets.
from googleapiclient.discovery import build  # Import the build function to connect to the YouTube API.
#
def load_config():  # Define a function to load user configuration settings.
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")  # Find config.json path in the same directory.
    if not os.path.exists(config_path):  # Check if the config.json file is missing.
        print("Error: config.json file not found in the script directory.")  # Print a descriptive error message if missing.
        sys.exit(1)  # Terminate the script with a failure exit code of 1.
    with open(config_path, "r") as config_file:  # Open the config.json file in read-only mode.
        return json.load(config_file)  # Parse the JSON content and return it as a Python dictionary.
#
def fetch_summary(url, headers):  # Define a helper function to fetch a 1-sentence summary for a given article URL.
    try:  # Start a try block to handle request timeouts or parsing failures.
        response = requests.get(url, headers=headers, timeout=5)  # Fetch the article page HTML with a short 5-second timeout.
        if response.status_code == 200:  # If the article page loaded successfully.
            soup = BeautifulSoup(response.content, 'html.parser')  # Parse the article HTML content.
            meta_desc = soup.find('meta', attrs={'name': 'description'})  # Look for standard description meta tag.
            og_desc = soup.find('meta', attrs={'property': 'og:description'})  # Look for OpenGraph description meta tag.
            if meta_desc and meta_desc.get('content'):  # If the standard description tag has text content.
                return meta_desc['content'].strip()  # Return the stripped standard description text.
            elif og_desc and og_desc.get('content'):  # Else if OpenGraph description tag has text content.
                return og_desc['content'].strip()  # Return the stripped OpenGraph description text.
    except Exception:  # Ignore errors and fail silently.
        pass  # Do nothing and continue.
    return "No summary available."  # Return fallback string if no summary could be fetched.
#
def get_next_issue_number():  # Define a function to determine the next sequential issue number from the newsletter index.
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get script directory path.
    index_path = os.path.join(script_dir, "newsletters", "index.json")  # Path to the edition index file.
    if not os.path.exists(index_path):  # If index file does not exist yet.
        return 1  # Start at issue #1.
    try:  # Attempt to read the existing index.
        with open(index_path, "r", encoding="utf-8") as f:  # Open the index file.
            index = json.load(f)  # Parse JSON list of past editions.
        today_str = datetime.date.today().strftime("%Y-%m-%d")  # Get today's date string.
        if index and index[0].get("date") == today_str:  # If today's edition already exists (re-run).
            return index[0].get("issue_number", len(index))  # Return existing issue number for today.
        return len(index) + 1  # New issue = total past editions + 1.
    except Exception:  # If any error occurs while reading.
        return 1  # Default to issue 1 on failure.
#
def generate_newsletter_with_llm(config, raw_text):  # Define function to call Gemini API to generate the newsletter.
    api_key = os.environ.get("GEMINI_API_KEY")  # Check if GEMINI_API_KEY is set in environment variables.
    if not api_key:  # If it is not found in the environment variables.
        api_key = config.get("gemini_api_key", "")  # Get Gemini API key from config.
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":  # Check if key is not configured.
        print("Warning: Gemini API Key not configured. Using fallback text newsletter formatting.")  # Log warning.
        return None  # Return None to signal fallback.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"  # Set API endpoint.
    issue_number = get_next_issue_number()  # Compute the correct sequential issue number.
    prompt = f"""You are an expert newsletter editor specializing in AI and emerging technology communications. Your task is to transform raw source text into a polished, professional newsletter edition focused on AI updates.

IMPORTANT: Use exactly "Issue #{issue_number:03d}" in the header — do not invent or change this number.

ROLE & GOAL
Convert any provided text — notes, articles, bullet points, or drafts — into a structured, engaging AI update newsletter suitable for a professional audience including executives, developers, researchers, and business leaders.

NEWSLETTER STRUCTURE (follow exactly — modern, scannable editorial format)
1. HEADER (3 lines, exactly)
   • Line 1: the edition title as an H1 (# Title) — an evocative 2–5 word theme for today, not the newsletter name
   • Line 2: **Issue #{issue_number:03d} · today's date in Month Day, Year format** in bold
   • Line 3: a one-line italic tagline capturing the edition's theme

2. ## TL;DR
   • Exactly 3 bullet points — the day's signal in 3 fast reads
   • Each bullet ≤ 20 words, leads with the single most important fact
   • This is the most important section: a busy reader should get the gist from these 3 lines alone

3. ## THE BIG STORY
   • Pick the single most impactful update from the source text
   • 2–3 tight paragraphs: What happened → Why it matters → Who's affected
   • Lead with the consequence, not the background

4. ## MORE SIGNALS
   • 2–3 other notable items, each as a ### short headline followed by 2–3 sentences
   • Keep each item tight and self-contained; cut anything not essential

5. ## QUICK HITS
   • 3–5 single-line bullets for smaller items worth knowing
   • Format: **Company/Topic** — what happened, in one clause

6. ## WHAT TO WATCH
   • 2–3 sentences on upcoming trends, releases, or events on the horizon

7. ## THE SIGNAL
   • One-sentence closing thought that ties the edition together
   • One clear call-to-action (e.g., "Reply with your take")
   • Then on its own final line: Subject: [recommended email subject line]

TONE & STYLE RULES
• Tone: Authoritative yet accessible — like a trusted industry expert, not a press release
• Voice: Active voice, present tense where possible
• Clarity: Explain technical terms briefly on first use; assume smart but not deeply technical readers
• Length: 550–800 words total — sleek and scannable, not padded
• No filler phrases: avoid "In conclusion", "It is worth noting", "As we know"
• No hype language: avoid "revolutionary", "game-changing", "groundbreaking" unless quoting
• Attribute all claims: use "According to [source]" or "[Company] announced" phrasing
• Highlight numbers and stats using bold formatting
• Use em dashes (—) for asides, not parentheses

FORMATTING OUTPUT (render-critical — the website styles these exactly)
• Use markdown-compatible formatting
• Title line: a single H1 with "# " — used once, only for the edition title at the very top
• Section headings: H2 with "## " — keep them SHORT and punchy (these render as small uppercase labels): TL;DR, THE BIG STORY, MORE SIGNALS, QUICK HITS, WHAT TO WATCH, THE SIGNAL
• Item headlines inside MORE SIGNALS: H3 with "### "
• **Bold** for key terms, stats, and product names on first mention
• Use "- " for every bullet point; no nested bullets
• One blank line between paragraphs and sections
• End with the email subject line on its own final line: Subject: [your suggestion]

QUALITY CHECKLIST (review before finalizing)
✓ Every claim maps to content in the source text — do not invent facts
✓ The header uses exactly "Issue #{issue_number:03d}" and today's date
✓ The TL;DR has exactly 3 bullets and stands alone as a summary
✓ Section labels are short and match the required names exactly
✓ Technical details are accurate and contextualized for a business audience
✓ Quick Hits and Signals are tight — no filler, no repetition
✓ Total length is within 550–800 words
✓ Tone is consistent throughout"""  # Set the structured system prompt; issue number injected via f-string.
    today_str = datetime.date.today().strftime("%B %d, %Y")  # Format current date.
    full_prompt = f"{prompt}\n\nUse today's date: {today_str}.\n\nSource Text to summarize:\n{raw_text}"  # Combine system prompt with instructions.
    headers = {"Content-Type": "application/json"}  # Set content header.
    data = {  # Set request payload structure.
        "contents": [{  # Set contents element.
            "parts": [{  # Set parts element.
                "text": full_prompt  # Set prompt text.
            }]  # End parts list.
        }]  # End contents list.
    }  # End payload dictionary.
    for attempt in range(1, 4):  # Retry up to 3 times to handle temporary 503/429 errors.
        try:  # Start a try block for HTTP request.
            response = requests.post(url, headers=headers, json=data, timeout=60)  # Send content request to Gemini API.
            if response.status_code == 200:  # If response is successful.
                result = response.json()  # Parse response as JSON.
                candidates = result.get('candidates', [])  # Retrieve candidate generations.
                if candidates:  # If candidates exist.
                    return candidates[0]['content']['parts'][0]['text']  # Extract and return generated text output.
            elif response.status_code in (429, 503):  # If rate-limited or service unavailable.
                print(f"Gemini API attempt {attempt} returned {response.status_code}. Retrying in {attempt * 10}s...")  # Log retry.
                time.sleep(attempt * 10)  # Wait before retrying (10s, 20s, 30s).
            else:  # If API request fails with other error.
                print(f"Gemini API returned status code {response.status_code}: {response.text}")  # Log error response.
                break  # Do not retry on non-retriable errors.
        except Exception as e:  # Catch network errors.
            print(f"Error calling Gemini API (attempt {attempt}): {e}")  # Log error message.
            time.sleep(attempt * 10)  # Wait before retrying.
    return None  # Return None after all retries exhausted.
#
def scrape_techcrunch(headers):  # Define a function to scrape AI news articles from TechCrunch.
    url = "https://techcrunch.com/category/artificial-intelligence/"  # Set the target TechCrunch AI category URL.
    articles = []  # Initialize an empty list to store the scraped TechCrunch articles.
    try:  # Start a try block to handle any connection or parsing errors.
        response = requests.get(url, headers=headers, timeout=10)  # Fetch the webpage HTML content with a 10-second timeout.
        if response.status_code == 200:  # Check if the webpage request was successful.
            soup = BeautifulSoup(response.content, 'html.parser')  # Parse the HTML content using BeautifulSoup.
            for link in soup.find_all('a', href=True):  # Loop through all anchor elements with a link destination.
                href = link['href']  # Extract the destination URL of the current link.
                parent_h2 = link.find_parent('h2')  # Check if this link is nested inside an h2 heading.
                parent_h3 = link.find_parent('h3')  # Check if this link is nested inside an h3 heading.
                title = link.get_text(strip=True)  # Retrieve the visible link text and remove extra whitespace.
                if (parent_h2 or parent_h3 or 'post-title' in str(link.get('class', []))) and title and len(title) > 10:  # Filter for article titles.
                    if href.startswith('http') and 'category' not in href and 'tag' not in href:  # Ensure it is a valid article URL.
                        articles.append({"title": title, "link": href, "source": "TechCrunch", "author": "TechCrunch Staff"})  # Add details to list.
        else:  # If the status code is not 200.
            print(f"TechCrunch responded with status code: {response.status_code}")  # Print the error code.
    except Exception as e:  # Catch any exception that occurs during fetching or parsing.
        print(f"Error scraping TechCrunch: {e}")  # Print the detailed exception message.
    return articles[:10]  # Return the top 10 articles found.
#
def scrape_openai(headers):  # Define a function to scrape recent news releases from OpenAI.
    url = "https://openai.com/news/"  # Set the target OpenAI news section URL.
    articles = []  # Initialize an empty list to store the scraped OpenAI articles.
    try:  # Start a try block to handle potential scraping errors.
        response = requests.get(url, headers=headers, timeout=10)  # Send a GET request to the OpenAI news page.
        if response.status_code == 200:  # Verify that the web page loaded successfully.
            soup = BeautifulSoup(response.content, 'html.parser')  # Parse the HTML markup code.
            for link in soup.find_all('a', href=True):  # Loop through all hyperlinks present on the webpage.
                href = link['href']  # Extract the hyperlink destination string.
                if href.startswith('/index/'):  # Check if the hyperlink points to a news article path starting with /index/.
                    outer_div = link.find('div')  # Look for a wrapper div element nested inside the link.
                    if outer_div:  # If a wrapper div element is present.
                        inner_div = outer_div.find('div')  # Search for an inner div element containing the title.
                        if inner_div:  # If the inner div is successfully found.
                            title = inner_div.get_text(strip=True)  # Extract the clean title text from the inner div.
                            full_url = f"https://openai.com{href}"  # Construct the absolute URL by prefixing the host.
                            articles.append({"title": title, "link": full_url, "source": "OpenAI", "author": "OpenAI"})  # Save details to list.
        else:  # If the server returned an error status code.
            print(f"OpenAI news responded with status code: {response.status_code}")  # Print the error status code.
    except Exception as e:  # Handle connection dropouts or selector failures.
        print(f"Error scraping OpenAI: {e}")  # Print the error message to console.
    return articles[:10]  # Return the top 10 unique articles.
#
def scrape_google_blog(headers):  # Define a function to scrape AI posts from Google Blog.
    url = "https://blog.google/technology/ai/"  # Set the target Google AI blog URL.
    articles = []  # Initialize a list to hold the scraped Google Blog articles.
    try:  # Start a try block for error handling.
        response = requests.get(url, headers=headers, timeout=10)  # Make a HTTP request to fetch Google's blog.
        if response.status_code == 200:  # Check if the page fetched successfully.
            soup = BeautifulSoup(response.content, 'html.parser')  # Parse the page content.
            for link in soup.find_all('a', href=True):  # Loop through all links in the document.
                href = link['href']  # Extract the link location URL.
                header = link.find(['h2', 'h3'])  # Find any embedded h2 or h3 header inside the link.
                if header:  # If a header is found inside the anchor tag.
                    title = header.get_text(strip=True)  # Extract the text of the header.
                    if title and len(title) > 10 and not title.lower().startswith(('view more', 'see all')):  # Filter out utility links.
                        full_url = href if href.startswith('http') else f"https://blog.google{href}"  # Build absolute URL.
                        articles.append({"title": title, "link": full_url, "source": "Google Blog", "author": "Google"})  # Save details.
        else:  # If Google Blog responded with an error.
            print(f"Google Blog responded with status code: {response.status_code}")  # Print the error code.
    except Exception as e:  # Catch any exception.
        print(f"Error scraping Google Blog: {e}")  # Print the error description.
    return articles[:10]  # Return the top 10 Google Blog articles.
#
def scrape_hacker_news(headers):  # Define a function to scrape AI-related stories from Hacker News.
    url = "https://news.ycombinator.com/"  # Set the target Hacker News home URL.
    ai_keywords = [  # Keywords used to filter for AI-relevant stories.
        "ai", "artificial intelligence", "machine learning", "deep learning", "neural",
        "llm", "gpt", "claude", "gemini", "openai", "anthropic", "deepmind", "mistral",
        "chatgpt", "chatbot", "transformer", "generative", "diffusion", "nlp",
        "language model", "reinforcement learning", "computer vision", "ml "
    ]  # End of keyword list.
    articles = []  # Initialize an empty list to store matching articles.
    try:  # Start a try block to handle network and scraping errors.
        response = requests.get(url, headers=headers, timeout=10)  # Fetch Hacker News HTML content.
        if response.status_code == 200:  # Check if the webpage request succeeded.
            soup = BeautifulSoup(response.content, 'html.parser')  # Parse the HTML code.
            for span in soup.find_all('span', class_='titleline'):  # Loop through all story titles on the page.
                link = span.find('a')  # Find the primary link tag inside the span.
                if link:  # If a link tag is found.
                    title = link.get_text(strip=True)  # Retrieve the article title text.
                    href = link['href']  # Extract the destination URL.
                    title_lower = title.lower()  # Lowercase for case-insensitive keyword matching.
                    if not any(kw in title_lower for kw in ai_keywords):  # Skip stories not related to AI.
                        continue  # Move to the next story.
                    full_url = href if href.startswith('http') else f"https://news.ycombinator.com/{href}"  # Build absolute URL.
                    articles.append({"title": title, "link": full_url, "source": "Hacker News", "author": "Hacker News User"})  # Save details.
        else:  # If the server returned an error.
            print(f"Hacker News responded with status code: {response.status_code}")  # Log the status code.
    except Exception as e:  # Catch any exception.
        print(f"Error scraping Hacker News: {e}")  # Print the error details.
    print(f"Hacker News: found {len(articles[:10])} AI-related stories.")  # Log how many matched.
    return articles[:10]  # Return up to 10 AI-related stories.
#
def scrape_the_verge(headers):  # Define a function to fetch AI articles from The Verge via RSS.
    url = "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"  # Use The Verge AI RSS feed (avoids JS rendering issues).
    articles = []  # Initialize empty list.
    try:  # Start error handling block.
        response = requests.get(url, headers=headers, timeout=10)  # Fetch the RSS feed.
        if response.status_code == 200:  # If successful.
            soup = BeautifulSoup(response.content, 'xml')  # Parse as XML.
            for item in soup.find_all('item'):  # Loop through each RSS item.
                title_tag = item.find('title')  # Find title tag.
                link_tag = item.find('link')  # Find link tag.
                if title_tag and link_tag:  # If both are present.
                    title = title_tag.get_text(strip=True)  # Extract title text.
                    link = link_tag.get_text(strip=True)  # Extract link URL.
                    if title and len(title) > 10 and link:  # Filter short/empty entries.
                        articles.append({"title": title, "link": link, "source": "The Verge", "author": "The Verge"})  # Save article.
        else:  # If request failed.
            print(f"The Verge RSS responded with status code: {response.status_code}")  # Log error.
    except Exception as e:  # Catch errors.
        print(f"Error fetching The Verge RSS: {e}")  # Log error message.
    print(f"The Verge: found {len(articles[:8])} articles.")  # Log count.
    return articles[:8]  # Return top 8 articles.
#
def scrape_mit_tech_review(headers):  # Define a function to fetch AI articles from MIT Technology Review via RSS.
    url = "https://www.technologyreview.com/feed/"  # Use MIT Tech Review RSS feed for reliable access.
    ai_keywords = ["ai", "artificial intelligence", "machine learning", "llm", "gpt", "neural", "model", "robot", "autonomous", "deep learning"]  # AI filter keywords.
    articles = []  # Initialize empty list.
    try:  # Start error handling block.
        response = requests.get(url, headers=headers, timeout=10)  # Fetch the RSS feed.
        if response.status_code == 200:  # If successful.
            soup = BeautifulSoup(response.content, 'xml')  # Parse as XML.
            for item in soup.find_all('item'):  # Loop through each RSS item.
                title_tag = item.find('title')  # Find title tag.
                link_tag = item.find('link')  # Find link tag.
                if title_tag and link_tag:  # If both are present.
                    title = title_tag.get_text(strip=True)  # Extract title text.
                    link = link_tag.get_text(strip=True)  # Extract link URL.
                    if title and len(title) > 10 and any(kw in title.lower() for kw in ai_keywords):  # Filter to AI articles only.
                        articles.append({"title": title, "link": link, "source": "MIT Tech Review", "author": "MIT Technology Review"})  # Save article.
        else:  # If request failed.
            print(f"MIT Tech Review RSS responded with status code: {response.status_code}")  # Log error.
    except Exception as e:  # Catch errors.
        print(f"Error fetching MIT Tech Review RSS: {e}")  # Log error message.
    print(f"MIT Tech Review: found {len(articles[:8])} articles.")  # Log count.
    return articles[:8]  # Return top 8 articles.
#
def scrape_venturebeat(headers):  # Define a function to fetch AI articles from VentureBeat via RSS.
    url = "https://venturebeat.com/category/ai/feed/"  # Use VentureBeat AI RSS feed (avoids 429 rate limiting on HTML pages).
    articles = []  # Initialize empty list.
    try:  # Start error handling block.
        response = requests.get(url, headers=headers, timeout=10)  # Fetch the RSS feed.
        if response.status_code == 200:  # If successful.
            soup = BeautifulSoup(response.content, 'xml')  # Parse as XML.
            for item in soup.find_all('item'):  # Loop through each RSS item.
                title_tag = item.find('title')  # Find title tag.
                link_tag = item.find('link')  # Find link tag.
                if title_tag and link_tag:  # If both are present.
                    title = title_tag.get_text(strip=True)  # Extract title text.
                    link = link_tag.get_text(strip=True)  # Extract link URL.
                    if title and len(title) > 10 and link:  # Filter short/empty entries.
                        articles.append({"title": title, "link": link, "source": "VentureBeat", "author": "VentureBeat"})  # Save article.
        else:  # If request failed.
            print(f"VentureBeat RSS responded with status code: {response.status_code}")  # Log error.
    except Exception as e:  # Catch errors.
        print(f"Error fetching VentureBeat RSS: {e}")  # Log error message.
    print(f"VentureBeat: found {len(articles[:8])} articles.")  # Log count.
    return articles[:8]  # Return top 8 articles.
#
def scrape_wired(headers):  # Define a function to scrape AI articles from Wired.
    url = "https://www.wired.com/tag/artificial-intelligence/"  # Set Wired AI tag page URL.
    articles = []  # Initialize empty list.
    try:  # Start error handling block.
        response = requests.get(url, headers=headers, timeout=10)  # Fetch the page.
        if response.status_code == 200:  # If successful.
            soup = BeautifulSoup(response.content, 'html.parser')  # Parse HTML.
            for link in soup.find_all('a', href=True):  # Loop through all links.
                href = link['href']  # Get link URL.
                header = link.find(['h2', 'h3'])  # Look for heading inside link.
                if header:  # If heading found.
                    title = header.get_text(strip=True)  # Extract title text.
                    if title and len(title) > 10:  # Filter short/empty titles.
                        full_url = href if href.startswith('http') else f"https://www.wired.com{href}"  # Build absolute URL.
                        if 'wired.com' in full_url and '/tag/' not in full_url:  # Skip tag index pages.
                            articles.append({"title": title, "link": full_url, "source": "Wired", "author": "Wired"})  # Save article.
        else:  # If request failed.
            print(f"Wired responded with status code: {response.status_code}")  # Log error.
    except Exception as e:  # Catch errors.
        print(f"Error scraping Wired: {e}")  # Log error message.
    print(f"Wired: found {len(articles[:8])} articles.")  # Log count.
    return articles[:8]  # Return top 8 articles.
#
def fetch_youtube_videos(api_key):  # Define a function to fetch videos using the YouTube Data API.
    videos = []  # Initialize an empty list to store video search results.
    env_key = os.environ.get("YOUTUBE_API_KEY")  # Check if YOUTUBE_API_KEY is set in environment variables.
    if env_key:  # If environment variable key is found.
        api_key = env_key  # Use the environment variable.
    if not api_key or api_key == "YOUR_YOUTUBE_API_KEY":  # Check if the user has not configured their API key yet.
        print("Warning: YouTube API Key is not configured. Skipping YouTube fetch.")  # Warn the user in the logs.
        return videos  # Return the empty list of videos.
    try:  # Start a try block to catch API request errors.
        youtube = build('youtube', 'v3', developerKey=api_key)  # Construct the YouTube service object using developer key.
        request = youtube.search().list(  # Define the search query request.
            q="AI news today",  # Set the search query string.
            part="snippet",  # Request the snippet block containing title and channel name.
            maxResults=5,  # Fetch the top 5 video search results.
            type="video"  # Restrict the search results to videos only.
        )  # End of request definition.
        response = request.execute()  # Execute the API request synchronously.
        for item in response.get('items', []):  # Loop through each item in the API response.
            title = item['snippet']['title']  # Extract the title of the video.
            channel = item['snippet']['channelTitle']  # Extract the channel name.
            video_id = item['id']['videoId']  # Extract the video ID.
            link = f"https://www.youtube.com/watch?v={video_id}"  # Build the absolute URL to view the video.
            summary = item['snippet']['description']  # Extract the video description from the response.
            videos.append({"title": title, "link": link, "source": "YouTube", "author": channel, "summary": summary})  # Add video to results.
    except Exception as e:  # Catch any network or authentication errors.
        print(f"Error fetching YouTube videos: {e}")  # Print the error detail.
    return videos  # Return the list of fetched videos.
#
def save_to_google_sheets(config, all_data):  # Define a function to save the parsed items to Google Sheets.
    if not os.path.exists(config["google_credentials_file"]):  # Check if credentials JSON file is missing.
        print(f"Warning: Google credentials file '{config['google_credentials_file']}' not found. Skipping Google Sheets update.")  # Log warning.
        return  # Exit function early.
    try:  # Start a try block for Google Sheets operations.
        gc = gspread.service_account(filename=config["google_credentials_file"])  # Authenticate with Google using service account JSON.
        sh = gc.open(config["google_sheet_name"])  # Open the spreadsheet by its name.
        worksheet = sh.get_worksheet(0)  # Access the first worksheet in the workbook.
        existing_headers = worksheet.row_values(1)  # Read the values of the first row to check for headers.
        if not existing_headers:  # If the first row is completely empty.
            worksheet.append_row(["Date", "Source", "Type", "Title", "Author/Channel", "Summary", "Link"])  # Append column headers.
        rows_to_append = []  # Initialize an empty list to accumulate rows.
        today_str = datetime.date.today().strftime("%Y-%m-%d")  # Get today's date formatted as YYYY-MM-DD.
        for item in all_data:  # Loop through each article or video collected.
            item_type = "Video" if item["source"] == "YouTube" else "Article"  # Identify if item is a video or article.
            rows_to_append.append([  # Add a list containing cell values for this row.
                today_str,  # Set Date column.
                item["source"],  # Set Source column.
                item_type,  # Set Type column.
                item["title"],  # Set Title column.
                item["author"],  # Set Author/Channel column.
                item.get("summary", "No summary available."),  # Set Summary column.
                item["link"]  # Set Link column.
            ])  # End of row data structure.
        if rows_to_append:  # If we have rows to add.
            worksheet.append_rows(rows_to_append)  # Append all accumulated rows to the worksheet in a single API call.
            print(f"Successfully saved {len(rows_to_append)} items to Google Sheet '{config['google_sheet_name']}'.")  # Print success logs.
    except Exception as e:  # Catch authentication, permissions, or quota errors.
        print(f"Error writing to Google Sheets: {e}")  # Print the detailed error message.
#
def update_telegram_subscribers(config):  # Discover Telegram subscribers via getUpdates and persist them to a repo file.
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("telegram_bot_token", "")  # Get the bot token.
    sub_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers")  # Path to the subscribers folder.
    os.makedirs(sub_dir, exist_ok=True)  # Create the folder if it does not exist.
    path = os.path.join(sub_dir, "telegram.json")  # Path to the persisted Telegram subscriber file.
    existing = {}  # Dictionary of chat_id -> subscriber record.
    if os.path.exists(path):  # If we already have a saved list.
        try:  # Attempt to load it.
            with open(path, encoding="utf-8") as f:  # Open the file.
                for record in json.load(f):  # Loop through saved records.
                    if record.get("chat_id"):  # If the record has a chat id.
                        existing[str(record["chat_id"])] = record  # Index it by chat id.
        except Exception:  # If the file is unreadable.
            existing = {}  # Reset to empty.
    default_chat = os.environ.get("TELEGRAM_CHAT_ID") or config.get("telegram_chat_id", "")  # The owner's own chat id.
    if default_chat and default_chat not in ("", "YOUR_TELEGRAM_CHAT_ID") and str(default_chat) not in existing:  # If owner not yet listed.
        existing[str(default_chat)] = {"chat_id": str(default_chat), "name": "Owner", "joined": datetime.date.today().strftime("%Y-%m-%d")}  # Add the owner.
    if bot_token and bot_token not in ("", "YOUR_TELEGRAM_BOT_TOKEN"):  # If a real bot token is configured.
        try:  # Attempt to fetch recent bot updates.
            resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", timeout=15)  # Call getUpdates.
            if resp.status_code == 200:  # If successful.
                for upd in resp.json().get("result", []):  # Loop through each update.
                    message = upd.get("message") or upd.get("edited_message") or {}  # Get the message object.
                    chat = message.get("chat", {})  # Get the chat object.
                    cid = chat.get("id")  # Read the chat id.
                    if cid is None:  # Skip updates without a chat id.
                        continue  # Next update.
                    cid = str(cid)  # Normalize to string.
                    if cid not in existing:  # If this is a brand-new subscriber.
                        name = chat.get("first_name") or chat.get("title") or chat.get("username") or "Subscriber"  # Best-effort display name.
                        existing[cid] = {"chat_id": cid, "name": name, "joined": datetime.date.today().strftime("%Y-%m-%d")}  # Record them.
                        print(f"New Telegram subscriber: {name} ({cid})")  # Log the new sign-up.
            else:  # If getUpdates failed.
                print(f"Telegram getUpdates returned status {resp.status_code}.")  # Log the status.
        except Exception as e:  # Catch network errors.
            print(f"Error fetching Telegram updates: {e}")  # Log the error.
    subscribers = list(existing.values())  # Collapse the dictionary back into a list.
    try:  # Attempt to persist the updated list.
        with open(path, "w", encoding="utf-8") as f:  # Open the file for writing.
            json.dump(subscribers, f, indent=2, ensure_ascii=False)  # Save as formatted JSON.
    except Exception as e:  # Catch write errors.
        print(f"Error saving Telegram subscribers: {e}")  # Log the error.
    ids = [s["chat_id"] for s in subscribers]  # Extract just the chat ids.
    print(f"Telegram subscriber list: {len(ids)} total.")  # Log the total count.
    return ids  # Return the list of chat ids.
#
def save_backup(config, articles, videos, llm_newsletter=None):  # Define a function to save a backup summary to Desktop.
    backup_dir = config.get("desktop_backup_dir", "")  # Get the desktop backup directory path from config.
    if not backup_dir or not os.path.exists(backup_dir):  # If path is not set or does not exist on disk.
        backup_dir = os.path.expanduser("~/Desktop")  # Fallback to default user Desktop location path.
        if not os.path.exists(backup_dir):  # Check if fallback directory also does not exist.
            backup_dir = os.path.dirname(os.path.abspath(__file__))  # Fallback to local script folder directory.
    today_str = datetime.date.today().strftime("%Y-%m-%d")  # Get current date formatted.
    filename = f"AI_Updates_{today_str}.txt"  # Build the filename using the current date string.
    filepath = os.path.join(backup_dir, filename)  # Construct the absolute path.
    try:  # Start a try block to handle write operations.
        with open(filepath, "w", encoding="utf-8") as f:  # Open the backup file in write mode with UTF-8 encoding.
            if llm_newsletter:  # If the LLM generated newsletter is available.
                f.write(llm_newsletter)  # Write the generated newsletter content directly.
            else:  # Else fallback to default text newsletter format.
                f.write("┌" + "─" * 56 + "┐\n")  # Write top box border.
                f.write(f"│{'DAILY AI NEWS BRIEFING':^56}│\n")  # Write centered title inside box.
                f.write(f"│{today_str:^56}│\n")  # Write centered date inside box.
                f.write("└" + "─" * 56 + "┘\n\n")  # Write bottom box border.
                f.write("Dear Reader,\n\n")  # Write professional greeting.
                f.write("Here is your automated daily digest of the latest developments in\n")  # Write introductory line.
                f.write("Artificial Intelligence, gathered from across the tech landscape.\n\n")  # Write second intro line.
                f.write("═" * 58 + "\n")  # Write double-line section divider.
                f.write("📰 WEBSITE ARTICLES & EDITORIALS\n")  # Write section header.
                f.write("═" * 58 + "\n\n")  # Write double-line section end.
                current_source = ""  # Keep track of the current article source.
                for art in articles:  # Loop through all scraped articles.
                    if art["source"] != current_source:  # Check if the source has changed.
                        current_source = art["source"]  # Update current source variable.
                        f.write(f"[{current_source}]\n")  # Write source label like [TechCrunch].
                    f.write(f"  • {art['title']}\n")  # Write bullet point and article title.
                    f.write(f"    Url: {art['link']}\n")  # Write indented link destination.
                    f.write(f"    Summary: {art.get('summary', 'No summary available.')}\n\n")  # Write indented summary.
                f.write("═" * 58 + "\n")  # Write double-line section divider.
                f.write("🎥 TRENDING YOUTUBE VIDEOS\n")  # Write section header.
                f.write("═" * 58 + "\n\n")  # Write double-line section end.
                if not videos:  # Check if no videos were fetched.
                    f.write("  No videos collected today. Check your API settings.\n\n")  # Write warning note.
                for vid in videos:  # Loop through all fetched YouTube videos.
                    f.write(f"  • {vid['title']}\n")  # Write bullet point and video title.
                    f.write(f"    Channel: {vid['author']} | Url: {vid['link']}\n")  # Write channel and URL link.
                    f.write(f"    Summary: {vid.get('summary', 'No summary available.')}\n\n")  # Write video summary.
                f.write("─" * 58 + "\n")  # Write simple divider.
                f.write("Generated automatically by the Daily AI News Scheduler.\n")  # Write footer text.
        print(f"Backup file successfully saved to: {filepath}")  # Print location path.
    except Exception as e:  # Catch write permission or file access errors.
        print(f"Error saving backup file: {e}")  # Print the error details.
#
def send_telegram(config, llm_newsletter, chat_ids=None):  # Send the newsletter to one or many Telegram subscribers.
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("telegram_bot_token", "")  # Get bot token from env var or config fallback.
    if not bot_token or bot_token in ("", "YOUR_TELEGRAM_BOT_TOKEN"):  # Check if token is missing.
        print("Warning: Telegram bot token not configured. Skipping Telegram delivery.")  # Log warning.
        return  # Exit early.
    recipients = list(chat_ids) if chat_ids else []  # Start from the provided subscriber chat ids.
    if not recipients:  # If no subscriber list was passed, fall back to the single configured chat id.
        single = os.environ.get("TELEGRAM_CHAT_ID") or config.get("telegram_chat_id", "")  # Get the owner's chat id.
        if single and single not in ("", "YOUR_TELEGRAM_CHAT_ID"):  # If it is valid.
            recipients = [str(single)]  # Use it as the only recipient.
    recipients = [str(c) for c in dict.fromkeys(recipients) if c]  # De-duplicate while preserving order.
    if not recipients:  # If we still have nobody to send to.
        print("Warning: No Telegram subscribers configured. Skipping Telegram delivery.")  # Log warning.
        return  # Exit early.
    today_display = datetime.date.today().strftime("%B %d, %Y")  # Format today's date.
    website_url = "https://sivag2000.github.io/ai-daily-signal-newsletter/"  # Newsletter website URL.
    def md_to_telegram_html(text):  # Inner helper to convert markdown to Telegram HTML.
        import re  # Import regex for pattern matching.
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)  # Convert **bold** to <b>.
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)  # Convert *italic* to <i>.
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)  # Convert [text](url) to <a>.
        text = re.sub(r'^#{1,3} (.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)  # Convert headings to bold.
        text = re.sub(r'^---+$', '─────────────', text, flags=re.MULTILINE)  # Replace hr with line.
        return text  # Return converted text.
    if llm_newsletter:  # If LLM newsletter content is available.
        converted = md_to_telegram_html(llm_newsletter)  # Convert markdown to Telegram HTML.
        lines = converted.split('\n')  # Split into lines.
        chunks = []  # Store message chunks.
        current = f"🤖 <b>AI Daily Signal — {today_display}</b>\n\n"  # Start first chunk with header.
        for line in lines:  # Loop through each line.
            if len(current) + len(line) + 1 > 3800:  # If adding this line exceeds Telegram's limit.
                chunks.append(current)  # Save current chunk.
                current = line + '\n'  # Start new chunk.
            else:  # Otherwise.
                current += line + '\n'  # Append line to current chunk.
        if current.strip():  # If remaining content exists.
            chunks.append(current)  # Save last chunk.
        chunks[-1] += f'\n\n📖 <a href="{website_url}">Read full edition on the website →</a>'  # Append website link to last chunk.
    else:  # If no LLM content.
        chunks = [f"🤖 <b>AI Daily Signal — {today_display}</b>\n\nNewsletter not available today.\n\n📖 <a href=\"{website_url}\">Visit the website →</a>"]  # Fallback message.
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"  # Set Telegram Bot API endpoint.
    sent_count = 0  # Track how many subscribers were delivered to successfully.
    for chat_id in recipients:  # Loop through every subscriber chat id.
        ok = True  # Track delivery success for this subscriber.
        for i, chunk in enumerate(chunks):  # Loop through each message chunk.
            try:  # Start error handling.
                resp = requests.post(api_url, json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": i < len(chunks) - 1}, timeout=15)  # Send message.
                if resp.status_code != 200:  # If this chunk failed.
                    ok = False  # Mark this subscriber as failed.
                    print(f"Telegram error for {chat_id} chunk {i+1}: {resp.status_code} — {resp.json().get('description', resp.text)}")  # Log error.
            except Exception as e:  # Catch network errors.
                ok = False  # Mark failed.
                print(f"Error sending Telegram message to {chat_id}: {e}")  # Log error.
        if ok:  # If all chunks delivered.
            sent_count += 1  # Count this subscriber as delivered.
    print(f"Telegram newsletter delivered to {sent_count}/{len(recipients)} subscriber(s).")  # Log the broadcast result.
#
def save_newsletter_to_repo(llm_newsletter, hn_articles=None):  # Save newsletter to newsletters/ dir and update index.json for the website.
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory containing the script.
    newsletters_dir = os.path.join(script_dir, "newsletters")  # Build path to newsletters folder.
    os.makedirs(newsletters_dir, exist_ok=True)  # Create the directory if it does not yet exist.
    today = datetime.date.today()  # Get today's date object.
    today_str = today.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD for filenames and JSON keys.
    today_display = today.strftime("%B %d, %Y")  # Format as human-readable string for titles.
    content = llm_newsletter if llm_newsletter else f"# AI Daily Signal — {today_display}\n\nNo newsletter generated today."  # Use LLM output or fallback.
    if hn_articles:  # If Hacker News articles were scraped, append a dedicated section.
        hn_section = "\n\n---\n\n## 🔥 Trending on Hacker News\n\n"  # Section header.
        for art in hn_articles:  # Loop through each HN article.
            hn_section += f"- [{art['title']}]({art['link']})\n"  # Append as a markdown link bullet.
        content += hn_section  # Append the HN section to the newsletter content.
    dated_path = os.path.join(newsletters_dir, f"{today_str}.md")  # Path for the dated newsletter file.
    latest_path = os.path.join(newsletters_dir, "latest.md")  # Path for the always-current latest file.
    with open(dated_path, "w", encoding="utf-8") as f:  # Write the dated newsletter file.
        f.write(content)  # Save full content.
    with open(latest_path, "w", encoding="utf-8") as f:  # Overwrite latest.md with today's content.
        f.write(content)  # Save full content.
    index_path = os.path.join(newsletters_dir, "index.json")  # Path for the edition index file.
    index = []  # Start with an empty list.
    if os.path.exists(index_path):  # If an existing index file is found.
        try:  # Attempt to load it.
            with open(index_path, "r", encoding="utf-8") as f:  # Open for reading.
                index = json.load(f)  # Parse JSON into a list.
        except Exception:  # If parsing fails for any reason.
            index = []  # Reset to empty list.
    existing_today = next((e for e in index if e.get("date") == today_str), None)  # Check if today already has an entry.
    issue_number = existing_today.get("issue_number") if existing_today else len(index) + 1  # Preserve existing number or assign next sequential one.
    index = [e for e in index if e.get("date") != today_str]  # Remove any existing entry for today to avoid duplicates.
    index.insert(0, {  # Prepend today's entry at the top of the index.
        "date": today_str,  # Store the date key.
        "issue_number": issue_number,  # Store the real sequential issue number.
        "title": f"AI Daily Signal — Issue #{issue_number:03d} — {today_display}",  # Full display title with issue number.
        "file": f"newsletters/{today_str}.md"  # Relative path to the newsletter file.
    })  # End entry dictionary.
    with open(index_path, "w", encoding="utf-8") as f:  # Write updated index file.
        json.dump(index, f, indent=2)  # Save as formatted JSON.
    print(f"Newsletter saved to repo: newsletters/{today_str}.md (Issue #{issue_number:03d})")  # Log success with issue number.
#
def job():  # Define the main job wrapper that combines all tasks.
    print(f"\n--- Starting AI News Collection Job at {datetime.datetime.now()} ---")  # Log startup timestamp.
    config = load_config()  # Load configuration values.
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}  # Set browser headers to prevent scraping blocks.
    tc_articles = scrape_techcrunch(headers)  # Fetch recent articles from TechCrunch.
    oa_articles = scrape_openai(headers)  # Fetch recent news items from OpenAI.
    gb_articles = scrape_google_blog(headers)  # Fetch recent posts from Google Blog.
    hn_articles = scrape_hacker_news(headers)  # Fetch recent AI stories from Hacker News.
    vg_articles = scrape_the_verge(headers)  # Fetch recent AI articles from The Verge.
    mt_articles = scrape_mit_tech_review(headers)  # Fetch recent AI articles from MIT Tech Review.
    vb_articles = scrape_venturebeat(headers)  # Fetch recent AI articles from VentureBeat.
    wd_articles = scrape_wired(headers)  # Fetch recent AI articles from Wired.
    all_articles = tc_articles + oa_articles + gb_articles + hn_articles + vg_articles + mt_articles + vb_articles + wd_articles  # Combine all articles.
    print("Fetching article summaries...")  # Log summary fetch start.
    for art in all_articles:  # Loop through all articles.
        art["summary"] = fetch_summary(art["link"], headers)  # Fetch and save the summary.
    youtube_videos = fetch_youtube_videos(config["youtube_api_key"])  # Fetch search results from YouTube.
    all_data = all_articles + youtube_videos  # Combine all collected items.
    raw_source_text = "WEBSITE ARTICLES:\n"  # Initialize raw text variable.
    for art in all_articles:  # Loop through articles.
        raw_source_text += f"- Title: {art['title']}\n  Source: {art['source']}\n  Url: {art['link']}\n  Summary: {art['summary']}\n\n"  # Add article details.
    if youtube_videos:  # If videos exist.
        raw_source_text += "YOUTUBE VIDEOS:\n"  # Add header.
        for vid in youtube_videos:  # Loop through videos.
            raw_source_text += f"- Title: {vid['title']}\n  Channel: {vid['author']}\n  Url: {vid['link']}\n  Description: {vid['summary']}\n\n"  # Add video details.
    print("Generating professional newsletter via Gemini API...")  # Log message.
    llm_newsletter = generate_newsletter_with_llm(config, raw_source_text)  # Call Gemini API.
    save_to_google_sheets(config, all_data)  # Append data to the Google sheet.
    save_backup(config, all_articles, youtube_videos, llm_newsletter)  # Write updates backup file.
    save_newsletter_to_repo(llm_newsletter, hn_articles)  # Save newsletter to newsletters/ directory for the website.
    telegram_subscribers = update_telegram_subscribers(config)  # Discover and persist Telegram subscribers (from /start messages).
    send_telegram(config, llm_newsletter, telegram_subscribers)  # Broadcast the newsletter to all Telegram subscribers.
    print(f"--- Job Completed at {datetime.datetime.now()} ---\n")  # Log successful finish timestamp.
#
if __name__ == "__main__":  # Executed if the file is run directly.
    if "--now" in sys.argv:  # Check if user passed the --now command argument.
        job()  # Run the news collection process immediately.
    else:  # If no argument is passed, start scheduling mode.
        print("Starting Scheduler in daily background mode. Press Ctrl+C to exit.")  # Print startup instruction logs.
        print("Script will run daily at 6:00 PM (18:00). Keep this window open.")  # Clarify time rules.
        schedule.every().day.at("18:00").do(job)  # Configure the scheduler to fire at 6:00 PM.
        while True:  # Enter loop.
            schedule.run_pending()  # Execute any scheduled jobs.
            time.sleep(10)  # Pause execution for 10 seconds.
