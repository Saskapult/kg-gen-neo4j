#!/usr/bin/env python3

import sys
import os
from kg_gen import KGGen, Graph
import json 
# from neo4j import GraphDatabase
from post4j import GraphDatabase


# 
# Reads scraped pregnancy data
# Generates a knowledge graph using kg-gen 
#  - Caches graph results in a JSON file for testing 
# Uploads the knowledge graph to a neo4j database
# 
# Set the OPENAI_API_KEY environment variable to generate the graph 
# 


# Neo4j information
neo4j_url = os.getenv("DB_HOST", "localhost:5432")
neo4j_user = os.getenv("DB_USER", "postgres")
neo4j_base = os.getenv("DB_DATABASE", "db")
# neo4j_url = os.getenv("DB_HOST", "neo4j://localhost:7687")
# neo4j_user = os.getenv("DB_USER", "neo4j")
neo4j_pass = os.getenv("DB_PASSWORD", "no_password")
# neo4j_base = os.getenv("DB_DATABASE", "neo4j")

# openai/o1-mini gives weird errors that I do not know how to solve
# It might be okay to run this once 
kg_gen_model = "openai/gpt-4o-mini"
# This will only let it sample the first document, which will reduce testing costs
only_sample_first_document = True
# Cache kg-gen graph results to further save testing costs 
graph_cache_file = "cached_graph.json"
data_dir = "./scraped_data"


def generate_graph():
	kg = KGGen(
		model=kg_gen_model,
		api_key=os.getenv("OPENAI_API_KEY"),
	)

	data_files = os.listdir(data_dir)
	graphs = []
	for i, f in enumerate(data_files):
		print(f"Reading {i+1}/{len(data_files)} '{f}'")
		with open(data_dir + "/" + f, "r") as file:
			datas = json.load(file)
			print(f"\tcontains {len(datas)} entries")
			for j, entry in enumerate(datas):
				print(f"\t\tGraph {j+1}/{len(datas)}")
				graph = kg.generate(
					input_data=entry["html"],
					context="pregnancy information",
				)
				graphs.append(graph)

				if only_sample_first_document:
					print("WARN: Stopping kg-gen early to reduce api costs")
					return graph
	
	print("Aggregate...")
	graph = kg.aggregate(graphs)
	print("Finished data insertion")
	return graph


# The driver seems pretty good so this might not take too long to run
def write_graph_to_neo(graph):
	print("Connecting to neo4j...")
	with GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_pass)) as driver:
		driver.verify_connectivity()
		print("Connected!")

		for i, entity in enumerate(graph.entities):
			print(f"Write entity {i+1}/{len(graph.entities)}")
			driver.execute_query(
				"CREATE (:Entity {id: $id})",
				id=entity,
				database_=neo4j_base,
			)
		
		# I am unsure of how to encode the relation names into the edges
		# The driver will not allow reationships to be passed as parameters 
		# When I add them manually I need to get around the spaces 
		# For now I will just replace the sapces with underscores
		for i, (a, r, b) in enumerate(graph.relations):
			print(f"Write relation {i+1}/{len(graph.relations)} ({a} ~ {r} ~ {b})")
			# summary = driver.execute_query(
			# 	"MATCH (a:Entity {id: $id_a})" +
			# 	"MATCH (b:Entity {id: $id_b})" + 
			# 	"CREATE (a)-[:GRAPH_EDGE {description: $relation}]->(b)",
			# 	id_a=a,
			# 	id_b=b,
			# 	relation=r,
			# 	database_="neo4j",
			# ).summary
			summary = driver.execute_query(
				"MATCH (a:Entity {id: $id_a})" +
				"MATCH (b:Entity {id: $id_b})" + 
				f"CREATE (a)-[:{r.replace(" ", "_")}]->(b)",
				id_a=a,
				id_b=b,
				relation=r,
				database_=neo4j_base,
			).summary
			# assert summary.counters["relationships_created"] == 1 


# A basic test to discern that the data is there
# It could verify more than this but that'd take longer and I trust myself a little 
def verify_neo_contents(graph):
	with GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_pass)) as driver:
		driver.verify_connectivity()

		# Test that there is an entry for one of the graph entities 
		records, summary, keys = driver.execute_query(
			"MATCH (e:Entity {id: $id}) RETURN e.id AS id",
			id=list(graph.entities)[0],
			database_=neo4j_base,
		)
		print(f"{len(records)} records")
		assert len(records) >= 1
		print(records[0].data()) #list obj attr -> val
		print(summary) # obj
		print(keys) # id


def main():
	# Retrieve or generate and cache the graph
	if (not os.path.isfile(graph_cache_file)) or input("Re-generate cached graph? [y/N] ") == "y":
		graph = generate_graph()
		
		with open(graph_cache_file, "w") as f:
			data = {
				"entities": list(graph.entities),
				"edges": list(graph.edges),
				"relations": list(graph.relations),
			}
			print(data)
			json.dump(data, f, indent=2)
	graph = None
	with open(graph_cache_file, "r") as file:
		data = json.load(file)
		graph = Graph(
			entities = data["entities"],
			relations = data["relations"],
			edges = data["edges"],
		)
	
	if input("Write to neo4j database? [y/N] ") == "y":
		write_graph_to_neo(graph)

	print("Verifying database contents...")
	verify_neo_contents(graph)
	print("Done!")


if __name__ == "__main__":
	main()
