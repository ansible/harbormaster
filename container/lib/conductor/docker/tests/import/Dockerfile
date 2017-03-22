# This Dockerfile is to test importing from a Dockerfile
FROM centos:7

# Test straight string form
RUN yum -y update
# Test JSON array form
RUN ["yum", "-y", "install", "epel-release"]
# Test multiline run
RUN yum -y install redis; \
    yum -y install httpd

# Test CMD
CMD ['/usr/bin/redis-server', '/etc/redis.conf', '--daemonize no']

# Test LABEL
LABEL war=peace "freedom"="slavery" \
      ignorance="strength or something"

MAINTAINER me

EXPOSE 6379

ARG intelligence=brilliant
ARG quality=noble

ENV yourmom accomplished
# Test variable substitution
ENV yoursister="${intelligence}" yourdad="$noble" \
    yourdog="${dog_name:-Spot}"

# Switch user to redis
USER redis
# Change directory
WORKDIR /var/lib/redis

# This file should be owned by the redis user and its home dir
RUN touch whoami.txt

# Test ADD with a tarball
ADD lulz.tgz /ohai
# Test ADD with a URL
ADD https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64 /usr/bin/dumb-init
# Test ADD with files and directories
ADD one-fish.txt two-fish/ red-fish blue-fish.txt /etc/

# Use dumb-init
ENTRYPOINT ["/usr/bin/dumb-init"]

VOLUME ["/var/lib/redis"]

