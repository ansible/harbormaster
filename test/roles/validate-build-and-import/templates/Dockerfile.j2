FROM {{ distro.base_image }}

# Uses shell module - should be two tasks
RUN {{ distro.template.package_update_command }} && \
    {{ distro.template.httpd_install_command }} && \
    mkdir -p {{ distro.template.httpd_logdir }} && \
    chown -R {{ distro.template.httpd_user }} {{ distro.template.httpd_logdir }} && \
    mkdir -p {{ distro.template.httpd_rundir }} && \
    chown -R {{ distro.template.httpd_user }} {{ distro.template.httpd_rundir }}

# Install dumb-init from URL - get_url module
ADD https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64 /usr/sbin/dumb-init

# Install httpd.conf - copy module
ADD {{ distro.template.httpd_conf_src }} {{ distro.template.httpd_conf_dest }}

# Install heartbeat page - unarchive module
ADD html.tar.gz {{ distro.template.httpd_pageroot }}

# Install chaff - synchronize module
COPY foo /

# Uses command module
RUN ["chmod", "755", "/usr/sbin/dumb-init"]

# I am defaults
ARG apache_port=8000
ARG apache_pid_file={{ distro.template.httpd_pid_file }}
ARG apache_run_user={{ distro.template.httpd_user }}
ARG apache_run_group={{ distro.template.httpd_run_group }}
ARG apache_log_dir={{ distro.template.httpd_logdir }}
ARG apache_lock_dir={{ distro.template.httpd_lock_dir }}
ENV APACHE_PORT=${apache_port}
ENV APACHE_PID_FILE=${apache_pid_file}
ENV APACHE_RUN_USER=${apache_run_user}
ENV APACHE_RUN_GROUP=${apache_run_group}
ENV APACHE_RUN_DIR={{ distro.template.httpd_rundir }}
ENV APACHE_LOG_DIR=${apache_log_dir}
ENV APACHE_LOCK_DIR=${apache_lock_dir}

# Single label
LABEL a=1
# Multiple labels
LABEL b=2 c=3
# Quoted keys and values
LABEL "the bird"="the word"
# Multi-line
LABEL foo=bar \
      baz=buzz

# I am metadata
CMD ["{{ distro.template.httpd_bin }}", "-DFOREGROUND"]
ENTRYPOINT ["/usr/sbin/dumb-init"]
EXPOSE $apache_port
USER {{ distro.template.httpd_user }}
VOLUME ["/vol"]
WORKDIR /tmp
SHELL ["/bin/sh", "-c"]

# Should be run using shell module as {{ distro.template.httpd_user }} in /tmp explicitly using /bin/sh -c
# RUN /bin/true

