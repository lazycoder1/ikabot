FROM python:3
WORKDIR /ikabot
COPY . .
RUN python3 -m pip install --user -e . && apt-get update && apt-get install -y dnsutils
CMD "python3" "-m" "ikabot"
