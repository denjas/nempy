FROM python:3.9.5
ARG NOT_ROOT_USER=nempy
ARG PACKAGE=nempy

ENV PATH="/home/${NOT_ROOT_USER}/.local/bin:${PATH}"

RUN set -xe \
    && apt-get update \
    && apt-get install python3-pip -y

# create not root user
RUN useradd -ms /bin/bash ${NOT_ROOT_USER}
USER ${NOT_ROOT_USER}
WORKDIR /home/${NOT_ROOT_USER}

# update/install pip and pipenv
RUN pip install --user pip==21.1.2 pipenv==2021.5.29
RUN pip --version

# copy the package to the container
RUN mkdir ${PACKAGE}
COPY --chown=${NOT_ROOT_USER}:${NOT_ROOT_USER} . ${PACKAGE}
WORKDIR ${PACKAGE}
#  install requirements
RUN set -ex && pipenv install --deploy --system --dev
#  install package
RUN pip install --use-feature=in-tree-build --no-dependencies .


ENTRYPOINT ["nempy-cli.py"]
