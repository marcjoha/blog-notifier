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

# Suppress excessive logging
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

CHAT_WEBHOOK = os.environ.get("CHAT_WEBHOOK")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")

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
    if not CHAT_WEBHOOK:
        log.error("BLOG_NOTIFIER_WEBHOOK environment variable missing, exiting...")
        return
    if not GOOGLE_CLOUD_PROJECT:
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
            try:
                pubDate = parser.parse(entry.updated)
            except AttributeError:
                log.warning(f"Encountered post without date in feed [{feed_url}]")
                continue
           
        # also skip if pubDate is older than our cut off date
        if(pubDate < cut_off_date):
            continue

        # if there's content available, clean it up and run AI magic
        if(entry.summary):
            content = re.sub(html_tags, "", entry.summary)
            summary = get_summary(entry.summary)

        posts += [{"site": feed.feed.title, "url": entry.link, "title": entry.title, "summary": summary}]

    return posts

def get_summary(content):
    return ask_gemini("Summarize the following with at most 25 words: " + content)

def ask_gemini(prompt):
    try:
        client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location="us-central1", http_options=HttpOptions(api_version="v1"))
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=[prompt],
        )
        return response.text
    except Exception as e:
        log.error(f"Error from Vertex: [{e}]")
        return ""

def notify(post):
    message = ""

    if post["site"]:
        if "Google Kubernetes Engine" in post["site"]:
            message += "GKE feature log: "
        else:
            message += post["site"] + ": "


    message += "<" + post["url"] + "|" + post["title"] + ">"

    if post["summary"]:
        message += "\n\n" + post["summary"]

    response = Http().request(
        uri=CHAT_WEBHOOK,
        method="POST",
        headers={"Content-Type": "application/json; charset=UTF-8"},
        body=json.dumps({"text": message}),
    )

    if response[0].status != 200:
        log.error(f"Failed to notify with status [{response[0].status}] on post [{post['url']}]")
        return False
    
    return True

if __name__ == "__main__":
    main()
