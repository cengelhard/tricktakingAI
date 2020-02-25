from deckView import Card, deck52
from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)

def hearts_points(card):
	return 1 if card.suit == "♥" else 13 if card.key == "Q♠" else 0
	#return 2 if card.suit == "♥" else 0

len4 = lambda p: (len(p)==4, "must be len 4")


#public information about a player in a hand of Hearts.
class HeartsPlayer(PRecord):

	#cards you've played previously this hand.
	played = pvector_field(Card, initial=v())
	#cards you've won in previous tricks this hand.
	won    = pvector_field(Card, initial=v())
	hand   = pset_field(Card, initial=s())

	#What you did in the previous hand.
	prev_player = field(initial=None) #field(type=('tricktaking.HeartsPlayer', type(None)))

	penalty = field(int, initial=0)


	def points_sans_penalty(self):
		return sum(map(hearts_points, self.won))
	def points(self):
		return self.points_sans_penalty() + self.penalty
	def total_points(self):
		return self.points() + (self.prev_player.total_points() if self.prev_player else 0)
	def privatize(self):
		return self.set(hand=s())
	def play_card(self, card):
		return self.set(played = self.played.append(card), hand=self.hand.remove(card))
	def with_penalty(self, amount=10):
		return self.set(penalty=self.penalty+amount)
	def shot_the_moon(self):
		return self.points_sans_penalty() == 26

class PlayerVec(CheckedPVector):
	__type__ = HeartsPlayer

unsigned = field(int, 
				 initial=0, 
				 invariant=lambda n: 
				 	(n >= 0, f"unsigned int can't be negative. got {n}"))

player_id = field(int,
				  initial=-1,
				  invariant=lambda n: (n>=-1 and n<4, f"player_id can't be {n}"))

#TODO: refactor with this structure
# class Trick(PRecord):
# 	#indexed by player id.
# 	played = pvector_field((Card, type(None)), initial=v(None, None, None, None))
# 	leader = player_id #who led.
# 	def winner(self):
# 		led_suit = self.played[self.leader].suit

#the four players
class GameState(PRecord):

	players = field(PlayerVec, invariant=len4)
	trick_leader = player_id
	hand_count = unsigned 
	trick_count = field(int, initial=0, invariant = lambda n: (n >= 0 and n <= 13, f"trick count should be betwen 0 and 12. got {n}")) 

	#featurization might want this.
	last_played = player_id


	def _delta_pass(self, from_pid, dir):
		return (from_pid + dir*(((self.hand_count)%3) + 1))%4

	def passing_to(self,from_pid):
		'''get the player that from_pid will be passing to.'''
		return self._delta_pass(from_pid, 1)

	def passing_from(self,from_pid):
		'''inverse of passing_to'''
		return self._delta_pass(from_pid, -1)

	def set_player(self, pid, player):
		return self.set(players=self.players.set(pid, player))

	def map_players(self, f):
		return self.set(players=PlayerVec.create(map(f, range(4), self.players)))

	def private_to(self, pid): #i should not be able to see others' hands
		return self.map_players(lambda i, p: p if pid==i else p.privatize())

	#assumes everyone else has all the unaccounted-for cards in their hand.
	def unprivate(self, pid):
		possible_cards = pset(deck52)
		possible_cards = possible_cards.difference(self.players[pid].hand)
		for pl in self.players:
			possible_cards = possible_cards.difference(pset(pl.won))
		return self.map_players(lambda i, p: p if pid==i else p.set(hand=possible_cards))

	def played_this_trick(self):
		'''returns both positional and list form.'''
		lens = [len(p.played) for p in self.players]
		m = max(lens)
		if m == 0:
			return [], []
		positional = pvector([p.played[-1] if len(p.played)==m else None for p in self.players])
		tl = self.trick_leader
		return positional, pvector(filter(None, positional.extend(positional)[tl:tl+4]))

	def hand_done(self):
		return self.trick_count == 12

	def current_turn(self):
		'''whose turn is it?'''
		# if (len(self.players[0].played)):
		# 	_, played_so_far = self.played_this_trick()
		# 	num_played = len(played_so_far)
		# 	return (self.trick_leader + num_played)%4
		# else:
		# 	return -1

		_, played_so_far = self.played_this_trick()
		nplayed = len(played_so_far)
		if (nplayed):
			return (self.trick_leader + nplayed)%4
		else:
			return -1

	def legal_card(self, card, hand):
		played, only_played = self.played_this_trick()
		lsuit = played[self.trick_leader].suit
		not_in_hand = not (card in hand)
		not_first_play = len(only_played) != 4
		wrong_suit = card.suit != lsuit
		no_excuse = lsuit in [c.suit for c in hand]
		return not(not_in_hand or (not_first_play and wrong_suit and no_excuse))
