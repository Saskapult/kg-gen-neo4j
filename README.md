# Kg-gen Neo4j Uploader 
Generates a knowledge graph with kg-gen and uploads it to a neo4j database. 

Steps for usage:
- Place scraped json files in the `scraped_data` directory
- Sync uv dependencies with `uv sync`
- Start neo4j using `cd neo4j && docker compose up -d && cd ..`
- Set the OpenAI api key environment variable with `export OPENAI_API_KEY=<your key here>`
- Run the upload script with `uv run generate_upload_kg.py`
