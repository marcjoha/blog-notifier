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
HOURS_OLD = 24

# Google Meet space webhook
WEBHOOK = ""

FEED_URLS = [
    "https://cloudblog.withgoogle.com/products/api-management/rss/",
    "https://cloudblog.withgoogle.com/products/application-development/rss/",
    "https://cloudblog.withgoogle.com/products/application-modernization/rss/",
    "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",
    "https://cloudblog.withgoogle.com/products/devops-sre/rss/",
    "https://cloudblog.withgoogle.com/products/serverless/rss/"
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

        # if there's content available, clean it up and run AI magic
        if(entry.summary):
            content = re.sub(HTML_TAGS, "", entry.summary)
            summary = summarize(entry.summary)
            techiness = get_techiness(entry.summary)

        posts += [{"url": entry.link, "title": entry.title, "summary": summary, "techiness": techiness}]

    return posts

def summarize(content):

    query = "Summarize the following text using at most 30 words"

    model = TextGenerationModel.from_pretrained("text-bison")
    parameters = {
        "temperature": .2,
        "max_output_tokens": 256,   
        "top_p": .8,                
        "top_k": 40,                 
    }
    try:
        response = model.predict(query + ": " + content, **parameters)

    except PermissionDenied:
        log.error("Not allowed to query Vertex AI to create summary")
    except Exception as e:
        log.error(e)
        return ""

    # clean up output
    summary = re.sub(HTML_TAGS, "", response.text.strip())

    if summary.startswith(query):
        summary = summary[len(query)+1:].strip()

    if summary:
        return summary
    else:
        return None

# returns a 1-5 emoji

def get_techiness(content):

    model = TextGenerationModel.from_pretrained("text-bison")
    parameters = {
        "temperature": 0,
        "max_output_tokens": 256,   
        "top_p": .8,                
        "top_k": 40,                 
    }
    try:
        response = model.predict("Estimate how technical the following text is by assigning a score 1-5, where 1 is the least technical and 5 is the most technical (return only the number, nothing else): " + content, **parameters)
    except PermissionDenied:
        log.error("Not allowed to query Vertex AI to gauge techiness")
    except Exception as e:
        log.error(e)
        return ""

    techiness = response.text.strip()
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

def notify(post):

    # message = "*" + post["title"] + "*\n" + post["url"]

    # if post["techiness"]:
    #     message += "\n\n_Tech score_: " + post["techiness"] + " / 5️⃣"
    #     if post["summary"]:
    #         message += "\n_Summary_: " + post["summary"]
    # else:
    #     if post["summary"]:
    #         message += "\n\n_Summary_: " + post["summary"]

    message = ""

    if post["techiness"]:
         message += post["techiness"] + " / 5️⃣: "

    message += post["title"]

    if post["summary"]:
        message += "\n\n" + post["summary"]

    if post["url"]:
        message += "\n\n" + post["url"]

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
