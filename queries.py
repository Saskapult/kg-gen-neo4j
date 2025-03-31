from neo4j import GraphDatabase
from kg_gen import KGGen, Graph
import json 
import os

db_url = os.getenv("DB_HOST", "neo4j://localhost:7687")
db_user = os.getenv("DB_USER", "neo4j")
db_pass = os.getenv("DB_PASSWORD", "no_password")
db_base = os.getenv("DB_DATABASE", "neo4j")

kg_gen_model = os.getenv("KG_GEN_MODEL", "openai/gpt-4o-mini")


# Imports a graph into the database
def import_graph(graph_path):
	graph = None
	with open(graph_path, "r") as f:
		data = json.load(f)
		graph = Graph(
			entities = data["entities"],
			relations = data["relations"],
			edges = data["edges"],
		)
	
	# Precompute embeddings for each entity in G
	# hg = [st_model.encode(entity) for entity in graph.entities]

	with GraphDatabase.driver(db_url, auth=(db_user, db_pass)) as driver:
		driver.verify_connectivity()
		print("Connected to database")

		print("Clear database")
		driver.execute_query("MATCH (n) DETACH DELETE n")

		for i, entity in enumerate(graph.entities):
			print(f"Write entity {i+1}/{len(graph.entities)}")
			driver.execute_query(
				"CREATE (:Entity {id: $id})",
				id=entity,
				database_=db_base,
			)
	
		# I am unsure of how to encode the relation names into the edges
		# The driver will not allow reationships to be passed as parameters 
		# When I add them manually I need to get around the spaces 
		# For now I will just replace the sapces with underscores
		for i, (a, r, b) in enumerate(graph.relations):
			print(f"Write relation {i+1}/{len(graph.relations)} ({a} ~ {r} ~ {b})")
			driver.execute_query(
				"MATCH (a:Entity {id: $id_a})" +
				"MATCH (b:Entity {id: $id_b})" + 
				f"CREATE (a)-[:{r.replace(" ", "_")}]->(b)",
				id_a=a,
				id_b=b,
				relation=r,
				database_=db_base,
			)
	
	print("Graph imported!")


def dalk_query(query):
	# Coarse-grained Knowledge Sample
	q = query
	kg = KGGen(
		model=kg_gen_model,
		api_key=os.getenv("OPENAI_API_KEY", ""),
	)
	qg = kg.generate(
		input_data=q,
	)
	e = qg.entities

	# Compute he
	# he = [st_model.encode(entity) for entity in e]
	# Find links with similarity to hg
	# Find of like this but you extract the one with the highest similarity
	# eg = st_model.similairties(he, hg)
	# We don't actually need to do that I think
	eg = e 

	gpathq = []
	segment = []
	e1 = eg[0]
	candidates = eg[1:]
	while len(candidates) != 0:
		neighbours = """
		MATCH p = ALL SHORTEST (e1:Entity {id: "FEMA"})-[r]-{1,2}(neighbours:Entity)
		RETURN neighbours.id AS id, [e in r | TYPE(e)] AS edges, [n in nodes(p) | n.id] AS nodes
		"""
		for e2 in candidates:
			if e2 in neighbours:
				segment.append((e1, "", e2))
				e1 = e2
				candidates.remove(e2)
				break
		# Not found in k hops
		gpathq.append(segment)
		e1 = candidates[0]
		candidates = candidates[1:]
	gpathq.append(segment) # might result in an added empty list to gpathq

	gneiq = []
	for e in eg:
		e_neighbours = """
		MATCH (e:Entity {id: e})--{1}(neighbours:Entity)
		RETURN DISTINCT neighbours.id AS id
		"""
		for ep in e_neighbours:
			gneiq.append((e, "", ep))
			if is_relevant(ep):
				ep_neighbours = """
				MATCH (ep:Entity {id: ep})--{1}(neighbours:Entity)
				RETURN DISTINCT neighbours.id AS id
				"""
				for e_nei in ep_neighbours:
					gneiq.append((e_nei, "", ep))
	
	# Filtering examples in appendix B and C 			



	# Similarity base to connect with g 
	# Semantic sim to get dense embeddings 
	# Cosine sim 

	# Path-based 



def main():
	import_graph("cached_graph.json")




if __name__ == "__main__":
	main()
