from post4j import GraphDatabase
from kg_gen import KGGen, Graph
import json 
import os
from litellm import completion
import argparse

db_url = os.getenv("DB_HOST", "neo4j://localhost:7687")
db_user = os.getenv("DB_USER", "neo4j")
db_pass = os.getenv("DB_PASSWORD", "no_password")
db_base = os.getenv("DB_DATABASE", "neo4j")

kg_gen_model = os.getenv("KG_GEN_MODEL", "openai/gpt-4o-mini")
rag_model = os.getenv("RAG_MODEL", "openai/gpt-4o-mini")


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
		driver.execute_query(
			"MATCH (n) DETACH DELETE n",
			database_=db_base,
		)

		for i, entity in enumerate(graph.entities):
			print(f"Write entity {i+1}/{len(graph.entities)}")
			driver.execute_query(
				"CREATE (:Entity {id: $id})",
				id=entity,
				database_=db_base,
			)
	
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
			database_=db_base,
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
			database_=db_base,
		)
		print(e_neighbours)

		for ep, rel in e_neighbours:
			# The relationship is returned as a list, but it only has one element
			gneiq.append([e, rel[0], ep])
			# How semantic relevance? 
			# It seem to be based on the application, see MindMap_revised.py line 638
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


def path_evidence(q, gpathq, k, completion_fn):
	gq_str = "\n".join(["->".join(v) for v in gpathq])
	# Table 15
	pself = f"""
		There is a question and some knowledge graph. The knowledge graphs follow entity->relationship->entity list format.
		Graph: 
		{gq_str}

		Question:
		{q}

		Please rerank the knowledge graph and output at most {k} important and relevant triples for solving the given question. Output the reranked knowledge in the following format:
		{"\n".join([f"Reranked Triple{i+1}: xxx ——>xxx" for i in range(0, k)])}

		Answer:
	""".replace("\t", "")

	print("pself:")
	print(pself)
	print()

	gselfq = completion_fn(pself).choices[0].message.content

	# Table 16
	pinference = f"""
		There are some knowledge graph paths. They follow entity->relationship->entity format.

		{gselfq}

		Use the knowledge graph information. Try to convert them to natural language, respectively.
		Use single quotation marks for entity name and relation name.
		And name them as Path-based Evidence 1, Path-based Evidence 2,...

		Output:
	""".replace("\t", "")

	print("pinference:")
	print(pinference)
	print()

	# This is gathered to be the output because it is used in table 17
	a = completion_fn(pinference).choices[0].message.content

	print("a:")
	print(a)
	print()

	return a


def dalk_query(query, kg, driver, completion_fn):
	q = query
	print(f"query: '{q}'")
	qg = kg.generate(
		input_data=q,
	)
	e = list(qg.entities)
	print(f"entities: {e}")

	# Compute he
	# he = [st_model.encode(entity) for entity in e]
	# Find links with similarity to hg
	# Find of like this but you extract the one with the highest similarity
	# eg = st_model.similairties(he, hg)
	# We don't actually need to do that I think
	eg = e 

	gpathq = path_based_subgraph(eg, driver)
	gneiq = neighbour_based_subgraph(query, eg, driver)
	
	pathstuff = path_evidence(query, gpathq, 5, completion_fn)
	# Not described in the paper?
	# MindMap_revised.py uses different prompts than the paper too 
	neighbourstuff = None 

	panswer = f"""
		Question: {q}

		You have some medical knowledge information in the following:
		###{pathstuff}
		###{neighbourstuff}

		Answer: Let's think step by step:
	""".replace("\t", "")

	print("panswer:")
	print(panswer)
	print()

	answer = completion_fn(panswer).choices[0].message.content

	print("answer:")
	print(answer)
	print()	

	return answer


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("-u", "--upload")
	parser.add_argument("-q", "--query")
	args = parser.parse_args()

	kg = KGGen(
		model=kg_gen_model,
	)

	completion_fn = lambda q: completion(
		model=rag_model,
		messages=[{"content": q,"role": "user"}]
	)

	with GraphDatabase.driver(db_url, auth=(db_user, db_pass)) as driver:
		driver.verify_connectivity()

		if args.upload:
			import_graph(args.upload)

		if args.query:
			dalk_query(args.query, kg, driver, completion_fn)


if __name__ == "__main__":
	main()
