import base64
from datetime import datetime
from dotenv import load_dotenv
import instaloader
from instaloader import Profile
import logging
import os
import random
import re
import requests
import shutil
import sys
import traceback

# File to store the last downloaded post ID
LAST_POST_FILE = "last_post_date.txt"

# How many posts to pull down each time - 0 for all
POSTS_PER_INVOKE = 20

# Load environment variables from the .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/instadram.log"),
        logging.StreamHandler()
    ]
)

instagram_username = os.getenv("INSTA_NAME")
wordpress_url = os.getenv("WP_URL")
wp_username = os.getenv("WP_USER")
wp_application_password = os.getenv("WP_PASS")


# Initialize variables
last_post_date = None

# def extractfiles(path):
#     for file in os.listdir(path):
#         if file.endswith(".xz"):
#             input_file = os.path.join(path, file)
#             output_file = os.path.join(path, file[:-3])  # Remove .xz extension

#             with lzma.open(input_file, "rb") as compressed_file:
#                 with open(output_file, "wb") as decompressed_file:
#                     decompressed_file.write(compressed_file.read())

#             logging.info(f"Decompressed {input_file}")


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

def download_new_posts(username):
    
    """Download only new Instagram posts."""
    loader = instaloader.Instaloader()
    loader.load_session_from_file(username)
    # logging.info(f"Logging in...")
    # loader.login(username, os.getenv("INSTA_PASSWORD"))

    global last_post_date

    try:
        logging.debug(f"Username: {username}")
        profile = Profile.from_username(loader.context, username)

        # Set post filter to only download posts after the last downloaded post date
        if last_post_date:
            logging.debug(f"Fetch all posts after {last_post_date}")
            loader.download_profiles({profile}, profile_pic=False, stories=False, post_filter=lambda post: post.date_utc > last_post_date)
        else:
            logging.debug("Fetch all posts")
            loader.download_profiles({profile}, profile_pic=False, stories=False)

    except Exception as e:
        logging.error(f"An error occurred: {traceback.format_exc()}")

# Parse downloaded Instagram data
def build_post_array(folder_path):
    posts_data = []
    if not os.path.exists(folder_path):
        logging.warning(f"Folder not found: {folder_path}")
        return []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.txt'):
                with open(os.path.join(root, file), 'r') as txt_file:
                    post_data = txt_file.readline()
                    image_path = os.path.join(root, file.replace(".txt", ".jpg"))
                    if os.path.exists(image_path):
                        posts_data.append({
                            "fname": file,
                            "caption": post_data,
                            "image_path": image_path,
                        })
    return posts_data

# Upload to WordPress
def upload_to_wordpress(post, wordpress_url, authheaders):
    try:
        with open(post["image_path"], "rb") as image_file:
            
            media_response = requests.post(
                f"{wordpress_url}/wp-json/wp/v2/media",
                headers=authheaders,
                files={"file": image_file},
            )
            if media_response.status_code == 201:
                media_id = media_response.json()["id"]
                # Create WordPress post
                pattern = r"^#(\w+)\s+(.*)\s+(\d{4}-\d{2}-\d{2})$"

                # Match the pattern
                match = re.match(pattern, post["caption"])

                if match:
                    hashtag = match.group(1)
                    remaining_text = match.group(2)
                    date = match.group(3)
                    datet = match.group(3) + f"T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}" + ":00"

                    distillery_name = find_distillery_by_name(distilleries, remaining_text)

                    post_data = {
                        "title": remaining_text,
                        "status": "publish",
                        "featured_media": media_id,
                        "date": datet,
                    }

                    if distillery_name:
                        post_data["distillery"] = distillery_name

                    if hashtag == "in":
                        post_data["date_bought"] = date
                    elif hashtag == "open":
                        post_data["date_opened"] = date
                    elif hashtag == "out":
                        post_data["date_finished"] = date

                    logging.info(f"bits {date}")
                else:
                    post_data = {
                        "title": post["caption"],
                        "status": "draft",
                        "featured_media": media_id,
                    }

                post_response = requests.post(
                    f"{wordpress_url}/wp-json/wp/v2/whisky_bottle",
                    headers=authheaders,
                    json=post_data,
                )
                if post_response.status_code == 201:
                    logging.info(f"Post uploaded: {post_response.json().get('link')}")
                else:
                    logging.error(f"Failed to create post: {post_response.status_code} - {post_response.text}")
                    # print(f"Failed to create post: {post_response.status_code}")
            else:
                logging.error(f"Failed to upload media: {media_response.status_code} - {media_response.text}")
                # print(f"Failed to upload media: {media_response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def fetch_distilleries(authheaders):
    """
    Fetch the list of distilleries from the custom API endpoint.
    Returns a list of distillery objects.
    """
    try:
        distilleries_endpoint = f"{wordpress_url}/wp-json/whisky-bottle/v1/distilleries"
        response = requests.get(distilleries_endpoint, headers=authheaders)

        if response.status_code != 200:
            print(f"Error retrieving distilleries: {response.status_code} - {response.text}")
            return []

        # Return the list of distilleries
        return response.json()

    except Exception as e:
        print(f"An error occurred while fetching distilleries: {e}")
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

def postDate(e):
  return e['fname']

def cleanupFiles(path):
    shutil.rmtree(path, ignore_errors=False, onexc=fileDelHandler)

def fileDelHandler(func, path, exc_info):
    logging.error(f"Error in cleanup: {exc_info}")


# Main script
if __name__ == "__main__":

    os.environ['https_proxy'] = "https://sp2178jfc3:rf99ezswYS4aXk+S4c@gate.smartproxy.com:10001"

    try:
        # Get the last downloaded post date
        last_post_date = get_last_post_date()
        logging.info(f"Last downloaded post date: {last_post_date} - obj {isinstance(last_post_date, datetime)}")

        # Step 1: Download Instagram posts
        download_new_posts(instagram_username)

        # Step 2: Parse Instagram data
        posts = build_post_array('./'+instagram_username)
        logging.debug('array built')
        posts.sort(key=postDate)

        logging.debug('posts sorted')
        logging.debug(posts)

        # Step 3: Upload to WordPress & cleanup
        if posts:
            new_posts_processed = 0

            credentials = f"{wp_username}:{wp_application_password}"
            token = base64.b64encode(credentials.encode())
            authheaders = {"Authorization": f"Basic {token.decode('utf-8')}"}

            distilleries = fetch_distilleries(authheaders)
            for post in posts:
                upload_to_wordpress(post, wordpress_url, authheaders)
                last_post_date = datetime.strptime(post['fname'].rsplit('.', 1)[0], "%Y-%m-%d_%H-%M-%S_UTC")
                new_posts_processed += 1

                if POSTS_PER_INVOKE > 0 and new_posts_processed >= POSTS_PER_INVOKE:
                    break
            
            save_last_post_date(last_post_date)

            cleanupFiles('./'+instagram_username)
        else:
            logging.warning("No posts found to upload.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(42)

    finally:
        os.environ['https_proxy'] = None

