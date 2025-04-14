import os
import feedparser
import json
import re
from datetime import datetime, timedelta, timezone
from dateutil import parser
from httplib2 import Http
import logging
from google import genai
from google.genai.types import HttpOptions, Part

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
log = logging.getLogger("blog-notifier")

# Get WEBHOOK and GCP_PROJECT from environment variables
WEBHOOK = os.environ.get("BLOG_NOTIFIER_WEBHOOK")
GCP_PROJECT = os.environ.get("BLOG_NOTIFIER_GCP_PROJECT")

HOURS_OLD = 24*7
FEED_URLS = [
    "https://cloudblog.withgoogle.com/products/api-management/rss/",
    "https://cloudblog.withgoogle.com/products/application-development/rss/",
    "https://cloudblog.withgoogle.com/products/application-modernization/rss/",
    "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",
    "https://cloudblog.withgoogle.com/products/devops-sre/rss/",
    "https://cloudblog.withgoogle.com/products/serverless/rss/",
    "https://cloud.google.com/feeds/gke-new-features-release-notes.xml"
]

def main():

    # Check if environment variables are set
    if not WEBHOOK:
        log.error("BLOG_NOTIFIER_WEBHOOK environment variable missing, exiting...")
        return
    if not GCP_PROJECT:
        log.error("BLOG_NOTIFIER_GCP_PROJECT environment variable missing, exiting...")
        return

    log.info(f"Querying [{len(FEED_URLS)}] feed{'s'[:len(FEED_URLS)^1]} for new posts over the last [{HOURS_OLD}] hour{'s'[:HOURS_OLD^1]}")

    posts = []
    for feed_url in FEED_URLS:
        posts += fetch_posts(feed_url, HOURS_OLD)

    # google blogs often publish the same post in multiple channels at
    # the same time, so this prevents notifying twice for the same post
    done = []
    for post in posts:
        if post["url"] not in done:
            success = notify(post)
            done += [post["url"] if success else []]

    if len(done):
        log.info(f"Found and notified [{len(done)}] new post{'s'[:len(done)^1]}")
    else:
        log.info("No new posts")
    
def fetch_posts(feed_url, hours_old):

    html_tags = re.compile("<.*?>")

    # only consider posts newer than HOURS_OLD
    cut_off_date = datetime.now().replace(tzinfo=timezone.utc) - timedelta(hours=hours_old)

    feed = feedparser.parse(feed_url)

    posts = []
    for entry in feed.entries:

        try:
            pubDate = parser.parse(entry.published)
        except AttributeError:
            # skip post if there's no date information
            continue
            
        # also skip if pubDate is older than our cut off date
        if(pubDate < cut_off_date):
            continue

        # if there's content available, clean it up and run AI magic
        if(entry.summary):
            content = re.sub(html_tags, "", entry.summary)
            summary = get_summary(entry.summary)
            techiness = get_techiness(entry.summary)

        posts += [{"url": entry.link, "title": entry.title, "summary": summary, "techiness": techiness}]

    return posts

def get_summary(content):
    return ask_gemini("Summarize the following with at most 25 words: " + content)

def get_techiness(content):
    answer = ask_gemini("Estimate how technical the following text is by assigning a score 1-5, where 1 is the least technical and 5 is the most technical (return only the number, nothing else): " + content)
    techiness = answer.strip()
    if techiness.isdigit():
        if techiness == '1':
            return '1️⃣'
        elif techiness == '2':
            return '2️⃣'
        elif techiness == '3':
            return '3️⃣'
        elif techiness == '4':
            return '4️⃣'
        elif techiness == '5':
            return '5️⃣'
        else:
            return None
    else:
        return None

def ask_gemini(prompt):
    try:
        client = genai.Client(vertexai=True, project=GCP_PROJECT, location="us-central1", http_options=HttpOptions(api_version="v1"))
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=[prompt],
        )
        return response.text
    except Exception as e:
        log.error(f"Error from Vertex: {e}")
        return ""

def notify(post):
    message = ""

    if post["techiness"]:
         message += post["techiness"] + " / 5️⃣: "

    message += "<" + post["url"] + "|" + post["title"] + ">"

    if post["summary"]:
        message += "\n\n" + post["summary"]

    response = Http().request(
        uri=WEBHOOK,
        method="POST",
        headers={"Content-Type": "application/json; charset=UTF-8"},
        body=json.dumps({"text": message}),
    )

    if response[0].status != 200:
        log.error(f"Failed to notify with status [{response[0].status_code}] on post [{post['url']}]")
        return False
    
    return True

if __name__ == "__main__":
    main()
