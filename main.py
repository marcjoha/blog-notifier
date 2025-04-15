import json
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
from dateutil import parser
from google import genai
from google.genai.types import HttpOptions
from httplib2 import Http

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
log = logging.getLogger("blog-notifier")

# Suppress excessive INFO logging to not clog log output
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

CHAT_WEBHOOK = os.environ.get("CHAT_WEBHOOK")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
AI_REGION = os.environ.get("AI_REGION")

# Only look for posts newer than POST_MAX_AGE_HOURS (match this to scheduling frequency)
POST_MAX_AGE_HOURS = 24

# RSS/Atom feeds to monitor 
FEED_URLS = {
    "APIs": "https://cloudblog.withgoogle.com/products/api-management/rss/",
    "AppDev": "https://cloudblog.withgoogle.com/products/application-development/rss/",
    "AppMod": "https://cloudblog.withgoogle.com/products/application-modernization/rss/",
    "K8s": "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",
    "DevOps": "https://cloudblog.withgoogle.com/products/devops-sre/rss/",
    "Serverless": "https://cloudblog.withgoogle.com/products/serverless/rss/",
    "GKE feature log": "https://cloud.google.com/feeds/gke-new-features-release-notes.xml"
}

def main():
    
    if not CHAT_WEBHOOK:
        log.error("CHAT_WEBHOOK environment variable missing, exiting...")
        return
    elif not is_valid_url(CHAT_WEBHOOK):
        log.error(f"CHAT_WEBHOOK environment variable is not a valid URL [{CHAT_WEBHOOK}], exiting...")
        return
    
    if not GOOGLE_CLOUD_PROJECT:
        log.error("GOOGLE_CLOUD_PROJECT environment variable missing, exiting...")
        return
    
    if not AI_REGION:
        log.error("AI_REGION environment variable missing, exiting...")
        return

    log.info(f"Querying [{len(FEED_URLS)}] feed{'s'[:len(FEED_URLS)^1]} for new posts over the last [{POST_MAX_AGE_HOURS}] hour{'s'[:POST_MAX_AGE_HOURS^1]}")

    posts = []
    for feed_title, feed_url in FEED_URLS.items():
        posts.extend(fetch_posts(feed_title, feed_url, POST_MAX_AGE_HOURS))

    # google blogs often publish the same post in multiple channels at
    # the same time, this prevents notifying twice for the same post
    done = set()
    for post in posts:
        if post["url"] not in done:
            success = notify(post)
            if success:
                done.add(post["url"])

    if done:
        log.info(f"Found and notified [{len(done)}] new post{'s'[:len(done)^1]}")
    else:
        log.info("No new posts")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False
    
def fetch_posts(feed_title, feed_url, max_age_hours):
    # Only consider posts newer than POST_MAX_AGE_HOURS
    cut_off_date = datetime.now().replace(tzinfo=timezone.utc) - timedelta(hours=max_age_hours)

    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        log.error(f"Error parsing feed [{feed_url}]: [{e}]")
        return []

    posts = []
    for entry in feed.entries:
        if hasattr(entry, 'published'):
            pubDate = parser.parse(entry.published)
        elif hasattr(entry, 'updated'):
            pubDate = parser.parse(entry.updated)
        elif hasattr(entry, 'created'):
            pubDate = parser.parse(entry.created)
        else:
            log.warning(f"Encountered post without date in feed [{feed_url}]")
            continue

        # Skip if pubDate is older than our cut off date
        if pubDate < cut_off_date:
            continue

        # if there's content available, clean it up and run AI magic
        summary = get_summary(entry.summary) if entry.summary else ""

        posts.append({"feed_title": feed_title, "url": entry.link, "title": entry.title, "summary": summary})

    return posts

def get_summary(content):
    try:
        client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location=AI_REGION, http_options=HttpOptions(api_version="v1"))
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=["You're a Google Cloud technical professional. Summarize the following with at most 40 words: " + content],
        )
        return response.text
    except Exception as e:
        log.error(f"Error from Vertex: [{e}]")
        return ""

def notify(post):
    message = post["feed_title"] + ": <" + post["url"] + "|" + post["title"] + ">"

    if post["summary"]:
        message += "\n\n" + post["summary"].strip()

    response = Http().request(
        uri=CHAT_WEBHOOK,
        method="POST",
        headers={"Content-Type": "application/json; charset=UTF-8"},
        body=json.dumps({"text": message}),
    )

    if response[0].status != 200:
        log.error(f"Failed to notify due to web hook response [{response[0]}]")
        return False
    
    return True

if __name__ == "__main__":
    main()