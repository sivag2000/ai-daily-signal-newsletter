import os  # Import the os module to handle file paths and directory operations.
import sys  # Import the sys module to read command line flags like --now.
import json  # Import the json module to read configuration parameters from config.json.
import datetime  # Import the datetime module to fetch and format the current date.
import time  # Import the time module to pause execution inside the scheduler loop.
import smtplib  # Import the smtplib module to connect to Gmail's mail server.
from email.mime.text import MIMEText  # Import MIMEText to construct the text/HTML email.
from email.mime.multipart import MIMEMultipart  # Import MIMEMultipart to support HTML email formatting.
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
def generate_newsletter_with_llm(config, raw_text):  # Define function to call Gemini API to generate the newsletter.
    api_key = os.environ.get("GEMINI_API_KEY")  # Check if GEMINI_API_KEY is set in environment variables.
    if not api_key:  # If it is not found in the environment variables.
        api_key = config.get("gemini_api_key", "")  # Get Gemini API key from config.
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":  # Check if key is not configured.
        print("Warning: Gemini API Key not configured. Using fallback text newsletter formatting.")  # Log warning.
        return None  # Return None to signal fallback.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"  # Set API endpoint.
    prompt = """You are an expert newsletter editor specializing in AI and emerging technology communications. Your task is to transform raw source text into a polished, professional newsletter edition focused on AI updates.

ROLE & GOAL
Convert any provided text — notes, articles, bullet points, or drafts — into a structured, engaging AI update newsletter suitable for a professional audience including executives, developers, researchers, and business leaders.

NEWSLETTER STRUCTURE (follow exactly)
1. HEADER
   • Newsletter name (create if not provided)
   • Issue number and publication date
   • One-line tagline that captures the edition's theme

2. OPENING HOOK (2–3 sentences)
   • Start with a compelling insight or trend observation
   • Frame why this edition matters right now
   • Preview the main topics briefly

3. MAIN SECTIONS (2–4 sections based on content)
   • Use clear H2 headings for each topic area
   • Each section: 3–5 sentences max per paragraph
   • Lead with the most important point (inverted pyramid)
   • Include business/practical implications, not just technical facts
   • Use bullet points only for key specs, lists, or comparisons

4. SPOTLIGHT FEATURE
   • Pick the single most impactful update from the source text
   • Give it a dedicated section with deeper context
   • Include: What happened → Why it matters → Who is affected

5. KEY TAKEAWAYS (3–5 bullets)
   • Concise, actionable insights the reader should remember
   • Start each with a strong verb (Expect, Watch, Consider, Note)

6. WHAT'S NEXT
   • 2–3 sentences on upcoming trends, releases, or events to watch

7. FOOTER
   • Brief closing sign-off
   • One clear call-to-action (e.g., "Reply with your thoughts")
   • Issue subject line recommendation for email

TONE & STYLE RULES
• Tone: Authoritative yet accessible — like a trusted industry expert, not a press release
• Voice: Active voice, present tense where possible
• Clarity: Explain technical terms briefly on first use; assume smart but not deeply technical readers
• Length: 650–900 words total
• No filler phrases: avoid "In conclusion", "It is worth noting", "As we know"
• No hype language: avoid "revolutionary", "game-changing", "groundbreaking" unless quoting
• Attribute all claims: use "According to [source]" or "[Company] announced" phrasing
• Highlight numbers and stats using bold formatting
• Use em dashes (—) for asides, not parentheses

FORMATTING OUTPUT
• Use markdown-compatible formatting
• ## for section headings, ### for subsections
• **Bold** for key terms, stats, and product names on first mention
• Bullet points (–) for lists only; no nested bullets
• One blank line between paragraphs and sections
• End with a recommended email subject line on a new line: Subject: [your suggestion]

QUALITY CHECKLIST (review before finalizing)
✓ Every claim maps to content in the source text — do not invent facts
✓ Technical details are accurate and contextualized for a business audience
✓ The opening hook would make someone want to keep reading
✓ Takeaways are specific, not generic
✓ Total length is within 650–900 words
✓ Tone is consistent throughout"""  # Set the user's exact system prompt.
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
    try:  # Start a try block for HTTP request.
        response = requests.post(url, headers=headers, json=data, timeout=60)  # Send content request to Gemini API.
        if response.status_code == 200:  # If response is successful.
            result = response.json()  # Parse response as JSON.
            candidates = result.get('candidates', [])  # Retrieve candidate generations.
            if candidates:  # If candidates exist.
                return candidates[0]['content']['parts'][0]['text']  # Extract and return generated text output.
        else:  # If API request fails.
            print(f"Gemini API returned status code {response.status_code}: {response.text}")  # Log error response.
    except Exception as e:  # Catch network errors.
        print(f"Error calling Gemini API: {e}")  # Log error message.
    return None  # Return None on failure.
#
def convert_markdown_to_html(md_text):  # Define a helper function to convert basic markdown into clean HTML.
    lines = md_text.split("\n")  # Split input text into lines.
    html_lines = []  # Initialize an empty list for HTML markup lines.
    in_list = False  # Track if we are currently inside a list block.
    for line in lines:  # Loop through each line in the text.
        line = line.strip()  # Strip leading and trailing whitespace.
        if not line:  # Check if line is empty.
            if in_list:  # If we were building a list.
                html_lines.append("</ul>")  # Close the HTML list container.
                in_list = False  # Reset list tracking state.
            continue  # Proceed to the next line.
        if line.startswith("## "):  # Check for H2 heading pattern.
            if in_list:  # Close list if open.
                html_lines.append("</ul>")  # Close the list.
                in_list = False  # Reset state.
            title = line[3:].strip()  # Extract title text.
            html_lines.append(f"<h2 style='color:#1e3c72; border-bottom:2px solid #eef2f7; padding-bottom:8px; margin-top:30px;'>{title}</h2>")  # Append H2 markup.
        elif line.startswith("### "):  # Check for H3 heading pattern.
            if in_list:  # Close list if open.
                html_lines.append("</ul>")  # Close list.
                in_list = False  # Reset state.
            title = line[4:].strip()  # Extract title text.
            html_lines.append(f"<h3 style='color:#2a5298; margin-top:20px;'>{title}</h3>")  # Append H3 markup.
        elif line.startswith("- ") or line.startswith("– ") or line.startswith("• "):  # Check for bullet point patterns.
            if not in_list:  # If we are starting a list block.
                html_lines.append("<ul style='padding-left:20px; line-height:1.6;'>")  # Open the HTML list block.
                in_list = True  # Set list tracking state to True.
            content = line[2:].strip()  # Extract bullet text content.
            while "**" in content:  # Loop while bold markers exist.
                content = content.replace("**", "<strong>", 1).replace("**", "</strong>", 1)  # Replace pairs with tags.
            html_lines.append(f"<li style='margin-bottom:8px;'>{content}</li>")  # Append list item markup.
        else:  # Handle normal paragraph lines.
            if in_list:  # Close list if open.
                html_lines.append("</ul>")  # Close list.
                in_list = False  # Reset state.
            content = line  # Set content variable to line string.
            while "**" in content:  # Loop while bold markers exist.
                content = content.replace("**", "<strong>", 1).replace("**", "</strong>", 1)  # Replace pairs with tags.
            html_lines.append(f"<p style='line-height:1.6; margin-bottom:15px;'>{content}</p>")  # Append paragraph markup.
    if in_list:  # If a list block remains unclosed at the end of text.
        html_lines.append("</ul>")  # Close the final list container.
    return "".join(html_lines)  # Join the lines and return the full HTML markup string.
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
def scrape_hacker_news(headers):  # Define a function to scrape top stories from Hacker News.
    url = "https://news.ycombinator.com/"  # Set the target Hacker News home URL.
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
                    full_url = href if href.startswith('http') else f"https://news.ycombinator.com/{href}"  # Build absolute URL.
                    articles.append({"title": title, "link": full_url, "source": "Hacker News", "author": "Hacker News User"})  # Save details.
        else:  # If the server returned an error.
            print(f"Hacker News responded with status code: {response.status_code}")  # Log the status code.
    except Exception as e:  # Catch any exception.
        print(f"Error scraping Hacker News: {e}")  # Print the error details.
    return articles[:10]  # Return the top 10 stories found.
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
def send_summary_email(config, articles, videos, llm_newsletter=None):  # Define a function to send the compiled daily digest via Gmail.
    sender = config["gmail_sender"]  # Retrieve sender's Gmail address from configuration.
    app_password = config["gmail_app_password"]  # Retrieve the Gmail App Password.
    receiver = config["gmail_receiver"]  # Retrieve the recipient's email address.
    if sender == "your_email@gmail.com" or app_password == "your_gmail_app_password":  # Check if email config is still default.
        print("Warning: Gmail credentials not configured. Skipping email delivery.")  # Print warning message.
        return  # Exit function early.
    today_str = datetime.date.today().strftime("%B %d, %Y")  # Format today's date nicely (e.g. May 23, 2026).
    msg = MIMEMultipart('alternative')  # Create a MIMEMultipart container to support HTML email markup.
    subject = f"Daily AI News Summary - {today_str}"  # Set default subject.
    if llm_newsletter:  # If we have an LLM generated newsletter.
        lines = llm_newsletter.split("\n")  # Split into lines.
        for line in lines:  # Loop through lines.
            if line.strip().lower().startswith("subject:"):  # Check if line contains subject suggestion.
                subject = line.replace("Subject:", "", 1).replace("subject:", "", 1).strip()  # Extract the subject.
                if subject.startswith("[") and subject.endswith("]"):  # Strip brackets.
                    subject = subject[1:-1].strip()  # Remove brackets.
    msg['Subject'] = subject  # Set the email subject line.
    msg['From'] = sender  # Set the sender email address header.
    msg['To'] = receiver  # Set the recipient email address header.
    if llm_newsletter:  # If we have an LLM newsletter content.
        newsletter_html = convert_markdown_to_html(llm_newsletter)  # Convert Markdown to HTML.
        html = f"""<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f7f9fc; color: #333333; padding: 20px; }}
  .container {{ max-width: 650px; background-color: #ffffff; margin: 0 auto; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); padding: 30px; }}
  .footer {{ background-color: #f1f3f5; color: #666666; text-align: center; padding: 15px; font-size: 12px; border-top: 1px solid #e9ecef; margin-top: 30px; }}
</style>
</head>
<body>
<div class="container">
  {newsletter_html}
  <div class="footer">
    Sent automatically by your Daily AI News Scheduler Script.<br>
    Running on Python and Gemini API.
  </div>
</div>
</body>
</html>
"""  # Complete HTML format template for LLM newsletter.
    else:  # Else fallback to default HTML layout.
        html = f"""<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f7f9fc; color: #333333; padding: 20px; }}
  .container {{ max-width: 600px; background-color: #ffffff; margin: 0 auto; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
  .header {{ background: linear-gradient(135deg, #1e3c72, #2a5298); color: #ffffff; padding: 30px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px; }}
  .header p {{ margin: 10px 0 0 0; opacity: 0.9; font-size: 14px; }}
  .content {{ padding: 30px; }}
  .section-title {{ font-size: 18px; color: #1e3c72; border-bottom: 2px solid #eef2f7; padding-bottom: 8px; margin-top: 0; margin-bottom: 15px; font-weight: 600; }}
  .item {{ margin-bottom: 20px; }}
  .item-title {{ font-weight: bold; font-size: 15px; margin: 0 0 5px 0; }}
  .item-title a {{ color: #1a0dab; text-decoration: none; }}
  .item-title a:hover {{ text-decoration: underline; }}
  .item-meta {{ font-size: 12px; color: #777777; margin: 0; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase; margin-right: 5px; }}
  .badge-tc {{ background-color: #e8f5e9; color: #2e7d32; }}
  .badge-oa {{ background-color: #eceff1; color: #37474f; }}
  .badge-gb {{ background-color: #e3f2fd; color: #1565c0; }}
  .badge-hn {{ background-color: #ffebd6; color: #d84b00; }}
  .badge-yt {{ background-color: #ffebee; color: #c62828; }}
  .footer {{ background-color: #f1f3f5; color: #666666; text-align: center; padding: 15px; font-size: 12px; border-top: 1px solid #e9ecef; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Daily AI News Summary</h1>
    <p>Your curated digest for {today_str}</p>
  </div>
  <div class="content">
    <h2 class="section-title">Latest Articles</h2>
    """  # Start HTML layout definition.
        if not articles:  # Check if no articles were found.
            html += "<p>No new articles collected today.</p>"  # Add empty notification.
        else:  # If we have articles.
            for art in articles:  # Loop through all articles.
                if art["source"] == "TechCrunch":  # If article is from TechCrunch.
                    badge_class, badge_code = "badge-tc", "TC"  # Set TC styles.
                elif art["source"] == "OpenAI":  # If article is from OpenAI.
                    badge_class, badge_code = "badge-oa", "OA"  # Set OA styles.
                elif art["source"] == "Google Blog":  # If article is from Google Blog.
                    badge_class, badge_code = "badge-gb", "Google"  # Set Google styles.
                else:  # Else if article is from Hacker News.
                    badge_class, badge_code = "badge-hn", "HN"  # Set HN styles.
                html += f"""
    <div class="item">
      <p class="item-title"><a href="{art['link']}">{art['title']}</a></p>
      <p class="item-meta">
        <span class="badge {badge_class}">{badge_code}</span>
        Published by {art['author']}
      </p>
      <p style="margin: 5px 0 0 0; font-size: 13px; color: #555555; font-style: italic;">{art.get('summary', 'No summary available.')}</p>
    </div>
                """  # Format article card details.
        html += """
    <h2 class="section-title" style="margin-top: 30px;">Trending YouTube Videos</h2>
    """  # Add YouTube header section.
        if not videos:  # Check if video list is empty.
            html += "<p>No YouTube videos retrieved today.</p>"  # Add empty notification.
        else:  # If we have videos.
            for vid in videos:  # Loop through each video.
                html += f"""
    <div class="item">
      <p class="item-title"><a href="{vid['link']}">{vid['title']}</a></p>
      <p class="item-meta">
        <span class="badge badge-yt">YouTube</span>
        Channel: {vid['author']}
      </p>
      <p style="margin: 5px 0 0 0; font-size: 13px; color: #555555; font-style: italic;">{vid.get('summary', 'No summary available.')}</p>
    </div>
                """  # Format video card details.
        html += """
  </div>
  <div class="footer">
    Sent automatically by your Daily AI News Scheduler Script.<br>
    Running on Python.
  </div>
</div>
</body>
</html>
"""  # Complete HTML format template.
    try:  # Start a try block for sending emails.
        msg.attach(MIMEText(html, 'html'))  # Attach the HTML body string to the MIME message structure.
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)  # Connect to Gmail SMTP server using SSL encryption on port 465.
        server.login(sender, app_password)  # Authenticate with the Gmail server using credentials.
        server.sendmail(sender, receiver, msg.as_string())  # Send the email to the recipient address.
        server.quit()  # Disconnect and close the SMTP session cleanly.
        print(f"Summary email successfully sent to {receiver}!")  # Print success logs.
    except Exception as e:  # Capture connection or authentication errors.
        print(f"Error sending email: {e}")  # Print the error details to log.
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
def save_newsletter_to_repo(llm_newsletter):  # Save newsletter to newsletters/ dir and update index.json for the website.
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory containing the script.
    newsletters_dir = os.path.join(script_dir, "newsletters")  # Build path to newsletters folder.
    os.makedirs(newsletters_dir, exist_ok=True)  # Create the directory if it does not yet exist.
    today = datetime.date.today()  # Get today's date object.
    today_str = today.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD for filenames and JSON keys.
    today_display = today.strftime("%B %d, %Y")  # Format as human-readable string for titles.
    content = llm_newsletter if llm_newsletter else f"# AI Daily Signal — {today_display}\n\nNo newsletter generated today."  # Use LLM output or fallback.
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
    index = [e for e in index if e.get("date") != today_str]  # Remove any existing entry for today.
    index.insert(0, {"date": today_str, "title": f"AI Daily Signal — {today_display}", "file": f"newsletters/{today_str}.md"})  # Prepend today's entry.
    with open(index_path, "w", encoding="utf-8") as f:  # Write updated index file.
        json.dump(index, f, indent=2)  # Save as formatted JSON.
    print(f"Newsletter saved to repo: newsletters/{today_str}.md")  # Log success.
#
def job():  # Define the main job wrapper that combines all tasks.
    print(f"\n--- Starting AI News Collection Job at {datetime.datetime.now()} ---")  # Log startup timestamp.
    config = load_config()  # Load configuration values.
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}  # Set browser headers to prevent scraping blocks.
    tc_articles = scrape_techcrunch(headers)  # Fetch recent articles from TechCrunch.
    oa_articles = scrape_openai(headers)  # Fetch recent news items from OpenAI.
    gb_articles = scrape_google_blog(headers)  # Fetch recent posts from Google Blog.
    hn_articles = scrape_hacker_news(headers)  # Fetch recent stories from Hacker News.
    all_articles = tc_articles + oa_articles + gb_articles + hn_articles  # Combine all articles from the websites.
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
    send_summary_email(config, all_articles, youtube_videos, llm_newsletter)  # Deliver digest email.
    save_backup(config, all_articles, youtube_videos, llm_newsletter)  # Write updates backup file.
    save_newsletter_to_repo(llm_newsletter)  # Save newsletter to newsletters/ directory for the website.
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
