#!/bin/zsh

rm -rf src/.env srv/.env bruno/.env
if [ -d "srv/storage" ]; then
    find srv/storage -type f ! -name '.gitignore' -delete
fi

