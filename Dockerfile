FROM python:3-alpine

RUN mkdir /instadram
RUN mkdir /instadram/app

WORKDIR /instadram

ADD main.py /instadram/app/
ADD requirements.txt /instadram/

RUN pip install -r requirements.txt

CMD ["python", "app/main.py"]

# docker build -t instadram_img .
# docker run --rm -it --env-file .env -v /mnt/user/maindrv/dev/instadram-data/data:/instadram/data -v /mnt/user/maindrv/dev/instadram-data/bstandingwhisky:/instadram/bstandingwhisky -v /mnt/user/maindrv/dev/logs-data/data:/instadram/logs instadram_img
# docker run --rm -it --env-file .env -v /home/jason/dev/instadram/data:/instadram/data -v /home/jason/dev/instadram/bstandingwhisky:/instadram/bstandingwhisky -v /home/jason/dev/instadram/logs:/instadram/logs instadram_img


