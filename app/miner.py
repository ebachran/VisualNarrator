from app.utility import Utility, NLPUtility
from lang.en.indicators import *

class StoryMiner:
	def mine(self, story):
		story = self.get_indicators(story)
		if not story.role.indicator:
			raise ValueError('Could not find a role indicator', 0)
		if not story.means.indicator:
			raise ValueError('Could not find a means indicator', 1)

		story = self.get_functional_role(story)
		if not story.role.functional_role:
			raise ValueError('Could not find a functional role', 2)

		story = self.get_main_verb(story)
		if not story.means.main_verb.main:
			raise ValueError('Could not find a main verb', 3)

		story = self.get_direct_object(story)
		if not story.means.direct_object.main:
			raise ValueError('Could not find a direct object', 4)	

		story = self.get_free_form(story)

	def get_indicators(self, story):
		returnlist = []
		rm = MinerUtility.reasonable_max(story.data)
		indicators = [['Role', rm[0]], ['Means', rm[1]], ['Ends', rm[2]]]

		for indicator in indicators:
			found_ind = self.get_one_indicator(story.data, indicator[0], indicator[1])
			returnlist.append(found_ind)
			story.indicators.extend(found_ind)

		story.role.indicator = returnlist[0]
		story.means.indicator = returnlist[1]
		story.ends.indicator = returnlist[2]

		return story

	def get_one_indicator(self, story_data, indicator_type, reasonable_max):
		pattern = [x.split(' ') for x in eval(indicator_type.upper() + '_INDICATORS')]
		present_pattern = []
		for p in pattern:
			if Utility.is_sublist([MinerUtility.lower(pl) for pl in p], [MinerUtility.lower(sd) for sd in NLPUtility.get_tokens(story_data[0:reasonable_max])]):
				present_pattern.append(p)		

		found_pattern = []
		for p in present_pattern:
			for s in story_data:
				if MinerUtility.lower(p[0]) == MinerUtility.lower(s.text):
					found_pattern.append(story_data[s.i:s.i++len(p)]) 
					
		if found_pattern:
			return max(found_pattern, key=len)
		return []

	def get_functional_role(self, story):
		potential_role_part = story.data[story.role.indicator[-1].i + 1:story.means.indicator[0].i]
		potential_without_with = []

		with_i = -1
		for token in potential_role_part:
			if MinerUtility.lower(token.text) == 'with' or MinerUtility.lower(token.text) == 'w/':
				with_i = token.i
		if with_i > 0:
			potential_without_with = potential_role_part[0:with_i]
		else:
			potential_without_with = potential_role_part
		
		compound = MinerUtility.get_compound_nouns(story, potential_without_with)
		story.role.functional_role.compound = compound

		if story.role.functional_role.compound:
			story.role.functional_role.main = story.role.functional_role.compound[-1]
		else:
			story.role.functional_role.main = story.role.indicator[0].right_edge

		return story

	def get_main_verb(self, story):
		last_idx = story.means.indicator[-1].i
		main_verb = story.data[last_idx].nbor(1)

		story.means.main_verb.main = main_verb
		
		pv = MinerUtility.get_phrasal_verb(story, main_verb)
		story.means.main_verb.phrase = MinerUtility.get_span(story, pv[0])
		story.means.main_verb.type = pv[1]

		return story

	def get_direct_object(self, story):
		if not story.means.main_verb.phrase:
			pointer = story.means.main_verb.main
		else:
			phrase = story.means.main_verb.phrase
			pointer = phrase[-1]
	
		np = MinerUtility.get_noun_phrase(story, pointer)
		story.means.direct_object.main = np[0]
		story.means.direct_object.phrase = np[1]
		if story.means.direct_object.phrase:
			compound = MinerUtility.get_compound_nouns(story, story.means.direct_object.phrase)
			story.means.direct_object.compound = compound

		return story

	def get_free_form(self, story):
		list = []

		func_role = []
		func_role.append(story.role.functional_role.main)
		func_role.extend(story.role.functional_role.compound)

		main_verb = []
		main_verb.append(story.means.main_verb.main)
		main_verb.extend(story.means.main_verb.phrase)

		direct_obj = []
		direct_obj.append(story.means.direct_object.main)
		direct_obj.extend(story.means.direct_object.phrase)		

		not_free_form = story.indicators + func_role + main_verb + direct_obj

		for token in story.data:
			if token not in not_free_form:
				list.append(token)
		
		story.free_form = MinerUtility.get_span(story, list)

		means_free_form = []
		ends_free_form = []
		for token in story.free_form:
			if story.ends.indicator and token.i > story.ends.indicator[-1].i:
				ends_free_form.append(token)
			else:
				means_free_form.append(token)
		
		story.means.free_form = MinerUtility.get_span(story, means_free_form)
		story.ends.free_form = MinerUtility.get_span(story, ends_free_form)
		
		if story.means.free_form or story.ends.free_form:
			self.get_ff_verbs(story)
			self.get_ff_nouns(story)
			if story.means.free_form:
				story.means.proper_nouns = MinerUtility.get_proper_nouns(story, story.means.nouns)
				story.means.noun_phrases = MinerUtility.get_noun_phrases(story, story.means.free_form)
				story.means.compounds = MinerUtility.get_compound_nouns(story, story.means.free_form)
			if story.ends.free_form:
				story.ends.proper_nouns = MinerUtility.get_proper_nouns(story, story.ends.nouns)
				story.ends.noun_phrases = MinerUtility.get_noun_phrases(story, story.ends.free_form)
				story.ends.compounds = MinerUtility.get_compound_nouns(story, story.ends.free_form)

		return story

	def get_ff_nouns(self, story):
		story.means.nouns = MinerUtility.get_nouns(story, story.means.free_form)
		story.ends.nouns = MinerUtility.get_nouns(story, story.ends.free_form)	

		return story

	def get_ff_verbs(self, story):
		story.means.verbs = MinerUtility.get_verbs(story, story.means.free_form)
		story.ends.verbs = MinerUtility.get_verbs(story, story.ends.free_form)

		if story.means.verbs:
			story.means.phrasal_verbs = MinerUtility.get_phrasal_verbs(story, story.means.verbs)
		if story.ends.verbs:
			story.ends.phrasal_verbs = MinerUtility.get_phrasal_verbs(story, story.ends.verbs)

		return story


class MinerUtility:
	# Fixes that a real lower string is used, instead of a reference
	def lower(str):
		return str.lower()

	def reasonable_max(doc):
		rm = []
		l = len(doc)
		if l > 1:
			rm.append(2)	# Role
		else:
			rm.append(l)
		if l - 1 > 15:		# Means
			rm.append(15)
		else:
			rm.append(l)
		rm.append(l)		# Ends
		return rm 

	# Fixes that spaCy dependencies are not spans, but temporary objects that get deleted when loaded into memory
	def get_span(story, li):
		ret = []
		idxlist = NLPUtility.get_idx(li)
		for i in idxlist:
			ret.append(story.data[i])
		return ret

	# Obtain noun phrases (including form 'x of y')
	def get_noun_phrase(story, pointer):
		phrase = []
		main = []

		for chunk in story.data.noun_chunks:
			if pointer == chunk.root.head:
				phrase = MinerUtility.get_span(story, chunk)

		if phrase:
			main = phrase[-1]
			if phrase[-1].i < story.data[-1].i:
				potential_of = story.data[phrase[-1].i + 1]
				if MinerUtility.lower(potential_of.text) == 'of':
					for chunk in story.data.noun_chunks:
						if chunk.root.head == potential_of:	
							phrase.append(potential_of)	
							phrase.extend(MinerUtility.get_span(story, chunk))
		elif pointer == story.data[pointer.i]:
			main = story.system.main
		else:
			main = story.data[pointer.i + 1]

		return main, phrase

	# Obtain Type I, II and III phrasal verbs
	def get_phrasal_verb(story, head):
		particles = TYPE_II_PARTICLES + TYPE_II_PARTICLES_MARGINAL
		phrasal_verb = head
		phrase = []
		vtype = ""

		if MinerUtility.lower(phrasal_verb.right_edge.text) in particles:
			phrasal_verb = phrasal_verb.right_edge
			phrase.append(phrasal_verb)
			vtype = "II"
		else:
			for chunk in story.data.noun_chunks:
				for c in phrasal_verb.children:
					if c == chunk.root.head:
						if not c in story.indicators:
							if c.pos_ == 'PART':
								phrase.append(c)
								vtype = "I"
							if c.pos_ == 'ADP':
								phrase.append(c)
								vtype = "III"
		
		if phrase:
			phrase.insert(0, head)

		return phrase, vtype

	def get_nouns(story, span):
		nouns = []

		for token in span:
			if token.pos_ == "NOUN":
				nouns.append(token)

		return MinerUtility.get_span(story, nouns)

	def get_proper_nouns(story, nouns):
		proper = []

		for token in nouns:
			if token.tag_ == "NNP" or token.tag_ == "NNPS":
				proper.append(token)

		return MinerUtility.get_span(story, proper)

	def get_compound_nouns(story, span):
		compounds = []
		nouns = MinerUtility.get_nouns(story, span)

		for token in nouns:
			for child in token.children:
				if child.dep_ == "compound":
					compounds.append([child, token])
		
		for c in compounds:
			c = MinerUtility.get_span(story, c)

		if compounds and type(compounds[0]) is not list:
			compounds = compounds[0]

		return compounds

	def get_noun_phrases(story, span):
		phrases = []
		
		for chunk in story.data.noun_chunks:
			chunk = MinerUtility.get_span(story, chunk)
			if Utility.is_sublist(chunk, span):
				phrases.append(MinerUtility.get_span(story, chunk))

		return phrases

	def get_verbs(story, span):
		verbs = []

		for token in span:
			if token.pos_ == "VERB":
				verbs.append(token)

		return MinerUtility.get_span(story, verbs)

	def get_phrasal_verbs(story, verbs):
		phrasal_verbs = []

		for token in verbs:
			phrasal_verbs.append(MinerUtility.get_phrasal_verb(story, token)) 

		return phrasal_verbs
