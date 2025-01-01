from dotenv import load_dotenv
import os
import instaloader
import json
import requests
import lzma
import base64
import re
import random
import logging

# File to store the last downloaded post ID
LAST_POST_FILE = "last_post_id.txt"


# Load environment variables from the .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("instadram.log"),
        logging.StreamHandler()
    ]
)

instagram_username = os.getenv("INSTA_NAME")
wordpress_url = os.getenv("WP_URL")
wp_username = os.getenv("WP_USER")
wp_application_password = os.getenv("WP_PASS")



# Initialize variables
new_posts_downloaded = 0
last_fetched_post_id = None


def extractfiles(path):
    for file in os.listdir(path):
        if file.endswith(".xz"):
            input_file = os.path.join(path, file)
            output_file = os.path.join(path, file[:-3])  # Remove .xz extension

            with lzma.open(input_file, "rb") as compressed_file:
                with open(output_file, "wb") as decompressed_file:
                    decompressed_file.write(compressed_file.read())

            logging.info(f"Decompressed {input_file}")


def get_last_post_id():
    """Read the last post ID from the file."""
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE, "r") as file:
            return file.read().strip()
    return None

def save_last_post_id(post_id):
    """Save the last downloaded post ID to the file."""
    with open(LAST_POST_FILE, "w") as file:
        file.write(post_id)

def download_new_posts(username, max=0):
    """Download only new Instagram posts."""
    loader = instaloader.Instaloader()
    global last_fetched_post_id, new_posts_downloaded

    # Login (optional if accessing private profiles)
    # loader.login("your_username", "your_password")

    # Get the last downloaded post ID
    last_post_id = get_last_post_id()
    logging.info(f"Last downloaded post ID: {last_post_id}")

    try:
        # Fetch posts from the user's profile
        profile = instaloader.Profile.from_username(loader.context, username)
        for post in profile.get_posts():
            # Save the ID of the latest post in the current session
            if last_fetched_post_id is None:
                last_fetched_post_id = post.shortcode

            # Stop if we reach the last downloaded post
            if post.shortcode == last_post_id:
                break

            # Download the post
            loader.download_post(post, target=profile.username)
            new_posts_downloaded += 1
            if max > 0 and new_posts_downloaded >= max:
                break

        # Update the last downloaded post ID if new posts were found
        if last_fetched_post_id:
            save_last_post_id(last_fetched_post_id)

        if new_posts_downloaded > 0:
            logging.info(f"{new_posts_downloaded} new posts downloaded.")
            extractfiles('./'+instagram_username)
        else:
            logging.warning("No new posts found.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")


# Download Instagram posts
def download_instagram_posts(username):
    loader = instaloader.Instaloader()
    try:
        # Download posts of the given username
        print(f"Downloading posts from @{username}...")
        loader.download_profile(username, profile_pic=False, download_stories=False)
        print(f"Download complete. Posts saved in the current directory.")
        return f"./{username}"  # Folder path of the downloaded content
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Parse downloaded Instagram data
def parse_instagram_data(folder_path):
    posts_data = []
    if not os.path.exists(folder_path):
        logging.warning(f"Folder not found: {folder_path}")
        return []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.json') and file != "profile.json":
                with open(os.path.join(root, file), 'r') as json_file:
                    post_data = json.load(json_file)
                    image_path = os.path.join(root, file.replace(".json", ".jpg"))
                    if os.path.exists(image_path):
                        posts_data.append({
                            # "caption": post_data.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", ""),
                            "caption": post_data.get("node", {}).get("caption", ""),
                            "image_path": image_path,
                        })
    return posts_data

# Upload to WordPress
def upload_to_wordpress(posts_data, wordpress_url, username, application_password):
    # Upload media to WordPress
    credentials = f"{username}:{application_password}"
    token = base64.b64encode(credentials.encode())
    authheaders = {"Authorization": f"Basic {token.decode('utf-8')}"}

    distilleries = fetch_distilleries(authheaders)
        
    for post in posts_data:
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



# Main script
if __name__ == "__main__":
    # Step 1: Download Instagram posts
    folder = download_instagram_posts(instagram_username)
    download_new_posts(instagram_username)
    # new_posts_downloaded is a global
    # download_new_posts(instagram_username, 5)
    # new_posts_downloaded = 5
    if new_posts_downloaded > 0:
        # Step 2: Parse Instagram data
        posts = parse_instagram_data('./'+instagram_username)

        # Step 3: Upload to WordPress
        if posts:
            upload_to_wordpress(posts, wordpress_url, wp_username, wp_application_password)
        else:
            logging.warning("No posts found to upload.")
