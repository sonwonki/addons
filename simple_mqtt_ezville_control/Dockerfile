FROM python:3.8-slim-buster
  
ENV LANG C.UTF-8
ENV TZ=Asia/Seoul

# Install requirements for add-on
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir paho-mqtt
#RUN pip install --no-cache-dir telnetlib

# Copy data for add-on
COPY run.sh /
COPY ezville.py /

WORKDIR /share

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
