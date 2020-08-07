FROM python:3.7

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get \
      update \
  && apt-get \
      install -y --no-install-recommends \
        python3.7-dev \
        libffi-dev \
        libssl-dev \
        psmisc \
        bash \
  && pip3.7 \
      install --no-cache-dir -q -U \
        pip \
        setuptools \
        wheel \
        pytest \
  && apt-get \
      clean -y \
  && rm -rf /var/lib/apt/lists/*
  
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
    
        
  
