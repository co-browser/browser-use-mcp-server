FROM ghcr.io/astral-sh/uv:bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_PREFERENCE=only-managed

# Install build dependencies and clean up in the same layer
RUN apt-get update -y && \
    apt-get install --no-install-recommends -y clang git && \
    rm -rf /var/lib/apt/lists/*

# Install Python before the project for caching
RUN uv python install 3.13

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM debian:bookworm-slim AS runtime

# VNC password will be read from Docker secrets or fallback to default
# Create a fallback default password file
RUN mkdir -p /run/secrets && \
    echo "browser-use" > /run/secrets/vnc_password_default

# Install required packages including Chromium and clean up in the same layer
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    xfce4 \
    xfce4-terminal \
    dbus-x11 \
    tigervnc-standalone-server \
    tigervnc-tools \
    nodejs \
    npm \
    fonts-freefont-ttf \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-thai-tlwg \
    fonts-kacst \
    fonts-symbola \
    fonts-noto-color-emoji && \
    npm i -g proxy-login-automator && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/cache/apt/*

# Copy only necessary files from builder
COPY --from=builder /python /python
COPY --from=builder /app /app
# Set proper permissions
RUN chmod -R 755 /python /app

ENV PATH="/app/.venv/bin:$PATH" \
    DISPLAY=:0 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMIUM_FLAGS="--no-sandbox --headless --disable-gpu --disable-software-rasterizer --disable-dev-shm-usage"

# Combine VNC setup commands to reduce layers
RUN mkdir -p ~/.vnc && \
    printf '#!/bin/sh\nunset SESSION_MANAGER\nunset DBUS_SESSION_BUS_ADDRESS\nstartxfce4' > /root/.vnc/xstartup && \
    chmod +x /root/.vnc/xstartup && \
    printf '#!/bin/bash\n\n# Use Docker secret for VNC password if available, else fallback to default\nif [ -f "/run/secrets/vnc_password" ]; then\n  cat /run/secrets/vnc_password | vncpasswd -f > /root/.vnc/passwd\nelse\n  cat /run/secrets/vnc_password_default | vncpasswd -f > /root/.vnc/passwd\nfi\n\nchmod 600 /root/.vnc/passwd\nvncserver -depth 24 -geometry 1920x1080 -localhost no -PasswordFile /root/.vnc/passwd :0\nproxy-login-automator\npython /app/server --port 8000' > /app/boot.sh && \
    chmod +x /app/boot.sh

RUN playwright install --with-deps --no-shell chromium

EXPOSE 8000

ENTRYPOINT ["/bin/bash", "/app/boot.sh"]
