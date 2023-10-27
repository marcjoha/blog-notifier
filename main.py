import os
import feedparser
import json
import re
from datetime import datetime, timedelta, timezone
from dateutil import parser
from httplib2 import Http
from vertexai.preview.language_models import TextGenerationModel
from google.api_core.exceptions import PermissionDenied
import logging

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
log = logging.getLogger("blog-notifier")

HTML_TAGS = re.compile("<.*?>")
HOURS_OLD = 1

# Google Chat space webhook
WEBHOOK = ""

FEED_URLS = [
    "https://cloudblog.withgoogle.com/products/api-management/rss/",
    "https://cloudblog.withgoogle.com/products/application-development/rss/",
    "https://cloudblog.withgoogle.com/products/application-modernization/rss/",
    "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",
    "https://cloudblog.withgoogle.com/products/devops-sre/rss/",
    "https://cloudblog.withgoogle.com/products/serverless/rss/",
    "https://cloudblog.withgoogle.com/topics/developers-practitioners/rss/",
    "https://kubernetes.io/feed.xml"
]

def main():

    if not WEBHOOK:
        log.error("Webhook missing, exiting...")
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

        # if there's content available, try to summarize it using AI
        summary = summarize(entry.summary) if entry.summary else ""

        posts += [{"url": entry.link, "title": entry.title, "summary": summary}]

    return posts

def summarize(content):

    # remove html that might interfere 
    content = re.sub(HTML_TAGS, "", content)

    model = TextGenerationModel.from_pretrained("text-bison@001")
    parameters = {
        "temperature": .2,
        "max_output_tokens": 256,   
        "top_p": .8,                
        "top_k": 40,                 
    }
    try:
        response = model.predict("Provide a summary with about two sentences for the following article: " + content, **parameters)
    except PermissionDenied:
        log.error("Not allowed to query Vertex AI to create summary")
    except Exception as e:
        log.error(e)
        return ""

    return response.text

def notify(post):

    if post["summary"]:
        message = "*" + post["title"] + "*\n" + post["url"] + "\n\n" + post["summary"]
    else:
        message = "*" + post["title"] + "*\n" + post["url"]

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
