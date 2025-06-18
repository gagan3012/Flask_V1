ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-slim AS compiler
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

# create and enable venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# add actual app
#nowaday packages could be in requirements.txt, setup.py or pyproject.toml. just copy all of it, including local packages
COPY . /app/

# populate venv
RUN pip install -U .

### start the production image
FROM python:${PYTHON_VERSION}-slim AS runner

# dependencies i.e. of run_with_healthcheck.sh
RUN apt-get update && apt-get install -y --no-install-recommends curl bash && rm -rf /var/lib/apt/lists/*

WORKDIR /app/
COPY --from=compiler /opt/venv /opt/venv

# Enable venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . /app/


CMD ["python", "main.py"]
