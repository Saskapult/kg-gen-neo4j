
# Postgres on 6432
# postgres
# db
# pass
cd postgres
docker compose up -d
cd ..

cd fastapi-neo4j-api
source /home/kieran/uvenv/bin/activate
uv pip install psycopg2-binary "fastapi[standard]" pydantic
python3 app.py
cd ..

python3 generate_upload_kg.py
