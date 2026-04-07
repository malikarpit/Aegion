#!/bin/bash
# Scripts to prune stale sandbox containers

echo "Starting sandbox cleanup..."

# Prune containers with specific label
if docker container prune --force --filter "label=aegion.sandbox=true" --filter "until=1h"; then
    echo "Successfully pruned stale sandbox containers."
else
    echo "Failed to prune containers (or no docker daemon available)."
    # Don't fail the script if docker is missing (dev env)
fi

# Also clean up tmp volumes if we used named volumes (we use tmpfs, so this is handled by container removal)
echo "Cleanup complete."
