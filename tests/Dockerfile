# NOTE: run from parent directory to copy requirements

FROM ubuntu:20.04
 
ENV DEBIAN_FRONTEND noninteractive
 
# Install dependencies.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
   make \
   build-essential \
   libssl-dev \
   zlib1g-dev \
   libbz2-dev \
   libreadline-dev \
   libsqlite3-dev \
   wget \
   curl \
   llvm \
   libncurses5-dev \
   xz-utils \
   tk-dev \
   libxml2-dev \
   libxmlsec1-dev \
   git \
   ca-certificates \
   libffi-dev \
   liblzma-dev \
 && apt-get clean autoclean \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /var/cache/apt/archives/*.deb
 
# Install ``pyenv``.
RUN git clone https://github.com/pyenv/pyenv /root/.pyenv

# Add in all requirements
RUN mkdir /root/requirements
COPY ./requirements* /root/requirements/
 
# Install the desired versions of Python.
RUN for PYTHON_VERSION in 3.5.10 3.6.15 3.7.16 3.8.16 3.9.16 3.10.9 3.11.1; do \
 set -ex \
   && /root/.pyenv/bin/pyenv install ${PYTHON_VERSION} \ 
   && /root/.pyenv/versions/${PYTHON_VERSION}/bin/python -m pip install --upgrade pip \
   && for req_file in /root/requirements/*; do /root/.pyenv/versions/${PYTHON_VERSION}/bin/python -m pip install -r $req_file; done \
 ; done
