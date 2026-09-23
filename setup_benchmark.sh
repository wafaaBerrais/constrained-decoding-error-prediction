#!/usr/bin/env bash
# Fetch the JSONSchemaBench / MaskBench data this project was built on.
#
# The benchmark itself is NOT part of this repository: it belongs to its authors
# (https://github.com/guidance-ai/jsonschemabench, paper: arXiv:2501.10868).
# This script downloads it next to `extension_jsonschemabench/`, which is where
# the scripts expect it (`<repo>/data` and `<repo>/maskbench`).
set -euo pipefail

UPSTREAM_URL="https://github.com/guidance-ai/jsonschemabench.git"
# Commit used during the internship (code identical to the version we ran).
UPSTREAM_COMMIT="ba103c73"

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Cloning $UPSTREAM_URL ..."
git clone --quiet "$UPSTREAM_URL" "$TMP_DIR/jsonschemabench"
git -C "$TMP_DIR/jsonschemabench" checkout --quiet "$UPSTREAM_COMMIT"

for dir in data maskbench; do
  if [ -e "$REPO_ROOT/$dir" ]; then
    echo "$dir/ already exists, skipping."
  else
    cp -r "$TMP_DIR/jsonschemabench/$dir" "$REPO_ROOT/$dir"
    echo "Copied $dir/"
  fi
done

# Small fix used during the internship: load the Outlines vocabulary from the
# local Hugging Face cache when `Vocabulary.from_pretrained` fails (offline server).
if git -C "$REPO_ROOT" apply --ignore-whitespace --check patches/outlines_engine_offline_vocabulary.patch 2>/dev/null; then
  git -C "$REPO_ROOT" apply --ignore-whitespace patches/outlines_engine_offline_vocabulary.patch
  echo "Applied patches/outlines_engine_offline_vocabulary.patch"
else
  echo "Outlines patch already applied or not applicable, skipping."
fi

echo "Done. Benchmark data is in data/ and maskbench/ (both git-ignored)."
