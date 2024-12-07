from dotenv import load_dotenv
import os
import instaloader
import json
import requests
import lzma

# File to store the last downloaded post ID
LAST_POST_FILE = "last_post_id.txt"


# Load environment variables from the .env file
load_dotenv()

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

            print(f"Decompressed {input_file}")


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
    print(f"Last downloaded post ID: {last_post_id}")

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
            print(f"{new_posts_downloaded} new posts downloaded.")
            extractfiles('./'+instagram_username)
        else:
            print("No new posts found.")

    except Exception as e:
        print(f"An error occurred: {e}")


# # Download Instagram posts
# def download_instagram_posts(username):
#     loader = instaloader.Instaloader()
#     try:
#         # Download posts of the given username
#         print(f"Downloading posts from @{username}...")
#         loader.download_profile(username, profile_pic=False, posts=True)
#         print(f"Download complete. Posts saved in the current directory.")
#         return f"./{username}"  # Folder path of the downloaded content
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         return None

# Parse downloaded Instagram data
def parse_instagram_data(folder_path):
    posts_data = []
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.json') and file != "profile.json":
                with open(os.path.join(root, file), 'r') as json_file:
                    post_data = json.load(json_file)
                    image_path = os.path.join(root, file.replace(".json", ".jpg"))
                    if os.path.exists(image_path):
                        posts_data.append({
                            "caption": post_data.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", ""),
                            "image_path": image_path,
                        })
    return posts_data

# Upload to WordPress
def upload_to_wordpress(posts_data, wordpress_url, username, application_password):
    for post in posts_data:
        try:
            with open(post["image_path"], "rb") as image_file:
                # Upload media to WordPress
                media_response = requests.post(
                    f"{wordpress_url}/wp-json/wp/v2/media",
                    headers={"Authorization": f"Basic {username}:{application_password}"},
                    files={"file": image_file},
                )
                if media_response.status_code == 201:
                    media_id = media_response.json()["id"]
                    # Create WordPress post
                    post_data = {
                        "title": "Instagram Post",
                        "content": post["caption"],
                        "status": "publish",
                        "featured_media": media_id
                    }
                    post_response = requests.post(
                        f"{wordpress_url}/wp-json/wp/v2/posts",
                        headers={"Authorization": f"Basic {username}:{application_password}"},
                        json=post_data,
                    )
                    if post_response.status_code == 201:
                        print(f"Post uploaded: {post_response.json().get('link')}")
                    else:
                        # print(f"Failed to create post: {post_response.status_code} - {post_response.text}")
                        print(f"Failed to create post: {post_response.status_code}")
                else:
                    # print(f"Failed to upload media: {media_response.status_code} - {media_response.text}")
                    print(f"Failed to upload media: {media_response.status_code}")
        except Exception as e:
            print(f"An error occurred")
            # print(f"An error occurred: {e}")

# Main script
if __name__ == "__main__":
    # Step 1: Download Instagram posts
    # folder = download_instagram_posts(instagram_username)
    # download_new_posts(instagram_username, 5)
    new_posts_downloaded = 5
    if new_posts_downloaded > 0:
        # Step 2: Parse Instagram data
        posts = parse_instagram_data('./'+instagram_username)

        # Step 3: Upload to WordPress
        if posts:
            upload_to_wordpress(posts, wordpress_url, wp_username, wp_application_password)
        else:
            print("No posts found to upload.")
