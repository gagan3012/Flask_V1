ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-slim AS compiler

ENV PYTHONUNBUFFERED=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

# Create and enable venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only necessary files first to cache layer better
COPY pyproject.toml README.md ./

# Install pip and poetry support (if needed)
RUN pip install --upgrade pip setuptools

# Install project (as defined in pyproject.toml)
RUN pip install .

# Now copy the full source code
COPY . /app/

### --- Final production image ---
FROM python:${PYTHON_VERSION}-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/
COPY --from=compiler /opt/venv /opt/venv

# Enable virtualenv
ENV PATH="/opt/venv/bin:$PATH"

# Copy app files (optional if already copied during compile)
COPY . /app/

CMD ["bash", "run_with_healthcheck.sh"]
