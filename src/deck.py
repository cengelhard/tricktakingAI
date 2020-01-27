import random as rand

suit_names = {"♠": "Spades",
			  "♥": "Hearts",
			  "♦": "Diamonds",
			  "♣": "Clubs"}
rank_names = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
class Card:
	def __init__(self,r,s):
		self.rank = r
		self.suit = s
		self.key = f"{rank_names[r]}{s}"
		self.name = f"{rank_names[r]} of {suit_names[s]}"

#the indecies of this list are used in most places instead of the actual Card objects.
deck52 = [Card(r,s) for r in range(13) for s in ["♠","♥","♦","♣"]]

#returns indecies.
def shuffled_deck():
	return rand.shuffle(range(52)) 

