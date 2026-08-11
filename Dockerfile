# Carcassonne cloud-bootstrap image.
#
# Bakes torch + all non-torch requirements into the image so that fresh
# vast.ai rentals don't have to re-download ~5 GB of PyTorch wheels on
# every bootstrap. Code + checkpoints are still pulled fresh from git/GH
# releases at run time (so we can pick branches and recipe variants).
#
# Built and pushed via .github/workflows/build-cloud-image.yml on every
# push to gpu-orchestrator (and on manual workflow_dispatch).
#
# Usage on vast.ai:
#   --image dentaljosh/carcassone-cloud:latest
# Then SSH in and run:
#   git clone --depth 1 --branch <branch> https://github.com/dentaljosh/carcassone.git /workspace/carcassone
#   bash /workspace/carcassone/scripts/bootstrap_cloud.sh
# (bootstrap_cloud.sh will skip the torch upgrade step automatically because
# torch is already at the right version in this image.)

# Base: NVIDIA's official torch image with Blackwell sm_120 support.
# 25.01-py3 (Jan 2025) ships torch 2.6+ with cu128. If a newer pytorch/pytorch
# tag with explicit sm_120 surfaces (e.g. 2.7.0-cuda12.8-cudnn9-runtime), we
# can swap to it — both work.
FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime

# Sanity: confirm torch is what we expect at build time (build fails loudly
# if the base image silently changed).
RUN python -c "import torch; v = torch.__version__.split('+')[0]; major, minor = int(v.split('.')[0]), int(v.split('.')[1]); assert (major, minor) >= (2, 7), f'torch {v} too old for sm_120 Blackwell support'; print(f'base torch={torch.__version__} OK')"

# Install non-torch deps. Drop the torch line from requirements.txt since
# it's already in the base image at a known-good version.
COPY requirements.txt /tmp/requirements.txt
RUN grep -v "^torch" /tmp/requirements.txt > /tmp/reqs.txt \
    && pip install --timeout 300 -r /tmp/reqs.txt \
    && rm /tmp/requirements.txt /tmp/reqs.txt

# vast.ai's ssh proxy connects to port 22 INSIDE the container — but the
# pytorch base image has no sshd. Without openssh-server, every connection
# fails "Permission denied (publickey)" because no sshd answers. Install it
# here so vast.ai's onstart can write authorized_keys + start sshd and we
# can SSH in. (Discovered 2026-05-12 the hard way.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-server \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/sshd

# Convenience: pre-create workspace dir so the bootstrap script's git clone
# target exists without a mkdir step.
RUN mkdir -p /workspace

# Don't bake in code or checkpoints — those come from git clone + gh release
# download at run time so we can vary branch/recipe per rental.

WORKDIR /workspace
CMD ["/bin/bash"]
