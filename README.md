Grab Tumblr posts from whisky feed
Parse
Upload to Wordpress


Docker Stuff:

docker build -t instadram .

docker run --rm -it --env-file .env -v /home/jason/dev/instadram/data:/instadram/data -v /home/jason/dev/instadram/logs:/instadram/logs instadram
