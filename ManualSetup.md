## 🚀 Manual Setup

Instructions on starting the environment without launching directly into the CLI

```bash
# 1. Clone the repo
git clone https://github.com/20arjuna/TemporalWorkflow.git

# 2. Navigate to the root directory
cd TemporalWorkflow

# 3. Create Virtual Environment
python3 -m venv .venv

# 4. Activate Virtual Environment
source .venv/bin/activate

# 5. Install Requirements
pip3 install -r requirements.txt

# 6. Start all services
docker compose down
docker compose -f docker-compose.yml up -d --build
```

> Note**: `docker compose` automatically starts your database, Temporal server, and workers - everything you need is running in containers!
