#!/bin/bash

# This script sets up the environment, starts the temporal server, and runs the CLI
# It's designed to be run from the root of the project

echo "Welcome to Arjun's Temporal Workflow Demo! Let's get you set up..."

echo "1️⃣ Setting up the environment. Hang tight..."
python3 -m venv venv

source venv/bin/activate

pip3 install -r requirements.txt

echo "2️⃣ Starting the environment..."
docker compose down 2>/dev/null
docker compose -f docker-compose-2.yml up -d

echo "3️⃣ Booting up the temporal server..."
sleep 7

echo "4️⃣ Temporal is ready. Running CLI..."
python3 cli.py