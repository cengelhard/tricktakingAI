from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)
import random as rand
from termcolor import cprint
from heartsModel import nextp
from deckView import suit_keys
from heartsView import hearts_points

class QuitGameException(Exception):
	pass

def ControlledGame(game, controllers):
	state, cont = game()
	while cont:
		try:
			state, cont = cont(controllers)
		except QuitGameException:
			print("quitting game")
			return
	return state

dont_care = lambda _:_
#basically just names to lambdas.
class HeartsController(PRecord):
	#required to play the game.
	play_trick = field(mandatory=True)
	pass_cards  = field(mandatory=True)

	#for IO, no return value.
	#these actually are mandatory when you pass it into the model.
	#but HeartsAdapter fills them in.
	alert_played         = field()
	alert_trick_complete = field()
	alert_hand_complete  = field()
	alert_shot_moon      = field()

#converts functions that take (state) into more useful args
#basically this just covers boilerplate for hand-coded controllers.
def HeartsAdapter(pid, ctrlr):

	def my_hand(state):
		return state.players[pid].hand

	def pass_cards(state):
		return ctrlr.pass_cards(my_hand(state), 
								state.passing_to(pid), 
								[p.total_points() for p in state.players])

	def play_trick(state):
		return ctrlr.play_trick(my_hand(state), state)

	#alerts
	#TODO: find a clever way to factor these.
	def alert_played(state):
		f = ctrlr.get('alert_played')
		if f:
			curr = state.trick_leader
			played, _ = state.played_this_trick()
			f(curr, played[curr])
	def alert_trick_complete(state):
		f = ctrlr.get('alert_trick_complete')
		if f:
			played, _ = state.played_this_trick()
			f(state, played)
	def alert_hand_complete(state):
		f = ctrlr.get('alert_hand_complete')
		if f:
			f(state.players) #probably want scores.
	def alert_shot_moon(state):
		f = ctrlr.get('alert_shot_moon')
		if f:
			f(state.trick_leader)

	return HeartsController(
		pass_cards = pass_cards,
		play_trick = play_trick,
		alert_played=alert_played,
		alert_trick_complete=alert_trick_complete,
		alert_hand_complete=alert_hand_complete,
		alert_shot_moon=alert_shot_moon
	)

#a completely random AI.
def random_controller(pid):
	def pass_cards(hand, passing_to, points):
		return rand.sample(hand, 3)

	def play_trick(hand, state):
		if len(hand):
			return rand.choice(tuple(hand))
		else:
			print("was passed an empty hand?")

	return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))

#random within legality
def random_legal_controller(pid):
	def pass_cards(hand, passing_to, points):
		return rand.sample(hand, 3)

	def play_trick(hand, state):
		assert len(hand), f"passed an empty hand? {state}"
		return rand.choice(tuple([c for c in hand if state.legal_card(c,hand)]))



	return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))


def input_controller(pid):

	def print_hand(hand):
		print("your hand:")
		cprint("|".join(f"{i}:{card.key}" for i,card in enumerate(hand)), "red")

	def _input(hand):

		string = input("--->")
		if string[0] == '/':
			command = string[1:]
			if command == "quit":
				raise QuitGameException()
			elif command == "hand":
				print_hand(hand)
				return _input(hand)
			elif command == "score":
				pass 
		return string

	def pass_cards(hand, passing_to, points):
		print(f"player {pid}, please choose 3 card indecies, separated by commas.")
		print(f"passing to: {passing_to}")
		hand = list(hand)
		print_hand(hand)
		try:
			choices = [hand[int(sub)] for sub in _input(hand).split(',')]
			if len(choices)==3:
				return choices
		except QuitGameException:
			raise QuitGameException()
		except:
			pass
		print("something wasn't right.")
		return pass_cards(hand, passing_to, points)

	def play_trick(hand, state):
		print(f"---player {pid}'s turn---")

		#TODO: print how the previous trick went.

		played, just_played = state.played_this_trick()
		nplayed = len(just_played)
		if nplayed == 4:
			print("You are leading the trick.")
		else:
			leader = nextp(pid)
			while played[leader] == None:
				leader = nextp(leader)
			print(f"{[(c.key if c else '__') for c in played]}")
			#print(f"played so far: {[c.key for c in played.extend(played)[leader:leader+nplayed]]}")
			
		lhand = list(card for card in hand if state.legal_card(card, hand))
		#lhand.sort(key=lambda c: state.legal_card(c, hand))
		#lhand = lhand[::-1]
		print_hand(lhand)
		try:
			choice = lhand[int(_input(lhand))]
			return choice
		except QuitGameException:
			raise QuitGameException()
		except:
			pass
		print("something wasn't right")
		return play_trick(lhand, state)

	def alert_played(pid, card):
		pass#print(f"{other_pid} played {card.key}")

	def alert_trick_complete(state, played):
		print(f"{[c.key for c in played]}")
		print(f"{state.trick_leader} wins!")

	def alert_hand_complete(players):
		print(f"hand score : {[p.points() for p in players]}")
		print(f"total score: {[p.total_points() for p in players]}")

	return HeartsAdapter(pid,HeartsController(
		pass_cards=pass_cards,
		play_trick=play_trick,
		alert_played=alert_played,
		alert_trick_complete=alert_trick_complete,
		alert_hand_complete=alert_hand_complete))

#did a simplex descent and 0 was the best losing_index for both sort and non sort.
#non-sort also performed better.
def hyper_smart_controller(losing_index=0, sort_rank=False):

	def smart_controller(pid):

		def card_power(hand):
			by_suit = {s: list(filter(lambda c: c.suit==s, hand)) for s in suit_keys}
			return lambda c: (hearts_points(c)+1)**2 * (c.rank+1) / (len(by_suit[c.suit])+1)

		def sorted_hand(hand):
			lhand = list(hand)
			lhand.sort(key=card_power(hand), reverse=True)
			return lhand

		def pass_cards(hand, passing_to, points):
			return sorted_hand(hand)[:3]

		def play_trick(hand, state):
			played, played_so_far = state.played_this_trick()
			if state.trick_leader == pid:
				#lead card. for now just play weakest card.
				return sorted_hand(hand)[-1]
			else:
				#following
				on_suit = [c for c in hand if c.suit == played[state.trick_leader].suit]
				legals = [c for c in hand if state.legal_card(c,hand)]
				legals.sort(key=card_power(hand), reverse=True)
				points_in_play = sum(hearts_points(c) for c in played_so_far)
				points_previously_played = sum(sum(hearts_points(c) for c in p.won) for p in state.players)
				points_in_hand = sum(hearts_points(c) for c in hand)
				points_left_to_be_played = 26-points_previously_played-points_in_play-points_in_hand

				tricks_left = 13-state.trick_count
				#how many points can you expect in a trick
				trick_danger =  points_left_to_be_played/(tricks_left+1)
				#how many points can you expect in the rest of this trick
				play_danger = trick_danger*(3-len(played_so_far))*state.trick_count
				if not len(on_suit): #you can't follow suit and know you'll lose
					return legals[0] #play most powerful card.
				elif play_danger < 1.5 and not all(hearts_points(c) for c in legals): 
					#okay with winning, play most powerful point-free card.
					return [c for c in legals if not hearts_points(c)][0]
				else: #try to lose
					rank_to_beat = max(c.rank for c in played_so_far)
					worse_cards = [c for c in legals if c.rank < rank_to_beat]
					if len(worse_cards):
						return worse_cards[0] #play your highest card that will lose.
					else:
						#it isn't clear how this should be chosen so it's a hyperparam.
						if sort_rank:
							legals.sort(key=lambda c: c.rank)
						return legals[int((losing_index-.0000001)*len(legals))]

		return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))
	return smart_controller
