#!/bin/zsh

rm -rf frontend/.env backend/.env bruno/.env
if [ -d "backend/storage" ]; then
    find backend/storage -type f ! -name '.gitignore' -delete
fi

