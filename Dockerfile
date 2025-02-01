FROM python:3-alpine

RUN pip install --upgrade pip
RUN mkdir /instadram
RUN mkdir /instadram/app

WORKDIR /instadram

ADD main.py /instadram/app/
ADD requirements.txt /instadram/

RUN pip install -r requirements.txt

CMD ["python", "app/main.py"]
