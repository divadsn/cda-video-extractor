FROM python:3.7-slim
LABEL maintainer="David Sn <divad.nnamtdeis@gmail.com>"
ADD . /app
RUN pip install -r /app/requirements.txt
ENTRYPOINT [ "python", "/app/server.py" ]
