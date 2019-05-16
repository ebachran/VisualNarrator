import string
import timeit
import os.path
import spacy
import pkg_resources

from jinja2 import FileSystemLoader, Environment, PackageLoader

from vn.config import default_threshold, default_base, default_weights
from vn.io import Reader, Writer, Printer
from vn.miner import StoryMiner
from vn.matrix import Matrix
from vn.userstory import UserStory
from vn.pattern import Constructor
from vn.statistics import Statistics, Counter
from vn.utils.utility import multiline, remove_punct, t, is_i, tab, is_comment, occurence_list, is_us


def initialize_nlp():
	# Initialize spaCy just once (this takes most of the time...)
	print("Initializing Natural Language Processor. . .")
	return spacy.load('en_core_web_md')


def run_vn(filename,
		   systemname,
		   threshold = default_threshold,
		   base = default_base,
		   weights = default_weights,
		   spacy_nlp = initialize_nlp(),
		   print_us = False,
		   print_ont = False,
		   statistics = False,
		   link = False,
		   prolog = False,
		   json = False,
		   per_role = False,
		   stories = None):
	"""General class to run Visual Narrator

	Positional Args:
		filename (str): File name to read
		systemname (str): Name of System (for output and in model)
	
	Optional Args:
		threshold (float): threshold for which classes to select
		base (int): base weight (multiplier for all weights)
		weights (dict): weights for type of objects

		spacy_nlp (spacy.load object): spacy NLP using spacy.load('en_core_web_md')

		print_us (bool): print data per user story in the console
		print_ont (bool): print ontology in the console

		statistics (bool): show user story set statistics and output these to a .csv file
		link (bool): link ontology classes to user story they originate from
		per_role (bool): create an additional conceptual model per role

		prolog (bool): generate Prolog output (.pl)
		json (bool): export user stories as JSON (.json)	

		stories (list): preprocessed stories (from filename)

	Returns:
		dict: dictionary with US objects, Ontology + Prolog + JSON objects, matrix
	"""
	if stories is None:
		stories = Reader.parse(filename)

	start_nlp_time = timeit.default_timer()
	nlp = spacy_nlp
	nlp_time = timeit.default_timer() - start_nlp_time

	start_parse_time = timeit.default_timer()
	miner = StoryMiner()

	# Read the input file
	us_id = 1

	# Keep track of all errors	
	errors = ""
	c = Counter()

	# Keeps track of all succesfully created User Stories objects
	us_instances = []  
	failed_stories = []
	success_stories = []

	# Parse every user story (remove punctuation and mine)
	for s in stories:
		try:
			user_story = parse(s, us_id, systemname, nlp, miner)
			user_story = c.count(user_story)
			us_instances.append(user_story)
			success_stories.append(s)
		except ValueError as err:
			failed_stories.append([us_id, s, err.args])
			errors += "\n[User Story {} ERROR] {}! (\"{}\")".format(us_id, err.args[0], " ".join(str.split(s)))
		us_id += 1

	# Print errors (if found)
	if errors:
		Printer.print_head("PARSING ERRORS")
		print(errors)

	parse_time = timeit.default_timer() - start_parse_time

	# Generate the term-by-user story matrix (m), and additional data in two other matrices
	start_matr_time = timeit.default_timer()

	matrix = Matrix(base, weights)
	matrices = matrix.generate(us_instances, ' '.join([u.sentence for u in us_instances]), nlp)
	m, count_matrix, stories_list, rme = matrices

	matr_time = timeit.default_timer() - start_matr_time

	# Print details per user story, if argument '-u'/'--print_us' is chosen
	if print_us:
		print("Details:\n")
		for us in us_instances:
			Printer.print_us_data(us)

	# Generate the ontology
	start_gen_time = timeit.default_timer()
	
	patterns = Constructor(nlp, us_instances, m)
	out = patterns.make(systemname, threshold, link)
	output_ontology, output_prolog, output_ontobj, output_prologobj, onto_per_role = out

	# Print out the ontology in the terminal, if argument '-o'/'--print_ont' is chosen
	if print_ont:
		Printer.print_head("MANCHESTER OWL")
		print(output_ontology)

	gen_time = timeit.default_timer() - start_gen_time

	# Gather statistics and print the results
	stats_time = 0
	if statistics:
		start_stats_time = timeit.default_timer()

		statsarr = Statistics.to_stats_array(us_instances)

		Printer.print_head("USER STORY STATISTICS")
		Printer.print_stats(statsarr[0], True)
		Printer.print_stats(statsarr[1], True)
		Printer.print_subhead("Term - by - User Story Matrix ( Terms w/ total weight 0 hidden )")
		hide_zero = m[(m['sum'] > 0)]
		print(hide_zero)

		stats_time = timeit.default_timer() - start_stats_time	

	# Write output files
	w = Writer

	folder = "output/" + str(systemname)
	reports_folder = folder + "/reports"
	stats_folder = reports_folder + "/stats"
	ontology_folder = folder + "/ontology"

	outputfile = w.make_file(ontology_folder, str(systemname), "omn", output_ontology)
	files = [["Manchester Ontology", outputfile]]

	if statistics:
		files.append(["General statistics", w.make_file(stats_folder, str(systemname), "csv", statsarr[0])])
		files.append(["Term-by-User Story matrix", w.make_file(stats_folder, f"{systemname}-term_by_US_matrix", "csv", m)])
		files.append(["Sentence statistics", w.make_file(stats_folder,  f"{systemname}-sentences", "csv", statsarr[1])])
	if prolog:
		files.append(["Prolog", w.make_file(folder + "/prolog", str(systemname), "pl", output_prolog)])
	if json:
		output_json = "\n".join([str(us.toJSON()) for us in us_instances]).replace('\'', '\"')
		files.append(["JSON", w.make_file(folder + "/json", f"{systemname}-user_stories", "json", output_json)])
	if per_role:
		for o in onto_per_role:
			files.append([f"Individual Ontology for '{o[0]}'", w.make_file(folder + "/ontology", f"{systemname}-{o[0]}", "omn", o[1])])

	# Print the used ontology generation settings
	Printer.print_gen_settings(matrix, base, threshold)

	# Print details of the generation
	fail = len(failed_stories)
	success = len(success_stories)

	Printer.print_details(fail, success, nlp_time, parse_time, matr_time, gen_time, stats_time)

	report_dict = {
		"stories": us_instances,
		"failed_stories": failed_stories,
		"systemname": systemname,
		"us_success": success,
		"us_fail": fail,
		"times": [["Initializing Natural Language Processor (<em>spaCy</em> v" + pkg_resources.get_distribution("spacy").version + ")" , nlp_time], ["Mining User Stories", parse_time], ["Creating Factor Matrix", matr_time], ["Generating Manchester Ontology", gen_time], ["Gathering statistics", stats_time]],
		"dir": os.path.dirname(os.path.realpath(__file__)),
		"inputfile": filename,
		"inputfile_lines": len(stories),
		"outputfiles": files,
		"threshold": threshold,
		"base": base,
		"matrix": matrix,
		"weights": m['sum'].copy().reset_index().sort_values(['sum'], ascending=False).values.tolist(),
		"counts": count_matrix.reset_index().values.tolist(),
		"classes": output_ontobj.classes,
		"relationships": output_prologobj.relationships,
		"types": list(count_matrix.columns.values),
		"ontology": multiline(output_ontology)
	}

	# Finally, generate a report
	report = w.make_file(reports_folder, str(systemname) + "_REPORT", "html", generate_report(report_dict))
	files.append(["Report", report])

	# Print the location and name of all output files
	for file in files:
		if str(file[1]) != "":
			print(f"{file[0]} file succesfully created at: \"{file[1]}\"")
	
	# Return objects so that they can be used as input for other tools
	return {'us_instances': us_instances,
	        'output_ontobj': output_ontobj,
			'output_prologobj': output_prologobj,
			'output_json': output_json if json else None,
			'matrix': m}


def parse(text, id, systemname, nlp, miner):
	"""Create a new user story object and mines it to map all data in the user story text to a predefined model
	
	text: The user story text
	id: The user story ID, which can later be used to identify the user story
	systemname: Name of the system this user story belongs to
	nlp: Natural Language Processor (spaCy)
	miner: instance of class Miner
	:returns: A new user story object
	"""
	no_punct = remove_punct(text)
	no_double_space = ' '.join(no_punct.split())
	doc = nlp(no_double_space)
	user_story = UserStory(id, text, no_double_space)
	user_story.system.main = nlp(systemname)[0]
	user_story.data = doc
	#Printer.print_dependencies(user_story)
	#Printer.print_noun_phrases(user_story)
	miner.structure(user_story)
	user_story.old_data = user_story.data
	user_story.data = nlp(user_story.sentence)
	miner.mine(user_story, nlp)
	return user_story
	
def generate_report(report_dict):
	"""Generates a report using Jinja2
	
	report_dict: Dictionary containing all variables used in the report
	:returns: HTML page
	"""
	CURR_DIR = os.path.dirname(os.path.abspath(__file__))

	loader = FileSystemLoader( searchpath=str(CURR_DIR) + "/templates/" )
	env = Environment( loader=loader, trim_blocks=True, lstrip_blocks=True )
	env.globals['text'] = t
	env.globals['is_i'] = is_i
	env.globals['apply_tab'] = tab
	env.globals['is_comment'] = is_comment
	env.globals['occurence_list'] = occurence_list
	env.tests['is_us'] = is_us
	template = env.get_template("report.html")

	return template.render(report_dict)