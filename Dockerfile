
FROM ubuntu:16.04
ENV DEBIAN_FRONTEND noninteractive

# We need GITHUB_USER and GITHUB_TOKEN passed in as 
#   --build-arg GITHUB_USER=...
#   --build-arg GITHUB_TOKEN=...
# so that we can access github to post comments.
# User *MUST* provide this for posting to github to work.
ARG GITHUB_USER
ARG GITHUB_TOKEN
RUN echo "checking if gave GITHUB_USER build arg" && test -n "$GITHUB_USER"
RUN echo "checking if gave GITHUB_TOKEN build arg" && test -n "$GITHUB_TOKEN"

# Need to do an apt-get update early on or lots of things won't work.
RUN apt-get update

# Need a few things early on so install them first
RUN apt-get -y install software-properties-common wget iproute2

RUN add-apt-repository -y ppa:certbot/certbot

RUN apt-get update && \
    apt-get -y install curl python3 build-essential python3-pip && \
    apt-get -y install libffi-dev git screen apache2-utils && \
    apt-get -y install lynx nano openssh-server redis-server

# Setup the user to run ox_herd making sure to:
#   1. Make the primary group www-data so WSGI works if you later decide
#      to use it. This is helpful since if you "git pull" some new files, 
#      you want them to have group www-data so the WSGI web server can 
#      read them.
#   2. Setup profile properly
RUN useradd -ms /bin/bash ox_user && \
  usermod -g www-data ox_user && \
  usermod -a -G www-data ox_user && \
  echo "[pytest/DEFAULT]" > /home/ox_user/.ox_herd_conf && \
  echo "github_user = $GITHUB_USER >> /home/ox_user/.ox_herd_conf && \
  echo "github_token = $GITHUB_TOKEN >> /home/ox_user/.ox_herd_conf && \
  echo "export LC_ALL=C.UTF-8" >> /home/ox_user/.profile && \
  echo "export LANG=C.UTF-8" >> /home/ox_user/.profile && \
  echo "export PYTHONPATH=/home/ox_user/ox_server/ox_herd:/home/ox_user/ox_server/ox_herd/ox_herd" \
    >> /home/ox_user/.profile

WORKDIR /home/ox_user/ox_server
RUN git clone https://github.com/aocks/ox_herd

RUN pip3 install -r ./ox_herd/requirements.txt


# Setup home directory and pull in setup items.
RUN mkdir -p /home/ox_user/ox_server/logs


ADD ./scripts/server_start.sh /ox_server/

RUN chmod ugo+rx /ox_server/server_start.sh

RUN chown -R ox_user:www-data /home/ox_user


WORKDIR /ox_server
CMD /ox_server/server_start.sh