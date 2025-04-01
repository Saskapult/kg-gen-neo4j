from neo4j import GraphDatabase
from kg_gen import KGGen, Graph
import json 
import os
from pprint import pprint

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


def path_based_subgraph(eg, driver):
	gpathq = []
	segment = []
	e1 = eg[0]
	candidates = eg[1:]
	while len(candidates) != 0:
		print(f"e1: '{e1}'")
		print(f"candidates: {candidates}")

		neighbours, summary, _ = driver.execute_query("""
			MATCH p = ALL SHORTEST (e1:Entity {id: $e1})-[r]-{1,2}(neighbours:Entity)
			RETURN neighbours.id AS id, [e in r | TYPE(e)] AS edges, [n in nodes(p) | n.id] AS nodes
			ORDER BY length(p)
			""",
			e1=e1,
		)
		for e2, edges, nodes in neighbours:
			# if e2 != e1:
			# 	print(e2, edges, nodes)
			if e2 != e1 and e2 in candidates:
				print(f"path to '{e2}'")

				# Interleave lists
				for n, e in zip(nodes, edges):
					segment.append(n)
					segment.append(e)
				segment.append(nodes[len(nodes)-1])

				print(" -> ".join(segment))

				e1 = e2
				candidates.remove(e2)
				break

		# Not found in k hops
		if len(candidates) != 0:
			print("New segment")
			gpathq.append(segment)
			e1 = candidates[0]
			candidates = candidates[1:]
	gpathq.append(segment)

	print("Path-based sub-graph:")
	for path in gpathq:
		print(" -> ".join(path))
	
	return gpathq


def neighbour_based_subgraph(query, eg, driver):
	gneiq = []
	for e in eg:
		print(f"neighbours of {e}")
		e_neighbours, summary, _ = driver.execute_query("""
			MATCH (e:Entity {id: $e})-[r]->{1}(neighbours:Entity)
			RETURN DISTINCT neighbours.id AS id, [e in r | TYPE(e)] AS edge
			""",
			e=e,
		)
		print(e_neighbours)

		for ep, rel in e_neighbours:
			# The relationship is returned as a list, but it only has one element
			gneiq.append([e, rel[0], ep])
			# How semantic relevance? 
			# if is_relevant(ep):
			# 	ep_neighbours = """
			# 	MATCH (ep:Entity {id: ep})--{1}(neighbours:Entity)
			# 	RETURN DISTINCT neighbours.id AS id
			# 	"""
			# 	for e_nei in ep_neighbours:
			# 		gneiq.append((e_nei, "", ep))
	
	print("Neighbour-based sub-graph:")
	for path in gneiq:
		print(" -> ".join(path))
	
	return gneiq


def dalk_query(query, kg, driver):
	q = query
	print(f"query: '{q}'")
	# qg = kg.generate(
	# 	input_data=q,
	# )
	# e = list(qg.entities)
	e = ['partners', 'FEMA']
	# print(f"entities: {e}")

	# Compute he
	# he = [st_model.encode(entity) for entity in e]
	# Find links with similarity to hg
	# Find of like this but you extract the one with the highest similarity
	# eg = st_model.similairties(he, hg)
	# We don't actually need to do that I think
	eg = e 

	gpathq = path_based_subgraph(eg, driver)
	gneiq = neighbour_based_subgraph(query, eg, driver)

	# Filtering examples in appendix B and C 			



	# Similarity base to connect with g 
	# Semantic sim to get dense embeddings 
	# Cosine sim 

	# Path-based 



def main():
	kg = KGGen(
		model=kg_gen_model,
		api_key=os.getenv("KG_GEN_API_KEY", ""),
	)
	with GraphDatabase.driver(db_url, auth=(db_user, db_pass)) as driver:
		driver.verify_connectivity()
		dalk_query("What partners does FEMA have?", kg, driver)
	# import_graph("cached_graph.json")




if __name__ == "__main__":
	main()
