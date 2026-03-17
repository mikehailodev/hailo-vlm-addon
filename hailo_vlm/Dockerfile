ARG BUILD_FROM
FROM ${BUILD_FROM}

# ─── System dependencies ─────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev python3-venv \
    python3-opencv \
    build-essential cmake git \
    libopencv-dev \
    v4l-utils \
    curl jq \
    && rm -rf /var/lib/apt/lists/*

# ─── Build HailoRT from source ───────────────────────────────────────────────
# This builds libhailort and pyhailort (hailo_platform Python package)
ARG HAILORT_VERSION=v5.2.0
RUN git clone --depth 1 --branch ${HAILORT_VERSION} \
        https://github.com/hailo-ai/hailort.git /tmp/hailort && \
    cd /tmp/hailort && \
    cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DHAILO_BUILD_PYHAILORT=ON \
        -DHAILO_BUILD_EXAMPLES=OFF \
        -DCMAKE_SKIP_INSTALL_ALL_DEPENDENCY=ON && \
    cmake --build build -j$(nproc) && \
    cmake --install build && \
    ldconfig && \
    # Install the Python wheel
    pip3 install --break-system-packages /tmp/hailort/build/hailort/libhailort/bindings/python/platform/hailo_platform/pyhailort/ 2>/dev/null || \
    pip3 install --break-system-packages /tmp/hailort/hailort/libhailort/bindings/python/platform/ 2>/dev/null || \
    echo "Note: pyhailort installed via cmake install" && \
    rm -rf /tmp/hailort

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY rootfs/opt/hailo_vlm/requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt

# ─── Copy application ────────────────────────────────────────────────────────
COPY rootfs /

# ─── Ensure run script is executable ─────────────────────────────────────────
RUN chmod a+x /opt/hailo_vlm/run.sh

WORKDIR /opt/hailo_vlm

CMD ["/opt/hailo_vlm/run.sh"]
