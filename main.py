import base64
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import pytumblr
import logging
import os
import random
import re
import requests
import shutil
import sys

# File & path to store the last downloaded post ID
LAST_POST_FILE = "./data/last_post_date.txt"

# How many posts to pull down each time - 0 for all
POSTS_PER_INVOKE = 20

# Load environment variables from the .env file
load_dotenv(override=True)

logLevel = logging.INFO
if os.getenv("LOGLEVEL") == "DEBUG":
    logLevel = logging.DEBUG

# Configure logging
logging.basicConfig(
    level=logLevel,
    format='%(asctime)s - %(levelname)s (%(lineno)d)- %(message)s',
    handlers=[
        logging.FileHandler("./logs/instadram.log"),
        logging.StreamHandler()
    ]
)

tumblr_username = os.getenv("TUMBLR_NAME")
wordpress_url = os.getenv("WP_URL")
wp_jwt = os.getenv("WP_JWT", None)
# fallback to Application Password if no JWT is provided
wp_username = os.getenv("WP_USER", None)
wp_application_password = os.getenv("WP_PASS", None)


# Initialize variables
last_post_date = None

tumblr_client = pytumblr.TumblrRestClient(
    os.getenv("TUMBLR_API_KEY"),
    os.getenv("TUMBLR_SECRET"),
    "",
    ""
)

def get_last_post_date():
    """Read the last post date from the file."""
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE, "r") as file:
            return datetime.strptime(file.read().strip(), '%Y-%m-%d %H:%M:%S')
    return None

def save_last_post_date(post_date):
    """Save the last downloaded post date to the file."""
    with open(LAST_POST_FILE, "w") as file:
        file.write(post_date.strftime('%Y-%m-%d %H:%M:%S'))

def upload_to_wordpress(posts, photos, wordpress_url, headers):
    logging.debug(f"---upload_to_wordpress---")
    # Iterate Posts
    #  - upload the image to wordpress
    #  - create a new post in wordpress using the fields

    iterator = 0

    for post in posts:
        logging.debug(f"Pre-frig: {post}")
        media_id = None
        if photos[iterator]:
            post["image_path"] = photos[iterator]
        else:
            logging.debug(f"No image found for post: {post['summary']}")

        try:
            if post["image_path"]:
                logging.debug(f"Uploading image: {post['image_path']}")

                with open(post["image_path"], "rb") as image_file:
                    media_response = requests.post(
                        f"{wordpress_url}/wp-json/wp/v2/media",
                        headers=headers,
                        files={"file": image_file},
                    )
                    if media_response.status_code == 201:
                        media_id = media_response.json()["id"]

            if media_id:
                post["featured_media"] = media_id

            logging.debug(f"Postfrig: {post}")

            post_response = requests.post(
                f"{wordpress_url}/wp-json/wp/v2/whisky_bottle",
                headers=headers,
                json=post,
            )

            if post_response.status_code == 201:
                logging.debug(f"Post uploaded: {post_response.json().get('link')}")
            else:
                logging.error(f"Failed to create post: {post_response.status_code} - {post_response.text}")
        except Exception as e:
            logging.error(f"An error occurred: {e}")
        finally:
            iterator += 1


def fetch_distilleries(authheaders):
    """
    Fetch the list of distilleries from the custom API endpoint.
    Returns a list of distillery objects.
    """
    try:
        distilleries_endpoint = f"{wordpress_url}/wp-json/whisky-bottle/v1/distilleries"
        response = requests.get(distilleries_endpoint, headers=authheaders)

        if response.status_code != 200:
            logging.warning(f"Error retrieving distilleries: {response.status_code} - {response.text}")
            return []

        # Return the list of distilleries
        return response.json()

    except Exception as e:
        logging.warning(f"An error occurred while fetching distilleries: {e}")
        return []

def find_distillery_by_name(distilleries, search_string):
    """
    Search the list of distilleries for a partial match in the search string.
    Returns the first matching distillery name or empty string
    """
    search_string_lower = search_string.lower()

    for distillery in distilleries:
        distillery_name = distillery.get("name", "").lower()
        if distillery_name in search_string_lower:
            return distillery_name

    return ""

def fetch_bottlers(authheaders):
    """
    Fetch the list of bottlers from the custom API endpoint.
    Returns a list of bottler objects.
    """
    try:
        bottlers_endpoint = f"{wordpress_url}/wp-json/whisky-bottle/v1/bottlers"
        response = requests.get(bottlers_endpoint, headers=authheaders)

        if response.status_code != 200:
            logging.warning(f"Error retrieving bottlers: {response.status_code} - {response.text}")
            return []

        # Return the list of bottlers
        return response.json()

    except Exception as e:
        logging.warning(f"An error occurred while fetching bottlers: {e}")
        return []

def find_bottler_by_name(bottlers, search_string):
    """
    Search the list of bottlers for a partial match in the search string.
    Returns the first matching bottler name or empty string
    """
    search_string_lower = search_string.lower()

    for bottler in bottlers:
        bottler_name = bottler.get("name", "").lower()
        if bottler_name in search_string_lower:
            return bottler_name

    return ""


def cleanupFiles(path):
    shutil.rmtree(path, ignore_errors=False, onexc=fileDelHandler)

def fileDelHandler(func, path, exc_info):
    logging.error(f"Error in cleanup: {exc_info}")



def parse_captions(posts):
    logging.debug(f"---parse_captions---")
    for idx, post in enumerate(posts):
        logging.debug(f"Before: {post}")

        match = re.match(r"^#(\w+)\s+(.*)\s+(\d{4}-\d{2}-\d{2})$", post['summary'])

        if match:
            hashtag = match.group(1)
            remaining_text = match.group(2)
            date = match.group(3)
            datet = match.group(3) + f"T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}" + ":00"

            distillery_name = find_distillery_by_name(distilleries, remaining_text)
            bottler_name = find_bottler_by_name(bottlers, remaining_text)

            post_data = {
                "title": remaining_text,
                "status": "publish",
                "date": datet,
                "hashtag": hashtag,
            }

            if distillery_name:
                post_data["distillery"] = distillery_name

            if bottler_name:
                post_data["bottler"] = bottler_name

            if hashtag == "in":
                post_data["date_bought"] = date
            elif hashtag == "open":
                post_data["date_opened"] = date
            elif hashtag == "out":
                post_data["date_finished"] = date

        else:
            post_data = {
                "title": post['summary'],
                "status": "draft",
            }

        posts[idx] = post_data
        logging.debug(f"After: {posts[idx]}")

    return posts

def fetch_images_from_tumblr(photos, tumblr_username):
    logging.debug(f"---fetch_images_from_tumblr---")
    for idx, photo in enumerate(photos):
        if photo:
            try:
                response = requests.get(photo)
                response.raise_for_status()  # Raise an exception for HTTP errors
            except requests.RequestException as e:
                logging.warning("Error downloading the image:", e)
            else:
                # Save the image to a file (you can change the filename as needed)
                filename = f'./{tumblr_username}/downloaded_image_{idx}.jpg'
                with open(filename, 'wb') as f:
                    f.write(response.content)
                logging.debug(f"Image successfully downloaded and saved as {filename}")
                photos[idx] = filename

    return photos

def fetch_posts_from_tumblr(client: pytumblr.TumblrRestClient, blog_name: str, last_post_date: datetime) -> list:
    logging.debug(f"---fetch_posts_from_tumblr---")
    posts = []
    photos = []
    latest_post_date = None

    # fetches in reverse-chron (i.e newest first)
    response = client.posts(blog_name, limit=50, offset=0) 
        
    for post in response['posts']:
        post_date = datetime.strptime(post['date'], '%Y-%m-%d %H:%M:%S %Z')
        if last_post_date is None or post_date > last_post_date:
            logging.debug(f"Fetched {post_date} - {post['summary']}")
            posts.append(post)
            # Parse the HTML with BeautifulSoup
            soup = BeautifulSoup(post['body'], 'html.parser')
            # Find the first <img> tag
            img_tag = soup.find('img')
            if img_tag:
                image_url = None

                # If the tag has a srcset attribute, we'll parse it to find the largest width.
                if img_tag.has_attr('srcset'):
                    srcset = img_tag['srcset']
                    # Each candidate is separated by a comma.
                    candidates = [candidate.strip() for candidate in srcset.split(',')]
                    max_width = 0
                    
                    for candidate in candidates:
                        # Each candidate is in the form: "<url> <descriptor>"
                        parts = candidate.split()
                        if len(parts) >= 2:
                            url = parts[0]
                            descriptor = parts[1]
                            # We assume the descriptor is something like "1152w"
                            try:
                                width = int(descriptor.rstrip('w'))
                                if width > max_width:
                                    max_width = width
                                    image_url = url
                            except ValueError:
                                # If the conversion fails, skip this candidate
                                continue

                # If no srcset is found or parsing fails, fall back to the 'src' attribute.
                if not image_url and img_tag.has_attr('src'):
                    image_url = img_tag['src']

                logging.debug(f"Found image URL: {image_url}")
            
            else:
                image_url = None
                logging.debug(f"No image")

            photos.append(image_url)

            if latest_post_date is None or post_date > latest_post_date:
                latest_post_date = post_date

        else: # this means the post_date we're now looking at was prior to the stored last_post_date, which we have already downloaded up to
            logging.debug(f"{last_post_date} reached - Skipped from {post_date} - {post['summary']}")
            break

    return (latest_post_date, posts, photos)

# Main script
if __name__ == "__main__":

    try:
        latest_post_date = None
        posts = []
        photos = []

        # Get the last downloaded post date
        last_post_date = get_last_post_date()
        logging.info(f"Last downloaded post date: {last_post_date} - obj {isinstance(last_post_date, datetime)}")

        # Step 1 - download posts from Tumblr
        # Ensure that we're getting anything timestamped after the last post we downloaded
        (latest_post_date, posts, photos) = fetch_posts_from_tumblr(tumblr_client, tumblr_username, last_post_date)

        if posts:
            new_posts_processed = 0
            os.makedirs(tumblr_username, exist_ok=True)

            headers = {"User-Agent": "curl/8.5.0"}
            if wp_jwt:
                headers["Authorization"] = f"Bearer {wp_jwt}"
            else:
                credentials = f"{wp_username}:{wp_application_password}"
                token = base64.b64encode(credentials.encode())
                headers["Authorization"] = f"Basic {token.decode('utf-8')}"

            logging.debug(f"Headers: {headers}")

            distilleries = fetch_distilleries(headers)
            bottlers = fetch_bottlers(headers)

            posts = parse_captions(posts)

            photos = fetch_images_from_tumblr(photos, tumblr_username)

            upload_to_wordpress(posts, photos, wordpress_url, headers)

            # Step 3 - save the timestamp of the last post we uploaded
            save_last_post_date(latest_post_date)

            cleanupFiles(f'./{tumblr_username}')

    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(42)

    finally:
        print("Done")
