ARG BUILD_FROM
FROM ${BUILD_FROM}

# ─── System dependencies ─────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev \
    python3-opencv \
    libopencv-dev \
    v4l-utils \
    jq \
    && rm -rf /var/lib/apt/lists/*

# ─── Install HailoRT from pre-built packages ─────────────────────────────────
# The .deb installs libhailort, hailortcli, and udev rules.
# The .whl installs the hailo_platform Python bindings.
COPY packages/ /tmp/packages/
RUN dpkg -i /tmp/packages/h10-hailort_5.2.0_arm64.deb || \
    apt-get update && apt-get install -f -y && \
    dpkg -i /tmp/packages/h10-hailort_5.2.0_arm64.deb && \
    ldconfig
RUN pip3 install --break-system-packages --no-cache-dir \
    /tmp/packages/hailort-5.2.0-cp311-cp311-linux_aarch64.whl && \
    rm -rf /tmp/packages

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY rootfs/opt/hailo_vlm/requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt

# ─── Copy application ────────────────────────────────────────────────────────
COPY rootfs /

# ─── Ensure run script is executable ─────────────────────────────────────────
RUN chmod a+x /opt/hailo_vlm/run.sh

WORKDIR /opt/hailo_vlm

CMD ["/opt/hailo_vlm/run.sh"]
