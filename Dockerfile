FROM fedora

MAINTAINER Christoph Görn <goern@redhat.com>

RUN dnf install --setopt=tsflags=nodocs -y gcc redhat-rpm-config git python python-devel libffi-devel openssl-devel ansible && \
    git clone https://github.com/goern/ansible-container && \
    cd ansible-container && \
    pip install -r requirements.txt && \
    python ./setup.py install && \
    dnf remove -y  gcc redhat-rpm-config  python-devel libffi-devel openssl-devel

VOLUME ["/work"]

WORKDIR "/work"

ENTRYPOINT ["ansible-container"]
CMD ["help"]
